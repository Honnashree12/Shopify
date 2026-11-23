import os
import sys
import logging
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Prevent module loading startup crash during testing
os.environ["TESTING"] = "True"
os.environ["ALLOW_AUTH_FALLBACK"] = "True"

from config import settings, setup_logging, request_id_var, session_id_var, workflow_id_var
from services.auth_service import get_current_user, require_role, User
from main import app

client = TestClient(app)


def test_settings_secrets_masking():
    """Verify that settings __repr__ masks sensitive credentials."""
    settings.shopify_access_token = "shpat_test_token_123"
    settings.firebase_service_account_key = "secret_firebase_key"
    settings.gemini_api_key = "gemini_key_abc"
    settings.smtp_password = "smtp_pass_123"
    
    repr_str = repr(settings)
    assert "shpat_test_token_123" not in repr_str
    assert "secret_firebase_key" not in repr_str
    assert "gemini_key_abc" not in repr_str
    assert "smtp_pass_123" not in repr_str
    assert "********" in repr_str


def test_settings_validation():
    """Verify that validate_startup raises ValueError when required config is missing."""
    # Force is_testing check bypass
    with patch("sys.modules", {}):
        with patch.dict(os.environ, {"TESTING": "False"}):
            settings.shopify_store_url = None
            settings.shopify_access_token = None
            
            with pytest.raises(ValueError) as exc:
                settings.validate_startup()
            assert "CRITICAL STARTUP ERROR" in str(exc.value)


def test_logging_context_tracing():
    """Verify that ContextFilter dynamically adds tracing variables to log records."""
    log_capture = []
    
    class CaptureHandler(logging.Handler):
        def emit(self, record):
            log_capture.append(record)
            
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    handler = CaptureHandler()
    
    from config import ContextFilter
    handler.addFilter(ContextFilter())
    logger.addHandler(handler)
    
    # 1. Default values
    request_id_var.set("-")
    session_id_var.set("-")
    workflow_id_var.set("-")
    
    logger.info("Default log")
    assert len(log_capture) == 1
    assert log_capture[0].request_id == "-"
    assert log_capture[0].session_id == "-"
    assert log_capture[0].workflow_id == "-"
    
    # 2. Context variables set
    req_token = request_id_var.set("req123")
    sess_token = session_id_var.set("sess456")
    wf_token = workflow_id_var.set("wf789")
    
    logger.info("Contextual log")
    assert len(log_capture) == 2
    assert log_capture[1].request_id == "req123"
    assert log_capture[1].session_id == "sess456"
    assert log_capture[1].workflow_id == "wf789"
    
    # Reset
    request_id_var.reset(req_token)
    session_id_var.reset(sess_token)
    workflow_id_var.reset(wf_token)


def test_auth_service_stubs():
    """Verify auth service mock token resolution and role constraints."""
    from services.auth_service import HTTPAuthorizationCredentials
    
    # 1. Resolve Admin token
    creds_admin = HTTPAuthorizationCredentials(scheme="Bearer", credentials="mock-admin-token")
    user_admin = get_current_user(creds_admin)
    assert user_admin.uid == "admin-uid"
    assert user_admin.role == "PLATFORM_ADMIN"
    
    # 2. Resolve Approver token
    creds_app = HTTPAuthorizationCredentials(scheme="Bearer", credentials="mock-approver-token")
    user_app = get_current_user(creds_app)
    assert user_app.uid == "approver-uid"
    assert user_app.role == "APPROVER"

    # 3. Resolve fallback / default
    user_no_token = get_current_user(None)
    assert user_no_token.uid == "default-user"
    assert user_no_token.role == "PLATFORM_ADMIN"
    
    # 4. Enforce role checks
    checker = require_role(["PLATFORM_ADMIN"])
    # Should pass without exception
    assert checker(user_admin) == user_admin
    
    # Should fail for insufficient role
    checker_admin_only = require_role(["PLATFORM_ADMIN"])
    creds_catalogue = HTTPAuthorizationCredentials(scheme="Bearer", credentials="mock-catalogue-token")
    user_cat = get_current_user(creds_catalogue)
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        checker_admin_only(user_cat)
    assert exc.value.status_code == 403


def test_health_check_endpoint():
    """Verify that the health check endpoint returns expanded connection metrics.

    Phase 5 made /health's top-level "status" reflect real sub-component
    connectivity (degrading when Shopify isn't actually reachable) instead
    of hardcoding "healthy" -- see main.py's health(). This sandbox has no
    real Shopify credentials, so "degraded" is the CORRECT result here.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["adk_ready"] is True
    assert data["runner"] is True
    assert "shopify_connectivity" in data
    assert "firestore_connectivity" in data


def test_launches_and_audit_logs_endpoints():
    """Verify that the launches and audit logs API endpoints return structured response payloads."""
    # 1. Test launches list endpoint
    response = client.get("/api/launches")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    # 2. Test audit logs endpoint
    from services.firebase_service import save_audit_log
    save_audit_log("test-log-id", {
        "timestamp": "2026-08-11T12:00:00Z",
        "actor": "System",
        "role": "SYSTEM",
        "action": "TEST",
        "description": "Test audit log"
    })
    response_logs = client.get("/api/audit-logs")
    assert response_logs.status_code == 200
    logs_data = response_logs.json()
    assert isinstance(logs_data, list)
    assert len(logs_data) > 0
    assert "timestamp" in logs_data[0]
    assert "actor" in logs_data[0]
    assert "role" in logs_data[0]
    assert "action" in logs_data[0]
