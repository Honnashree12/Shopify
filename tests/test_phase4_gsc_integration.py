"""
Phase 4 Focused Mocked Tests -- Google Search Console (GSC) Integration.
Tests OAuth URL generation, token exchange, token refresh, property verification
for Avenue Products, Search Console analytics retrieval, Shopify URL mapping,
error handling (403, 429), and FastAPI RBAC endpoints.
No live Google or Shopify calls; no Vertex AI billing.
"""

import os
import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "True"

import main
from main import app
from services.google_search_console_service import (
    GoogleSearchConsoleService,
    GSC_READONLY_SCOPE,
    DEFAULT_AVENUE_PROPERTY,
)

client = TestClient(app)

APPROVER_HEADERS = {"Authorization": "Bearer mock-approver-token"}
ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}
CATALOGUE_HEADERS = {"Authorization": "Bearer mock-catalogue-token"}


@pytest.fixture(autouse=True)
def disable_auth_fallback(monkeypatch):
    monkeypatch.setenv("ALLOW_AUTH_FALLBACK", "False")


# ==============================================================================
# 1. Configuration & Diagnostic Status Tests
# ==============================================================================

def test_gsc_status_unconfigured(monkeypatch, tmp_path):
    """Verify service reports UNCONFIGURED when credentials are missing."""
    token_file = str(tmp_path / "gsc_token.json")
    svc = GoogleSearchConsoleService(
        client_id="",
        client_secret="",
        token_path=token_file,
        site_url="https://kinq5t-q5.myshopify.com",
    )
    status = svc.get_service_status()
    assert status["status"] == "UNCONFIGURED"
    assert status["connected"] is False
    assert status["verified"] is False
    assert status["site_url"] == "https://kinq5t-q5.myshopify.com"
    assert "credentials" in status["message"]


def test_gsc_status_needs_authentication(monkeypatch, tmp_path):
    """Verify service reports NEEDS_AUTHENTICATION when client credentials exist but no token stored."""
    token_file = str(tmp_path / "gsc_token.json")
    svc = GoogleSearchConsoleService(
        client_id="mock-client-id.apps.googleusercontent.com",
        client_secret="mock-client-secret",
        token_path=token_file,
        site_url="https://kinq5t-q5.myshopify.com",
    )
    status = svc.get_service_status()
    assert status["status"] == "NEEDS_AUTHENTICATION"
    assert status["connected"] is False
    assert status["verified"] is False
    assert "Authorize Search Console" in status["message"]


# ==============================================================================
# 2. Property Verification (Avenue Products) Tests
# ==============================================================================

@patch("httpx.Client.get")
def test_gsc_property_verification_verified(mock_get, tmp_path):
    """Verify site property verification succeeds for verified Avenue Products ownership."""
    token_file = str(tmp_path / "gsc_token.json")
    with open(token_file, "w") as f:
        json.dump({"access_token": "mock-access-token", "expires_at": "2099-01-01T00:00:00Z"}, f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "siteUrl": "https://kinq5t-q5.myshopify.com/",
        "permissionLevel": "siteOwner",
    }
    mock_get.return_value = mock_resp

    svc = GoogleSearchConsoleService(
        client_id="mock-client-id",
        client_secret="mock-client-secret",
        token_path=token_file,
        site_url="https://kinq5t-q5.myshopify.com",
    )
    verification = svc.verify_site_property()
    assert verification["verified"] is True
    assert verification["status"] == "VERIFIED"
    assert verification["permission_level"] == "siteOwner"

    status = svc.get_service_status()
    assert status["status"] == "CONNECTED"
    assert status["verified"] is True


@patch("httpx.Client.get")
def test_gsc_property_verification_unverified_property(mock_get, tmp_path):
    """Verify status detects unverified property and does not falsely assume verification."""
    token_file = str(tmp_path / "gsc_token.json")
    with open(token_file, "w") as f:
        json.dump({"access_token": "mock-access-token", "expires_at": "2099-01-01T00:00:00Z"}, f)

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp

    svc = GoogleSearchConsoleService(
        client_id="mock-client-id",
        client_secret="mock-client-secret",
        token_path=token_file,
        site_url="https://kinq5t-q5.myshopify.com",
    )
    verification = svc.verify_site_property()
    assert verification["verified"] is False
    assert verification["status"] == "NOT_FOUND"

    status = svc.get_service_status()
    assert status["status"] == "PROPERTY_UNVERIFIED"
    assert status["verified"] is False
    assert "verify" in status["message"].lower()


# ==============================================================================
# 3. OAuth 2.0 Flow Tests
# ==============================================================================

def test_gsc_auth_url_generation():
    """Verify OAuth consent URL requests minimum read-only scope."""
    svc = GoogleSearchConsoleService(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
        redirect_uri="http://localhost:8000/api/seo/search-console/oauth/callback",
    )
    res = svc.get_authorization_url(state="test-state-123")
    assert res["success"] is True
    auth_url = res["auth_url"]
    assert "accounts.google.com" in auth_url
    assert "test-client-id.apps.googleusercontent.com" in auth_url
    assert urllib_parse_safe_contains(auth_url, GSC_READONLY_SCOPE)
    assert "access_type=offline" in auth_url
    assert "state=test-state-123" in auth_url


def urllib_parse_safe_contains(url: str, substring: str) -> bool:
    import urllib.parse
    return urllib.parse.quote(substring, safe="") in url or substring in url


@patch("httpx.Client.post")
def test_gsc_token_exchange(mock_post, tmp_path):
    """Verify token exchange persists tokens server-side securely."""
    token_file = str(tmp_path / "gsc_token.json")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "ya29.mock-new-access-token",
        "refresh_token": "1//mock-refresh-token",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    mock_post.return_value = mock_resp

    svc = GoogleSearchConsoleService(
        client_id="test-client-id",
        client_secret="test-client-secret",
        token_path=token_file,
    )
    res = svc.exchange_code("mock-auth-code-123")
    assert res["success"] is True
    assert res["connected"] is True
    assert os.path.exists(token_file)

    with open(token_file, "r") as f:
        saved = json.load(f)
    assert saved["access_token"] == "ya29.mock-new-access-token"
    assert saved["refresh_token"] == "1//mock-refresh-token"
    assert "expires_at" in saved


@patch("httpx.Client.post")
def test_gsc_token_refresh(mock_post, tmp_path):
    """Verify automatic token renewal using stored refresh token."""
    token_file = str(tmp_path / "gsc_token.json")
    with open(token_file, "w") as f:
        json.dump({
            "access_token": "old-token",
            "refresh_token": "valid-refresh-token",
            "expires_at": "2020-01-01T00:00:00Z"  # Expired
        }, f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "ya29.refreshed-token",
        "expires_in": 3600,
    }
    mock_post.return_value = mock_resp

    svc = GoogleSearchConsoleService(
        client_id="test-client-id",
        client_secret="test-client-secret",
        token_path=token_file,
    )
    valid_token = svc.get_valid_access_token()
    assert valid_token == "ya29.refreshed-token"


# ==============================================================================
# 4. Search Analytics Retrieval & URL Mapping Tests
# ==============================================================================

@patch("httpx.Client.post")
def test_gsc_fetch_search_analytics(mock_post, tmp_path):
    """Verify search analytics query calculates summary KPIs, top queries, and averages."""
    token_file = str(tmp_path / "gsc_token.json")
    with open(token_file, "w") as f:
        json.dump({"access_token": "mock-token", "expires_at": "2099-01-01T00:00:00Z"}, f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "rows": [
            {
                "keys": ["https://kinq5t-q5.myshopify.com/products/robotics-kit", "stem robot kit"],
                "clicks": 45,
                "impressions": 1000,
                "ctr": 0.045,
                "position": 3.2,
            },
            {
                "keys": ["https://kinq5t-q5.myshopify.com/products/robotics-kit", "kids robotics kit"],
                "clicks": 15,
                "impressions": 500,
                "ctr": 0.03,
                "position": 4.8,
            },
            {
                "keys": ["https://kinq5t-q5.myshopify.com/products/solar-rover", "solar rover toy"],
                "clicks": 20,
                "impressions": 400,
                "ctr": 0.05,
                "position": 2.1,
            },
        ]
    }
    mock_post.return_value = mock_resp

    svc = GoogleSearchConsoleService(
        token_path=token_file,
        site_url="https://kinq5t-q5.myshopify.com"
    )
    res = svc.fetch_search_analytics(start_date="2026-10-01", end_date="2026-10-28")
    assert res["success"] is True
    assert res["summary"]["total_clicks"] == 80
    assert res["summary"]["total_impressions"] == 1900
    assert res["summary"]["average_ctr"] == round((80 / 1900) * 100, 2)
    assert len(res["top_queries"]) >= 2
    assert res["top_queries"][0]["query"] == "stem robot kit"


def test_gsc_shopify_url_mapping():
    """Verify URL mapping categorizes top-performing, low-visibility, unranked, and unmatched pages."""
    gsc_rows = [
        {
            "keys": ["https://kinq5t-q5.myshopify.com/products/smart-drone", "smart drone kids"],
            "clicks": 80,
            "impressions": 1200,
            "position": 2.5,
        },
        {
            "keys": ["https://kinq5t-q5.myshopify.com/products/coding-kit", "coding kit beginner"],
            "clicks": 2,
            "impressions": 40,
            "position": 12.0,
        },
        {
            "keys": ["https://kinq5t-q5.myshopify.com/collections/all-toys", "educational toys"],
            "clicks": 10,
            "impressions": 300,
            "position": 5.0,
        },
    ]

    shopify_products = [
        {"id": "1", "title": "Smart Drone", "handle": "smart-drone"},
        {"id": "2", "title": "Coding Kit", "handle": "coding-kit"},
        {"id": "3", "title": "Unranked Solar Car", "handle": "unranked-solar-car"},
    ]

    mapping = GoogleSearchConsoleService.map_search_console_to_shopify(
        gsc_rows=gsc_rows,
        shopify_products=shopify_products,
    )

    assert mapping["matched_count"] == 2
    assert mapping["unranked_count"] == 1
    assert mapping["unmatched_pages_count"] == 1

    # Matched product verification
    matched_drone = next(p for p in mapping["matched_products"] if p["handle"] == "smart-drone")
    assert matched_drone["clicks"] == 80
    assert matched_drone["impressions"] == 1200

    # Top performing vs low visibility
    assert len(mapping["top_performing_products"]) >= 1
    assert mapping["top_performing_products"][0]["handle"] == "smart-drone"

    assert len(mapping["low_visibility_products"]) >= 1
    assert mapping["low_visibility_products"][0]["handle"] == "coding-kit"

    # Unranked verification
    assert mapping["unranked_products"][0]["handle"] == "unranked-solar-car"
    assert mapping["unmatched_pages"][0]["page_url"] == "https://kinq5t-q5.myshopify.com/collections/all-toys"


# ==============================================================================
# 5. Error Handling Tests (403 Permission Denied & 429 Rate Limited)
# ==============================================================================

@patch("httpx.Client.post")
def test_gsc_error_handling_rate_limited_429(mock_post, tmp_path):
    """Verify HTTP 429 rate limit produces structured RATE_LIMITED status."""
    token_file = str(tmp_path / "gsc_token.json")
    with open(token_file, "w") as f:
        json.dump({"access_token": "mock-token", "expires_at": "2099-01-01T00:00:00Z"}, f)

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_post.return_value = mock_resp

    svc = GoogleSearchConsoleService(token_path=token_file)
    res = svc.fetch_search_analytics("2026-10-01", "2026-10-28")
    assert res["success"] is False
    assert res["status"] == "RATE_LIMITED"
    assert "rate limit" in res["error"]


@patch("httpx.Client.post")
def test_gsc_error_handling_permission_denied_403(mock_post, tmp_path):
    """Verify HTTP 403 produces structured PERMISSION_DENIED status."""
    token_file = str(tmp_path / "gsc_token.json")
    with open(token_file, "w") as f:
        json.dump({"access_token": "mock-token", "expires_at": "2099-01-01T00:00:00Z"}, f)

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "User does not have sufficient permissions for this site."
    mock_post.return_value = mock_resp

    svc = GoogleSearchConsoleService(token_path=token_file)
    res = svc.fetch_search_analytics("2026-10-01", "2026-10-28")
    assert res["success"] is False
    assert res["status"] == "PERMISSION_DENIED"
    assert "Access denied" in res["error"]


# ==============================================================================
# 6. FastAPI GSC Endpoints & RBAC Protection Tests
# ==============================================================================

@patch("services.google_search_console_service.GoogleSearchConsoleService.get_service_status")
def test_gsc_fastapi_status_endpoint(mock_status):
    """Verify GET /api/seo/search-console/status returns service diagnostics."""
    mock_status.return_value = {
        "status": "CONNECTED",
        "connected": True,
        "verified": True,
        "site_url": "https://kinq5t-q5.myshopify.com",
        "message": "Connected and verified for Avenue Products.",
    }
    res = client.get("/api/seo/search-console/status", headers=CATALOGUE_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "CONNECTED"
    assert data["verified"] is True
    assert data["site_url"] == "https://kinq5t-q5.myshopify.com"


@patch("services.google_search_console_service.GoogleSearchConsoleService.verify_site_property")
def test_gsc_fastapi_verify_endpoint(mock_verify):
    """Verify GET /api/seo/search-console/verify endpoint checks Avenue Products."""
    mock_verify.return_value = {
        "verified": True,
        "status": "VERIFIED",
        "site_url": "https://kinq5t-q5.myshopify.com",
        "permission_level": "siteOwner",
    }
    res = client.get("/api/seo/search-console/verify", headers=APPROVER_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is True
    assert data["status"] == "VERIFIED"


def test_gsc_fastapi_auth_url_rbac_guard():
    """Verify unauthenticated requests cannot request OAuth authorization URL."""
    res = client.get("/api/seo/search-console/auth-url")
    assert res.status_code == 401


@patch("services.google_search_console_service.GoogleSearchConsoleService.get_authorization_url")
def test_gsc_fastapi_auth_url_catalogue_admin_allowed(mock_auth_url):
    """Verify CATALOGUE_ADMIN role is permitted to generate OAuth authorization URL."""
    mock_auth_url.return_value = {"success": True, "auth_url": "https://accounts.google.com/o/oauth2/v2/auth"}
    res = client.get("/api/seo/search-console/auth-url", headers=CATALOGUE_HEADERS)
    assert res.status_code == 200
    assert "accounts.google.com" in res.json()["auth_url"]


@patch("services.google_search_console_service.GoogleSearchConsoleService.refresh_access_token")
def test_gsc_fastapi_refresh_endpoint(mock_refresh):
    """Verify POST /api/seo/search-console/refresh allows approver to refresh token."""
    mock_refresh.return_value = "new-valid-token"
    res = client.post("/api/seo/search-console/refresh", headers=APPROVER_HEADERS)
    assert res.status_code == 200
    assert res.json()["success"] is True
