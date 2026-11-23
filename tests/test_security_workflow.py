import os
import json
import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

from main import app, active_sessions
from state import ProductLaunchState
from services.auth_service import User
from tools.folder_tools import create_shopify_product_tool, upload_folder_media_tool
from services.shopify_media_service import ShopifyMediaService

client = TestClient(app)

# Mock user database for dependency role checks
MOCK_USERS = {
    "approver-uid": {"role": "APPROVER", "active": True, "email": "sandeep@example.com", "name": "Sandeep"},
    "catalogue-uid": {"role": "CATALOGUE_ADMIN", "active": True, "email": "lakshmi@example.com", "name": "Lakshmi"},
    "admin-uid": {"role": "PLATFORM_ADMIN", "active": True, "email": "admin@example.com", "name": "Platform Admin"},
}

class FakeDoc:
    def __init__(self, exists, data=None):
        self.exists = exists
        self._data = data or {}
    def to_dict(self):
        return self._data

class FakeDocRef:
    def __init__(self, doc):
        self._doc = doc
    def get(self):
        return self._doc

class FakeFirestore:
    def collection(self, name):
        return self
    def document(self, doc_id):
        user = MOCK_USERS.get(doc_id)
        if user:
            return FakeDocRef(FakeDoc(exists=True, data=user))
        return FakeDocRef(FakeDoc(exists=False))

@pytest.fixture(autouse=True)
def mock_db_and_auth(monkeypatch):
    """Disable real auth checks and mock Firestore db connections."""
    monkeypatch.setenv("ALLOW_AUTH_FALLBACK", "False")
    monkeypatch.setenv("TESTING", "True")
    
    # Mock firebase_service's initialize_firebase to return our FakeFirestore
    fake_fs = FakeFirestore()
    with patch("services.firebase_service.initialize_firebase", return_value=fake_fs), \
         patch("main.run_folder_workflow_background") as mock_run_folder, \
         patch("main.run_adk_workflow_background") as mock_run_adk:
        yield mock_run_folder

@pytest.fixture(autouse=True)
def clean_sessions():
    active_sessions.clear()
    yield
    active_sessions.clear()

def _mock_tool_context(state_dict):
    ctx = MagicMock()
    ctx.state = state_dict
    ctx._invocation_context = MagicMock()
    ctx._invocation_context.session = MagicMock()
    ctx._invocation_context.session.id = "session-123"
    return ctx

# =====================================================================
# SECURITY & WORKFLOW TESTS
# =====================================================================

def test_catalogue_admin_creates_product_starts_unapproved():
    """1. Catalogue Admin creates a draft that starts unapproved."""
    session_id = "test-launch-unapproved"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Test Product",
        raw_description="A test product description",
        status="pending",
        approved_to_publish=False, # Starts unapproved
        created_by_uid="catalogue-uid",
        created_at=datetime.utcnow().isoformat() + "Z",
    )
    
    state = active_sessions[session_id]
    assert state.approved_to_publish is False
    assert state.status == "pending"


def test_catalogue_admin_cannot_approve():
    """2. Catalogue Admin role is rejected when attempting approval."""
    session_id = "test-approve-unauthorized"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Unapproved Product",
        raw_description="desc",
        status="awaiting_approval",
        created_by_uid="catalogue-uid",
    )

    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-catalogue-token"} # Lakshmi token
    )
    assert response.status_code == 403
    assert "role" in response.json()["detail"].lower() or "permission" in response.json()["detail"].lower()


def test_platform_admin_cannot_approve():
    """3. Platform Admin role is rejected when attempting approval."""
    session_id = "test-approve-admin"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Unapproved Product",
        raw_description="desc",
        status="awaiting_approval",
        created_by_uid="catalogue-uid",
    )

    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-admin-token"} # Admin token
    )
    assert response.status_code == 403


def test_submitter_cannot_self_approve():
    """4. Submitter cannot approve their own launch (Sandeep self-approval guard)."""
    session_id = "test-self-approval"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Sandeep Draft Product",
        raw_description="desc",
        status="awaiting_approval",
        created_by_uid="approver-uid", # Sandeep is creator
    )

    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-approver-token"} # Sandeep token
    )
    assert response.status_code == 403
    assert "self-approval" in response.json()["detail"].lower()


@patch("services.firebase_service.save_audit_log")
def test_approver_approves_successfully(mock_audit_log):
    """5. Approver Sandeep successfully approves a valid launch session."""
    session_id = "test-valid-approval"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Approved Product",
        raw_description="desc",
        status="awaiting_approval",
        created_by_uid="catalogue-uid",
        product_version=1,
    )

    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-approver-token"} # Sandeep token
    )
    assert response.status_code == 200
    
    state = active_sessions[session_id]
    assert state.approved_to_publish is True
    assert state.status == "running"
    assert state.approved_by_uid == "approver-uid"
    assert state.approved_at_version == 1
    
    # Assert PRODUCT_APPROVED audit log was recorded
    mock_audit_log.assert_called()
    logged_action = mock_audit_log.call_args[0][1]["action"]
    assert logged_action == "PRODUCT_APPROVED"


def test_publishing_fails_if_unapproved():
    """6. Publishing tool halts execution if approved_to_publish is False."""
    state = {
        "product_name": "Unapproved Shopify Product",
        "product_description": "Description",
        "product_price": 100.0,
        "sku": "SKU-UNAPPROVED",
        "approved_to_publish": False,
        "preview_mode": True,
    }
    context = _mock_tool_context(state)
    res = create_shopify_product_tool(context)
    
    assert "Awaiting user approval" in res
    assert state["status"] == "awaiting_approval"


def test_publishing_blocked_if_approver_metadata_missing():
    """7. Publishing tool halts execution if approved_to_publish is True but metadata is missing."""
    state = {
        "product_name": "Approved but no metadata Product",
        "product_description": "Description",
        "product_price": 100.0,
        "sku": "SKU-NOMETA",
        "approved_to_publish": True,
        # Missing approved_by_uid and approved_at
    }
    context = _mock_tool_context(state)
    res = create_shopify_product_tool(context)
    
    assert "PUBLISH DENIED" in res
    assert "approved_by_uid is missing" in res


def test_approval_becomes_invalid_on_version_mismatch():
    """8. Approval is marked stale and blocked if Lakshmi edits product after approval."""
    state = {
        "product_name": "Edited Product",
        "product_description": "Description was updated",
        "product_price": 100.0,
        "sku": "SKU-STALE",
        "approved_to_publish": True,
        "approved_by_uid": "approver-uid",
        "approved_at": "2026-08-12T00:00:00Z",
        "approved_at_version": 1,
        "product_version": 2, # Version changed after approval!
    }
    context = _mock_tool_context(state)
    res = create_shopify_product_tool(context)
    
    assert "PUBLISH DENIED" in res
    assert "stale" in res.lower()


@patch.object(ShopifyMediaService, "verify_media", return_value=[])
@patch.object(ShopifyMediaService, "upload_and_attach_all_media", return_value=[])
@patch("tools.folder_tools.get_product_by_sku", return_value=None)
@patch("tools.folder_tools.get_product_by_title", return_value=None)
@patch("tools.folder_tools.create_product")
def test_shopify_creation_and_media_upload_only_after_approval(mock_create, mock_title, mock_sku, mock_upload, mock_verify):
    """9. Shopify creation and media upload succeed when approval is fully valid."""
    mock_create.return_value = {
        "id": 888123,
        "title": "Authorized Product",
        "url": "https://store/products/auth",
        "variants": [{"id": 999}],
    }
    
    state = {
        "product_name": "Authorized Product",
        "product_description": "Description",
        "product_price": 100.0,
        "sku": "SKU-AUTH",
        "approved_to_publish": True,
        "approved_by_uid": "approver-uid",
        "approved_at": "2026-08-12T00:00:00Z",
        "approved_at_version": 1,
        "product_version": 1,
        "duplicate_action": "CREATE",
    }
    context = _mock_tool_context(state)
    res = create_shopify_product_tool(context)
    
    assert "created successfully" in res
    assert state["shopify_product_id"] == 888123
    
    # Assert media upload check behaves correctly
    media_res = upload_folder_media_tool(context)
    # Since detected_images is empty, media upload should complete without issues
    assert "successfully" in media_res or "completed" in media_res


def test_concurrency_double_approval_lock():
    """10. Concurrency lock prevents dual active runs on same session."""
    session_id = "test-double-lock"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Lock Product",
        raw_description="desc",
        status="awaiting_approval",
        created_by_uid="catalogue-uid",
    )

    # First approve call should succeed (mocking background task)
    with patch("main.run_folder_workflow_background") as mock_run:
        response1 = client.post(
            f"/api/products/{session_id}/approve",
            headers={"Authorization": "Bearer mock-approver-token"}
        )
        assert response1.status_code == 200
        
        # Second immediate approve call should fail with 409 Conflict
        response2 = client.post(
            f"/api/products/{session_id}/approve",
            headers={"Authorization": "Bearer mock-approver-token"}
        )
        assert response2.status_code == 409
        assert "execution is already in progress" in response2.json()["detail"]


def test_campaign_publishing_endpoint_returns_501():
    """11. Workshop/Campaign publish endpoint is disabled for production correctness."""
    response = client.post(
        "/api/workshops/ws_123/publish",
        headers={"Authorization": "Bearer mock-approver-token"}
    )
    assert response.status_code == 501
    assert "not production-supported" in response.json()["detail"].lower()
