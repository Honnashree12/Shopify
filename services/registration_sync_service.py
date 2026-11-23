"""
Student Registration Synchronization Module.

Processes Shopify orders/paid and orders/create webhooks, verifies HMAC signatures,
extracts workshop line items and student/parent details, persists raw events for reliability,
and synchronizes registrations idempotently to Google Sheets.
"""

import os
import hmac
import hashlib
import base64
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from config import settings
from data.database import (
    get_workshop_by_shopify_id,
    save_webhook_event,
    update_webhook_event,
    scrub_webhook_event_payload,
    save_student_registration,
    get_student_registration,
    update_student_registration_sync,
    get_failed_student_registrations
)
from services.google_sheets_service import (
    SHEET_COLUMNS,
    get_sheets_client,
    sync_registration_to_sheets_with_retry
)

logger = logging.getLogger(__name__)

# Thread-safe lock to prevent race conditions during concurrent webhook deliveries
_sync_lock = threading.Lock()


class StudentRegistrationRecord(BaseModel):
    """Normalized student registration data representing a workshop attendee."""
    registration_id: str
    shopify_order_id: str
    workshop_name: str
    parent_name: str = "N/A"
    parent_phone: str = "N/A"
    parent_email: str = "N/A"
    area: str = "N/A"
    child_name: str = "N/A"
    child_age: str = "N/A"
    payment_status: str = "paid"
    registration_date: str
    sync_status: str = "Pending"
    raw_properties: Dict[str, Any] = Field(default_factory=dict)

    def to_sheet_row(self) -> List[Any]:
        """Convert to the exact 12 columns required by Google Sheets."""
        return [
            self.registration_id,
            self.shopify_order_id,
            self.workshop_name,
            self.parent_name,
            self.parent_phone,
            self.parent_email,
            self.area,
            self.child_name,
            self.child_age,
            self.payment_status,
            self.registration_date,
            self.sync_status
        ]


def verify_shopify_hmac(raw_body: bytes, hmac_header: Optional[str], secret: Optional[str]) -> bool:
    """
    Verify the Shopify HMAC-SHA256 signature against the raw request body.
    Returns True if valid, False otherwise.
    """
    if not secret:
        # In testing/dev environments without a secret configured, allow if no header is enforced
        if not hmac_header:
            return True
        logger.warning("HMAC header provided but SHOPIFY_API_SECRET is not configured.")
        return False

    if not hmac_header:
        logger.warning("Missing X-Shopify-Hmac-Sha256 header.")
        return False

    try:
        digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        computed_hmac = base64.b64encode(digest).decode("utf-8")
        is_valid = hmac.compare_digest(computed_hmac, hmac_header.strip())
        if not is_valid:
            logger.warning("HMAC signature verification failed.")
        return is_valid
    except Exception as e:
        logger.error("Error during HMAC computation: %s", e)
        return False


def _normalize_dict_keys(raw: Any) -> Dict[str, str]:
    """Normalize properties or attributes into lowercase-stripped key-value dict."""
    normalized: Dict[str, str] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                k = str(item.get("name", "")).strip().lower()
                v = str(item.get("value", "")).strip()
                if k:
                    normalized[k] = v
    elif isinstance(raw, dict):
        for k, v in raw.items():
            if k is not None:
                normalized[str(k).strip().lower()] = str(v).strip()
    return normalized


def _get_first_matching(dict_obj: Dict[str, str], aliases: List[str]) -> Optional[str]:
    """Retrieve first value matching any alias."""
    for alias in aliases:
        if alias in dict_obj and dict_obj[alias]:
            return dict_obj[alias]
    return None


def is_workshop_line_item(item: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """
    Determine if a line item is a workshop registration vs unrelated product.
    Checks:
    1. Product ID mapped in local workshops database.
    2. Registration properties present on the item (Child Name, Child Age, Area, etc.).
    3. Product name/title contains 'workshop'.
    """
    product_id = item.get("product_id")
    if product_id:
        try:
            db_workshop = get_workshop_by_shopify_id(int(product_id))
            if db_workshop:
                return True
        except Exception:
            pass

    # Check item properties
    props = _normalize_dict_keys(item.get("properties", []))
    workshop_keys = [
        "child name", "child_name", "student name", "student_name", "child",
        "child age", "child_age", "student age", "student_age", "age",
        "area", "parent name", "parent_name"
    ]
    if any(k in props for k in workshop_keys):
        return True

    # Check title / product type
    title = str(item.get("title") or item.get("name") or "").lower()
    product_type = str(item.get("product_type", "")).lower()
    if "workshop" in title or "workshop" in product_type:
        return True

    # Check cart note attributes if only 1 item in order
    line_items = payload.get("line_items", [])
    if len(line_items) == 1:
        note_attrs = _normalize_dict_keys(payload.get("note_attributes", []))
        if any(k in note_attrs for k in workshop_keys):
            return True

    return False


def extract_student_registration(
    item: Dict[str, Any],
    payload: Dict[str, Any],
    item_index: int
) -> StudentRegistrationRecord:
    """
    Extract normalized student registration record from order payload and line item.
    Safe extraction: missing fields fall back to 'N/A' gracefully.
    """
    order_id = str(payload.get("id") or payload.get("order_number") or payload.get("name") or "UNKNOWN_ORDER")
    item_id = str(item.get("id") or f"L{item_index}")

    # Combine line item properties with order note attributes as fallback
    item_props = _normalize_dict_keys(item.get("properties", []))
    order_notes = _normalize_dict_keys(payload.get("note_attributes", []))
    customer = payload.get("customer", {})
    if not isinstance(customer, dict):
        customer = {}
    billing = payload.get("billing_address", {})
    if not isinstance(billing, dict):
        billing = {}
    shipping = payload.get("shipping_address", {})
    if not isinstance(shipping, dict):
        shipping = {}

    # 1. Registration ID (stable deterministic ID)
    explicit_id = _get_first_matching(item_props, ["registration_id", "registrationid", "reg_id"])
    if not explicit_id and len(payload.get("line_items", [])) == 1:
        explicit_id = _get_first_matching(order_notes, ["registration_id", "registrationid", "reg_id"])

    registration_id = explicit_id or f"REG-{order_id}-{item_id}"

    # 2. Workshop Name
    workshop_name = item.get("title") or item.get("name")
    if not workshop_name and item.get("product_id"):
        try:
            ws = get_workshop_by_shopify_id(int(item["product_id"]))
            if ws:
                workshop_name = ws.get("name")
        except Exception:
            pass
    if not workshop_name:
        workshop_name = "KiddyPi Workshop"

    # 3. Child Name
    child_name = (
        _get_first_matching(item_props, ["child name", "child_name", "student name", "student_name", "child", "student", "kid name"])
        or _get_first_matching(order_notes, ["child name", "child_name", "student name", "student_name", "child", "student"])
        or "N/A"
    )

    # 4. Child Age
    child_age = (
        _get_first_matching(item_props, ["child age", "child_age", "student age", "student_age", "age", "kid age"])
        or _get_first_matching(order_notes, ["child age", "child_age", "student age", "student_age", "age"])
        or "N/A"
    )

    # 5. Parent Name
    cust_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    parent_name = (
        _get_first_matching(item_props, ["parent name", "parent_name", "parent's name", "parent", "guardian name", "guardian"])
        or _get_first_matching(order_notes, ["parent name", "parent_name", "parent's name", "parent"])
        or cust_name
        or billing.get("name")
        or shipping.get("name")
        or "N/A"
    )

    # 6. Parent Phone
    parent_phone = (
        _get_first_matching(item_props, ["parent phone", "parent_phone", "phone", "phone number", "mobile", "parent mobile", "contact"])
        or _get_first_matching(order_notes, ["parent phone", "parent_phone", "phone", "mobile"])
        or customer.get("phone")
        or payload.get("phone")
        or billing.get("phone")
        or shipping.get("phone")
        or "N/A"
    )

    # 7. Parent Email
    parent_email = (
        _get_first_matching(item_props, ["parent email", "parent_email", "email", "email address", "parent's email"])
        or _get_first_matching(order_notes, ["parent email", "parent_email", "email"])
        or customer.get("email")
        or payload.get("email")
        or payload.get("contact_email")
        or "N/A"
    )

    # 8. Area
    area = (
        _get_first_matching(item_props, ["area", "location", "locality", "city", "neighborhood", "region", "address"])
        or _get_first_matching(order_notes, ["area", "location", "locality", "city"])
        or shipping.get("city")
        or billing.get("city")
        or shipping.get("province")
        or "N/A"
    )

    # 9. Payment Status (Default to pending if not present; NEVER assume paid)
    raw_status = payload.get("financial_status")
    payment_status = str(raw_status).lower().strip() if raw_status else "pending"

    # 10. Registration Date
    raw_date = payload.get("created_at") or payload.get("processed_at")
    if raw_date:
        reg_date = str(raw_date)
    else:
        reg_date = datetime.now(timezone.utc).isoformat()

    return StudentRegistrationRecord(
        registration_id=registration_id,
        shopify_order_id=order_id,
        workshop_name=workshop_name,
        parent_name=parent_name,
        parent_phone=parent_phone,
        parent_email=parent_email,
        area=area,
        child_name=child_name,
        child_age=str(child_age),
        payment_status=payment_status,
        registration_date=reg_date,
        sync_status="Pending",
        raw_properties=item_props
    )


def process_order_webhook_sync(
    raw_body: bytes,
    headers: Dict[str, Any],
    sheets_client=None
) -> Dict[str, Any]:
    """
    Main pipeline to process incoming Shopify order webhooks (orders/paid or orders/create):
    1. Verifies HMAC.
    2. Persists raw webhook event in SQLite before processing (reliability / no data loss).
    3. Filters workshop items vs unrelated products.
    4. Extracts student registration records safely.
    5. Checks for duplicate deliveries (idempotency).
    6. Synchronizes to Google Sheets with exponential backoff retry.
    7. Updates SQLite records and event status.
    8. Returns result dictionary.
    """
    # 1. HMAC Verification
    hmac_header = headers.get("X-Shopify-Hmac-Sha256") or headers.get("x-shopify-hmac-sha256")
    secret = settings.shopify_api_secret or settings.shopify_client_secret or os.getenv("SHOPIFY_API_SECRET")

    if not verify_shopify_hmac(raw_body, hmac_header, secret):
        logger.warning("[WEBHOOK SECURITY] Rejected webhook request due to invalid HMAC signature.")
        return {
            "status": "unauthorized",
            "error": "Invalid webhook signature",
            "status_code": 401
        }

    # Parse JSON
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error("[WEBHOOK ERROR] Failed to parse JSON payload: %s", e)
        return {
            "status": "invalid_payload",
            "error": "Invalid JSON payload",
            "status_code": 400
        }

    order_id = str(payload.get("id") or payload.get("order_number") or "unknown")
    topic = str(headers.get("X-Shopify-Topic") or headers.get("x-shopify-topic") or "orders/paid")
    webhook_id = str(headers.get("X-Shopify-Webhook-Id") or headers.get("x-shopify-webhook-id") or f"EVT-{order_id}-{int(datetime.now(timezone.utc).timestamp()*1000)}")

    # 2. Persist raw webhook event before acknowledging
    save_webhook_event(
        event_id=webhook_id,
        topic=topic,
        order_id=order_id,
        raw_payload=raw_body.decode("utf-8", errors="replace"),
        status="received",
        sync_status="pending"
    )
    logger.info("[WEBHOOK PERSISTED] Event ID %s persisted for Order ID %s (topic: %s)", webhook_id, order_id, topic)

    line_items = payload.get("line_items", [])
    if not line_items:
        update_webhook_event(webhook_id, status="ignored", sync_status="ignored", error_message="No line items")
        return {
            "status": "ignored",
            "message": "No line items in order",
            "registrations_synced": 0,
            "status_code": 200
        }

    # 3. Filter workshop line items vs unrelated products
    workshop_items = []
    for idx, item in enumerate(line_items):
        if is_workshop_line_item(item, payload):
            workshop_items.append((idx + 1, item))
        else:
            logger.info(
                "[WEBHOOK FILTER] Ignoring non-workshop product in Order ID %s (Item: %s)",
                order_id, item.get("title") or item.get("name") or "Unknown"
            )

    if not workshop_items:
        update_webhook_event(webhook_id, status="ignored", sync_status="ignored", error_message="No workshop items")
        logger.info("[WEBHOOK FILTER] Order ID %s has no workshop items. Webhook ignored.", order_id)
        return {
            "status": "ignored",
            "message": "Order does not contain workshop registrations",
            "registrations_synced": 0,
            "status_code": 200
        }

    # 4. Extract student registrations
    registrations: List[StudentRegistrationRecord] = []
    for idx, item in workshop_items:
        reg = extract_student_registration(item, payload, item_index=idx)
        registrations.append(reg)

    if sheets_client is None:
        sheets_client = get_sheets_client()

    synced_count = 0
    duplicate_count = 0
    failure_count = 0
    results_summary = []

    for reg in registrations:
        with _sync_lock:
            # 1. Verify Payment Status: Only paid orders synchronize to Google Sheets
            if reg.payment_status != "paid":
                logger.info(
                    "[PAYMENT STATUS] Registration ID %s has financial_status='%s' (unpaid). "
                    "Saved locally with status 'Awaiting_Payment'; skipping Google Sheets until paid.",
                    reg.registration_id, reg.payment_status
                )
                reg_dict = reg.model_dump()
                reg_dict["sync_status"] = "Awaiting_Payment"
                save_student_registration(reg_dict)
                results_summary.append({
                    "registration_id": reg.registration_id,
                    "status": "awaiting_payment",
                    "payment_status": reg.payment_status
                })
                continue

            # 2. Check Idempotency: Has this registration ID already been synced?
            existing_reg = get_student_registration(reg.registration_id)
            if existing_reg and existing_reg.get("sync_status") == "Synced":
                logger.info(
                    "[IDEMPOTENCY] Registration ID %s already synced in DB. Skipping duplicate Google Sheets append.",
                    reg.registration_id
                )
                duplicate_count += 1
                results_summary.append({
                    "registration_id": reg.registration_id,
                    "status": "duplicate_already_synced"
                })
                continue

            # 3. Save to SQLite with Pending status
            reg_dict = reg.model_dump()
            save_student_registration(reg_dict)
            logger.info(
                "[REGISTRATION SAVED] Saved registration ID %s for workshop '%s' to database",
                reg.registration_id, reg.workshop_name
            )

            # 4. Sync to Google Sheets with retry
            row_values = reg.to_sheet_row()
            row_values[11] = "Synced"

            success, err_msg = sync_registration_to_sheets_with_retry(
                row_values=row_values,
                max_retries=3,
                base_delay_seconds=0.2,
                client=sheets_client
            )

            if success:
                synced_count += 1
                update_student_registration_sync(reg.registration_id, sync_status="Synced")
                results_summary.append({
                    "registration_id": reg.registration_id,
                    "status": "synced"
                })
                logger.info("[SHEETS SYNC] Successfully synced registration ID %s to Google Sheets", reg.registration_id)
            else:
                failure_count += 1
                update_student_registration_sync(
                    reg.registration_id,
                    sync_status="Failed",
                    error_message=err_msg,
                    increment_retry=True
                )
                results_summary.append({
                    "registration_id": reg.registration_id,
                    "status": "failed",
                    "error": err_msg
                })
                logger.error("[SHEETS SYNC ERROR] Failed to sync registration ID %s: %s", reg.registration_id, err_msg)

    # Update webhook event status
    final_sync_status = "synced" if failure_count == 0 else ("partial" if synced_count > 0 else "failed")
    update_webhook_event(
        webhook_id,
        status="processed",
        sync_status=final_sync_status,
        error_message=f"Synced: {synced_count}, Duplicates: {duplicate_count}, Failures: {failure_count}"
    )

    # Scrub customer/child PII from raw_payload to ensure GDPR/DPDP privacy compliance
    try:
        scrub_webhook_event_payload(webhook_id)
    except Exception as e:
        logger.warning("Could not scrub webhook payload for event %s: %s", webhook_id, e)

    return {
        "status": "processed" if failure_count == 0 else "completed_with_errors",
        "order_id": order_id,
        "registrations_synced": synced_count,
        "duplicates_skipped": duplicate_count,
        "failures": failure_count,
        "details": results_summary,
        "status_code": 200
    }


def retry_failed_student_registrations(sheets_client=None) -> Dict[str, Any]:
    """
    Query database for all registrations with sync_status in ('Failed', 'Pending')
    and attempt to synchronize them to Google Sheets.
    """
    failed_regs = get_failed_student_registrations()
    if not failed_regs:
        return {"status": "none_pending", "retried": 0, "successful": 0}

    if sheets_client is None:
        sheets_client = get_sheets_client()

    success_count = 0
    still_failed = 0

    with _sync_lock:
        for reg_data in failed_regs:
            reg_id = reg_data["registration_id"]
            row_values = [
                reg_data.get("registration_id"),
                reg_data.get("shopify_order_id"),
                reg_data.get("workshop_name"),
                reg_data.get("parent_name"),
                reg_data.get("parent_phone"),
                reg_data.get("parent_email"),
                reg_data.get("area"),
                reg_data.get("child_name"),
                reg_data.get("child_age"),
                reg_data.get("payment_status"),
                reg_data.get("registration_date"),
                "Synced"
            ]

            success, err_msg = sync_registration_to_sheets_with_retry(
                row_values=row_values,
                max_retries=3,
                base_delay_seconds=0.2,
                client=sheets_client
            )

            if success:
                update_student_registration_sync(reg_id, sync_status="Synced", error_message=None)
                success_count += 1
                logger.info("[RETRY SUCCESS] Registration ID %s synced to Google Sheets on retry", reg_id)
            else:
                update_student_registration_sync(reg_id, sync_status="Failed", error_message=err_msg, increment_retry=True)
                still_failed += 1
                logger.error("[RETRY FAILED] Registration ID %s still failed: %s", reg_id, err_msg)

    return {
        "status": "retry_completed",
        "retried": len(failed_regs),
        "successful": success_count,
        "still_failed": still_failed
    }
