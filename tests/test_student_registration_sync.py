"""
Test Suite for Shopify to Google Sheets Student Registration Automation.

Tests all 8 mandatory scenarios:
1. Valid paid workshop registration.
2. Duplicate webhook delivery (idempotency).
3. Multiple workshop registrations in a single order.
4. Missing student information (graceful defaults).
5. Non-workshop order (unrelated product filtering).
6. Invalid webhook HMAC signature.
7. Google Sheets API failure (safe error capture and persistence).
8. Retry after failure (recovery of failed registrations).
"""

import os
import json
import base64
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient

# Ensure test mode
os.environ["TESTING"] = "True"
os.environ["ALLOW_AUTH_FALLBACK"] = "True"

from main import app
from config import settings
from data.database import (
    init_db,
    get_student_registration,
    get_all_student_registrations,
    get_webhook_event
)
from services.google_sheets_service import (
    SHEET_COLUMNS,
    get_mock_sheets_client,
    reset_mock_sheets_client
)
from services.registration_sync_service import (
    retry_failed_student_registrations
)

client = TestClient(app)

TEST_SECRET = "test_shopify_webhook_secret_key_12345"
settings.shopify_api_secret = TEST_SECRET
settings.mock_google_sheets = True


def compute_hmac(payload_bytes: bytes, secret: str = TEST_SECRET) -> str:
    """Compute base64 HMAC-SHA256 signature for test payloads."""
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def reset_test_environment():
    """Reset database and mock Google Sheets client with test configuration."""
    settings.app_env = "development"
    settings.shopify_api_secret = TEST_SECRET
    settings.mock_google_sheets = True
    init_db(clear=True)
    sheets_mock = reset_mock_sheets_client()
    return sheets_mock


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch=None):
    """Set up clean database and mock Google Sheets client for each pytest test."""
    if monkeypatch:
        monkeypatch.setattr(settings, "shopify_api_secret", TEST_SECRET)
        monkeypatch.setattr(settings, "mock_google_sheets", True)
    return reset_test_environment()


def test_1_valid_paid_workshop_registration():
    """
    Scenario 1: Valid paid workshop registration.
    Verify:
    - Webhook returns 200 OK.
    - Webhook event is persisted in SQLite.
    - Student registration is stored with all 10 extracted fields.
    - Google Sheet has 1 row matching the 12 expected columns.
    """
    sheets_mock = get_mock_sheets_client()
    order_payload = {
        "id": 700101,
        "order_number": "1001",
        "financial_status": "paid",
        "created_at": "2026-10-14T10:00:00Z",
        "email": "priya.sharma@example.com",
        "customer": {
            "first_name": "Priya",
            "last_name": "Sharma",
            "email": "priya.sharma@example.com",
            "phone": "+91 98765 43210"
        },
        "line_items": [
            {
                "id": 88001,
                "title": "Robotics Explorer Workshop Ticket",
                "price": "499.00",
                "quantity": 1,
                "properties": [
                    {"name": "Parent Name", "value": "Priya Sharma"},
                    {"name": "Parent Phone", "value": "+91 98765 43210"},
                    {"name": "Parent Email", "value": "priya.sharma@example.com"},
                    {"name": "Area", "value": "Indiranagar, Bangalore"},
                    {"name": "Child Name", "value": "Aarav Sharma"},
                    {"name": "Child Age", "value": "10"}
                ]
            }
        ]
    }

    raw_body = json.dumps(order_payload).encode("utf-8")
    signature = compute_hmac(raw_body)

    response = client.post(
        "/api/webhooks/orders/paid",
        content=raw_body,
        headers={
            "X-Shopify-Hmac-Sha256": signature,
            "X-Shopify-Topic": "orders/paid",
            "X-Shopify-Webhook-Id": "webhook-evt-700101",
            "Content-Type": "application/json"
        }
    )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["registrations_synced"] == 1

    # Verify SQLite event persistence
    evt = get_webhook_event("webhook-evt-700101")
    assert evt is not None
    assert evt["order_id"] == "700101"
    assert evt["status"] == "processed"
    assert evt["sync_status"] == "synced"

    # Verify SQLite student registration
    reg = get_student_registration("REG-700101-88001")
    assert reg is not None
    assert reg["parent_name"] == "Priya Sharma"
    assert reg["parent_phone"] == "+91 98765 43210"
    assert reg["parent_email"] == "priya.sharma@example.com"
    assert reg["area"] == "Indiranagar, Bangalore"
    assert reg["child_name"] == "Aarav Sharma"
    assert reg["child_age"] == "10"
    assert reg["workshop_name"] == "Robotics Explorer Workshop Ticket"
    assert reg["payment_status"] == "paid"
    assert reg["sync_status"] == "Synced"

    # Verify Google Sheet output columns match exactly
    rows = sheets_mock.get_all_rows()
    assert len(rows) == 1
    row = rows[0]

    # Verify 12 columns in exact order
    assert len(row) == 12
    assert row[0] == "REG-700101-88001"            # Registration ID
    assert row[1] == "700101"                      # Shopify Order ID
    assert row[2] == "Robotics Explorer Workshop Ticket"  # Workshop Name
    assert row[3] == "Priya Sharma"                # Parent Name
    assert row[4] == "+91 98765 43210"             # Parent Phone
    assert row[5] == "priya.sharma@example.com"    # Parent Email
    assert row[6] == "Indiranagar, Bangalore"      # Area
    assert row[7] == "Aarav Sharma"                # Child Name
    assert row[8] == "10"                          # Child Age
    assert row[9] == "paid"                        # Payment Status
    assert row[10] == "2026-10-14T10:00:00Z"       # Registration Date
    assert row[11] == "Synced"                     # Sync Status


def test_2_duplicate_webhook_delivery():
    """
    Scenario 2: Duplicate webhook delivery.
    Verify:
    - Same webhook delivered twice.
    - Second delivery returns 200 OK.
    - Second delivery detects existing registration and skips duplicate row in sheet.
    - Sheet continues to have exactly 1 row.
    """
    sheets_mock = get_mock_sheets_client()
    order_payload = {
        "id": 700101,
        "financial_status": "paid",
        "created_at": "2026-10-14T10:00:00Z",
        "line_items": [
            {
                "id": 88001,
                "title": "Robotics Explorer Workshop Ticket",
                "properties": [
                    {"name": "Child Name", "value": "Aarav Sharma"},
                    {"name": "Child Age", "value": "10"}
                ]
            }
        ]
    }
    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)
    headers = {"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": "orders/paid"}

    # Delivery 1
    resp1 = client.post("/api/webhooks/orders/paid", content=raw_body, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["registrations_synced"] == 1
    assert len(sheets_mock.get_all_rows()) == 1

    # Delivery 2 (Duplicate)
    resp2 = client.post("/api/webhooks/orders/paid", content=raw_body, headers=headers)
    assert resp2.status_code == 200
    res2_data = resp2.json()
    assert res2_data["duplicates_skipped"] == 1
    assert res2_data["registrations_synced"] == 0

    # Ensure sheet still has exactly 1 row
    assert len(sheets_mock.get_all_rows()) == 1


def test_3_multiple_workshop_registrations():
    """
    Scenario 3: Multiple workshop registrations in a single order.
    Verify:
    - Order contains 2 workshop line items (e.g. 2 different children/workshops).
    - Both line items are parsed into distinct registrations.
    - Each receives a unique deterministic registration ID.
    - Google Sheet receives 2 distinct rows.
    """
    sheets_mock = get_mock_sheets_client()
    order_payload = {
        "id": 700102,
        "financial_status": "paid",
        "created_at": "2026-10-14T10:30:00Z",
        "email": "anand.verma@example.com",
        "customer": {
            "first_name": "Anand",
            "last_name": "Verma",
            "email": "anand.verma@example.com",
            "phone": "+91 91234 56789"
        },
        "line_items": [
            {
                "id": 88002,
                "title": "AI & Machine Learning for Kids",
                "properties": [
                    {"name": "Parent Name", "value": "Anand Verma"},
                    {"name": "Parent Phone", "value": "+91 91234 56789"},
                    {"name": "Parent Email", "value": "anand.verma@example.com"},
                    {"name": "Area", "value": "Whitefield, Bangalore"},
                    {"name": "Child Name", "value": "Rohan Verma"},
                    {"name": "Child Age", "value": "12"}
                ]
            },
            {
                "id": 88003,
                "title": "Space Science & Rocketry Workshop",
                "properties": [
                    {"name": "Parent Name", "value": "Anand Verma"},
                    {"name": "Parent Phone", "value": "+91 91234 56789"},
                    {"name": "Parent Email", "value": "anand.verma@example.com"},
                    {"name": "Area", "value": "Whitefield, Bangalore"},
                    {"name": "Child Name", "value": "Ananya Verma"},
                    {"name": "Child Age", "value": "9"}
                ]
            }
        ]
    }

    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)

    resp = client.post(
        "/api/webhooks/orders/paid",
        content=raw_body,
        headers={"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": "orders/paid"}
    )
    assert resp.status_code == 200
    assert resp.json()["registrations_synced"] == 2

    # Verify both rows in Google Sheet
    rows = sheets_mock.get_all_rows()
    assert len(rows) == 2

    assert rows[0][0] == "REG-700102-88002"
    assert rows[0][2] == "AI & Machine Learning for Kids"
    assert rows[0][7] == "Rohan Verma"
    assert rows[0][8] == "12"

    assert rows[1][0] == "REG-700102-88003"
    assert rows[1][2] == "Space Science & Rocketry Workshop"
    assert rows[1][7] == "Ananya Verma"
    assert rows[1][8] == "9"


def test_4_missing_student_information():
    """
    Scenario 4: Missing student information.
    Verify:
    - Workshop order without child name/age or area does not crash.
    - Gracefully defaults missing fields to 'N/A'.
    - Still synchronizes cleanly to Google Sheets.
    """
    sheets_mock = get_mock_sheets_client()
    order_payload = {
        "id": 700103,
        "financial_status": "paid",
        "created_at": "2026-10-14T11:00:00Z",
        "customer": {
            "first_name": "Suresh",
            "last_name": "Patel",
            "email": "suresh.patel@example.com",
            "phone": "+91 98888 77777"
        },
        "line_items": [
            {
                "id": 88004,
                "title": "Creative Coding Workshop Ticket",
                # No properties provided!
                "properties": []
            }
        ]
    }

    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)

    resp = client.post(
        "/api/webhooks/orders/paid",
        content=raw_body,
        headers={"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": "orders/paid"}
    )
    assert resp.status_code == 200
    assert resp.json()["registrations_synced"] == 1

    rows = sheets_mock.get_all_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row[3] == "Suresh Patel"             # Parent Name from customer
    assert row[4] == "+91 98888 77777"          # Parent Phone from customer
    assert row[5] == "suresh.patel@example.com" # Parent Email from customer
    assert row[6] == "N/A"                      # Area defaults to N/A
    assert row[7] == "N/A"                      # Child Name defaults to N/A
    assert row[8] == "N/A"                      # Child Age defaults to N/A
    assert row[11] == "Synced"


def test_5_non_workshop_order():
    """
    Scenario 5: Non-workshop order (unrelated product).
    Verify:
    - Order containing physical kits (e.g., Arduino Robotics Kit) without workshop details is ignored.
    - No student registration records are created.
    - No rows are appended to Google Sheets.
    """
    sheets_mock = get_mock_sheets_client()
    order_payload = {
        "id": 700104,
        "financial_status": "paid",
        "created_at": "2026-10-14T11:15:00Z",
        "line_items": [
            {
                "id": 99001,
                "title": "Arduino Robotics Starter Hardware Kit",
                "product_type": "Hardware Kit",
                "properties": []
            }
        ]
    }

    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)

    resp = client.post(
        "/api/webhooks/orders/paid",
        content=raw_body,
        headers={"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": "orders/paid"}
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "ignored"
    assert res_data["registrations_synced"] == 0

    # Assert Google Sheet was NOT modified
    assert len(sheets_mock.get_all_rows()) == 0
    # Assert no student registration in SQLite
    assert len(get_all_student_registrations()) == 0


def test_6_invalid_webhook_signature():
    """
    Scenario 6: Invalid webhook signature.
    Verify:
    - Request with forged or invalid HMAC signature is rejected with 401 Unauthorized.
    - No processing or synchronization occurs.
    """
    order_payload = {
        "id": 700105,
        "financial_status": "paid",
        "line_items": [
            {
                "id": 88005,
                "title": "Robotics Workshop",
                "properties": [{"name": "Child Name", "value": "Aarav"}]
            }
        ]
    }
    raw_body = json.dumps(order_payload).encode("utf-8")
    invalid_signature = "bad_signature_hash_12345"

    resp = client.post(
        "/api/webhooks/orders/paid",
        content=raw_body,
        headers={
            "X-Shopify-Hmac-Sha256": invalid_signature,
            "X-Shopify-Topic": "orders/paid"
        }
    )
    assert resp.status_code == 401
    assert "Invalid webhook signature" in resp.json()["detail"] or "Unauthorized" in resp.json()["detail"]

    # Ensure no rows added to Google Sheets
    sheets_mock = get_mock_sheets_client()
    assert len(sheets_mock.get_all_rows()) == 0


def test_7_google_sheets_api_failure():
    """
    Scenario 7: Google Sheets API failure.
    Verify:
    - Simulated Google Sheets API outage (503 Service Unavailable).
    - Webhook gracefully handles failure and does not crash unhandled.
    - Event is persisted in SQLite with sync_status = 'Failed'.
    - Error message and retry count are recorded.
    """
    sheets_mock = get_mock_sheets_client()
    # Enable simulated failure
    sheets_mock.simulate_failure(True, error_message="Google Sheets API 503 Service Unavailable")

    order_payload = {
        "id": 700106,
        "financial_status": "paid",
        "created_at": "2026-10-14T11:30:00Z",
        "line_items": [
            {
                "id": 88006,
                "title": "Space Workshop Ticket",
                "properties": [
                    {"name": "Child Name", "value": "Tara Singh"},
                    {"name": "Parent Name", "value": "Vikram Singh"}
                ]
            }
        ]
    }

    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)

    resp = client.post(
        "/api/webhooks/orders/paid",
        content=raw_body,
        headers={"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": "orders/paid"}
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["failures"] == 1
    assert res_data["registrations_synced"] == 0

    # Verify registration is persisted in SQLite as Failed
    reg = get_student_registration("REG-700106-88006")
    assert reg is not None
    assert reg["sync_status"] == "Failed"
    assert "503" in (reg["error_message"] or "")
    assert reg["retry_count"] >= 1


def test_8_retry_after_failure():
    """
    Scenario 8: Retry after failure.
    Verify:
    - After resolving the API failure, running retry_failed_student_registrations():
    - Successfully re-syncs the previously failed registration.
    - Updates SQLite status to 'Synced'.
    - Appends row into Google Sheets.
    """
    sheets_mock = get_mock_sheets_client()
    # 1. Trigger failure first
    sheets_mock.simulate_failure(True, error_message="Google Sheets API 503 Service Unavailable")

    order_payload = {
        "id": 700107,
        "financial_status": "paid",
        "created_at": "2026-10-14T11:45:00Z",
        "line_items": [
            {
                "id": 88007,
                "title": "Micro:bit Space Explorer Workshop",
                "properties": [
                    {"name": "Child Name", "value": "Meera Joshi"},
                    {"name": "Child Age", "value": "11"},
                    {"name": "Parent Name", "value": "Rajesh Joshi"},
                    {"name": "Area", "value": "Koramangala"}
                ]
            }
        ]
    }
    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)

    client.post(
        "/api/webhooks/orders/paid",
        content=raw_body,
        headers={"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": "orders/paid"}
    )

    reg_before = get_student_registration("REG-700107-88007")
    assert reg_before["sync_status"] == "Failed"
    assert len(sheets_mock.get_all_rows()) == 0

    # 2. Restore Google Sheets connectivity
    sheets_mock.simulate_failure(False)

    # 3. Trigger retry
    retry_result = retry_failed_student_registrations(sheets_client=sheets_mock)
    assert retry_result["successful"] >= 1
    assert retry_result["still_failed"] == 0

    # 4. Verify SQLite updated to Synced
    reg_after = get_student_registration("REG-700107-88007")
    assert reg_after["sync_status"] == "Synced"
    assert reg_after["error_message"] is None

    # 5. Verify row in Google Sheets
    rows = sheets_mock.get_all_rows()
    assert len(rows) == 1
    assert rows[0][0] == "REG-700107-88007"
    assert rows[0][7] == "Meera Joshi"
    assert rows[0][11] == "Synced"


def test_sheet_column_order_compliance():
    """Verify SHEET_COLUMNS matches the exact 12 columns mandated by requirements."""
    expected_columns = [
        "Registration ID",
        "Shopify Order ID",
        "Workshop Name",
        "Parent Name",
        "Parent Phone",
        "Parent Email",
        "Area",
        "Child Name",
        "Child Age",
        "Payment Status",
        "Registration Date",
        "Sync Status"
    ]
    assert SHEET_COLUMNS == expected_columns


def test_9_unpaid_order_not_synced_until_paid():
    """
    Check 1: Verify orders/create does not synchronize unpaid registrations as paid.
    - An order with financial_status='pending' is saved locally as 'Awaiting_Payment'.
    - Zero rows are added to Google Sheets.
    - When orders/paid arrives later with financial_status='paid', it synchronizes to Google Sheets.
    """
    sheets_mock = reset_test_environment()
    order_payload = {
        "id": 700109,
        "financial_status": "pending",  # Unpaid!
        "created_at": "2026-10-14T12:00:00Z",
        "customer": {"first_name": "Deepak", "last_name": "Rao", "email": "deepak@example.com"},
        "line_items": [
            {
                "id": 88009,
                "title": "Robotics Ticket",
                "properties": [
                    {"name": "Child Name", "value": "Aditi Rao"},
                    {"name": "Child Age", "value": "8"}
                ]
            }
        ]
    }
    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)

    # 1. Simulate orders/create webhook for unpaid order
    resp1 = client.post(
        "/api/webhooks/orders/create",
        content=raw_body,
        headers={"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": "orders/create"}
    )
    assert resp1.status_code == 200

    # Assert Google Sheet was NOT written to
    assert len(sheets_mock.get_all_rows()) == 0

    # Assert database recorded status as Awaiting_Payment
    reg = get_student_registration("REG-700109-88009")
    assert reg is not None
    assert reg["payment_status"] == "pending"
    assert reg["sync_status"] == "Awaiting_Payment"

    # 2. Now simulate orders/paid webhook once payment is completed
    order_payload["financial_status"] = "paid"
    raw_paid_body = json.dumps(order_payload).encode("utf-8")
    paid_sig = compute_hmac(raw_paid_body)

    resp2 = client.post(
        "/api/webhooks/orders/paid",
        content=raw_paid_body,
        headers={"X-Shopify-Hmac-Sha256": paid_sig, "X-Shopify-Topic": "orders/paid"}
    )
    assert resp2.status_code == 200
    assert resp2.json()["registrations_synced"] == 1

    # Now verify Google Sheet received the row
    rows = sheets_mock.get_all_rows()
    assert len(rows) == 1
    assert rows[0][0] == "REG-700109-88009"
    assert rows[0][9] == "paid"
    assert rows[0][11] == "Synced"


def test_10_concurrent_webhook_deliveries_idempotency():
    """
    Check 6: Check whether concurrent webhook deliveries can create duplicate registrations.
    Simulate 5 parallel threads delivering the same webhook payload concurrently.
    Verify that exactly 1 row is created in Google Sheets and no duplicates occur.
    """
    import concurrent.futures

    sheets_mock = reset_test_environment()
    order_payload = {
        "id": 700110,
        "financial_status": "paid",
        "created_at": "2026-10-14T12:05:00Z",
        "line_items": [
            {
                "id": 88010,
                "title": "Space Explorer Workshop Ticket",
                "properties": [
                    {"name": "Child Name", "value": "Dhruv Nair"},
                    {"name": "Child Age", "value": "11"}
                ]
            }
        ]
    }
    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)
    headers = {"X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": "orders/paid"}

    def send_webhook():
        return client.post("/api/webhooks/orders/paid", content=raw_body, headers=headers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_webhook) for _ in range(5)]
        responses = [f.result() for f in futures]

    # Verify all responses succeeded (200 OK)
    for resp in responses:
        assert resp.status_code == 200

    # Ensure Google Sheet contains exactly ONE row (no race condition duplicates)
    rows = sheets_mock.get_all_rows()
    assert len(rows) == 1
    assert rows[0][0] == "REG-700110-88010"


def test_11_webhook_event_pii_scrubbed():
    """
    Check 8: Check that webhook_events does not retain sensitive customer/child PII indefinitely.
    Verify that raw payload is sanitized after processing.
    """
    reset_test_environment()
    order_payload = {
        "id": 700111,
        "financial_status": "paid",
        "email": "sensitive_parent@example.com",
        "customer": {"first_name": "Confidential", "last_name": "Parent", "email": "sensitive@example.com", "phone": "9999999999"},
        "line_items": [
            {
                "id": 88011,
                "title": "AI Workshop",
                "properties": [
                    {"name": "Child Name", "value": "Confidential Child"},
                    {"name": "Area", "value": "Private Villa #123"}
                ]
            }
        ]
    }
    raw_body = json.dumps(order_payload).encode("utf-8")
    sig = compute_hmac(raw_body)

    resp = client.post(
        "/api/webhooks/orders/paid",
        content=raw_body,
        headers={
            "X-Shopify-Hmac-Sha256": sig,
            "X-Shopify-Topic": "orders/paid",
            "X-Shopify-Webhook-Id": "evt-privacy-test-700111"
        }
    )
    assert resp.status_code == 200

    # Verify raw_payload in SQLite has been scrubbed
    evt = get_webhook_event("evt-privacy-test-700111")
    assert evt is not None
    stored_payload = json.loads(evt["raw_payload"])
    assert stored_payload.get("_sanitized") is True
    assert stored_payload.get("email") == "[SCRUBBED]"
    # Ensure sensitive names are no longer stored in raw_payload
    assert "Confidential Child" not in evt["raw_payload"]
    assert "sensitive@example.com" not in evt["raw_payload"]


def test_12_retry_endpoint_security(monkeypatch):
    """
    Check 9: Ensure the retry endpoint is protected by appropriate authentication and authorization.
    """
    reset_test_environment()
    monkeypatch.setenv("ALLOW_AUTH_FALLBACK", "False")

    # 1. Unauthenticated request -> 401
    resp_unauth = client.post("/api/registrations/sync/retry")
    assert resp_unauth.status_code == 401

    # 2. Non-admin role (CATALOGUE_ADMIN) -> 403 Forbidden
    resp_forbidden = client.post(
        "/api/registrations/sync/retry",
        headers={"Authorization": "Bearer mock-catalogue-token"}
    )
    assert resp_forbidden.status_code == 403

    # 3. Platform Admin -> 200 OK
    resp_admin = client.post(
        "/api/registrations/sync/retry",
        headers={"Authorization": "Bearer mock-admin-token"}
    )
    assert resp_admin.status_code == 200


def test_13_production_mode_rejects_mock_sheets(monkeypatch=None):
    """
    Check 11: Verify production cannot silently use mock mode.
    """
    from services.google_sheets_service import get_sheets_client, GoogleSheetsError

    orig_env = settings.app_env
    orig_mock = settings.mock_google_sheets
    try:
        settings.app_env = "production"
        settings.mock_google_sheets = True

        with pytest.raises(GoogleSheetsError) as exc_info:
            get_sheets_client()

        assert "forbidden in production" in str(exc_info.value)
    finally:
        settings.app_env = orig_env
        settings.mock_google_sheets = orig_mock

