"""
Phase 3 Focused Tests -- SEO Dashboard Endpoints, Filters, Approvals & Safety Controls.
Tests dashboard REST API endpoints, search/severity filtering, dry-run defaults,
and role-based approval controls using TestClient with deterministic mocks.
No Vertex AI billing or live Shopify API calls.
"""

import os
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "True"

import main
from main import app

client = TestClient(app)

APPROVER_HEADERS = {"Authorization": "Bearer mock-approver-token"}
ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}
CATALOGUE_HEADERS = {"Authorization": "Bearer mock-catalogue-token"}


@pytest.fixture(autouse=True)
def disable_auth_fallback(monkeypatch):
    monkeypatch.setenv("ALLOW_AUTH_FALLBACK", "False")


# ==============================================================================
# 1. SEO Dashboard Audit & Filter Endpoints Tests
# ==============================================================================

@patch("workflow.seo_optimization_workflow.SEOOptimizationWorkflow.run_catalogue_audit")
def test_get_seo_audit_endpoint(mock_run_audit):
    """Verify GET /api/seo/audit returns catalogue health metrics and checklist score."""
    mock_run_audit.return_value = {
        "total_audited": 3,
        "products_with_issues": 2,
        "optimized_products": 1,
        "average_seo_score": 72.5,
        "issue_breakdown": {"MISSING_SEO_TITLE": 1, "MISSING_IMAGE_ALT_TEXT": 2},
        "products": [
            {
                "product_id": "101",
                "title": "Robotics Kit",
                "handle": "robotics-kit",
                "seo_score": 85,
                "status": "CAN_IMPROVE",
                "issues": [{"code": "MISSING_IMAGE_ALT_TEXT", "severity": "WARNING"}],
            },
            {
                "product_id": "102",
                "title": "AI Camera Board",
                "handle": "ai-camera-board",
                "seo_score": 40,
                "status": "NEEDS_OPTIMIZATION",
                "issues": [{"code": "MISSING_SEO_TITLE", "severity": "CRITICAL"}],
            },
            {
                "product_id": "103",
                "title": "Solar Rover",
                "handle": "solar-rover",
                "seo_score": 100,
                "status": "OPTIMIZED",
                "issues": [],
            },
        ],
        "disclaimer": "Internal technical checklist compliance score.",
    }

    res = client.get("/api/seo/audit", headers=APPROVER_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["total_audited"] == 3
    assert data["average_seo_score"] == 72.5
    assert len(data["products"]) == 3
    assert "MISSING_SEO_TITLE" in data["issue_breakdown"]


@patch("workflow.seo_optimization_workflow.SEOOptimizationWorkflow.run_catalogue_audit")
def test_get_seo_audit_search_and_severity_filtering(mock_run_audit):
    """Verify search and severity query parameters filter products correctly."""
    mock_run_audit.return_value = {
        "total_audited": 2,
        "products_with_issues": 2,
        "optimized_products": 0,
        "average_seo_score": 60.0,
        "products": [
            {
                "product_id": "201",
                "title": "STEM Coding Robot",
                "handle": "stem-coding-robot",
                "status": "NEEDS_OPTIMIZATION",
                "issues": [{"code": "MISSING_SEO_TITLE", "severity": "CRITICAL"}],
            },
            {
                "product_id": "202",
                "title": "Electronics Breadboard",
                "handle": "electronics-breadboard",
                "status": "CAN_IMPROVE",
                "issues": [{"code": "SHORT_SEO_TITLE", "severity": "WARNING"}],
            },
        ],
    }

    # Test keyword search filter
    res = client.get("/api/seo/audit?search=robot", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data["products"]) == 1
    assert data["products"][0]["title"] == "STEM Coding Robot"

    # Test severity filter
    res_sev = client.get("/api/seo/audit?severity=CRITICAL", headers=ADMIN_HEADERS)
    assert res_sev.status_code == 200
    data_sev = res_sev.json()
    assert len(data_sev["products"]) == 1
    assert data_sev["products"][0]["product_id"] == "201"


# ==============================================================================
# 2. Proposals & Dry-Run Generation Endpoints Tests
# ==============================================================================

@patch("workflow.seo_optimization_workflow.SEOOptimizationWorkflow.generate_proposals")
def test_get_seo_proposals_endpoint(mock_gen_proposals):
    """Verify GET /api/seo/proposals returns Before-and-After proposals."""
    mock_gen_proposals.return_value = {
        "mode": "PROPOSAL_DRY_RUN",
        "total_products_evaluated": 1,
        "proposals": [
            {
                "product_id": "301",
                "product_title": "Drone Kit",
                "before": {"seo_title": "(Default)", "handle": "drone-kit"},
                "after": {"seo_title": "STEM Drone Kit | KiddyPi", "handle": "drone-kit"},
                "changes_summary": ["Optimized SEO title under 60 chars."],
            }
        ],
    }

    res = client.get("/api/seo/proposals?product_id=301", headers=APPROVER_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "PROPOSAL_DRY_RUN"
    assert len(data["proposals"]) == 1
    assert data["proposals"][0]["after"]["seo_title"] == "STEM Drone Kit | KiddyPi"


# ==============================================================================
# 3. Apply Optimizations, Approval Gating & Safety Controls Tests
# ==============================================================================

@patch("workflow.seo_optimization_workflow.SEOOptimizationWorkflow.apply_approved_optimizations")
def test_apply_seo_optimizations_dry_run_by_default(mock_apply):
    """Verify POST /api/seo/apply defaults to dry_run=True for safe simulation."""
    mock_apply.return_value = {
        "dry_run": True,
        "successful_updates": 1,
        "failed_updates": 0,
        "details": [{"product_id": "401", "status": "SIMULATED_SUCCESS"}],
    }

    # Omit dry_run from payload -- should default to True
    payload = {
        "approved_proposals": [
            {
                "product_id": "401",
                "after": {
                    "seo_title": "AI Robot | KiddyPi",
                    "seo_description": "Learn artificial intelligence.",
                },
            }
        ]
    }

    res = client.post("/api/seo/apply", json=payload, headers=APPROVER_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["dry_run"] is True
    # Assert workflow was called with dry_run=True
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["dry_run"] is True


def test_apply_seo_optimizations_rejects_empty_proposals():
    """Verify POST /api/seo/apply rejects empty proposals with 400 Bad Request."""
    res = client.post(
        "/api/seo/apply",
        json={"approved_proposals": [], "dry_run": False},
        headers=APPROVER_HEADERS,
    )
    assert res.status_code == 400
    assert "No approved proposals provided" in res.json()["detail"]


@patch("workflow.seo_optimization_workflow.SEOOptimizationWorkflow.apply_approved_optimizations")
def test_apply_seo_optimizations_live_requires_explicit_approval(mock_apply):
    """Verify live updates execute only when dry_run=False and approver credentials are valid."""
    mock_apply.return_value = {
        "dry_run": False,
        "applied_by": "approver@kiddypi.com",
        "successful_updates": 1,
        "failed_updates": 0,
        "details": [{"product_id": "501", "status": "SUCCESS"}],
    }

    payload = {
        "approved_proposals": [
            {
                "product_id": "501",
                "after": {"seo_title": "Solar Robot | KiddyPi"},
                "approve_handle_change": False,
            }
        ],
        "dry_run": False,
    }

    res = client.post("/api/seo/apply", json=payload, headers=APPROVER_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["dry_run"] is False
    assert mock_apply.call_args.kwargs["dry_run"] is False


def test_apply_seo_optimizations_rbac_guard():
    """Verify users with non-approver roles cannot apply SEO updates (403 Forbidden)."""
    payload = {
        "approved_proposals": [{"product_id": "601", "after": {}}],
        "dry_run": False,
    }

    # CATALOGUE_ADMIN cannot approve or apply live updates
    res = client.post("/api/seo/apply", json=payload, headers=CATALOGUE_HEADERS)
    assert res.status_code == 403
    assert "Permission denied" in res.json()["detail"]


@patch("workflow.seo_optimization_workflow.SEOOptimizationWorkflow.apply_approved_optimizations")
def test_catalogue_admin_can_run_dry_run_simulation(mock_apply):
    """Verify CATALOGUE_ADMIN can freely run dry-run simulations."""
    mock_apply.return_value = {
        "mode": "PROPOSAL_DRY_RUN",
        "dry_run": True,
        "successful_updates": 1,
        "failed_updates": 0,
        "details": [{"product_id": "601", "status": "SIMULATED_SUCCESS"}],
    }
    payload = {
        "approved_proposals": [{"product_id": "601", "after": {}}],
        "dry_run": True,
    }
    res = client.post("/api/seo/apply", json=payload, headers=CATALOGUE_HEADERS)
    assert res.status_code == 200
    assert res.json()["dry_run"] is True


# ==============================================================================
# 4. SEO History Endpoint Test
# ==============================================================================

@patch("os.path.exists")
@patch("builtins.open")
@patch("json.load")
def test_get_seo_history_endpoint(mock_json_load, mock_open, mock_exists):
    """Verify GET /api/seo/history returns past execution runs."""
    mock_exists.return_value = True
    mock_json_load.return_value = [
        {
            "executed_at": "2026-11-03T12:00:00Z",
            "dry_run": True,
            "applied_by": "approver@kiddypi.com",
            "successful_updates": 5,
        }
    ]

    res = client.get("/api/seo/history", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["successful_updates"] == 5
