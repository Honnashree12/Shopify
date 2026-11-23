"""
Phase 4 -- Product Launch Agent Execution, Shopify Publishing & Production
Workflow. Covers the mechanisms added/hardened in this phase:

  Test Group A -- Approval Gate (version integrity, layer-2 defense in depth)
  Test Group B -- Shopify creation idempotency / duplicate protection
  Test Group F -- Concurrency / idempotency (double-approve, retry)
  Test Group G -- End-to-end: retry lifecycle and audit trail

Existing Phase 1/3 coverage (auth, RBAC, self-approval, basic idempotency,
state-transition guards) already lives in test_phase1_foundation.py and
test_phase3_security.py and is not duplicated here.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "True"

import main
from main import app, active_sessions
from services.auth_service import User
from state import ProductLaunchState
from workflow import progress_tracker
from tools.folder_tools import create_shopify_product_tool

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_auth_fallback(monkeypatch):
    monkeypatch.setenv("ALLOW_AUTH_FALLBACK", "False")


@pytest.fixture(autouse=True)
def clear_publish_locks():
    """Progress-tracker state is module-level and must not leak between tests."""
    yield
    progress_tracker._active_publishing_sessions.clear()
    progress_tracker._current_stage.clear()


def _mock_tool_context(state_dict):
    """Minimal ADK ToolContext stand-in exposing only `.state` as a dict."""
    ctx = MagicMock()
    ctx.state = state_dict
    ctx._invocation_context = MagicMock()
    ctx._invocation_context.session = MagicMock()
    ctx._invocation_context.session.id = "tool-ctx-session"
    return ctx


# ---------------------------------------------------------------------------
# Test Group A -- Approval Gate (Part 1 / Part 2)
# ---------------------------------------------------------------------------

def test_stale_approval_cannot_publish_layer2():
    """create_shopify_product_tool must refuse a create when approved_at_version
    no longer matches product_version -- the Layer 2 defense-in-depth check,
    independent of whatever main.py's endpoints already enforced."""
    state = {
        "approved_to_publish": True,
        "approved_by_uid": "approver-uid",
        "approved_at": "2026-08-12T00:00:00Z",
        "preview_mode": False,
        "approved_at_version": 1,
        "product_version": 2,  # product was edited after approval
        "manifest": {},
        "product_name": "Stale Approval Product",
        "product_description": "desc",
        "product_price": 10,
        "sku": "STALE-1",
    }
    ctx = _mock_tool_context(state)
    result = create_shopify_product_tool(ctx)

    assert "PUBLISH DENIED" in result
    assert "stale" in result.lower()
    assert state.get("workflow_error")
    # No Shopify product should ever have been attempted/created
    assert "shopify_product_id" not in state or state.get("shopify_product_id") is None


def test_matching_approval_version_is_not_blocked_by_gate():
    """A current (non-stale) approval must NOT be rejected by the version
    check -- only reach the duplicate-detection path beyond it."""
    state = {
        "approved_to_publish": True,
        "approved_by_uid": "approver-uid",
        "approved_at": "2026-08-12T00:00:00Z",
        "preview_mode": False,
        "approved_at_version": 3,
        "product_version": 3,
        "shopify_product_id": 999001,  # already created -- should short-circuit here
    }
    ctx = _mock_tool_context(state)
    result = create_shopify_product_tool(ctx)

    assert "already created" in result.lower()
    assert "PUBLISH DENIED" not in result
    assert not state.get("workflow_error")


def test_unapproved_product_cannot_reach_approve_endpoint_publish():
    """A product still in 'pending' (never submitted/approved) is rejected
    by the approve endpoint itself -- publishing is structurally unreachable."""
    session_id = "test-unapproved-product"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Unapproved Product",
        raw_description="desc",
        status="pending",
        created_by_uid="catalogue-uid",
        created_at="2026-08-11T12:00:00Z",
    )
    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-approver-token"},
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Test Group B -- Shopify creation idempotency / duplicate protection (Part 5/18)
# ---------------------------------------------------------------------------

def test_create_tool_skips_when_shopify_product_already_created():
    """A retry/resume after a later-stage failure must not attempt to create
    a second Shopify product when this workflow run already created one."""
    state = {
        "approved_to_publish": True,
        "approved_by_uid": "approver-uid",
        "approved_at": "2026-08-12T00:00:00Z",
        "approved_at_version": 1,
        "product_version": 1,
        "preview_mode": False,
        "shopify_product_id": 555123,
        "shopify_url": "https://example.myshopify.com/products/555123",
    }
    ctx = _mock_tool_context(state)
    with patch("tools.folder_tools.get_product_by_sku") as mock_lookup:
        result = create_shopify_product_tool(ctx)
        mock_lookup.assert_not_called()

    assert "555123" in result
    assert "skipping duplicate creation" in result.lower()


# ---------------------------------------------------------------------------
# Test Group F -- Concurrency / idempotency
# ---------------------------------------------------------------------------

def test_concurrent_approve_requests_only_one_wins():
    """Two near-simultaneous approve requests for the same product must not
    both be allowed to schedule a publishing run. Simulated by acquiring the
    lock out-of-band the way the first request's handler would, then issuing
    the HTTP request that represents the second, racing request."""
    session_id = "test-concurrent-approve"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Concurrency Test Product",
        raw_description="desc",
        status="awaiting_approval",
        created_by_uid="catalogue-uid",
        submitted_by_uid="catalogue-uid",
        created_at="2026-08-11T12:00:00Z",
        product_version=1,
    )

    assert progress_tracker.try_acquire_publish_lock(session_id) is True

    try:
        response = client.post(
            f"/api/products/{session_id}/approve",
            headers={"Authorization": "Bearer mock-approver-token"},
        )
        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"].lower()
        # The racing request must not have flipped status to running
        assert active_sessions[session_id].status == "awaiting_approval"
    finally:
        progress_tracker.release_publish_lock(session_id)


def test_approve_releases_lock_on_validation_failure():
    """If a later check (self-approval protection) rejects the request, the
    lock acquired at the top of the handler must be released -- otherwise a
    single bad request would permanently block all future legitimate
    approval attempts for that product."""
    session_id = "test-lock-release-on-403"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Self Approve Product",
        raw_description="desc",
        status="awaiting_approval",
        created_by_uid="approver-uid",
        submitted_by_uid="approver-uid",
        created_at="2026-08-11T12:00:00Z",
    )

    response = client.post(
        f"/api/products/{session_id}/approve",
        headers={"Authorization": "Bearer mock-approver-token"},
    )
    assert response.status_code == 403
    # Lock must have been released, not leaked
    assert progress_tracker.is_publishing(session_id) is False


# ---------------------------------------------------------------------------
# Test Group G -- Retry endpoint (Part 8 / Part 17)
# ---------------------------------------------------------------------------

def _patch_background_runner():
    main_modules = [m for n, m in sys.modules.items() if n == "main" or n.endswith(".main")]
    orig_funcs = {}
    mock_run = MagicMock()
    for m in main_modules:
        if hasattr(m, "run_folder_workflow_background"):
            orig_funcs[m] = m.run_folder_workflow_background
            m.run_folder_workflow_background = mock_run
    return orig_funcs, mock_run


def _restore_background_runner(orig_funcs):
    for m, orig in orig_funcs.items():
        m.run_folder_workflow_background = orig


def test_retry_requires_platform_admin():
    session_id = "test-retry-role-guard"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Retry Guard Product",
        raw_description="desc",
        status="failed",
        failed_stage="media",
        created_by_uid="catalogue-uid",
        approved_by_uid="approver-uid",
        approved_to_publish=True,
        product_version=1,
        approved_at_version=1,
        created_at="2026-08-11T12:00:00Z",
    )
    # Reviewer (not Platform Admin) attempts retry -> 403
    response = client.post(
        f"/api/products/{session_id}/retry",
        headers={"Authorization": "Bearer mock-approver-token"},
    )
    assert response.status_code == 403


def test_retry_requires_failed_status():
    session_id = "test-retry-status-guard"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Retry Status Guard Product",
        raw_description="desc",
        status="completed",
        approved_by_uid="approver-uid",
        approved_to_publish=True,
        product_version=1,
        approved_at_version=1,
        created_at="2026-08-11T12:00:00Z",
    )
    response = client.post(
        f"/api/products/{session_id}/retry",
        headers={"Authorization": "Bearer mock-admin-token"},
    )
    assert response.status_code == 409


def test_retry_refuses_stale_approval():
    """Retry must not resume a run whose approval no longer matches the
    current product version -- same integrity rule as a first-time publish."""
    session_id = "test-retry-stale-approval"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Retry Stale Approval Product",
        raw_description="desc",
        status="failed",
        failed_stage="media",
        approved_by_uid="approver-uid",
        approved_to_publish=True,
        product_version=2,          # edited after approval
        approved_at_version=1,      # approval is for the old version
        created_at="2026-08-11T12:00:00Z",
    )
    response = client.post(
        f"/api/products/{session_id}/retry",
        headers={"Authorization": "Bearer mock-admin-token"},
    )
    assert response.status_code == 409
    assert "modified after it was approved" in response.json()["detail"]
    # Status must remain "failed" -- retry must not have been scheduled
    assert active_sessions[session_id].status == "failed"


def test_retry_succeeds_for_valid_failed_run():
    """A legitimate retry: valid, current approval on record, status failed
    -> clears failed_stage/errors, flips to running, schedules the background
    run exactly once."""
    session_id = "test-retry-success"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Retry Success Product",
        raw_description="desc",
        status="failed",
        failed_stage="media",
        approved_by_uid="approver-uid",
        approved_to_publish=True,
        product_version=1,
        approved_at_version=1,
        created_at="2026-08-11T12:00:00Z",
        source="folder"
    )
    active_sessions[session_id].errors["workflow_error"] = "Shopify staged upload failed: HTTP 429"

    orig_funcs, mock_run = _patch_background_runner()
    try:
        response = client.post(
            f"/api/products/{session_id}/retry",
            headers={"Authorization": "Bearer mock-admin-token"},
        )
        assert response.status_code == 200
        assert active_sessions[session_id].status == "running"
        assert active_sessions[session_id].failed_stage is None
        assert "workflow_error" not in active_sessions[session_id].errors
        assert mock_run.called
    finally:
        _restore_background_runner(orig_funcs)


def test_retry_without_prior_approval_is_refused():
    """A product that somehow reached 'failed' without ever having a
    recorded approval must not be retryable -- retry resumes an
    authorization that must already exist, it never grants one."""
    session_id = "test-retry-no-approval"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Never Approved Product",
        raw_description="desc",
        status="failed",
        failed_stage="ingest",
        approved_to_publish=False,
        approved_by_uid=None,
        created_at="2026-08-11T12:00:00Z",
    )
    response = client.post(
        f"/api/products/{session_id}/retry",
        headers={"Authorization": "Bearer mock-admin-token"},
    )
    assert response.status_code == 403
    assert "no valid approval" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Live stage visibility (Part 9/10) and error redaction (Part 22)
# ---------------------------------------------------------------------------

def test_status_reports_live_current_stage_while_running():
    session_id = "test-current-stage-visibility"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Live Stage Product",
        raw_description="desc",
        status="running",
        created_by_uid="catalogue-uid",
        created_at="2026-08-11T12:00:00Z",
    )
    progress_tracker.set_stage(session_id, "media")

    response = client.get(
        f"/status/{session_id}",
        headers={"Authorization": "Bearer mock-admin-token"},
    )
    assert response.status_code == 200
    assert response.json()["current_stage"] == "media"


def test_status_redacts_stack_trace_for_non_platform_admin():
    """errors['workflow_error'] must be truncated to the friendly first line
    for every role except Platform Admin -- the full traceback must never
    reach a Catalogue Admin or Reviewer response, not just be hidden by the
    frontend."""
    session_id = "test-error-redaction"
    active_sessions[session_id] = ProductLaunchState(
        product_name="Error Redaction Product",
        raw_description="desc",
        status="failed",
        failed_stage="media",
        created_by_uid="catalogue-uid",
        created_at="2026-08-11T12:00:00Z",
    )
    full_message = "Shopify staged upload failed: HTTP 429\n\nStack Trace:\nTraceback (most recent call last)...\nsecret_internal_path=/srv/app/tools.py"
    active_sessions[session_id].errors["workflow_error"] = full_message

    # Catalogue Admin (owner) sees the friendly message only
    resp_owner = client.get(
        f"/status/{session_id}",
        headers={"Authorization": "Bearer mock-catalogue-token"},
    )
    assert resp_owner.status_code == 200
    owner_msg = resp_owner.json()["errors"]["workflow_error"]
    assert "Stack Trace" not in owner_msg
    assert "secret_internal_path" not in owner_msg
    assert owner_msg.startswith("Shopify staged upload failed")

    # Platform Admin sees the full technical detail
    resp_admin = client.get(
        f"/status/{session_id}",
        headers={"Authorization": "Bearer mock-admin-token"},
    )
    assert resp_admin.status_code == 200
    admin_msg = resp_admin.json()["errors"]["workflow_error"]
    assert "Stack Trace" in admin_msg
    assert "secret_internal_path" in admin_msg

    # The redaction for the owner's request must not have mutated the
    # shared in-memory record that the admin (or a later request) reads.
    assert "Stack Trace" in active_sessions[session_id].errors["workflow_error"]
