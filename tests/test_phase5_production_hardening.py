"""
Phase 5 -- Production Hardening, Real Authentication, BOSS Alignment & Final
Validation. Covers the mechanisms added/hardened in this phase:

  Test Group A -- Real Firebase ID token authentication (Part 1)
  Test Group B -- Mock-token path unaffected by the real-auth addition
  Test Group C -- Unauthenticated Workshop/Campaign endpoints now gated (Part 6-8)
  Test Group D -- /outputs IDOR / unauthenticated data exposure fix (Part 8)
  Test Group E -- CORS configuration (Part 10)
  Test Group F -- File upload validation (Part 11)
  Test Group G -- Health check status differentiation (Part 13)

Existing Phase 1/3/4 coverage (mock RBAC, self-approval, idempotency,
approval-gate integrity, concurrency) already lives in
test_phase1_foundation.py, test_phase3_security.py, and
test_phase4_publishing_pipeline.py and is not duplicated here.
"""

import io
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "True"

import main
from main import app, active_sessions
from config import settings
from services import auth_service
from services.auth_service import (
    FirebaseAuthProvider,
    MockAuthProvider,
    get_current_user,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_auth_fallback(monkeypatch):
    monkeypatch.setenv("ALLOW_AUTH_FALLBACK", "False")


# ---------------------------------------------------------------------------
# Test Group A -- Real Firebase ID token authentication (Part 1)
# ---------------------------------------------------------------------------

class _FakeDoc:
    def __init__(self, exists, data=None):
        self.exists = exists
        self._data = data or {}

    def to_dict(self):
        return self._data


class _FakeDocRef:
    def __init__(self, doc):
        self._doc = doc

    def get(self, *args, **kwargs):
        return self._doc


class _FakeDb:
    """Minimal Firestore client stand-in exposing only what
    FirebaseAuthProvider needs: .collection("users").document(uid).get()."""

    def __init__(self, role_by_uid):
        self._role_by_uid = role_by_uid

    def collection(self, name):
        assert name == "users"
        return self

    def document(self, uid):
        val = self._role_by_uid.get(uid)
        if val is None:
            return _FakeDocRef(_FakeDoc(exists=False))
        if isinstance(val, dict):
            return _FakeDocRef(_FakeDoc(exists=True, data=val))
        return _FakeDocRef(_FakeDoc(exists=True, data={"role": val, "active": True}))


def test_firebase_provider_accepts_valid_token_with_assigned_role():
    db = _FakeDb({"real-uid-1": "APPROVER"})
    provider = FirebaseAuthProvider(db)
    with patch("firebase_admin.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = {"uid": "real-uid-1", "email": "sandeep@realcompany.com"}
        user = provider.verify_token("a-real-looking-jwt")
    assert user.uid == "real-uid-1"
    assert user.role == "APPROVER"
    assert user.email == "sandeep@realcompany.com"


def test_firebase_provider_rejects_unassigned_real_account():
    """A verified Firebase identity with no users/{uid} doc must be REJECTED,
    not silently given a default role -- guessing a safe default for an
    unknown real account would itself be a privilege-escalation risk."""
    db = _FakeDb({})
    provider = FirebaseAuthProvider(db)
    with patch("firebase_admin.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = {"uid": "no-role-uid", "email": "nobody@realcompany.com"}
        with pytest.raises(Exception) as exc_info:
            provider.verify_token("a-real-looking-jwt")
    assert getattr(exc_info.value, "status_code", None) == 403


def test_firebase_provider_rejects_inactive_user():
    """An inactive user (active=False in Firestore users/{uid}) must be rejected
    with 403, preventing access even if their token is valid."""
    db = _FakeDb({"inactive-uid": {"role": "APPROVER", "active": False}})
    provider = FirebaseAuthProvider(db)
    with patch("firebase_admin.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = {"uid": "inactive-uid", "email": "inactive@realcompany.com"}
        with pytest.raises(Exception) as exc_info:
            provider.verify_token("a-real-looking-jwt")
    assert getattr(exc_info.value, "status_code", None) == 403
    assert "inactive" in str(exc_info.value.detail).lower()


def test_firebase_provider_rejects_invalid_or_expired_token():
    db = _FakeDb({})
    provider = FirebaseAuthProvider(db)
    with patch("firebase_admin.auth.verify_id_token", side_effect=ValueError("expired")):
        with pytest.raises(Exception) as exc_info:
            provider.verify_token("garbage")
    assert getattr(exc_info.value, "status_code", None) == 401


def test_get_current_user_routes_non_mock_token_to_firebase_when_configured():
    """When Firebase is configured, a non-'mock-' bearer token must go
    through real verification -- it must NOT silently fall back to the mock
    provider, which would defeat the point of having real auth."""
    fake_db = _FakeDb({"real-uid-2": "PLATFORM_ADMIN"})

    class _FakeCreds:
        credentials = "some.real.jwt"

    with patch("services.firebase_service.initialize_firebase", return_value=fake_db):
        with patch("firebase_admin.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = {"uid": "real-uid-2", "email": "admin@realcompany.com"}
            user = get_current_user(credentials=_FakeCreds())
    assert user.role == "PLATFORM_ADMIN"
    assert user.uid == "real-uid-2"


def test_get_current_user_rejects_forged_nonmock_token_when_firebase_configured():
    """A non-mock token that fails real verification must be rejected
    outright (401), not fall through to the mock provider."""
    fake_db = _FakeDb({})

    class _FakeCreds:
        credentials = "forged-token-not-a-real-jwt"

    with patch("services.firebase_service.initialize_firebase", return_value=fake_db):
        with patch("firebase_admin.auth.verify_id_token", side_effect=ValueError("bad token")):
            with pytest.raises(Exception) as exc_info:
                get_current_user(credentials=_FakeCreds())
    assert getattr(exc_info.value, "status_code", None) == 401


# ---------------------------------------------------------------------------
# Test Group B -- Mock-token path unaffected by the real-auth addition
# ---------------------------------------------------------------------------

def test_mock_tokens_still_work_when_firebase_not_configured():
    class _FakeCreds:
        credentials = "mock-admin-token"

    with patch("services.firebase_service.initialize_firebase", return_value=None):
        user = get_current_user(credentials=_FakeCreds())
    assert user.role == "PLATFORM_ADMIN"


def test_mock_tokens_bypass_firebase_verification_even_when_configured():
    """Mock tokens are always routed to MockAuthProvider regardless of
    whether Firebase happens to be configured -- this keeps the dev/test
    experience stable and is safe because MockAuthProvider only recognizes
    three exact, non-guessable-as-real-JWT strings."""
    fake_db = _FakeDb({})

    class _FakeCreds:
        credentials = "mock-catalogue-token"

    with patch("services.firebase_service.initialize_firebase", return_value=fake_db):
        with patch("firebase_admin.auth.verify_id_token") as mock_verify:
            user = get_current_user(credentials=_FakeCreds())
            mock_verify.assert_not_called()
    assert user.role == "CATALOGUE_ADMIN"


def test_unrecognized_mock_shaped_token_still_401s():
    class _FakeCreds:
        credentials = "mock-nonexistent-token"

    with patch("services.firebase_service.initialize_firebase", return_value=None):
        with pytest.raises(Exception) as exc_info:
            get_current_user(credentials=_FakeCreds())
    assert getattr(exc_info.value, "status_code", None) == 401


# ---------------------------------------------------------------------------
# Test Group C -- Previously-unauthenticated Workshop endpoints (Part 6-8)
# ---------------------------------------------------------------------------

def test_create_workshop_requires_auth():
    r = client.post("/api/workshops", json={
        "name": "Unauthed Workshop", "description": "x", "date": "2026-09-01",
        "time": "10:00", "duration": "2h", "venue": "Online", "age_group": "8-12",
        "price": 999.0, "sales_team_email": "sales@example.com",
    })
    assert r.status_code == 401


def test_create_workshop_rejects_wrong_role():
    r = client.post(
        "/api/workshops",
        headers={"Authorization": "Bearer mock-approver-token"},
        json={
            "name": "Wrong Role Workshop", "description": "x", "date": "2026-09-01",
            "time": "10:00", "duration": "2h", "venue": "Online", "age_group": "8-12",
            "price": 999.0, "sales_team_email": "sales@example.com",
        },
    )
    assert r.status_code == 403


def test_publish_workshop_requires_approver_role():
    r = client.post(
        "/api/workshops/some-nonexistent-handle/publish",
        headers={"Authorization": "Bearer mock-catalogue-token"},
    )
    # CATALOGUE_ADMIN is not APPROVER -- must be rejected before the 404
    # "workshop not found" branch is ever reached.
    assert r.status_code == 403


def test_publish_workshop_unauthenticated_rejected():
    r = client.post("/api/workshops/some-nonexistent-handle/publish")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Test Group D -- /outputs unauthenticated data exposure fix (Part 8)
# ---------------------------------------------------------------------------

def test_outputs_mock_firestore_no_longer_publicly_served():
    """outputs/mock_firestore contains raw product + audit-log JSON
    (including reviewer/customer emails) and must not be reachable at all
    now that the blanket /outputs mount has been replaced."""
    r = client.get("/outputs/mock_firestore/audit_logs/does-not-matter.json")
    assert r.status_code == 404


def test_outputs_temp_uploads_no_longer_publicly_served():
    r = client.get("/outputs/temp_uploads/some-session-id/product.json")
    assert r.status_code == 404


def test_outputs_emails_no_longer_publicly_served():
    r = client.get("/outputs/emails/some-file.html")
    assert r.status_code == 404


def test_outputs_images_still_publicly_served_route_exists():
    """outputs/images is the legitimate public path (workshop landing page
    marketing images) -- the route must exist (404 for a missing file is
    fine/expected, but it must not be swallowed by the removed blanket
    mount i.e. this must still resolve through the outputs-images app)."""
    r = client.get("/outputs/images/definitely-not-a-real-file.png")
    # Missing file under a real mount -> 404 from StaticFiles itself, which
    # is indistinguishable at this layer from "route doesn't exist" by
    # status code alone, so we assert the route is registered instead.
    routes = [r.path for r in app.routes]
    assert any(p.startswith("/outputs/images") for p in routes)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Test Group E -- CORS configuration (Part 10)
# ---------------------------------------------------------------------------

def test_cors_origins_list_defaults_to_wildcard():
    from config import Settings
    s = Settings(cors_allowed_origins="*")
    assert s.cors_origins_list == ["*"]


def test_cors_origins_list_parses_comma_separated_allowlist():
    from config import Settings
    s = Settings(cors_allowed_origins="https://a.example.com, https://b.example.com")
    assert s.cors_origins_list == ["https://a.example.com", "https://b.example.com"]


def test_production_startup_rejects_wildcard_cors(monkeypatch):
    """validate_startup()'s is_testing bypass checks `"pytest" in sys.modules`
    and `TESTING` env var -- both are true for every other test in this
    suite (by design, so they don't need real Shopify creds). To exercise
    the actual production-path check, temporarily hide both signals using
    monkeypatch to delete 'pytest' from sys.modules and clear the TESTING
    env var in-place; monkeypatch restores both automatically at teardown."""
    import sys as _sys
    from config import Settings

    monkeypatch.delitem(_sys.modules, "pytest", raising=False)
    monkeypatch.delenv("TESTING", raising=False)

    s = Settings(app_env="production", cors_allowed_origins="*",
                 shopify_store_url="x", shopify_access_token="y")
    with pytest.raises(ValueError, match="WILDCARD CORS"):
        s.validate_startup()


# ---------------------------------------------------------------------------
# Test Group F -- File upload validation (Part 11)
# ---------------------------------------------------------------------------

def test_folder_launch_rejects_disallowed_extension():
    files = [("files", ("product.exe", io.BytesIO(b"MZ"), "application/octet-stream"))]
    r = client.post(
        "/launch-folder",
        headers={"Authorization": "Bearer mock-catalogue-token"},
        files=files,
        data={"preview": "true"},
    )
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"]


def test_folder_launch_rejects_too_many_files(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_total_files", 2)
    files = [
        ("files", ("a.json", io.BytesIO(b"{}"), "application/json")),
        ("files", ("b.json", io.BytesIO(b"{}"), "application/json")),
        ("files", ("c.json", io.BytesIO(b"{}"), "application/json")),
    ]
    r = client.post(
        "/launch-folder",
        headers={"Authorization": "Bearer mock-catalogue-token"},
        files=files,
        data={"preview": "true"},
    )
    assert r.status_code == 400
    assert "Too many files" in r.json()["detail"]


def test_folder_launch_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_file_size_mb", 1)  # 1MB cap for this test
    oversized = io.BytesIO(b"0" * (2 * 1024 * 1024))  # 2MB payload
    files = [("files", ("product.json", oversized, "application/json"))]
    r = client.post(
        "/launch-folder",
        headers={"Authorization": "Bearer mock-catalogue-token"},
        files=files,
        data={"preview": "true"},
    )
    assert r.status_code == 400
    assert "exceeds" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Test Group G -- Health check status differentiation (Part 13)
# ---------------------------------------------------------------------------

def test_health_degraded_when_shopify_not_connected():
    with patch("shopify_client._get_config", side_effect=Exception("no creds")):
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["shopify_connectivity"] != "connected"
    assert body["status"] == "degraded"
