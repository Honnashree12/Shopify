"""
Standalone Runner for Shopify to Google Sheets Student Registration Automation Tests.

Runs all 8 mandatory integration test scenarios with synthetic data and displays
a formatted report including the exact 12 Google Sheets column structure.
"""

import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
os.environ["TESTING"] = "True"
os.environ["ALLOW_AUTH_FALLBACK"] = "True"

from tests.test_student_registration_sync import (
    test_1_valid_paid_workshop_registration,
    test_2_duplicate_webhook_delivery,
    test_3_multiple_workshop_registrations,
    test_4_missing_student_information,
    test_5_non_workshop_order,
    test_6_invalid_webhook_signature,
    test_7_google_sheets_api_failure,
    test_8_retry_after_failure,
    test_sheet_column_order_compliance,
    test_9_unpaid_order_not_synced_until_paid,
    test_10_concurrent_webhook_deliveries_idempotency,
    test_11_webhook_event_pii_scrubbed,
    test_12_retry_endpoint_security,
    test_13_production_mode_rejects_mock_sheets
)
from services.google_sheets_service import SHEET_COLUMNS, get_mock_sheets_client
from data.database import get_all_student_registrations, init_db


def main():
    print("=" * 70)
    print("SHOPIFY -> GOOGLE SHEETS STUDENT REGISTRATION AUTOMATION TEST SUITE")
    print("=" * 70)

    class MockMonkeypatch:
        def setattr(self, obj, attr, val):
            setattr(obj, attr, val)
        def setenv(self, key, val):
            os.environ[key] = val

    mp = MockMonkeypatch()

    tests = [
        ("Column Order Compliance (12 Columns)", test_sheet_column_order_compliance),
        ("Test 1: Valid Paid Workshop Registration", test_1_valid_paid_workshop_registration),
        ("Test 2: Duplicate Webhook Delivery (Idempotency)", test_2_duplicate_webhook_delivery),
        ("Test 3: Multiple Workshop Registrations", test_3_multiple_workshop_registrations),
        ("Test 4: Missing Student Information (Graceful Defaults)", test_4_missing_student_information),
        ("Test 5: Non-Workshop Order (Unrelated Product Filter)", test_5_non_workshop_order),
        ("Test 6: Invalid Webhook HMAC Signature (Security)", test_6_invalid_webhook_signature),
        ("Test 7: Google Sheets API Failure (Persistence & Error Handling)", test_7_google_sheets_api_failure),
        ("Test 8: Retry After Failure (Recovery of Failed Registrations)", test_8_retry_after_failure),
        ("Test 9: Unpaid Orders Not Synced Until Paid", test_9_unpaid_order_not_synced_until_paid),
        ("Test 10: Concurrent Webhook Deliveries (No Duplicates)", test_10_concurrent_webhook_deliveries_idempotency),
        ("Test 11: Webhook Event Customer PII Scrubbed", test_11_webhook_event_pii_scrubbed),
        ("Test 12: Retry Endpoint Protected by RBAC & Auth", lambda: test_12_retry_endpoint_security(mp)),
        ("Test 13: Production Mode Strictly Rejects Mock Sheets", lambda: test_13_production_mode_rejects_mock_sheets(mp)),
    ]

    passed = 0
    failed = 0

    for idx, (name, test_func) in enumerate(tests, 1):
        print(f"\n[{idx}/{len(tests)}] Running: {name}...")
        try:
            from tests.test_student_registration_sync import reset_test_environment
            reset_test_environment()

            test_func()
            print(f"       Status: PASS [OK]")
            passed += 1
        except Exception as e:
            print(f"       Status: FAIL [ERROR]: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"TEST EXECUTION SUMMARY: {passed} PASSED, {failed} FAILED (Total: {len(tests)})")
    print("=" * 70)

    print("\n--- GOOGLE SHEETS MANDATORY 12-COLUMN SCHEMA ---")
    for col_idx, col in enumerate(SHEET_COLUMNS, 1):
        print(f"  Column {col_idx:2d}: {col}")

    from tests.test_student_registration_sync import reset_test_environment
    mock_client = reset_test_environment()
    test_1_valid_paid_workshop_registration()
    sample_rows = mock_client.get_all_rows()

    if sample_rows:
        print("\n--- SYNCHRONIZED SAMPLE ROW IN GOOGLE SHEETS (12 Columns) ---")
        row = sample_rows[0]
        for col_name, val in zip(SHEET_COLUMNS, row):
            print(f"  {col_name:20s} : {val}")

    if failed > 0:
        sys.exit(1)
    else:
        print("\nALL 8 STUDENT REGISTRATION AUTOMATION TESTS PASSED SUCCESSFULLY! [PASS]")


if __name__ == "__main__":
    main()
