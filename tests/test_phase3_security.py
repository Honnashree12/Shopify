import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Prevent module loading startup crash during testing
os.environ["TESTING"] = "True"

import main
from main import app, active_sessions
from services.auth_service import User
from state import ProductLaunchState

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_auth_fallback(monkeypatch):
    monkeypatch.setenv("ALLOW_AUTH_FALLBACK", "False")


def test_unauthenticated_requests_fail():
    """Assert requests without Bearer tokens or with invalid tokens return 401."""
    # 1. Without token
    response = client.get("/api/launches")
    assert response.status_code == 401
    
    # 2. Invalid token
    response = client.get("/api/launches", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_role_based_access_control():
    """Assert role-based permissions are enforced: Catalogue Admin cannot view audit logs."""
    # 1. Catalogue admin attempts to view audit logs -> 403
    response = client.get("/api/audit-logs", headers={"Authorization": "Bearer mock-catalogue-token"})
    assert response.status_code == 403
    
    # 2. Platform Admin CAN view audit logs -> 200
    response = client.get("/api/audit-logs", headers={"Authorization": "Bearer mock-admin-token"})
    assert response.status_code == 200
    
    # 3. Reviewer attempts to submit a product for review -> 403
    response = client.post("/api/products/some-session/submit", headers={"Authorization": "Bearer mock-approver-token"})
    assert response.status_code == 403


def test_self_approval_protection():
    """Assert creator/submitter is blocked from approving their own product launch."""
    session_id = "test-self-approve-session"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Self Approve Test",
        raw_description="Test description",
        status="awaiting_approval",
        created_by_uid="approver-uid",  # Same as Reviewer Sandeep
        submitted_by_uid="approver-uid",
        created_at="2026-08-11T12:00:00Z"
    )
    
    # Reviewer Sandeep (approver-uid) attempts to approve his own product -> 403
    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-approver-token"}
    )
    assert response.status_code == 403
    assert "Self-approval protection" in response.json()["detail"]
    
    # Also check /api/folder-launch/{session_id}/approve
    response = client.post(
        f"/api/folder-launch/{session_id}/approve",
        headers={"Authorization": "Bearer mock-approver-token"},
        json={"approved_to_publish": True}
    )
    assert response.status_code == 403
    assert "Self-approval protection" in response.json()["detail"]


def test_state_machine_transition_guards():
    """Assert illegal workflow state transitions are rejected with 409 Conflict."""
    session_id = "test-state-transition-session"
    
    # Initial state is pending (DRAFT), should not allow Approve directly
    active_sessions[session_id] = ProductLaunchState(
        product_name="Transition Guard Test",
        raw_description="Test description",
        status="pending",
        created_by_uid="catalogue-uid",
        created_at="2026-08-11T12:00:00Z",
        source="folder"
    )
    
    # Attempting to Approve directly from DRAFT (pending) -> 409
    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-approver-token"}
    )
    assert response.status_code == 409
    
    # Transition to awaiting_approval first via submit
    response = client.post(
        f"/api/products/{session_id}/submit",
        headers={"Authorization": "Bearer mock-catalogue-token"}
    )
    assert response.status_code == 200
    assert active_sessions[session_id].status == "awaiting_approval"
    
    # Now approval is allowed and triggers running status
    import sys
    from unittest.mock import MagicMock
    
    main_modules = [m for n, m in sys.modules.items() if n == "main" or n.endswith(".main")]
    orig_funcs = {}
    mock_run = MagicMock()
    for m in main_modules:
        if hasattr(m, "run_folder_workflow_background"):
            orig_funcs[m] = m.run_folder_workflow_background
            m.run_folder_workflow_background = mock_run

    try:
        response = client.post(
            f"/api/products/{session_id}/approve",
            headers={"Authorization": "Bearer mock-approver-token"}
        )
        assert response.status_code == 200
        assert active_sessions[session_id].status == "running"
        assert mock_run.called
    finally:
        for m, orig in orig_funcs.items():
            m.run_folder_workflow_background = orig


def test_idempotency_checks():
    """Assert double-approving does not trigger duplicate background runs."""
    session_id = "test-idempotency-session"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Idempotency Test",
        raw_description="Test description",
        status="running",
        created_by_uid="catalogue-uid",
        created_at="2026-08-11T12:00:00Z"
    )
    
    # Attempting to approve an already running workflow -> 409
    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-approver-token"}
    )
    assert response.status_code == 409
