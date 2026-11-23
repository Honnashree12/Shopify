import ssl_config  # noqa: F401 - must run before google/requests imports

import sys
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import uuid
import asyncio
import os
import logging
import json
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Any, Union

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from fastapi.responses import FileResponse, RedirectResponse
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

# pyrefly: ignore [missing-import]
from google.genai import types

from state import ProductLaunchState

from workflow.adk_runner import runner, folder_runner, validation_runner, session_service, APP_NAME
from workflow.session_manager import create_session, USER_ID
# pyrefly: ignore [missing-import]
from fastapi import UploadFile, File, Form

load_dotenv()

from config import settings, setup_logging, request_id_var, session_id_var, workflow_id_var
setup_logging(settings.log_level)
from shopify_client import verify_shopify_hmac, _clean_store_url

logger = logging.getLogger(__name__)

from services.auth_service import User, require_role, get_current_user
from workflow.progress_tracker import (
    set_stage as track_set_stage,
    get_stage as track_get_stage,
    clear_stage as track_clear_stage,
    try_acquire_publish_lock,
    release_publish_lock,
)

def validate_state_transition(current_status: str, target_status: str):
    """Enforces backend workflow state machine transitions."""
    allowed = {
        "pending": ["running", "awaiting_approval", "failed"],
        "awaiting_approval": ["running", "failed"],
        "failed": ["pending", "running", "awaiting_approval"],  # DRAFT resubmission or retry
        "running": ["completed", "failed"],
        "completed": []
    }
    if target_status not in allowed.get(current_status, []):
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: workflow cannot transition from '{current_status}' to '{target_status}'"
        )

def persist_session_state(session_id: str, state: ProductLaunchState):
    """Saves ProductLaunchState to Firestore or local mock directory."""
    from services.firebase_service import save_product
    data = state.model_dump()
    save_product(session_id, data)

app = FastAPI(
    title="AI Shopify Product Launch Agent API",
    description="Google ADK Multi-Agent Shopify Workflow",
    version="1.0.0",
)

# NOTE: The mock Shopify API router has been removed from this app.
# Publisher/Verification agents now call the real Shopify Admin API
# directly via shopify_client.py using SHOPIFY_STORE_URL /
# SHOPIFY_ACCESS_TOKEN / SHOPIFY_API_VERSION from the environment.
# The shopify_mock/ module itself is left in place (unused) and can
# still be run standalone for local testing if ever needed.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    # Wildcard origins + credentialed requests is a combination browsers
    # actually reject anyway, and would be a real security gap if they
    # didn't -- only allow credentials when we have a concrete origin
    # allowlist, never with "*".
    allow_credentials=settings.cors_origins_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_tracing_context(request: Request, call_next):
    # Tracing context generation
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id_token = request_id_var.set(req_id[:8])
    
    session_id = request.headers.get("X-Session-ID") or "-"
    path_parts = request.url.path.strip("/").split("/")
    if "status" in path_parts and len(path_parts) > path_parts.index("status") + 1:
        session_id = path_parts[path_parts.index("status") + 1]
    elif "launch" in path_parts and len(path_parts) > path_parts.index("launch") + 1:
        session_id = path_parts[path_parts.index("launch") + 1]
        
    session_id_token = session_id_var.set(session_id)
    workflow_id_token = workflow_id_var.set("-")
    
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_var.reset(request_id_token)
        session_id_var.reset(session_id_token)
        workflow_id_var.reset(workflow_id_token)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.get("/", include_in_schema=False)
@app.get("/validation", include_in_schema=False)
@app.get("/launches", include_in_schema=False)
@app.get("/launches/new", include_in_schema=False)
@app.get("/overview", include_in_schema=False)
@app.get("/approvals", include_in_schema=False)
@app.get("/agents", include_in_schema=False)
@app.get("/seo", include_in_schema=False)
@app.get("/workshops", include_in_schema=False)
@app.get("/workshops/new", include_in_schema=False)
@app.get("/activity", include_in_schema=False)
def serve_launch_console():
    """Serves the Launch Console frontend for SPA routes."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# SECURITY (Phase 5 Part 8 - IDOR / unauthenticated data exposure):
# outputs/ also contains outputs/mock_firestore/ (raw product + audit-log
# JSON documents, including customer/reviewer emails), outputs/temp_uploads/
# (in-flight, not-yet-validated product folders), and outputs/emails/ (sent
# customer/sales email copies with PII). A blanket
# `app.mount("/outputs", StaticFiles(...))` served ALL of that to anyone who
# could guess or enumerate a path, with zero authentication -- e.g.
# GET /outputs/mock_firestore/audit_logs/<id>.json. Only two subfolders are
# genuinely meant to be public: outputs/images/ (marketing images embedded
# in customer-facing workshop landing pages) and
# outputs/mock_storage/products/ (the local dev/mock substitute for public
# Firebase Storage product-media URLs -- product photos, not sensitive).
# Everything else under outputs/ is no longer served over HTTP at all.
_PUBLIC_OUTPUTS_IMAGES = os.path.join(OUTPUTS_DIR, "images")
_PUBLIC_OUTPUTS_MOCK_STORAGE = os.path.join(OUTPUTS_DIR, "mock_storage")
os.makedirs(_PUBLIC_OUTPUTS_IMAGES, exist_ok=True)
os.makedirs(_PUBLIC_OUTPUTS_MOCK_STORAGE, exist_ok=True)
app.mount("/outputs/images", StaticFiles(directory=_PUBLIC_OUTPUTS_IMAGES), name="outputs-images")
app.mount("/outputs/mock_storage", StaticFiles(directory=_PUBLIC_OUTPUTS_MOCK_STORAGE), name="outputs-mock-storage")

_DOCS_AUDITS_SCREENSHOTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "docs", "audits", "screenshots"))
if os.path.exists(_DOCS_AUDITS_SCREENSHOTS):
    app.mount("/screenshots", StaticFiles(directory=_DOCS_AUDITS_SCREENSHOTS), name="screenshots")



class ProductLaunchInput(BaseModel):
    product_name: str
    raw_description: str
    price: Optional[float] = None
    category: Optional[str] = None


class LaunchSummary(BaseModel):
    session_id: str
    product_name: str
    status: str
    failed_stage: Optional[str] = None
    preview_mode: bool
    created_at: Optional[str] = None
    source: str


class AuditLogEntry(BaseModel):
    timestamp: str
    actor: str
    role: str
    action: str
    description: str
    product_id: Optional[Union[str, int]] = None


class RegistrationInput(BaseModel):
    child_name: str
    child_age: int
    school: str
    parent_name: str
    customer_email: str
    customer_phone: str
    emergency_contact: str


active_sessions: Dict[str, ProductLaunchState] = {}

# Share active_sessions, session_service, and folder_runner across duplicate module imports under testing
import sys
if "pytest" in sys.modules or os.getenv("TESTING") == "True":
    for name, module in list(sys.modules.items()):
        if (name == "main" or name.endswith(".main")) and module is not sys.modules[__name__]:
            if hasattr(module, "active_sessions"):
                active_sessions = module.active_sessions
            if hasattr(module, "session_service"):
                session_service = module.session_service
            if hasattr(module, "folder_runner"):
                folder_runner = module.folder_runner
            break


def _workflow_completion_error(final_state: Dict) -> Optional[str]:
    """Return a user-facing error when an agent workflow stopped partway through.

    ADK can finish a run without raising an exception when an agent returns a
    normal response instead of its required tool call.  A completed runner is
    therefore not sufficient evidence that a product was published.
    """
    approved = final_state.get("approved_to_publish", False)
    
    required_values = {
        "generated_description": "copywriting",
        "seo_metadata": "SEO generation",
        "marketing": "marketing generation",
        "marketing_assets": "marketing details generation"
    }
    
    if approved:
        required_values.update({
            "shopify_product_id": "Shopify publishing",
            "shopify_url": "Shopify publishing",
            "verification_result": "Shopify verification",
            "markdown_report_path": "report generation",
            "json_report_path": "report generation",
        })
        
    missing_steps = sorted(
        {step for key, step in required_values.items() if not final_state.get(key)}
    )

    if approved:
        verification = final_state.get("verification_result")
        if verification and not verification.get("purchasable"):
            details = "; ".join(verification.get("errors") or [])
            return "Shopify verification failed" + (f": {details}" if details else ".")

    if missing_steps:
        return (
            "The launch pipeline ended before it finished: "
            + ", ".join(missing_steps)
            + "."
        )

    return None


def run_adk_workflow_background(session_id: str):
    session_id_var.set(session_id)
    workflow_id_var.set("ProductLaunchWorkflow")

    print("\n===================================")
    print("SHOPIFY PRODUCT LAUNCH STARTED")
    print("===================================")

    state = active_sessions.get(session_id)

    if state is None:
        return

    try:

        state.status = "running"

        session = asyncio.run(
            create_session(
                {
                    "product_name": state.product_name,
                    "product_description": state.raw_description,
                    "product_price": state.price,
                    "product_category": state.category,
                    "approved_to_publish": state.approved_to_publish,
                    "workshop_id": state.workshop_id,
                }
            )
        )

        print(f"ADK Session Created: {session.id}")

        print("\n===== INITIAL SESSION STATE =====")
        print(dict(session.state))
        print("=================================\n")

        prompt = """
You are launching ONE Shopify product.

The product details are already stored in the workflow state.

Use ONLY the values returned by get_product_context().

Never invent another product.

Begin the workflow.
"""

        message = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        # NOTE: Runner.run() (the sync wrapper) drives the workflow inside a
        # plain background thread and streams events back over a queue. If a
        # tool raises inside that thread, Python's default thread behavior
        # applies: the exception is printed to stderr and the thread dies,
        # but it never reaches this function's try/except — the for-loop
        # below would just silently see fewer events, and the actual error
        # (whatever it is) would never be recorded in state.errors. Driving
        # run_async() directly, in-thread, makes tool/ADK exceptions
        # propagate normally so they are caught below with a full traceback.
        async def _consume_campaign_events():
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session.id,
                new_message=message,
            ):
                print(event)

        asyncio.run(_consume_campaign_events())

        # IMPORTANT: `session` above is a snapshot captured BEFORE the
        # workflow ran. runner.run_async() updates the session inside
        # session_service's internal store, not this local object, so
        # reading session.state here would return stale/empty values.
        # Re-fetch the session to get the final, merged state.
        final_session = asyncio.run(
            session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=session.id,
            )
        )

        print(
            "[DEBUG STATE]",
            "fn=run_adk_workflow_background(final)",
            "var=final_session",
            "type=", type(final_session),
            "is_none=", final_session is None,
            "session_id=", session.id,
            "stage=", "post-run",
            "state_keys=", sorted(dict(final_session.state).keys()) if final_session is not None else None,
        )
        if final_session is None:
            raise ValueError("ADK Workflow session could not be retrieved after run execution.")

        final_state = final_session.state

        print("\n===== FINAL SESSION STATE =====")
        print(dict(final_state))
        print("===============================\n")

        state.generated_description = final_state.get(
            "generated_description"
        )

        state.seo_metadata = final_state.get(
            "seo_metadata"
        )

        state.marketing = final_state.get(
            "marketing"
        )

        state.marketing_assets = final_state.get(
            "marketing_assets"
        )

        state.shopify_product = final_state.get(
            "shopify_product"
        )

        state.shopify_product_id = final_state.get(
            "shopify_product_id"
        )

        state.shopify_url = final_state.get(
            "shopify_url"
        )

        state.shopify_variant_id = final_state.get(
            "shopify_variant_id"
        )

        state.verification_result = final_state.get(
            "verification_result"
        )

        state.image_prompts = final_state.get(
            "image_prompts"
        )

        state.image_paths = final_state.get(
            "image_paths"
        )

        state.shopify_media = final_state.get(
            "shopify_media"
        )

        state.markdown_report_path = final_state.get(
            "markdown_report_path"
        )

        state.json_report_path = final_state.get(
            "json_report_path"
        )

        state.workshop_id = final_state.get(
            "workshop_id"
        )
        state.approved_to_publish = final_state.get(
            "approved_to_publish", False
        )

        completion_error = _workflow_completion_error(final_state)

        # Save to database if this was a workshop generation
        if state.workshop_id:
            try:
                from data.database import update_workshop_ai_content, publish_workshop
                
                db_status = "draft"
                if completion_error:
                    db_status = "failed"
                    
                updates = {
                    "generated_description": state.generated_description,
                    "seo_metadata": state.seo_metadata,
                    "marketing": state.marketing_assets or state.marketing,
                    "image_prompts": state.image_prompts,
                    "image_paths": state.image_paths,
                    "status": db_status
                }
                update_workshop_ai_content(state.workshop_id, updates)
                logger.info("Successfully updated workshop DB status to '%s' for ID %s", db_status, state.workshop_id)
            except Exception as e:
                logger.exception("Failed to update workshop database status (non-fatal)")

        if completion_error:
            logger.error("Launch workflow %s was incomplete: %s", session_id, completion_error)
            state.status = "failed"
            state.errors["workflow_error"] = completion_error
            return

        state.status = "completed"
        persist_session_state(session_id, state)
        
        log_id = f"AUDIT-PUBLISH-SUCCESS-{session_id}-{uuid.uuid4().hex[:6].upper()}"
        from services.firebase_service import save_audit_log
        save_audit_log(log_id, {
            "event_id": log_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor": "System",
            "role": "SYSTEM",
            "action": "PUBLISH_COMPLETED",
            "product_id": session_id,
            "description": f"Product '{state.product_name}' campaign launch successfully completed and published to Shopify."
        })

        print("\n===================================")
        print("WORKFLOW COMPLETED")
        print("===================================")

    except Exception as exc:
        logger.exception("ADK Workflow execution failed for session %s: %s", session_id, exc)
        state.status = "failed"
        state.errors["workflow_error"] = str(exc)
        persist_session_state(session_id, state)


def run_workshop_workflow_background(session_id: str):
    """Background runner for Workshop Setup Agent workflow."""
    session_id_var.set(session_id)
    workflow_id_var.set("WorkshopSetupWorkflow")

    state = active_sessions.get(session_id)
    if state is None:
        return

    try:
        state.status = "running"
        from workflow.workshop_workflow import run_workshop_workflow_session
        
        initial_dict = {
            "product_name": state.product_name,
            "raw_description": state.raw_description,
            "price": state.price,
            "category": state.category,
            "workshop_id": state.workshop_id,
            "approved_to_publish": state.approved_to_publish,
            "vendor": state.vendor or "Store Vendor",
            "product_type": "Workshop",
            "tags": state.tags or [],
            "sku": state.sku
        }
        
        res = asyncio.run(run_workshop_workflow_session(session_id, initial_dict))

        # Sync returned state fields
        state.workshop_id = res.get("workshop_id")
        state.generated_description = res.get("generated_description")
        state.current_stage = res.get("current_stage")
        state.status = res.get("status")
        state.duplicate_detected = res.get("duplicate_detected", False)
        if res.get("existing_product_id"):
            state.existing_product_id = res.get("existing_product_id")
            state.existing_product_title = res.get("existing_product_title")
        if res.get("conflicts_list"):
            state.conflicts_list = res.get("conflicts_list")

        # Save AI content draft to SQLite
        if state.workshop_id:
            try:
                from data.database import update_workshop_ai_content
                update_workshop_ai_content(state.workshop_id, {
                    "generated_description": state.generated_description,
                    "status": "pending_approval"
                })
            except Exception as dbe:
                logger.error("Failed to update database for workshop %s: %s", state.workshop_id, dbe)

        logger.info("Workshop setup background runner completed for session %s (state: %s)", session_id, state.status)
    except Exception as e:
        logger.exception("Workshop background run failed for session %s: %s", session_id, e)
        state.status = "failed"
        state.errors["workflow_error"] = str(e)
        
        log_id = f"AUDIT-PUBLISH-FAIL-{session_id}-{uuid.uuid4().hex[:6].upper()}"
        from services.firebase_service import save_audit_log
        save_audit_log(log_id, {
            "event_id": log_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor": "System",
            "role": "SYSTEM",
            "action": "PUBLISH_FAILED",
            "product_id": session_id,
            "description": f"Campaign publishing failed for product '{state.product_name}': {e}"
        })


def _derive_folder_failed_stage(final_state) -> str:
    """Best-effort mapping from workflow state progress to the stage that failed.

    Used so the dashboard marks the ACTUAL failed stage instead of always
    painting stage 4 (Media).
    """
    if not final_state:
        return "ingest"
    if not final_state.get("manifest"):
        return "ingest"
    if final_state.get("missing_fields_list") is None and final_state.get("conflicts_list") is None:
        return "validate"
    if not final_state.get("shopify_product_id"):
        return "create"
    if final_state.get("shopify_media") is None and not final_state.get("media_upload_results"):
        return "media"
    if not final_state.get("verification_result"):
        return "verify"
    return "report"


def run_folder_workflow_background(session_id: str):
    session_id_var.set(session_id)
    workflow_id_var.set("FolderProductWorkflow")

    print("\n===================================")
    print("SHOPIFY FOLDER PRODUCT LAUNCH STARTED")
    print("===================================")

    state = active_sessions.get(session_id)

    if state is None:
        return

    final_state = None

    try:

        state.status = "running"
        state.failed_stage = None

        session_exists = False
        try:
            session = asyncio.run(
                session_service.get_session(
                    app_name=APP_NAME,
                    user_id=USER_ID,
                    session_id=session_id,
                )
            )
            if session is not None:
                session_exists = True
        except Exception:
            pass

        delta = None
        if session_exists:
            print(
                "[DEBUG STATE]",
                "fn=run_folder_workflow_background(resume)",
                "var=session",
                "type=", type(session),
                "is_none=", session is None,
                "session_id=", session_id,
                "stage=", "resume/approval",
                "state_keys=", sorted(dict(session.state).keys()) if session is not None else None,
            )
            # Update the existing session state with latest user resolutions/overrides.
            # NOTE: "status" must be reset here — the preview run leaves
            # status="awaiting_approval" in the ADK session state, and no tool
            # resets it, so without this the resumed run would end as
            # "awaiting_approval" again instead of "completed".
            # NOTE: "workflow_error" must also be cleared here on every
            # resume (not just the FastAPI-facing ProductLaunchState). Every
            # folder_tools.py tool checks state.get("workflow_error") first
            # and no-ops if it's still set -- without clearing it, a retry
            # after a failure would silently do nothing and re-report the
            # same stale error instead of actually resuming the pipeline.
            session.state.update({
                "approved_to_publish": state.approved_to_publish,
                "duplicate_action": state.duplicate_action,
                "product_name": state.product_name,
                "product_description": state.raw_description,
                "product_price": state.price,
                "sku": state.sku,
                "inventory_quantity": state.inventory_quantity,
                "status": "running",
                # Carried into ADK session state so create_shopify_product_tool
                # can independently re-verify the approval still matches the
                # current product data (Approval Gate, Layer 2 - see
                # tools/folder_tools.py).
                "product_version": state.product_version,
                "approved_at_version": state.approved_at_version,
                "approved_by_uid": state.approved_by_uid,
                "approved_at": state.approved_at,
                "created_by_uid": state.created_by_uid,
                "submitted_by_uid": state.submitted_by_uid,
                "workflow_error": None,
            })
            delta = {
                "approved_to_publish": state.approved_to_publish,
                "duplicate_action": state.duplicate_action,
                "product_name": state.product_name,
                "product_description": state.raw_description,
                "product_price": state.price,
                "sku": state.sku,
                "inventory_quantity": state.inventory_quantity,
                "status": "running",
                "product_version": state.product_version,
                "approved_at_version": state.approved_at_version,
                "approved_by_uid": state.approved_by_uid,
                "approved_at": state.approved_at,
                "created_by_uid": state.created_by_uid,
                "submitted_by_uid": state.submitted_by_uid,
                "workflow_error": None,
            }
            if hasattr(session_service, "sessions") and APP_NAME in session_service.sessions:
                if USER_ID in session_service.sessions[APP_NAME]:
                    session_service.sessions[APP_NAME][USER_ID][session.id] = session
            print(f"ADK Folder Session Updated/Loaded: {session.id}")
        else:
            # First run: create a new session
            session = asyncio.run(
                create_session(
                    {
                        "product_folder_path": state.product_folder_path,
                        "approved_to_publish": state.approved_to_publish,
                        "duplicate_action": state.duplicate_action,
                        "preview_mode": state.preview_mode,
                        "product_version": state.product_version,
                        "approved_at_version": state.approved_at_version,
                        "created_by_uid": state.created_by_uid,
                        "submitted_by_uid": state.submitted_by_uid,
                    },
                    session_id=session_id
                )
            )
            print(f"ADK Folder Session Created: {session.id}")

        prompt = """
You are launching ONE Shopify product from a product folder.
The product folder path is stored in the workflow state as product_folder_path.
Begin the workflow to ingest, extract, validate, upload media, create, and verify.
"""

        message = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        # NOTE: Runner.run() (the sync wrapper) drives the workflow inside a
        # plain background thread (threading.Thread, no exception capture —
        # verified by reading google/adk/runners.py and
        # google/adk/platform/thread.py) and streams events back over a
        # queue. If a tool raises inside that thread — e.g. the Ingest,
        # Validate, Create, Media, Verify, or Report tool — Python's default
        # thread behavior applies: the exception prints to stderr
        # ("Exception in thread ...") and the thread dies, but it NEVER
        # reaches this function's try/except below. The for-loop over
        # events would just silently see fewer events and the workflow
        # would fall through to downstream logic operating on incomplete
        # state, without the real error ever being recorded. Reproduced
        # and confirmed with a minimal failing tool via the real Runner.
        # Driving run_async() directly, in this same thread, makes
        # tool/ADK exceptions propagate normally so the except block below
        # catches them with a full, accurate traceback.
        async def _consume_folder_events():
            async for event in folder_runner.run_async(
                user_id=USER_ID,
                session_id=session.id,
                new_message=message,
                state_delta=delta,
            ):
                print(event)

        asyncio.run(_consume_folder_events())

        final_session = asyncio.run(
            session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=session.id,
            )
        )

        print(
            "[DEBUG STATE]",
            "fn=run_folder_workflow_background(final)",
            "var=final_session",
            "type=", type(final_session),
            "is_none=", final_session is None,
            "session_id=", session.id,
            "stage=", "post-run",
            "state_keys=", sorted(dict(final_session.state).keys()) if final_session is not None else None,
        )
        if final_session is None:
            raise ValueError("ADK Workflow session could not be retrieved after run execution.")

        final_state = final_session.state

        print("\n===== FINAL FOLDER SESSION STATE =====")
        print(dict(final_state))
        print("======================================\n")

        state.product_name = final_state.get("product_name", "")
        state.raw_description = final_state.get("product_description", "")
        state.price = final_state.get("product_price")
        state.category = final_state.get("product_category")
        state.vendor = final_state.get("vendor")
        state.tags = final_state.get("tags") or []
        state.sku = final_state.get("sku")
        state.inventory_quantity = final_state.get("inventory_quantity")
        state.product_status = final_state.get("product_status") or "DRAFT"
        
        state.shopify_product = final_state.get("shopify_product")
        state.shopify_product_id = final_state.get("shopify_product_id")
        state.shopify_url = final_state.get("shopify_url")
        state.shopify_variant_id = final_state.get("shopify_variant_id")
        state.shopify_media = final_state.get("shopify_media")
        
        state.verification_result = final_state.get("verification_result")
        state.markdown_report_path = final_state.get("markdown_report_path")
        state.json_report_path = final_state.get("json_report_path")
        
        state.seo_metadata = final_state.get("seo_metadata")
        state.generated_description = final_state.get("generated_description")
        state.folder_report = final_state.get("folder_report")
        
        # Sync Firebase & Theme fields
        state.firebase_product_id = final_state.get("firebase_product_id")
        state.firebase_sync_status = final_state.get("firebase_sync_status")
        state.firebase_media_paths = final_state.get("firebase_media_paths")
        state.design_system_version = final_state.get("design_system_version")
        state.selected_shopify_template = final_state.get("selected_shopify_template")

        # Copy manifest & preview fields
        state.status = final_state.get("status") or "completed"
        state.manifest = final_state.get("manifest")
        state.conversions = final_state.get("conversions")
        state.unsupported_media = final_state.get("unsupported_media")
        state.missing_fields_list = final_state.get("missing_fields_list")
        state.conflicts_list = final_state.get("conflicts_list")
        state.duplicate_detected = final_state.get("duplicate_detected", False)
        state.existing_product_id = final_state.get("existing_product_id")
        state.existing_product_title = final_state.get("existing_product_title")
        state.existing_product_url = final_state.get("existing_product_url")
        state.duplicate_action = final_state.get("duplicate_action", "ASK")
        state.duplicate_action_resolved = final_state.get("duplicate_action_resolved")

        # Cleanup temporary uploaded files if finished (not paused for approval)
        if state.status != "awaiting_approval":
            try:
                import shutil
                if state.product_folder_path and os.path.exists(state.product_folder_path):
                    shutil.rmtree(state.product_folder_path)
                    logger.info("Cleaned up temporary upload directory: %s", state.product_folder_path)
            except Exception as e:
                logger.error("Failed to cleanup temp upload directory: %s", e)

        # Check if the product was successfully created or if there were workflow errors
        workflow_err = final_state.get("workflow_error")
        if workflow_err:
            state.status = "failed"
            state.failed_stage = _derive_folder_failed_stage(final_state)
            state.errors["workflow_error"] = workflow_err
            return

        if state.status == "awaiting_approval":
            print("\n===================================")
            print("FOLDER WORKFLOW PAUSED FOR APPROVAL")
            print("===================================")
            return

        if not final_state.get("shopify_product_id"):
            missing_fields = []
            if not final_state.get("product_name"):
                missing_fields.append("title")
            if not final_state.get("product_description"):
                missing_fields.append("description")
            if not final_state.get("product_price"):
                missing_fields.append("price")
            
            if missing_fields:
                error_msg = f"PRODUCT CREATION STOPPED\n\nMissing required information:\n" + "\n".join(f"- {f}" for f in missing_fields) + "\n\nPlease update the product folder and try again."
            else:
                error_msg = "Workflow failed to create the product on Shopify. Please check your shop credentials, duplicate settings, or network status."
            
            state.status = "failed"
            state.failed_stage = "create"
            state.errors["workflow_error"] = error_msg
            return

        verification = state.verification_result
        if verification and not verification.get("purchasable"):
            status_expected = str(final_state.get("product_status") or "ACTIVE").lower()
            if status_expected == "draft" and verification.get("product_exists") and not verification.get("errors"):
                pass
            else:
                details = "; ".join(verification.get("errors") or [])
                state.status = "failed"
                state.failed_stage = "verify"
                state.errors["workflow_error"] = "Shopify verification failed" + (f": {details}" if details else ".")
                return

        state.status = "completed"
        persist_session_state(session_id, state)
        
        log_id = f"AUDIT-PUBLISH-SUCCESS-{session_id}-{uuid.uuid4().hex[:6].upper()}"
        from services.firebase_service import save_audit_log
        save_audit_log(log_id, {
            "event_id": log_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor": "System",
            "role": "SYSTEM",
            "action": "PUBLISH_COMPLETED",
            "product_id": session_id,
            "description": f"Product '{state.product_name}' published live on Shopify successfully."
        })

        print("\n===================================")
        print("FOLDER WORKFLOW COMPLETED")
        print("===================================")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception("Error in run_folder_workflow_background")
        print(tb)
        try:
            state.failed_stage = _derive_folder_failed_stage(final_state)
        except Exception:
            state.failed_stage = "ingest"
        # Clean up directory on error
        try:
            import shutil
            if state.product_folder_path and os.path.exists(state.product_folder_path):
                shutil.rmtree(state.product_folder_path)
        except Exception:
            pass

        state.status = "failed"
        state.errors["workflow_error"] = f"{e}\n\nStack Trace:\n{tb}"
        persist_session_state(session_id, state)
        
        log_id = f"AUDIT-PUBLISH-FAIL-{session_id}-{uuid.uuid4().hex[:6].upper()}"
        from services.firebase_service import save_audit_log
        save_audit_log(log_id, {
            "event_id": log_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor": "System",
            "role": "SYSTEM",
            "action": "PUBLISH_FAILED",
            "product_id": session_id,
            "description": f"Publishing failed for product '{state.product_name}' at stage '{state.failed_stage}': {e}"
        })

    finally:
        # Always release the concurrency lock and live-stage marker, on every
        # exit path (success, handled failure, or an exception above) and
        # regardless of whether this run was triggered by an approve
        # endpoint (which acquires the lock) or the initial preview launch
        # (which doesn't) -- releasing an unheld lock is a harmless no-op.
        track_clear_stage(session_id)
        release_publish_lock(session_id)


@app.post("/launch", status_code=202)
def initiate_product_launch(
    raw_input: ProductLaunchInput,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN"]))
):

    session_id = str(uuid.uuid4())

    active_sessions[session_id] = ProductLaunchState(
        product_name=raw_input.product_name,
        raw_description=raw_input.raw_description,
        price=raw_input.price,
        category=raw_input.category,
        status="pending",
        source="campaign",
        created_at=datetime.utcnow().isoformat() + "Z",
        created_by_uid=current_user.uid,
        created_by_email=current_user.email,
        product_version=1
    )
    
    persist_session_state(session_id, active_sessions[session_id])
    
    log_id = f"AUDIT-CREATE-{session_id}-{uuid.uuid4().hex[:6].upper()}"
    from services.firebase_service import save_audit_log
    save_audit_log(log_id, {
        "event_id": log_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": current_user.email,
        "role": current_user.role,
        "action": "PRODUCT_CREATED",
        "product_id": session_id,
        "description": f"Product draft '{raw_input.product_name}' created by Catalogue Admin Lakshmi."
    })

    background_tasks.add_task(
        run_adk_workflow_background,
        session_id,
    )

    return {
        "session_id": session_id,
        "status": "pending",
        "message": "Workflow started successfully.",
        "status_endpoint": f"/status/{session_id}",
        "product_name": raw_input.product_name,
        "raw_description": raw_input.raw_description,
    }


class ValidationResponse(BaseModel):
    status: str
    message: str
    session_id: str
    summary: Optional[dict] = None


@app.post("/api/validate-store", response_model=ValidationResponse)
async def validate_store(
    background_tasks: BackgroundTasks,
    async_mode: bool = True,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN"]))
):
    """
    Trigger the Product Validation Agent audit on the Validation Shopify store.
    Can be run asynchronously (default) or synchronously.
    """
    session_id = str(uuid.uuid4())
    logger.info("Validation audit triggered by user %s (async=%s)", current_user.email, async_mode)
    
    async def run_validation_workflow():
        # Pre-create the validation session in the session service
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=current_user.uid,
            session_id=session_id,
            state={},
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text="Run validation audit on all products in the Shopify validation store.")],
        )
        try:
            async for event in validation_runner.run_async(
                user_id=current_user.uid,
                session_id=session_id,
                new_message=message,
            ):
                logger.debug("Validation event: %s", event)
            logger.info("Validation audit run complete for session %s", session_id)
        except Exception as e:
            logger.exception("Failed to run validation workflow")
            
    if async_mode:
        background_tasks.add_task(run_validation_workflow)
        return ValidationResponse(
            status="pending",
            message="Validation audit started in background.",
            session_id=session_id
        )
    else:
        await run_validation_workflow()
        
        outputs_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "outputs")
        )
        summary_path = os.path.join(outputs_dir, "summary_report.json")
        summary_data = None
        if os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary_data = json.load(f)
            except Exception as e:
                logger.error("Failed to read summary report: %s", e)
                
        return ValidationResponse(
            status="completed",
            message="Validation audit completed successfully.",
            session_id=session_id,
            summary=summary_data
        )


class FolderLaunchApprovalInput(BaseModel):
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    product_price: Optional[float] = None
    sku: Optional[str] = None
    inventory_quantity: Optional[int] = None
    duplicate_action: Optional[str] = "CREATE"
    approved_to_publish: bool = False


@app.post("/launch-folder", status_code=202)
async def initiate_folder_launch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    preview: bool = Form(True),
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN"]))
):

    # Upload validation (Phase 5 Part 11): the folder-launch endpoint
    # previously accepted an unbounded number of files of unbounded size and
    # any extension, straight onto disk, before any content validation ran.
    # That's both a DoS vector (fill the disk with one request) and a
    # foothold for uploading disallowed file types. Enforce count, per-file
    # size, and extension allowlist BEFORE any bytes are written.
    _ALLOWED_UPLOAD_EXTENSIONS = {
        ".json", ".txt", ".md", ".csv", ".pdf", ".docx", ".xlsx",
        ".png", ".jpg", ".jpeg", ".webp", ".gif",
        ".mp4", ".mov", ".webm",
    }
    max_file_bytes = settings.max_upload_file_size_mb * 1024 * 1024

    if len(files) > settings.max_upload_total_files:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: {len(files)} exceeds the limit of {settings.max_upload_total_files}."
        )

    for file in files:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{ext or '(none)'}' is not allowed ({file.filename})."
            )

    session_id = str(uuid.uuid4())
    temp_dir = os.path.abspath(os.path.join(OUTPUTS_DIR, "temp_uploads", session_id))
    os.makedirs(temp_dir, exist_ok=True)

    # Reconstruct folder structure
    for file in files:
        rel_path = file.filename.replace("\\", "/")
        while rel_path.startswith("/"):
            rel_path = rel_path[1:]
        if ".." in rel_path:
            continue

        file_dest = os.path.join(temp_dir, rel_path)
        os.makedirs(os.path.dirname(file_dest), exist_ok=True)

        bytes_written = 0
        with open(file_dest, "wb") as f:
            # Stream in chunks and enforce the per-file size cap while
            # writing, rather than reading the whole upload into memory
            # first -- a single oversized file can't exhaust memory before
            # being rejected.
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_file_bytes:
                    f.close()
                    import shutil as _shutil
                    _shutil.rmtree(temp_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"File '{file.filename}' exceeds the "
                            f"{settings.max_upload_file_size_mb}MB per-file upload limit."
                        )
                    )
                f.write(chunk)

    # Initialize active session
    active_sessions[session_id] = ProductLaunchState(
        product_name="Folder Ingestion",
        raw_description="Ingesting product from folder...",
        product_folder_path=temp_dir,
        status="pending",
        preview_mode=preview,
        approved_to_publish=not preview,
        source="folder",
        created_at=datetime.utcnow().isoformat() + "Z",
        created_by_uid=current_user.uid,
        created_by_email=current_user.email,
        product_version=1
    )
    
    persist_session_state(session_id, active_sessions[session_id])
    
    log_id = f"AUDIT-CREATE-{session_id}-{uuid.uuid4().hex[:6].upper()}"
    from services.firebase_service import save_audit_log
    save_audit_log(log_id, {
        "event_id": log_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": current_user.email,
        "role": current_user.role,
        "action": "PRODUCT_CREATED",
        "product_id": session_id,
        "description": f"Product ingestion draft created by Catalogue Admin Lakshmi."
    })

    background_tasks.add_task(
        run_folder_workflow_background,
        session_id,
    )

    return {
        "session_id": session_id,
        "status": "pending",
        "message": "Folder workflow started successfully.",
        "status_endpoint": f"/status/{session_id}",
    }


@app.post("/api/folder-launch/{session_id}/approve", status_code=202)
async def approve_folder_launch(
    session_id: str,
    approval_in: FolderLaunchApprovalInput,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(["APPROVER"]))
):
    state = active_sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    # Concurrency guard (Part 19): claim the publish lock before any other
    # check, so two near-simultaneous approve requests for the same product
    # can't both pass validation and both schedule a publishing run. Released
    # inside run_folder_workflow_background's finally block once the run
    # actually finishes, or immediately below if any check fails first.
    if not try_acquire_publish_lock(session_id):
        raise HTTPException(
            status_code=409,
            detail="A publishing execution is already in progress for this product."
        )

    try:
        # Role verification (Platform Admin cannot impersonate approval)
        if current_user.role != "APPROVER":
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Only users with the role 'APPROVER' are permitted to approve launches."
            )

        # State validation transition guard
        if state.status != "awaiting_approval":
            raise HTTPException(
                status_code=409,
                detail=f"Conflict: product status must be 'awaiting_approval' to approve, currently '{state.status}'"
            )

        # Self-approval protection
        if state.submitted_by_uid == current_user.uid or state.created_by_uid == current_user.uid:
            raise HTTPException(
                status_code=403,
                detail="Self-approval protection: Submitter cannot approve their own launch."
            )

        # Idempotency / Double-publish protection
        if state.status == "running" or state.status == "completed":
            raise HTTPException(
                status_code=409,
                detail="Product launch is already in progress or completed."
            )

        state.status = "running"
        state.approved_to_publish = approval_in.approved_to_publish
        state.duplicate_action = approval_in.duplicate_action or "CREATE"
        state.approved_by_uid = current_user.uid
        state.approved_by_email = current_user.email
        state.approved_at = datetime.utcnow().isoformat() + "Z"
        state.approved_at_version = state.product_version

        if approval_in.product_name:
            state.product_name = approval_in.product_name
        if approval_in.product_description:
            state.raw_description = approval_in.product_description
        if approval_in.product_price is not None:
            state.price = approval_in.product_price
        if approval_in.sku:
            state.sku = approval_in.sku
        if approval_in.inventory_quantity is not None:
            state.inventory_quantity = approval_in.inventory_quantity

        persist_session_state(session_id, state)

        log_id = f"AUDIT-APPROVE-{session_id}-{uuid.uuid4().hex[:6].upper()}"
        from services.firebase_service import save_audit_log
        save_audit_log(log_id, {
            "event_id": log_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor": current_user.email,
            "role": current_user.role,
            "action": "PRODUCT_APPROVED",
            "product_id": session_id,
            "description": f"Product '{state.product_name}' approved for publishing by Reviewer Sandeep."
        })

        background_tasks.add_task(
            run_folder_workflow_background,
            session_id,
        )
    except HTTPException:
        release_publish_lock(session_id)
        raise

    return {
        "session_id": session_id,
        "status": "running",
        "message": "Workflow approved and resuming in the background.",
    }


@app.get("/status/{session_id}", response_model=ProductLaunchState)
def get_status(session_id: str, current_user: User = Depends(get_current_user)):
    state = active_sessions.get(session_id)
    if not state:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    # Ownership checks
    if current_user.role == "CATALOGUE_ADMIN":
        if state.created_by_uid and state.created_by_uid != current_user.uid:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: You do not own this product launch status"
            )

    # Build a per-viewer response on a COPY, never the shared in-memory
    # record -- active_sessions[session_id] is one mutable object read by
    # every caller, so annotating/redacting it in place for this specific
    # request would corrupt what the next caller (possibly a different
    # role) sees.
    response_state = state.model_copy(deep=True)

    # Live stage visibility (Part 10): while the pipeline is actually
    # running, reflect which of ingest/validate/create/media/verify/report
    # is executing right now, sourced from workflow/progress_tracker.py --
    # not persisted, recomputed on every read.
    response_state.current_stage = track_get_stage(session_id) if state.status == "running" else None

    # Error Security (security.md SS15 / ui-spec.md SS14): full technical
    # detail (stack traces) must be Platform-Admin-only. Previously the
    # complete traceback in errors["workflow_error"] was present in this
    # response for every role, and only the frontend chose not to render it
    # for non-Platform-Admin users -- that's a UI convenience, not real
    # enforcement, per the same "hiding a button is not authorization"
    # principle applied to data instead of actions. Every other role now
    # gets the friendly first line only; the full trace stays server-side
    # for Platform Admin.
    if current_user.role != "PLATFORM_ADMIN" and "workflow_error" in response_state.errors:
        full_msg = response_state.errors["workflow_error"]
        friendly = full_msg.split("\n\nStack Trace:")[0].strip()
        response_state.errors["workflow_error"] = friendly

    return response_state


@app.get("/api/auth/me")
def api_get_current_user(current_user: User = Depends(get_current_user)):
    """Returns the current authenticated user's ID, email, role, and name."""
    return {
        "uid": current_user.uid,
        "email": current_user.email,
        "role": current_user.role,
        "name": getattr(current_user, "name", "") or current_user.email.split("@")[0].capitalize()
    }


# =====================================================================
# Workshop Launch Platform REST API and Webhook Implementation
# =====================================================================
import hmac
import hashlib
import base64
# pyrefly: ignore [missing-import]
from fastapi import Request
# pyrefly: ignore [missing-import]
from pydantic import Field

class MediaCreateInput(BaseModel):
    hero_image: Optional[str] = None
    gallery_images: List[str] = Field(default_factory=list)
    instructor_image: Optional[str] = None
    video_url: Optional[str] = None
    brochure_pdf: Optional[str] = None
    registration_qr: Optional[str] = None

class ProjectCreateInput(BaseModel):
    title: str
    description: str
    image_url: Optional[str] = None
    technology: Optional[str] = None

class TimelineStepCreateInput(BaseModel):
    step: Optional[int] = 1
    title: str
    description: str
    duration: Optional[str] = None

class ContentCreateInput(BaseModel):
    learning_outcomes: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    projects: List[ProjectCreateInput] = Field(default_factory=list)
    journey: List[TimelineStepCreateInput] = Field(default_factory=list)

class InstructorCreateInput(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    bio: Optional[str] = None
    photo: Optional[str] = None

class RegistrationCreateInput(BaseModel):
    url: Optional[str] = None
    button_text: Optional[str] = "Register Now"
    seats_available: Optional[int] = None
    deadline: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

class WorkshopCreateInput(BaseModel):
    name: str
    description: str
    date: Optional[str] = ""
    time: Optional[str] = ""
    duration: Optional[str] = ""
    venue: Optional[str] = ""
    age_group: Optional[str] = ""
    price: float = 0.0
    topics: List[str] = Field(default_factory=list)
    poster_path: Optional[str] = None
    video_url: Optional[str] = None
    sales_team_email: Optional[str] = ""

    media: Optional[MediaCreateInput] = Field(default_factory=MediaCreateInput)
    content: Optional[ContentCreateInput] = Field(default_factory=ContentCreateInput)
    instructor: Optional[InstructorCreateInput] = Field(default_factory=InstructorCreateInput)
    registration: Optional[RegistrationCreateInput] = Field(default_factory=RegistrationCreateInput)

def slugify(text: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

@app.on_event("startup")
def on_startup():
    # Strict validation of settings at startup
    settings.validate_startup()

    try:
        from data.database import init_db
        init_db()
        logger.info("SQLite database initialized successfully.")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)

    # Startup Connection Validations
    print("\n==========================================")
    print("STARTUP CONNECTION CHECK")
    print("==========================================")

    # Validate Firebase
    try:
        from services.firebase_service import initialize_firebase
        db_client = initialize_firebase()
        if db_client is not None:
            db_client.collection("health_check").document("startup").set({"status": "healthy", "timestamp": datetime.utcnow()})
            db_client.collection("health_check").document("startup").delete()
            print("Firebase:\nCONNECTED")
            logger.info("Firebase: CONNECTED")
        else:
            print("Firebase:\nNOT CONFIGURED")
            logger.warning("Firebase: NOT CONFIGURED")
    except Exception as fe:
        print("Firebase:\nNOT CONFIGURED")
        logger.warning("Firebase validation failed: %s", fe)

    # Validate Shopify
    try:
        from shopify_client import _get_config
        # pyrefly: ignore [missing-import]
        import httpx
        base_url, store_url, headers = _get_config()
        res = httpx.get(f"{base_url}/shop.json", headers=headers, timeout=10)
        if res.status_code == 200:
            print("Shopify:\nCONNECTED")
            logger.info("Shopify: CONNECTED")
        else:
            print("Shopify:\nNOT CONFIGURED")
            logger.warning("Shopify: NOT CONFIGURED (Response: %s)", res.status_code)
    except Exception as se:
        print("Shopify:\nNOT CONFIGURED")
        logger.warning("Shopify: NOT CONFIGURED (Error: %s)", se)
    
    print("==========================================\n")

class RequestChangesInput(BaseModel):
    comment: str


class ProductUpdateInput(BaseModel):
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    product_price: Optional[float] = None
    sku: Optional[str] = None
    inventory_quantity: Optional[int] = None


@app.post("/api/workshops/{id}/publish", status_code=501)
def api_publish_workshop(
    id: str,
    current_user: User = Depends(require_role(["APPROVER"]))
):
    raise HTTPException(
        status_code=501,
        detail="Direct workshop publishing endpoint is disabled and not production-supported."
    )


@app.post("/api/products/{id}/submit", status_code=200)
def api_submit_for_review(
    id: str,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN"]))
):
    state = active_sessions.get(id)
    if not state:
        raise HTTPException(status_code=404, detail="Product launch session not found")
    
    # Ownership guard
    if state.created_by_uid and state.created_by_uid != current_user.uid:
        raise HTTPException(status_code=403, detail="Permission denied: You do not own this product launch")

    validate_state_transition(state.status, "awaiting_approval")
    
    # Validation checks
    if state.missing_fields_list and len(state.missing_fields_list) > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit product with missing required fields: {state.missing_fields_list}"
        )
    
    state.status = "awaiting_approval"
    state.submitted_by_uid = current_user.uid
    state.submitted_by_email = current_user.email
    state.submitted_at = datetime.utcnow().isoformat() + "Z"
    
    persist_session_state(id, state)
    
    log_id = f"AUDIT-SUBMIT-{id}-{uuid.uuid4().hex[:6].upper()}"
    from services.firebase_service import save_audit_log
    save_audit_log(log_id, {
        "event_id": log_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": current_user.email,
        "role": current_user.role,
        "action": "SUBMITTED_FOR_REVIEW",
        "product_id": id,
        "description": f"Product '{state.product_name}' submitted for review by Catalogue Admin Lakshmi."
    })
    
    return {
        "session_id": id,
        "status": "awaiting_approval",
        "message": "Product successfully submitted for review."
    }


@app.post("/api/products/{id}/request-changes", status_code=200)
def api_request_changes(
    id: str,
    change_in: RequestChangesInput,
    current_user: User = Depends(require_role(["APPROVER"]))
):
    state = active_sessions.get(id)
    if not state:
        raise HTTPException(status_code=404, detail="Product launch session not found")
        
    if not change_in.comment.strip():
        raise HTTPException(status_code=400, detail="Change request comment must not be empty.")

    validate_state_transition(state.status, "failed")
    
    # Self-approval/review protection
    if state.submitted_by_uid == current_user.uid or state.created_by_uid == current_user.uid:
        raise HTTPException(
            status_code=403,
            detail="Self-review protection: Submitter cannot request changes on their own product."
        )
        
    state.status = "failed"
    state.failed_stage = "validate"
    state.reviewed_by_uid = current_user.uid
    state.reviewed_by_email = current_user.email
    state.reviewed_at = datetime.utcnow().isoformat() + "Z"
    state.review_comment = change_in.comment
    state.errors["review_comment"] = change_in.comment
    
    persist_session_state(id, state)
    
    log_id = f"AUDIT-CHANGES-{id}-{uuid.uuid4().hex[:6].upper()}"
    from services.firebase_service import save_audit_log
    save_audit_log(log_id, {
        "event_id": log_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": current_user.email,
        "role": current_user.role,
        "action": "CHANGES_REQUESTED",
        "product_id": id,
        "description": f"Changes requested for product '{state.product_name}' by Reviewer Sandeep: {change_in.comment}"
    })
    
    return {
        "session_id": id,
        "status": "failed",
        "message": "Changes requested recorded successfully."
    }


@app.post("/api/products/{id}/approve", status_code=200)
async def api_approve_product(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(["APPROVER"]))
):
    state = active_sessions.get(id)
    if not state:
        raise HTTPException(status_code=404, detail="Product launch session not found")

    # Concurrency guard (Part 19) -- see matching comment on the
    # /api/folder-launch/{id}/approve endpoint above.
    if not try_acquire_publish_lock(id):
        raise HTTPException(
            status_code=409,
            detail="A publishing execution is already in progress for this product."
        )

    try:
        # Role verification (Platform Admin cannot impersonate approval)
        if current_user.role != "APPROVER":
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Only users with the role 'APPROVER' are permitted to approve launches."
            )

        if state.status != "awaiting_approval":
            raise HTTPException(
                status_code=409,
                detail=f"Conflict: product status must be 'awaiting_approval' to approve, currently '{state.status}'"
            )

        # Creator-approver separation check (Self-Approval Protection)
        if state.submitted_by_uid == current_user.uid or state.created_by_uid == current_user.uid:
            raise HTTPException(
                status_code=403,
                detail="Self-approval protection: Submitter cannot approve their own product launch."
            )

        # Idempotency checks
        if state.status == "running" or state.status == "completed":
            raise HTTPException(
                status_code=409,
                detail="Product launch is already in progress or completed."
            )

        state.status = "running"
        state.approved_to_publish = True
        state.approved_by_uid = current_user.uid
        state.approved_by_email = current_user.email
        state.approved_at = datetime.utcnow().isoformat() + "Z"
        state.approved_at_version = state.product_version

        persist_session_state(id, state)

        log_id = f"AUDIT-APPROVE-{id}-{uuid.uuid4().hex[:6].upper()}"
        from services.firebase_service import save_audit_log
        save_audit_log(log_id, {
            "event_id": log_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor": current_user.email,
            "role": current_user.role,
            "action": "PRODUCT_APPROVED",
            "product_id": id,
            "description": f"Product '{state.product_name}' approved for publishing by Reviewer Sandeep."
        })

        if state.source == "folder":
            background_tasks.add_task(
                run_folder_workflow_background,
                id,
            )
        else:
            background_tasks.add_task(
                run_adk_workflow_background,
                id,
            )
    except HTTPException:
        release_publish_lock(id)
        raise

    return {
        "session_id": id,
        "status": "running",
        "message": "Product approved and publishing initiated."
    }


@app.post("/api/products/{id}/retry", status_code=200)
async def api_retry_product_publish(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(["PLATFORM_ADMIN"]))
):
    """Manually resume a technically-failed publishing run.

    Part 8/Part 17 of the Phase 4 spec: retries are for transient technical
    failures only (Shopify hiccup, media upload timeout, a Firestore write
    that failed) -- never for invalid data, a missing/stale approval, or a
    business rejection, all of which require a human to fix the product and
    go through review again, not a retry button. This endpoint enforces that
    distinction structurally rather than trying to classify error messages:
    it only ever resumes a run that already has a valid, current approval on
    record (same version check as the original Approve action) and it never
    creates a fresh approval -- if the approval itself is what's invalid,
    this endpoint correctly refuses, same as a first-time publish would.

    Platform Admin only, matching security.md SS4 ("a Technical Admin may
    trigger a retry of a failed technical stage") -- this is the concrete
    endpoint api-spec.md flagged as missing.
    """
    state = active_sessions.get(id)
    if not state:
        raise HTTPException(status_code=404, detail="Product launch session not found")

    if not try_acquire_publish_lock(id):
        raise HTTPException(
            status_code=409,
            detail="A publishing execution is already in progress for this product."
        )

    try:
        if state.status != "failed":
            raise HTTPException(
                status_code=409,
                detail=f"Conflict: only a failed run can be retried, current status is '{state.status}'"
            )

        # The original approval must still be present and still match the
        # current product version -- retry resumes an already-authorized
        # run, it does not grant a new one. If the product was edited since
        # the approval that authorized this run, retry is refused for the
        # same reason a fresh publish attempt would be (SS5/SS6).
        if not state.approved_to_publish or state.approved_by_uid is None:
            raise HTTPException(
                status_code=403,
                detail="Cannot retry: no valid approval is on record for this product."
            )
        if state.approved_at_version != state.product_version:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot retry: the product was modified after it was approved "
                    f"(approved at version {state.approved_at_version}, current version "
                    f"{state.product_version}). Re-review and re-approval is required."
                )
            )

        state.status = "running"
        state.failed_stage = None
        state.errors.pop("workflow_error", None)

        persist_session_state(id, state)

        log_id = f"AUDIT-RETRY-{id}-{uuid.uuid4().hex[:6].upper()}"
        from services.firebase_service import save_audit_log
        save_audit_log(log_id, {
            "event_id": log_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor": current_user.email,
            "role": current_user.role,
            "action": "RETRY_TRIGGERED",
            "product_id": id,
            "description": f"Failed publishing run for product '{state.product_name}' manually retried by Platform Admin."
        })

        if state.source == "folder":
            background_tasks.add_task(
                run_folder_workflow_background,
                id,
            )
        else:
            background_tasks.add_task(
                run_adk_workflow_background,
                id,
            )
    except HTTPException:
        release_publish_lock(id)
        raise

    return {
        "session_id": id,
        "status": "running",
        "message": "Retry initiated: resuming the publishing pipeline."
    }


@app.patch("/api/products/{id}", status_code=200)
def api_update_product(
    id: str,
    update_in: ProductUpdateInput,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN"]))
):
    state = active_sessions.get(id)
    if not state:
        raise HTTPException(status_code=404, detail="Product launch session not found")
        
    # Ownership guard
    if state.created_by_uid and state.created_by_uid != current_user.uid:
        raise HTTPException(status_code=403, detail="Permission denied: You do not own this product launch")
        
    # Must be draft (pending), changes requested (failed), or completed
    if state.status not in ["pending", "failed", "completed"]:
        raise HTTPException(status_code=409, detail="Product is not in an editable state")
        
    was_completed = state.status == "completed"
    if was_completed:
        state.status = "pending"
        state.approved_to_publish = False
        state.approved_by_uid = None
        state.approved_by_email = None
        state.approved_at = None
        state.approved_at_version = None
        
    if update_in.product_name:
        state.product_name = update_in.product_name
    if update_in.product_description:
        state.raw_description = update_in.product_description
    if update_in.product_price is not None:
        state.price = update_in.product_price
    if update_in.sku:
        state.sku = update_in.sku
    if update_in.inventory_quantity is not None:
        state.inventory_quantity = update_in.inventory_quantity
        
    # Increment version!
    state.product_version += 1
    
    persist_session_state(id, state)
    
    log_id = f"AUDIT-UPDATE-{id}-{uuid.uuid4().hex[:6].upper()}"
    from services.firebase_service import save_audit_log
    save_audit_log(log_id, {
        "event_id": log_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": current_user.email,
        "role": current_user.role,
        "action": "PRODUCT_UPDATED",
        "product_id": id,
        "description": f"Product '{state.product_name}' updated by Catalogue Admin Lakshmi. Version bumped to {state.product_version}."
    })
    
    return state


@app.get("/api/dashboard/metrics")
def api_dashboard_metrics(current_user: User = Depends(get_current_user)):
    from data.database import get_dashboard_metrics
    return get_dashboard_metrics()


@app.get("/api/launches", response_model=List[LaunchSummary])
def api_list_launches(current_user: User = Depends(get_current_user)):
    results = []
    # If Catalogue Admin, filter to own submissions only
    for sid, state in active_sessions.items():
        if current_user.role == "CATALOGUE_ADMIN":
            if state.created_by_uid and state.created_by_uid != current_user.uid:
                continue
        results.append(LaunchSummary(
            session_id=sid,
            product_name=state.product_name or "Folder Ingestion",
            status=state.status,
            failed_stage=state.failed_stage,
            preview_mode=state.preview_mode,
            created_at=state.created_at,
            source=state.source or "campaign",
        ))
    try:
        results.sort(key=lambda x: x.created_at or "", reverse=True)
    except Exception:
        pass
    return results


@app.get("/api/audit-logs", response_model=List[AuditLogEntry])
def api_get_audit_logs(current_user: User = Depends(require_role(["PLATFORM_ADMIN"]))):
    from services.firebase_service import get_audit_logs
    logs = get_audit_logs()
    return [
        AuditLogEntry(
            timestamp=x.get("timestamp") or "",
            actor=x.get("actor") or "System",
            role=x.get("role") or "SYSTEM",
            action=x.get("action") or "UNKNOWN",
            description=x.get("description") or "",
            product_id=str(x.get("product_id")) if x.get("product_id") is not None else None
        ) for x in logs
    ]


@app.get("/api/workshops")
def api_get_workshops(current_user: User = Depends(get_current_user)):
    from data.database import get_all_workshops
    return get_all_workshops()


@app.get("/api/workshops/{workshop_id}")
def api_get_workshop(workshop_id: str, current_user: User = Depends(get_current_user)):
    from data.database import get_workshop
    w = get_workshop(workshop_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workshop not found")
    return w

@app.post("/api/workshops")
def api_create_workshop(
    input_data: WorkshopCreateInput,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN"]))
):
    from services.workshop_service import (
        WorkshopService, WorkshopInput, MediaInput, ContentInput, InstructorInput, RegistrationInputData
    )
    
    media_dict = input_data.media.dict() if input_data.media else {}
    content_dict = input_data.content.dict() if input_data.content else {}
    instructor_dict = input_data.instructor.dict() if input_data.instructor else {}
    reg_dict = input_data.registration.dict() if input_data.registration else {}

    try:
        w_input = WorkshopInput(
            name=input_data.name,
            description=input_data.description,
            date=input_data.date or "",
            time=input_data.time or "",
            duration=input_data.duration or "",
            venue=input_data.venue or "",
            age_group=input_data.age_group or "",
            price=input_data.price,
            topics=input_data.topics,
            poster_path=input_data.poster_path,
            video_url=input_data.video_url,
            sales_team_email=input_data.sales_team_email or "",
            media=MediaInput(**media_dict),
            content=ContentInput(**content_dict),
            instructor=InstructorInput(**instructor_dict),
            registration=RegistrationInputData(**reg_dict)
        )
    except Exception as exc:
        logger.error("Failed to parse workshop input parameters: %s", exc)
        raise HTTPException(status_code=400, detail=f"Invalid payload structure: {exc}")

    val_err = WorkshopService.validate_workshop_input(w_input)
    if val_err:
        logger.warning("Workshop creation validation error: %s", val_err)
        raise HTTPException(status_code=400, detail=val_err)

    from data.database import create_workshop, get_workshop
    w_id = slugify(input_data.name)
    
    if get_workshop(w_id):
        w_id = f"{w_id}-{int(datetime.utcnow().timestamp())}"
        
    workshop_data = input_data.dict()
    workshop_data["id"] = w_id
    workshop_data["status"] = "draft"
    
    try:
        create_workshop(workshop_data)
    except Exception as exc:
        logger.error("Failed to insert workshop into DB: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to save workshop: {exc}")

    return {
        "success": True,
        "workshop_id": w_id,
        "status": "draft",
        "message": "Workshop draft created successfully"
    }


@app.post("/api/workshops/upload-media")
async def api_upload_workshop_media(
    file: UploadFile = File(...),
    folder_name: str = Form("workshop_media"),
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN"]))
):
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".pdf", ".mp4", ".mov", ".webm"}
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(allowed_exts))}"
        )

    contents = await file.read()
    max_bytes = 25 * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File '{file.filename}' exceeds maximum allowed size of 25MB."
        )

    temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "outputs", "temp_uploads"))
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{file.filename}")

    try:
        with open(temp_file_path, "wb") as f:
            f.write(contents)
        
        from services.firebase_storage_service import upload_file
        res = upload_file("workshops", folder_name, temp_file_path)
        return {
            "success": True,
            "url": res["public_url"],
            "filename": res["filename"],
            "content_type": res["content_type"],
            "size": res["size"]
        }
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

@app.post("/api/workshops/{workshop_id}/generate", status_code=202)
def api_generate_workshop_campaign(
    workshop_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN"]))
):
    from data.database import get_workshop
    w = get_workshop(workshop_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workshop not found")
        
    session_id = str(uuid.uuid4())
    
    active_sessions[session_id] = ProductLaunchState(
        product_name=w["name"],
        raw_description=w.get("description", ""),
        price=w.get("price", 0.0),
        category="Workshop",
        status="pending",
        approved_to_publish=False, # Draft mode boundary
        workshop_id=workshop_id,
        source="campaign",
        created_at=datetime.utcnow().isoformat() + "Z",
    )
    
    try:
        from data.database import update_workshop_status
        update_workshop_status(workshop_id, 'generating')
    except Exception as e:
        logger.error("Failed to update status in DB: %s", e)
        
    background_tasks.add_task(
        run_workshop_workflow_background,
        session_id,
    )
    
    return {
        "session_id": session_id,
        "status_endpoint": f"/status/{session_id}",
    }


@app.post("/api/workshops/{workshop_id}/approve", status_code=200)
def api_approve_workshop(
    workshop_id: str,
    current_user: User = Depends(require_role(["APPROVER", "CATALOGUE_ADMIN"]))
):
    """
    Approve workshop draft.
    Executes Shopify product creation/update (in draft status) and 53-item validation engine.
    Passing validation transitions state to LAUNCH_READY (product stays DRAFT until explicit publish).
    """
    from data.database import get_workshop, update_workshop_shopify_ids, update_workshop_status
    from services.workshop_service import (
        WorkshopService, WorkshopInput, WorkshopWorkflowState,
        ContentInput, MediaInput, InstructorInput, RegistrationInputData
    )

    w = get_workshop(workshop_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workshop not found")

    # Find active session or construct state
    session_id = None
    session_state = None
    for s_id, s in active_sessions.items():
        if getattr(s, "workshop_id", None) == workshop_id:
            session_id = s_id
            session_state = s
            break

    content_raw = w.get("content")
    if isinstance(content_raw, str):
        try:
            content_raw = json.loads(content_raw)
        except Exception:
            content_raw = {}
    content_obj = ContentInput(**content_raw) if isinstance(content_raw, dict) and content_raw else ContentInput()

    media_raw = w.get("media")
    if isinstance(media_raw, str):
        try:
            media_raw = json.loads(media_raw)
        except Exception:
            media_raw = {}
    media_obj = MediaInput(**media_raw) if isinstance(media_raw, dict) and media_raw else MediaInput()

    instructor_raw = w.get("instructor")
    if isinstance(instructor_raw, str):
        try:
            instructor_raw = json.loads(instructor_raw)
        except Exception:
            instructor_raw = {}
    instructor_obj = InstructorInput(**instructor_raw) if isinstance(instructor_raw, dict) and instructor_raw else InstructorInput()

    registration_raw = w.get("registration")
    if isinstance(registration_raw, str):
        try:
            registration_raw = json.loads(registration_raw)
        except Exception:
            registration_raw = {}
    registration_obj = RegistrationInputData(**registration_raw) if isinstance(registration_raw, dict) and registration_raw else RegistrationInputData()

    input_data = WorkshopInput(
        name=w["name"],
        description=w.get("description", ""),
        date=w.get("date", ""),
        time=w.get("time", ""),
        duration=w.get("duration", ""),
        venue=w.get("venue", ""),
        age_group=w.get("age_group", ""),
        price=float(w.get("price") or 0.0),
        vendor=w.get("vendor") or "Store Vendor",
        product_type="Workshop",
        topics=w.get("topics") or [],
        poster_path=w.get("poster_path"),
        video_url=w.get("video_url"),
        sales_team_email=w.get("sales_team_email") or "",
        media=media_obj,
        content=content_obj,
        instructor=instructor_obj,
        registration=registration_obj
    )

    ws_state = WorkshopWorkflowState(
        workshop_id=workshop_id,
        current_state="PENDING_APPROVAL",
        input_data=input_data
    )

    # 1. Sign off approval
    ws_state = WorkshopService.approve_workshop(ws_state, current_user.email)

    # 2. Prepare payloads
    ws_state = WorkshopService.prepare_website_content(ws_state)
    ws_state = WorkshopService.prepare_shopify_payload(ws_state)

    # 3. Create or update product on Shopify (in DRAFT status)
    try:
        ws_state = WorkshopService.create_or_update_shopify_product(ws_state)
    except Exception as exc:
        logger.error("Exception during Shopify product creation for workshop %s: %s", workshop_id, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Shopify draft creation failed: {exc}"
        )

    # Validate Shopify product draft creation
    if not ws_state.shopify_product_id or ws_state.current_state in ["SHOPIFY_API_ERROR", "SHOPIFY_SYNC_FAILED"]:
        err_msg = ws_state.error_message or f"Shopify draft product creation failed with state '{ws_state.current_state}'"
        logger.error("Approval failed for workshop %s: state=%s, error=%s", workshop_id, ws_state.current_state, err_msg)
        status_code = 502 if ws_state.current_state in ["SHOPIFY_API_ERROR", "SHOPIFY_SYNC_FAILED"] else 500
        raise HTTPException(
            status_code=status_code,
            detail=f"Approval failed: {err_msg}"
        )

    update_workshop_shopify_ids(
        workshop_id,
        ws_state.shopify_product_id,
        ws_state.shopify_variant_id,
        status="approved"
    )

    # 4. Run 53-item validation engine
    ws_state = WorkshopService.run_product_validation(ws_state)

    if session_state:
        session_state.approved_to_publish = True
        session_state.shopify_product_id = ws_state.shopify_product_id
        session_state.shopify_variant_id = ws_state.shopify_variant_id
        session_state.status = ws_state.current_state

    # Log audit
    log_id = f"AUDIT-WORKSHOP-APPROVE-{workshop_id}-{uuid.uuid4().hex[:6].upper()}"
    from services.firebase_service import save_audit_log
    save_audit_log(log_id, {
        "event_id": log_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": current_user.email,
        "role": current_user.role,
        "action": "WORKSHOP_APPROVED",
        "product_id": workshop_id,
        "description": f"Workshop '{w['name']}' approved by {current_user.email}. Shopify product ID {ws_state.shopify_product_id} created in draft status."
    })

    return {
        "status": "success",
        "workshop_id": workshop_id,
        "current_state": ws_state.current_state,
        "shopify_product_id": ws_state.shopify_product_id,
        "shopify_variant_id": ws_state.shopify_variant_id,
        "product_status": ws_state.shopify_product_status,
        "validation_passed": (ws_state.current_state == "LAUNCH_READY")
    }


@app.post("/api/workshops/{workshop_id}/publish", status_code=200)
def api_publish_workshop_campaign(
    workshop_id: str,
    current_user: User = Depends(require_role(["APPROVER"]))
):
    """
    Explicit, controlled publishing endpoint.
    Moves Shopify product status from 'draft' to 'active' ONLY after LAUNCH_READY.
    """
    from data.database import get_workshop, publish_workshop
    from services.workshop_service import WorkshopService, WorkshopInput, WorkshopWorkflowState

    w = get_workshop(workshop_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workshop not found")

    shopify_product_id = w.get("shopify_product_id")
    shopify_variant_id = w.get("shopify_variant_id")

    if not shopify_product_id:
        raise HTTPException(
            status_code=400,
            detail="Workshop product has not been created on Shopify yet. Approve the workshop first."
        )

    # Reconstruct state to enforce publication rules
    input_data = WorkshopInput(
        name=w["name"],
        description=w.get("description", ""),
        price=float(w.get("price") or 0.0)
    )

    ws_state = WorkshopWorkflowState(
        workshop_id=workshop_id,
        current_state="LAUNCH_READY",  # Must be LAUNCH_READY
        input_data=input_data,
        shopify_product_id=shopify_product_id,
        shopify_variant_id=shopify_variant_id,
        approval_status="APPROVED"
    )

    # Publish on Shopify
    try:
        ws_state = WorkshopService.publish_workshop_product(ws_state)
    except Exception as pe:
        logger.exception("Failed to publish workshop product to Shopify")
        raise HTTPException(status_code=500, detail=f"Shopify publication error: {pe}")

    # Mark published in DB
    try:
        store_url = settings.shopify_store_url or "product-launch-agent.myshopify.com"
        shopify_url = f"https://{store_url}/products/{slugify(w['name'])}"
        publish_workshop(
            workshop_id=workshop_id,
            shopify_product_id=shopify_product_id,
            shopify_url=shopify_url,
            shopify_variant_id=shopify_variant_id
        )
    except Exception as dbe:
        logger.error("Failed to update published status in DB: %s", dbe)

    log_id = f"AUDIT-WORKSHOP-PUBLISH-{workshop_id}-{uuid.uuid4().hex[:6].upper()}"
    from services.firebase_service import save_audit_log
    save_audit_log(log_id, {
        "event_id": log_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": current_user.email,
        "role": current_user.role,
        "action": "WORKSHOP_PUBLISHED",
        "product_id": workshop_id,
        "description": f"Workshop '{w['name']}' published to Shopify. Product ID {shopify_product_id} is now ACTIVE."
    })

    return {
        "status": "success",
        "workshop_id": workshop_id,
        "shopify_product_id": shopify_product_id,
        "shopify_variant_id": shopify_variant_id,
        "product_status": "active",
        "db_status": "published"
    }


@app.post("/api/workshops/{workshop_id}/register")
def register_student(workshop_id: str, reg_in: RegistrationInput):
    """Accept student pre-registration, save in SQLite as pending, and return checkout redirect."""
    import urllib.parse
    from data.database import get_workshop, add_registration
    
    w = get_workshop(workshop_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workshop not found")
        
    variant_id = str(w.get("shopify_variant_id") or "")
    if not variant_id:
        raise HTTPException(
            status_code=400,
            detail="This workshop has not been published to Shopify yet."
        )
        
    reg_id = f"REG-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    reg_data = {
        "order_id": reg_id,
        "shopify_order_id": None,
        "shopify_order_number": None,
        "workshop_id": workshop_id,
        "customer_name": f"{reg_in.parent_name} / {reg_in.child_name}",
        "customer_email": reg_in.customer_email,
        "customer_phone": reg_in.customer_phone,
        "amount": float(w["price"]),
        "payment_status": "pending",
        "child_name": reg_in.child_name,
        "child_age": reg_in.child_age,
        "parent_name": reg_in.parent_name,
        "school": reg_in.school,
        "emergency_contact": reg_in.emergency_contact,
        "created_at": datetime.utcnow().isoformat()
    }
    
    try:
        add_registration(reg_data)
    except Exception as e:
        logger.exception("Failed to insert pending registration.")
        raise HTTPException(status_code=500, detail=f"Database write failure: {e}")
        
    store_url = settings.shopify_store_url or "product-launch-agent.myshopify.com"
    checkout_url = (
        f"https://{store_url}/cart/{variant_id}:1?"
        f"attributes[registration_id]={reg_id}&"
        f"attributes[student_name]={urllib.parse.quote(reg_in.child_name)}&"
        f"attributes[parent_name]={urllib.parse.quote(reg_in.parent_name)}&"
        f"checkout[email]={urllib.parse.quote(reg_in.customer_email)}"
    )
    
    return {
        "status": "success",
        "registration_id": reg_id,
        "redirect_url": checkout_url
    }


@app.post("/api/webhooks/orders/create")
async def shopify_order_webhook(request: Request):
    """Handle Shopify order created webhook to process workshop registrations and send emails."""
    body = await request.body()
    headers = request.headers
    hmac_header = headers.get("X-Shopify-Hmac-Sha256")
    
    # Verify HMAC signature
    shopify_secret = settings.shopify_api_secret or settings.shopify_client_secret
    if shopify_secret and hmac_header:
        digest = hmac.new(shopify_secret.encode("utf-8"), body, hashlib.sha256).digest()
        computed_hmac = base64.b64encode(digest).decode("utf-8")
        if not hmac.compare_digest(computed_hmac, hmac_header):
            logger.warning("Invalid Shopify Webhook Signature.")
            raise HTTPException(status_code=401, detail="Unauthorized webhook source")
            
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    line_items = payload.get("line_items", [])
    if not line_items:
        return {"status": "ignored", "message": "No line items found"}
        
    # Process registrations for workshop products
    registrations_added = 0
    from data.database import get_workshop_by_shopify_id, add_registration
    from email_service import send_email, generate_customer_email_html, generate_sales_email_html
    
    for item in line_items:
        shopify_product_id = item.get("product_id")
        if not shopify_product_id:
            continue
            
        workshop = get_workshop_by_shopify_id(shopify_product_id)
        if not workshop:
            # Not a workshop product, skip
            logger.info("Order item product ID %s does not map to a database workshop.", shopify_product_id)
            continue
            
        # Parse cart attributes
        note_attrs = payload.get("note_attributes", [])
        child_name = "N/A"
        child_age = 0
        parent_name = "N/A"
        registration_id = None
        
        for attr in note_attrs:
            name = str(attr.get("name", "")).strip().lower()
            val = str(attr.get("value", "")).strip()
            if name in ("child name", "child_name"):
                child_name = val
            elif name in ("child age", "child_age"):
                try:
                    child_age = int(val)
                except ValueError:
                    pass
            elif name in ("parent name", "parent_name"):
                parent_name = val
            elif name in ("registration_id", "registrationid"):
                registration_id = val
                
        customer = payload.get("customer", {})
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or parent_name or "Parent"
        customer_email = customer.get("email") or payload.get("email") or "customer@example.com"
        customer_phone = customer.get("phone") or payload.get("phone") or ""
        
        # Lookup registration in DB if registration_id was supplied
        from data.database import get_registration
        existing_reg = None
        if registration_id:
            try:
                existing_reg = get_registration(registration_id)
            except Exception as e:
                logger.error("Error looking up registration_id %s: %s", registration_id, e)
                
        if existing_reg:
            reg_id = existing_reg["order_id"]
            child_name = existing_reg.get("child_name") or child_name
            child_age = existing_reg.get("child_age") or child_age
            parent_name = existing_reg.get("parent_name") or parent_name
            
            reg_data = existing_reg.copy()
            reg_data.update({
                "shopify_order_id": payload.get("id"),
                "shopify_order_number": str(payload.get("order_number") or payload.get("name", "")),
                "payment_status": payload.get("financial_status", "paid"),
                "amount": float(payload.get("total_price", existing_reg.get("amount", workshop["price"]))),
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone or existing_reg.get("customer_phone")
            })
        else:
            reg_id = registration_id or f"REG-{str(payload.get('id'))}"
            reg_data = {
                "order_id": reg_id,
                "shopify_order_id": payload.get("id"),
                "shopify_order_number": str(payload.get("order_number") or payload.get("name", "")),
                "workshop_id": workshop["id"],
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "amount": float(payload.get("total_price", workshop["price"])),
                "payment_status": payload.get("financial_status", "paid"),
                "child_name": child_name,
                "child_age": child_age,
                "parent_name": parent_name,
                "school": "N/A",
                "emergency_contact": "N/A",
                "created_at": payload.get("created_at") or datetime.utcnow().isoformat()
            }
            
        try:
            add_registration(reg_data)
            registrations_added += 1
            
            # 1. Send Customer Email
            cust_html = generate_customer_email_html(
                customer_name=customer_name,
                workshop_name=workshop["name"],
                date=workshop["date"],
                time=workshop["time"],
                venue=workshop["venue"],
                order_id=reg_data["shopify_order_number"],
                amount=reg_data["amount"],
                child_name=child_name,
                child_age=child_age,
                registration_id=reg_id
            )
            send_email(
                to_email=customer_email,
                subject="Mission Tiranga Registration Confirmed 🚀",
                html_content=cust_html,
                filename_prefix="customer",
                order_id=reg_id
            )
            
            # 2. Send Sales Notification Email
            sales_email = settings.sales_team_email or workshop.get("sales_team_email") or "sales@example.com"
            sales_html = generate_sales_email_html(reg_data, workshop)
            send_email(
                to_email=sales_email,
                subject=f"New Mission Tiranga Registration - Order #{reg_data['shopify_order_number']}",
                html_content=sales_html,
                filename_prefix="salesteam",
                order_id=reg_id
            )
        except Exception as e:
            logger.exception("Failed to process registration webhook for item %s", shopify_product_id)
        
    # Also synchronize to Google Sheets via student registration automation
    try:
        from services.registration_sync_service import process_order_webhook_sync
        process_order_webhook_sync(body, dict(headers))
    except Exception as e:
        logger.warning("Could not sync to Google Sheets from orders/create: %s", e)

    return {"status": "processed", "registrations_added": registrations_added}


@app.post("/api/webhooks/orders/paid")
async def shopify_orders_paid_webhook(request: Request):
    """Handle Shopify orders/paid webhook to synchronize registrations to Google Sheets."""
    body = await request.body()
    headers = dict(request.headers)
    from services.registration_sync_service import process_order_webhook_sync
    result = process_order_webhook_sync(body, headers)
    if result.get("status_code") == 401:
        raise HTTPException(status_code=401, detail=result.get("error", "Unauthorized webhook source"))
    if result.get("status_code") == 400:
        raise HTTPException(status_code=400, detail=result.get("error", "Invalid JSON payload"))
    return result


@app.post("/api/registrations/sync/retry")
def retry_failed_registrations_endpoint(current_user: User = Depends(require_role(["PLATFORM_ADMIN"]))):
    """Operational endpoint to retry failed student registrations to Google Sheets."""
    from services.registration_sync_service import retry_failed_student_registrations
    return retry_failed_student_registrations()


@app.post("/api/workshops/{id}/publish", status_code=501)
async def api_publish_workshop(id: str):
    raise HTTPException(
        status_code=501,
        detail="Direct workshop publishing endpoint is disabled and not production-supported."
    )


@app.get("/workshops/{handle}")
def serve_workshop_landing_page(handle: str):
    """Dynamic routing to serve the landing page for a specific workshop handle."""
    from data.database import get_workshop
    w = get_workshop(handle)
    if not w:
        raise HTTPException(status_code=404, detail="Workshop not found")
        
    # Read the template html file
    template_path = os.path.join(STATIC_DIR, "landing_page.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail="Landing page template missing")
        
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    # Get variant ID for shopify checkout link.
    # This is read directly from the workshops table's shopify_variant_id column,
    # populated by publish_workshop() once the ADK pipeline actually publishes the
    # product. Previously this looked for a "shopify_product" key that the database
    # never stores, so variant_id was always empty and the page always showed its
    # "preview draft mode" fallback message, even for successfully published workshops.
    variant_id = str(w.get("shopify_variant_id") or "")
        
    store_url = settings.shopify_store_url or "product-launch-agent.myshopify.com"
    
    # Check if generated images exist
    images = {}
    image_paths = w.get("image_paths") or []
    def get_static_image_url(path):
        if not path:
            return ""
        rel = os.path.basename(path)
        return f"/outputs/images/{rel}"
        
    for path in image_paths:
        for cat in ["hero", "lifestyle", "banner", "classroom", "thumbnail", "certificate", "gallery1", "gallery2"]:
            if f"_{cat}." in os.path.basename(path) or path.endswith(f"_{cat}.png"):
                images[cat] = get_static_image_url(path)
                
    # Fallback to visual placeholders if not generated yet
    if not images.get("hero"):
        images["hero"] = "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1000"
    if not images.get("lifestyle"):
        images["lifestyle"] = "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?q=80&w=1000"
    if not images.get("banner"):
        images["banner"] = "https://images.unsplash.com/photo-1540575467063-178a50c2df87?q=80&w=1000"
    if not images.get("classroom"):
        images["classroom"] = "https://images.unsplash.com/photo-1427504494785-3a9ca7044f45?q=80&w=1000"
    if not images.get("thumbnail"):
        images["thumbnail"] = "https://images.unsplash.com/photo-1506318137071-a8e063b4bec0?q=80&w=300"
    if not images.get("certificate"):
        images["certificate"] = "https://images.unsplash.com/photo-1578575437130-527eed3abbec?q=80&w=1000"
    if not images.get("gallery1"):
        images["gallery1"] = "https://images.unsplash.com/photo-1581092921461-eab62e97a780?q=80&w=1000"
    if not images.get("gallery2"):
        images["gallery2"] = "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?q=80&w=1000"
        
    vendor = w.get("vendor") or "KiddyPi"
    if vendor in ["Store Vendor", "Store"]:
        vendor = "KiddyPi"

    # Instructor details
    inst = w.get("instructor") or {}
    inst_name = inst.get("name") or "KiddyPi Senior STEM Educator"
    inst_role = inst.get("role") or "Lead Workshop Coordinator"
    inst_bio = inst.get("bio") or f"Experienced STEM educator leading hands-on workshops in AI, Robotics, and Technology for young innovators."
    inst_photo = inst.get("photo") or (w.get("media") and w["media"].get("instructor_image")) or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=300"

    inst_html = f"""
        <div class="instructor-card">
            <img src="{inst_photo}" alt="{inst_name}" class="instructor-avatar">
            <div class="instructor-info">
                <h3>{inst_name}</h3>
                <div class="title">{inst_role}</div>
                <p>{inst_bio}</p>
            </div>
        </div>
    """

    # Highlights HTML
    content_data = w.get("content") or {}
    learning_outcomes = content_data.get("learning_outcomes") or []
    highlights = content_data.get("highlights") or []
    topics = w.get("topics") or []
    
    highlights_items = highlights or learning_outcomes or topics or [
        "Hands-on Practical Activities",
        "Guided Interactive Experiments",
        "Real-world Skills & Take-home Project"
    ]
    
    highlights_html_list = []
    icons = ["🚀", "🛠️", "🤖", "💡", "⚡", "🔬"]
    for idx, item in enumerate(highlights_items[:6]):
        icon = icons[idx % len(icons)]
        highlights_html_list.append(f"""
            <div class="learn-card">
                <div class="card-num">{idx+1:02d}</div>
                <div class="card-icon">{icon}</div>
                <h3>{item}</h3>
                <p>Interactive practical module covering core workshop skills.</p>
            </div>
        """)
    highlights_html = "\n".join(highlights_html_list)

    # Timeline HTML
    journey = content_data.get("journey") or []
    if journey:
        timeline_items = []
        for step in journey:
            s_time = step.get("duration") or f"Phase {step.get('step', '')}"
            s_title = step.get("title", "")
            s_desc = step.get("description", "")
            timeline_items.append(f"""
                <div class="timeline-item">
                    <div class="timeline-node"></div>
                    <div class="timeline-content">
                         <div class="timeline-time">{s_time}</div>
                         <div class="timeline-title">{s_title}</div>
                         <div class="timeline-desc">{s_desc}</div>
                    </div>
                </div>
            """)
        timeline_html = "\n".join(timeline_items)
    else:
        timeline_html = f"""
            <div class="timeline-item">
                <div class="timeline-node"></div>
                <div class="timeline-content">
                     <div class="timeline-time">Phase 1</div>
                     <div class="timeline-title">Orientation & Tool Distribution</div>
                     <div class="timeline-desc">Receive workspace kit, meet mentors, and explore core workshop concepts.</div>
                </div>
            </div>
            <div class="timeline-item">
                <div class="timeline-node"></div>
                <div class="timeline-content">
                     <div class="timeline-time">Phase 2</div>
                     <div class="timeline-title">Hands-on Guided Experiments</div>
                     <div class="timeline-desc">Step-by-step interactive activities and practical project building.</div>
                </div>
            </div>
            <div class="timeline-item">
                <div class="timeline-node"></div>
                <div class="timeline-content">
                     <div class="timeline-time">Phase 3</div>
                     <div class="timeline-title">Project Showcase & Certification</div>
                     <div class="timeline-desc">Demonstrate outcomes, receive official certification, and Q&A session.</div>
                </div>
            </div>
        """

    # Inclusions HTML
    inclusions_html = f"""
        <div class="inclusion-card">
            <h3>🎁 What's Included</h3>
            <ul>
                <li>✨ Complete Hands-on Workshop Kit & Learning Materials</li>
                <li>📘 Comprehensive Student Workbook</li>
                <li>🏅 Official {vendor} Certificate of Participation</li>
                <li>👨‍🏫 Expert Mentor Guidance Throughout the Session</li>
                <li>🎒 Custom Workspace Entry Badge</li>
            </ul>
        </div>
        <div class="inclusion-card">
            <h3>💡 Requirements</h3>
            <ul>
                <li>🎒 Recommended Age Group: {w.get("age_group", "10-16")} Years</li>
                <li>💻 All tools and equipment provided at the venue</li>
                <li>💧 Bring a personal water bottle for comfort</li>
                <li>🧠 No prior experience required — beginner friendly!</li>
                <li>🌟 Curiosity and eagerness to build and learn</li>
            </ul>
        </div>
    """

    reg_data = w.get("registration") or {}
    contact_email = reg_data.get("contact_email") or w.get("sales_team_email") or "sales@kiddypi.com"

    category_badge = (content_data.get("course_category")) or "KIDDYPI WORKSHOP"
    about_pills_list = []
    if w.get("age_group"):
        about_pills_list.append(f'<span class="pill-tag">Ages {w["age_group"]}</span>')
    for t in (w.get("topics") or learning_outcomes)[:4]:
        about_pills_list.append(f'<span class="pill-tag">{t}</span>')
    if not about_pills_list:
        about_pills_list = ['<span class="pill-tag">Hands-on STEM</span>', '<span class="pill-tag">Guided Experiments</span>']
    about_pills_html = "\n".join(about_pills_list)

    # Replacements
    badge_text = f"{w.get('date', '')} — WORKSHOP".strip(" —") if w.get('date') else "UPCOMING WORKSHOP"
    html = html.replace("{{WORKSHOP_BRAND}}", vendor)
    html = html.replace("{{WORKSHOP_BADGE}}", badge_text)
    html = html.replace("{{WORKSHOP_CATEGORY_BADGE}}", category_badge.upper())
    html = html.replace("{{ABOUT_PILLS_HTML}}", about_pills_html)
    html = html.replace("{{WORKSHOP_ID}}", w["id"])
    html = html.replace("{{WORKSHOP_NAME}}", w["name"])
    html = html.replace("{{WORKSHOP_DESCRIPTION}}", w["description"])
    html = html.replace("{{WORKSHOP_DATE}}", w.get("date", ""))
    html = html.replace("{{WORKSHOP_TIME}}", w.get("time", ""))
    html = html.replace("{{WORKSHOP_DURATION}}", w.get("duration", ""))
    html = html.replace("{{WORKSHOP_VENUE}}", w.get("venue", ""))
    html = html.replace("{{WORKSHOP_PRICE}}", str(int(w.get("price") or 0)))
    html = html.replace("{{WORKSHOP_AGE}}", str(w.get("age_group") or ""))
    html = html.replace("{{SHOPIFY_STORE_URL}}", store_url)
    html = html.replace("{{VARIANT_ID}}", variant_id)
    html = html.replace("{{CONTACT_EMAIL}}", contact_email)

    marketing = w.get("marketing") or {}
    html = html.replace("{{CAMPAIGN_HEADLINE}}", marketing.get("campaign_headline", f"HANDS-ON {w['name'].upper()} FOR YOUNG INNOVATORS"))
    html = html.replace("{{SHORT_DESCRIPTION}}", marketing.get("short_description", w["description"]))
    html = html.replace("{{LONG_COPY}}", marketing.get("long_copy", w["description"]))

    html = html.replace("{{HIGHLIGHTS_HTML}}", highlights_html)
    html = html.replace("{{TIMELINE_HTML}}", timeline_html)
    html = html.replace("{{INCLUSIONS_HTML}}", inclusions_html)
    html = html.replace("{{INSTRUCTOR_HTML}}", inst_html)

    html = html.replace("{{HERO_IMAGE}}", images["hero"])
    html = html.replace("{{LIFESTYLE_IMAGE}}", images["lifestyle"])
    html = html.replace("{{BANNER_IMAGE}}", images["banner"])
    html = html.replace("{{CLASSROOM_IMAGE}}", images["classroom"])
    html = html.replace("{{THUMBNAIL_IMAGE}}", images["thumbnail"])
    html = html.replace("{{CERTIFICATE_IMAGE}}", images["certificate"])
    html = html.replace("{{GALLERY_IMAGE_1}}", images["gallery1"])
    html = html.replace("{{GALLERY_IMAGE_2}}", images["gallery2"])
    html = html.replace("{{POSTER_IMAGE}}", w.get("poster_path") or images["hero"])
    
    # pyrefly: ignore [missing-import]
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


oauth_states: Dict[str, str] = {}  # state -> shop


@app.get("/api/shopify/install")
async def shopify_install(shop: str, request: Request):
    """
    Initiates the Shopify OAuth flow. Redirects the merchant to Shopify's
    authorization page.
    """
    if not shop:
        raise HTTPException(status_code=400, detail="Missing shop parameter")
    
    # Normalize shop parameter
    shop = shop.strip().replace("https://", "").replace("http://", "").split("/")[0]
    if "." not in shop:
        shop = f"{shop}.myshopify.com"
        
    state = str(uuid.uuid4())
    oauth_states[state] = shop
    
    client_id = settings.shopify_client_id
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="SHOPIFY_CLIENT_ID is not configured in environment."
        )
        
    scopes = "read_products,write_products,read_inventory,write_inventory,read_themes,read_locations"
    
    # Resolve redirect URI (settings app URL, settings override or dynamically from request)
    redirect_uri = settings.shopify_redirect_uri
    if not redirect_uri:
        if settings.shopify_app_url:
            redirect_uri = f"{settings.shopify_app_url.rstrip('/')}/api/shopify/callback"
        else:
            redirect_uri = f"{request.url.scheme}://{request.url.netloc}/api/shopify/callback"
        
    authorization_url = (
        f"https://{shop}/admin/oauth/authorize"
        f"?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return RedirectResponse(url=authorization_url)


@app.get("/api/shopify/callback")
async def shopify_callback(request: Request):
    """
    Handles the Shopify OAuth callback, validates state and HMAC,
    exchanges the authorization code for an access token, and stores it.
    """
    query_params = dict(request.query_params)
    code = query_params.get("code")
    shop = query_params.get("shop")
    state = query_params.get("state")
    
    if not code or not shop or not state:
        raise HTTPException(status_code=400, detail="Missing query parameters (code, shop, or state)")
        
    # Verify HMAC signature first (cryptographically validates request came from Shopify)
    client_secret = settings.shopify_client_secret
    if not client_secret:
        raise HTTPException(
            status_code=500,
            detail="SHOPIFY_CLIENT_SECRET is not configured in environment."
        )
        
    if not verify_shopify_hmac(query_params, client_secret):
        raise HTTPException(status_code=400, detail="HMAC signature verification failed")

    # Clean stored state if present
    oauth_states.pop(state, None)
        
    # Exchange authorization code for permanent access token
    token_url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": settings.shopify_client_id,
        "client_secret": client_secret,
        "code": code
    }
    
    # pyrefly: ignore [missing-import]
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(token_url, json=payload, timeout=15)
            res.raise_for_status()
            token_data = res.json()
            access_token = token_data.get("access_token")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Shopify token exchange rejected: {exc.response.text}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to exchange code: {exc}"
        )
        
    if not access_token:
        raise HTTPException(status_code=500, detail="Shopify did not return an access token.")
        
    # Persist token securely for both returned shop domain and configured SHOPIFY_STORE_URL
    from services.firebase_service import save_shopify_token
    save_shopify_token(shop, access_token)
    if settings.shopify_store_url and settings.shopify_store_url != shop:
        save_shopify_token(settings.shopify_store_url, access_token)
    
# ==============================================================================
# PRODUCT VALIDATION API ENDPOINTS (53-Check Matrix Module)
# ==============================================================================
_validation_state = {
    "status": "idle",
    "message": "",
    "started_at": None,
    "completed_at": None
}


def _execute_validation_job():
    global _validation_state
    _validation_state["status"] = "running"
    _validation_state["message"] = "Running 53 checks across 26 products..."
    _validation_state["started_at"] = datetime.now().isoformat()
    try:
        import subprocess
        python_exe = sys.executable
        cwd = os.path.dirname(os.path.abspath(__file__))
        proc = subprocess.run(
            [python_exe, "run_unified_validation.py", "--run-api"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        if proc.returncode == 0:
            _validation_state["status"] = "idle"
            _validation_state["message"] = "Validation audit completed successfully."
            _validation_state["completed_at"] = datetime.now().isoformat()

            # Record in history log
            history_file = os.path.join(OUTPUTS_DIR, "validation_history.json")
            history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except Exception:
                    history = []

            summary_file = os.path.join(OUTPUTS_DIR, "unified_summary_report.json")
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, "r", encoding="utf-8") as f:
                        s_data = json.load(f)
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "total_products": s_data.get("total_products", 0),
                        "average_score": s_data.get("average_score", 0),
                        "blocker_compliance_rate": round((s_data.get("blockers_passed", 0) / (s_data.get("blocker_evaluations", 1))) * 100, 2),
                        "launch_ready": s_data.get("launch_ready", 0),
                        "launch_blocked": s_data.get("launch_blocked", 0),
                        "total_blockers_failed": s_data.get("blockers_failed", 0),
                        "total_warnings": s_data.get("warnings_failed", 0)
                    }
                    history.append(entry)
                    with open(history_file, "w", encoding="utf-8") as f:
                        json.dump(history, f, indent=4)
                except Exception as ex:
                    logger.warning("Failed to update validation history: %s", ex)
        else:
            _validation_state["status"] = "failed"
            _validation_state["message"] = f"Audit failed: {proc.stderr[:200]}"
    except Exception as e:
        logger.exception("Error executing background validation job")
        _validation_state["status"] = "failed"
        _validation_state["message"] = str(e)


@app.get("/api/validation/summary")
def get_validation_summary():
    """Serves unified_summary_report.json, last_validated timestamp, and audit history."""
    summary_path = os.path.join(OUTPUTS_DIR, "unified_summary_report.json")
    if not os.path.exists(summary_path):
        raise HTTPException(status_code=404, detail="unified_summary_report.json not found. Run validation audit first.")

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        mtime = os.path.getmtime(summary_path)
        last_validated = datetime.fromtimestamp(mtime).isoformat()

        history_path = os.path.join(OUTPUTS_DIR, "validation_history.json")
        history = []
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        return {
            "summary": summary,
            "last_validated": last_validated,
            "status": _validation_state["status"],
            "message": _validation_state["message"],
            "history": history
        }
    except Exception as e:
        logger.exception("Failed to read validation summary")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/validation/products")
def get_validation_products():
    """Serves unified_validation_report.json list of audited products."""
    report_path = os.path.join(OUTPUTS_DIR, "unified_validation_report.json")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="unified_validation_report.json not found. Run validation audit first.")

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            products = json.load(f)
        return products
    except Exception as e:
        logger.exception("Failed to read validation report")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/validation/media-completeness")
def get_media_completeness_report():
    """Serves downloadable outputs/media_completeness_report.json."""
    report_path = os.path.join(OUTPUTS_DIR, "media_completeness_report.json")
    if not os.path.exists(report_path):
        # Auto-generate if missing
        try:
            import subprocess
            subprocess.run([sys.executable, "run_media_completeness_audit.py"], check=True)
        except Exception as e:
            logger.warning("Failed to auto-generate media completeness report: %s", e)

    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="media_completeness_report.json not found. Run 'python run_media_completeness_audit.py' first.")

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("Failed to read media completeness report")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/validation/media-completeness/download/{ext}")
def download_media_completeness_report(ext: str):
    """Downloads the latest generated media completeness report file (.xlsx, .csv, .pdf)."""
    ext = ext.lower().strip(".")
    if ext not in ("xlsx", "csv", "pdf"):
        raise HTTPException(status_code=400, detail="Invalid format. Supported: xlsx, csv, pdf")
    
    files = [f for f in os.listdir(OUTPUTS_DIR) if f.startswith("media_completeness_audit_") and f.endswith(f".{ext}")]
    if not files:
        raise HTTPException(status_code=404, detail=f"No media completeness {ext} report found.")
    files.sort(reverse=True)
    latest_file = os.path.join(OUTPUTS_DIR, files[0])
    
    media_types = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "pdf": "application/pdf"
    }
    return FileResponse(
        latest_file,
        media_type=media_types.get(ext, "application/octet-stream"),
        filename=os.path.basename(latest_file)
    )


@app.get("/api/validation/products/{product_name:path}")
def get_validation_product_detail(product_name: str):
    """Serves detailed check results for a single product from unified validation report."""
    report_path = os.path.join(OUTPUTS_DIR, "unified_validation_report.json")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="unified_validation_report.json not found.")

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            products = json.load(f)
        
        from urllib.parse import unquote
        decoded_name = unquote(product_name).strip().lower()

        for p in products:
            if p.get("product_name", "").strip().lower() == decoded_name:
                return p

        # Fallback partial match
        for p in products:
            if decoded_name in p.get("product_name", "").strip().lower():
                return p

        raise HTTPException(status_code=404, detail=f"Product '{product_name}' not found in unified validation report.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to read product detail")
        raise HTTPException(status_code=500, detail=str(e))


class ExportPDFInput(BaseModel):
    product_ids: Optional[List[str]] = None
    assignee_name: Optional[str] = "Rachana"


@app.post("/api/validation/export-pdf")
def export_validation_pdf(data: Optional[ExportPDFInput] = None):
    """Generates and streams a PDF audit report for selected products or all active products."""
    # pyrefly: ignore [missing-import]
    from fastapi.responses import Response
    from services.pdf_export_service import generate_validation_pdf_report

    report_path = os.path.join(OUTPUTS_DIR, "unified_validation_report.json")
    if not os.path.exists(report_path):
        report_path = os.path.join(OUTPUTS_DIR, "validation_report.json")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Validation report not found. Run validation audit first.")

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            products = json.load(f)

        selected_ids = data.product_ids if data and data.product_ids else None
        assignee = data.assignee_name if data and data.assignee_name else "Rachana"

        pdf_bytes = generate_validation_pdf_report(
            products=products,
            selected_identifiers=selected_ids,
            assignee_name=assignee
        )

        filename = "Shopify_Product_Validation_Audit_Report.pdf"
        if selected_ids:
            filename = f"Shopify_Product_Validation_Audit_Report_{len(selected_ids)}_Selected_Products.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.exception("Failed to generate PDF audit report")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/validation/export-pdf")
def export_validation_pdf_get(assignee: Optional[str] = "Rachana"):
    """GET endpoint to stream full audit report PDF for active products."""
    return export_validation_pdf(ExportPDFInput(product_ids=None, assignee_name=assignee))



@app.get("/api/products/{product_id:path}/remediations")
def get_product_remediations(product_id: str):
    """Generates and returns remediation suggestions for a specific product."""
    clean_pid = product_id.replace("gid://shopify/Product/", "").strip()
    products = []
    
    report_path = os.path.join(OUTPUTS_DIR, "unified_validation_report.json")
    if not os.path.exists(report_path):
        report_path = os.path.join(OUTPUTS_DIR, "validation_report.json")
    
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                products = json.load(f)
        except Exception:
            products = []

    try:
        target_prod = None
        for p in products:
            pid = str(p.get("product_id") or p.get("id") or "")
            pname = p.get("product_name") or p.get("title") or ""
            if (clean_pid and clean_pid in pid) or (pid and pid in product_id) or (pname and product_id.lower() in pname.lower()):
                target_prod = p
                break

        if not target_prod:
            try:
                from shopify_client import get_validation_client
                client = get_validation_client()
                all_prods = client.fetch_all_products()
                for p in all_prods:
                    pid = str(p.get("id") or p.get("product_id") or "")
                    pname = p.get("title") or p.get("product_name") or ""
                    if (clean_pid and clean_pid in pid) or (pid and pid in product_id) or (pname and product_id.lower() in pname.lower()):
                        target_prod = p
                        break
            except Exception as ex:
                logger.warning("Shopify fallback lookup failed: %s", ex)

        if not target_prod:
            raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")

        from services.remediation_engine import generate_remediations_for_product
        remediations = generate_remediations_for_product(target_prod)
        return [r.to_dict() for r in remediations]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate remediations for product %s", product_id)
        raise HTTPException(status_code=500, detail=str(e))


class ApplyRemediationInput(BaseModel):
    proposed_value: Optional[Any] = None


@app.post("/api/products/{product_id:path}/remediations/{remediation_id:path}/apply")
def api_apply_remediation(
    product_id: str,
    remediation_id: str,
    input_data: Optional[ApplyRemediationInput] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Applies an explicit user-approved remediation change to Shopify,
    records an audit log entry, and automatically re-validates the product.
    """
    from services.remediation_engine import apply_remediation
    try:
        user_email = current_user.email if current_user else "system-user@kiddypi.com"
        override_val = input_data.proposed_value if input_data else None
        res = apply_remediation(
            product_id=product_id,
            remediation_id=remediation_id,
            proposed_value_override=override_val,
            user_email=user_email
        )
        if isinstance(res, dict) and res.get("status") == "SUCCESS":
            res["validation_refreshed"] = True
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re_err:
        raise HTTPException(status_code=502, detail=str(re_err))
    except Exception as e:
        logger.exception("Unexpected error applying remediation %s for product %s", remediation_id, product_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products/{product_id:path}/remediations/safe-batch-preview")
def api_get_product_safe_batch_preview(product_id: str):
    """Returns all pending SAFE_AUTO_FIX remediations for the specified product ONLY."""
    try:
        from shopify_client import get_validation_client
        from services.remediation_engine import generate_remediations_for_product, FIX_TYPE_SAFE_AUTO_FIX
        client = get_validation_client()
        all_products = client.fetch_all_products()

        target_prod = None
        for p in all_products:
            pid = str(p.get("id") or p.get("product_id") or "")
            if pid == str(product_id) or str(product_id) in pid or product_id.lower() in (p.get("title") or "").lower():
                target_prod = p
                break

        if not target_prod:
            raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")

        remediations = generate_remediations_for_product(target_prod)
        safe_rems = [r.to_dict() for r in remediations if r.fix_type == FIX_TYPE_SAFE_AUTO_FIX and r.can_auto_fix]

        return {
            "product_id": str(target_prod.get("id")),
            "product_name": target_prod.get("title") or target_prod.get("product_name"),
            "safe_fixes_count": len(safe_rems),
            "safe_fixes": safe_rems
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get safe batch preview for product %s", product_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/{product_id:path}/remediations/apply-all-safe")
def api_apply_product_all_safe_remediations(
    product_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Applies all SAFE_AUTO_FIX remediations for the specified CURRENT PRODUCT ONLY.
    Does NOT affect other products in the catalog.
    """
    from services.remediation_engine import apply_all_safe_remediations
    try:
        user_email = current_user.email if current_user else "system-user@kiddypi.com"
        res = apply_all_safe_remediations(product_id=product_id, user_email=user_email)
        if isinstance(res, dict):
            res["validation_refreshed"] = True
        return res
    except Exception as e:
        logger.exception("Unexpected error applying safe remediations for product %s", product_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/{product_id:path}/remediations/rule-11/transform-preview")
def api_rule11_transform_preview(product_id: str):
    """
    Non-mutating preview endpoint for Rule 11 square aspect ratio conversion.
    Pads existing Shopify image to 1:1 using Pillow.
    Performs ZERO Shopify API mutations.
    """
    try:
        from shopify_client import get_validation_client
        from services.remediation_engine import generate_remediations_for_product, transform_image_to_square_padded
        client = get_validation_client()
        all_products = client.fetch_all_products()

        target_prod = None
        for p in all_products:
            pid = str(p.get("id") or p.get("product_id") or "")
            if pid == str(product_id) or str(product_id) in pid or product_id.lower() in (p.get("title") or "").lower():
                target_prod = p
                break

        if not target_prod:
            raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")

        rems = generate_remediations_for_product(target_prod)
        rule11_rem = next((r for r in rems if r.rule_id == "11"), None)
        img_url = rule11_rem.image_url if rule11_rem else None
        if not img_url and target_prod.get("images"):
            img_url = target_prod["images"][0].get("url") or target_prod["images"][0].get("src")

        if not img_url:
            raise HTTPException(status_code=400, detail="No active product image found to transform.")

        transformed = transform_image_to_square_padded(img_url)
        import base64
        b64_img = base64.b64encode(transformed["image_bytes"]).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_img}"

        return {
            "product_id": product_id,
            "rule_id": "11",
            "rule_name": "Square Aspect Ratio",
            "before_url": img_url,
            "before_dimensions": transformed["before_dimensions"],
            "after_dimensions": transformed["after_dimensions"],
            "preview_data_url": data_url,
            "badges": {
                "original_pixels_preserved": True,
                "crop": "None",
                "regeneration": "None",
                "layout_change": "None"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate Rule 11 transform preview for product %s", product_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/{product_id:path}/remediations/rule-11/upload-custom")
async def api_upload_custom_image_remediation(
    product_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Handles user-uploaded custom replacement image for Rule 11 remediation.
    """
    try:
        from shopify_client import get_validation_client
        from services.shopify_media_service import ShopifyMediaService
        from services.remediation_engine import log_remediation_audit
        client = get_validation_client()
        all_products = client.fetch_all_products()

        target_prod = None
        for p in all_products:
            pid = str(p.get("id") or p.get("product_id") or "")
            if pid == str(product_id) or str(product_id) in pid:
                target_prod = p
                break

        if not target_prod and all_products:
            target_prod = all_products[0]

        outputs_dir = os.path.abspath(os.path.join(OUTPUTS_DIR, "remediated_images"))
        os.makedirs(outputs_dir, exist_ok=True)
        custom_file_path = os.path.join(outputs_dir, f"{product_id}_custom_{file.filename}")

        contents = await file.read()
        with open(custom_file_path, "wb") as f:
            f.write(contents)

        upload_res = ShopifyMediaService.retry_upload(target_prod.get("id"), custom_file_path)
        if not upload_res.get("success"):
            raise HTTPException(status_code=502, detail=f"Custom image upload failed: {upload_res.get('error')}")

        user_email = current_user.email if current_user else "system-user@kiddypi.com"
        audit_entry = log_remediation_audit(
            user_email=user_email,
            product_id=product_id,
            variant_id=None,
            rule_id="11",
            field="images",
            old_value="Non-square image",
            new_value=f"Custom uploaded image ({file.filename})",
            shopify_response=upload_res,
            success=True
        )

        if upload_res.get("success"):
            try:
                from agents.product_validation_agent import validate_products_checklist_tool
                from services.remediation_engine import update_saved_validation_result_for_product
                class SingleProductToolContext:
                    def __init__(self, prods):
                        self.state = {"validation_products": prods}
                tool_ctx = SingleProductToolContext([target_prod])
                validate_products_checklist_tool(tool_ctx)
                revalidated = tool_ctx.state.get("validation_results") or []
                if revalidated:
                    update_saved_validation_result_for_product(revalidated[0])
            except Exception as ve:
                logger.error("Failed to revalidate single product post-upload: %s", ve)

        return {
            "status": "SUCCESS",
            "message": "Custom replacement image uploaded successfully and catalog revalidated.",
            "upload_result": upload_res,
            "audit_entry": audit_entry,
            "validation_refreshed": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to upload custom replacement image for product %s", product_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/{product_id:path}/revalidate")
def api_revalidate_product(product_id: str):
    """Re-runs the 53-check validation checklist against Shopify for a single product."""
    try:
        from shopify_client import get_validation_client
        from services.remediation_engine import update_saved_validation_result_for_product
        client = get_validation_client()
        clean_pid = str(product_id).replace("gid://shopify/Product/", "").strip()
        target_prod = None
        try:
            if clean_pid and clean_pid.isdigit():
                target_prod = client.get_product(clean_pid)
        except Exception:
            pass

        if not target_prod:
            all_products = client.fetch_all_products()
            for p in all_products:
                pid = str(p.get("id") or p.get("product_id") or "")
                if pid == str(product_id) or str(product_id) in pid or product_id.lower() in (p.get("title") or "").lower():
                    target_prod = p
                    break

        if not target_prod and all_products:
            target_prod = all_products[0]

        from agents.product_validation_agent import validate_products_checklist_tool
        class SingleProductToolContext:
            def __init__(self, prods):
                self.state = {"validation_products": prods}

        ctx = SingleProductToolContext([target_prod] if target_prod else all_products)
        validate_products_checklist_tool(ctx)
        val_results = ctx.state.get("validation_results") or []
        updated_res = val_results[0] if val_results else {}
        
        if updated_res:
            update_saved_validation_result_for_product(updated_res)

        return {
            "status": "SUCCESS",
            "message": f"Product '{product_id}' successfully revalidated.",
            "validation_result": updated_res
        }
    except Exception as e:
        logger.exception("Failed to revalidate product %s", product_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validation/remediations/apply-all-safe-catalog")
def api_catalog_wide_apply_all_safe_remediations(current_user: User = Depends(get_current_user)):
    """
    Explicitly named catalog-wide batch safe fix feature.
    Batch applies SAFE_AUTO_FIX remediations across all active products in the store.
    """
    from services.remediation_engine import apply_all_safe_remediations
    try:
        user_email = current_user.email if current_user else "system-user@kiddypi.com"
        res = apply_all_safe_remediations(product_id=None, user_email=user_email)
        if isinstance(res, dict) and res.get("applied_count", 0) > 0:
            try:
                _execute_validation_job()
                res["validation_refreshed"] = True
                res["validation_message"] = _validation_state.get("message")
            except Exception as ve:
                logger.error("Failed to run post-remediation full catalog validation: %s", ve)
                res["validation_refreshed"] = False
        return res
    except Exception as e:
        logger.exception("Failed to execute catalog-wide apply-all-safe remediations")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validation/run", status_code=202)
def run_validation_audit(background_tasks: BackgroundTasks):
    """Triggers the 53-check product validation audit in the background."""
    global _validation_state
    if _validation_state["status"] == "running":
        return {
            "status": "running",
            "message": "Validation audit is already in progress.",
            "started_at": _validation_state["started_at"]
        }

    background_tasks.add_task(_execute_validation_job)
    _validation_state["status"] = "running"
    _validation_state["message"] = "Running 53 checks across 26 products..."
    _validation_state["started_at"] = datetime.now().isoformat()

    return {
        "status": "started",
        "message": "Validation audit started: Running 53 checks across 26 products...",
        "started_at": _validation_state["started_at"]
    }


@app.get("/api/validation/status")
def get_validation_run_status():
    """Returns the current execution status of the validation background job."""
    return _validation_state


@app.get("/health")
def health():
    # Firebase connectivity status
    firebase_status = "unconfigured"
    try:
        from services.firebase_service import initialize_firebase
        db_client = initialize_firebase()
        if db_client is not None:
            firebase_status = "connected"
        else:
            firebase_status = "mock"
    except Exception:
        firebase_status = "failed"

    # Shopify connectivity status
    shopify_status = "unconfigured"
    if settings.shopify_store_url:
        try:
            from shopify_client import _get_config
            # pyrefly: ignore [missing-import]
            import httpx
            base_url, store_url, headers = _get_config()
            res = httpx.get(f"{base_url}/shop.json", headers=headers, timeout=3)
            if res.status_code == 200:
                shopify_status = "connected"
            else:
                shopify_status = f"error_status_{res.status_code}"
        except Exception as e:
            shopify_status = f"failed_{str(type(e).__name__)}"

    # Overall status (Phase 5 Part 13): previously this endpoint always
    # returned "healthy" regardless of what Shopify/Firestore actually
    # reported below it, which makes it useless for real monitoring/alerting
    # -- a broken Shopify connection would still show a green "healthy".
    # Shopify is required for the core publish path, so any non-"connected"
    # Shopify state degrades the overall status. Firestore has an
    # intentional, working mock fallback (local JSON) elsewhere in this
    # codebase, so "mock" is not itself unhealthy -- only an outright
    # Firebase failure is.
    if shopify_status != "connected":
        overall_status = "degraded"
    elif firebase_status == "failed":
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "adk_ready": True,
        "runner": True,
        "shopify_connectivity": shopify_status,
        "firestore_connectivity": firebase_status,
    }



# ==============================================================================
# SEO Dashboard API Endpoints (Phase 3)
# ==============================================================================

class SEOProposalRequest(BaseModel):
    product_ids: Optional[List[str]] = None
    preserve_handles: bool = True


class SEOApplyRequest(BaseModel):
    approved_proposals: List[Dict[str, Any]]
    dry_run: bool = True  # Safe default: dry-run unless explicitly approved as live!
    preserve_handles: bool = True


@app.get("/api/seo/audit")
def get_seo_audit(
    search: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]))
):
    """Fetches or computes catalogue SEO audit with search and severity filters."""
    from workflow.seo_optimization_workflow import SEOOptimizationWorkflow
    report_path = os.path.join(OUTPUTS_DIR, "seo_audit_report.json")
    try:
        audit = SEOOptimizationWorkflow.run_catalogue_audit()
    except Exception as e:
        logger.warning("Live SEO catalogue audit failed (%s); attempting fallback to cached report at %s", e, report_path)
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                audit = json.load(f)
        else:
            raise HTTPException(status_code=503, detail=f"Shopify catalogue audit unavailable and no cached report found: {e}")
    products = audit.get("products", [])

    if search:
        s_lower = search.lower().strip()
        products = [
            p for p in products
            if s_lower in p.get("title", "").lower() or s_lower in p.get("handle", "").lower()
        ]

    if status and status.upper() != "ALL":
        products = [p for p in products if p.get("status") == status.upper()]

    if severity and severity.upper() != "ALL":
        target_sev = severity.upper()
        products = [
            p for p in products
            if any(i.get("severity") == target_sev for i in p.get("issues", []))
        ]

    audit_copy = dict(audit)
    audit_copy["products"] = products
    audit_copy["filtered_count"] = len(products)
    return audit_copy


@app.get("/api/seo/proposals")
def get_seo_proposals(
    product_id: Optional[str] = None,
    preserve_handles: bool = True,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]))
):
    """Generates or retrieves Before-and-After SEO optimization proposals (dry-run)."""
    from workflow.seo_optimization_workflow import SEOOptimizationWorkflow
    p_ids = [product_id] if product_id else None
    return SEOOptimizationWorkflow.generate_proposals(product_ids=p_ids, preserve_handles=preserve_handles)


@app.post("/api/seo/proposals")
def create_seo_proposals(
    req: SEOProposalRequest,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]))
):
    """Generates SEO proposals on demand for selected products or whole catalogue."""
    from workflow.seo_optimization_workflow import SEOOptimizationWorkflow
    return SEOOptimizationWorkflow.generate_proposals(
        product_ids=req.product_ids,
        preserve_handles=req.preserve_handles
    )


@app.post("/api/seo/apply")
def apply_seo_optimizations(
    req: SEOApplyRequest,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]))
):
    """Applies approved SEO proposals with strict safety boundaries and verification."""
    from workflow.seo_optimization_workflow import SEOOptimizationWorkflow
    if not req.approved_proposals:
        raise HTTPException(status_code=400, detail="No approved proposals provided.")

    # Guard: CATALOGUE_ADMIN can run dry-run simulations freely, but live updates require APPROVER or PLATFORM_ADMIN
    if not req.dry_run and current_user.role not in ["APPROVER", "PLATFORM_ADMIN"]:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: user role '{current_user.role}' lacks privileges for live Shopify mutations. Live updates require an APPROVER or PLATFORM_ADMIN."
        )

    summary = SEOOptimizationWorkflow.apply_approved_optimizations(
        approved_proposals=req.approved_proposals,
        user_email=current_user.email,
        dry_run=req.dry_run
    )
    return summary


@app.get("/api/seo/history")
def get_seo_history(
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]))
):
    """Retrieves historical SEO optimization audit logs and execution runs."""
    history_path = os.path.join(OUTPUTS_DIR, "seo_optimization_history.json")
    if os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Error reading SEO history log: %s", e)
    return []



class GSCOAuthExchangeRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None


@app.get("/api/seo/search-console/status")
def get_search_console_status(
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]))
):
    """Retrieves Google Search Console connection and authorization diagnostics."""
    from services.google_search_console_service import GoogleSearchConsoleService
    svc = GoogleSearchConsoleService()
    return svc.get_service_status()


@app.get("/api/seo/search-console/auth-url")
def get_search_console_auth_url(
    redirect_uri: Optional[str] = None,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "PLATFORM_ADMIN", "APPROVER"]))
):
    """Generates read-only Google OAuth 2.0 authorization consent URL."""
    from services.google_search_console_service import GoogleSearchConsoleService
    svc = GoogleSearchConsoleService(redirect_uri=redirect_uri)
    return svc.get_authorization_url()


@app.get("/api/seo/search-console/oauth/callback")
def search_console_oauth_callback_get(code: Optional[str] = None, error: Optional[str] = None):
    """Handles browser redirect callback from Google OAuth 2.0 consent flow."""
    if error:
        return HTMLResponse(
            f"<h3>Google Authentication Failed</h3><p>{error}</p><a href='/'>Return to Dashboard</a>",
            status_code=400
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code from Google redirect.")

    from services.google_search_console_service import GoogleSearchConsoleService
    svc = GoogleSearchConsoleService()
    res = svc.exchange_code(code)
    if not res.get("success"):
        return HTMLResponse(
            f"<h3>Connection Failed</h3><p>{res.get('error')}</p><a href='/'>Return to Dashboard</a>",
            status_code=400
        )

    return HTMLResponse(
        """
        <html>
          <head><title>Google Search Console Connected</title></head>
          <body style="font-family: sans-serif; text-align: center; padding: 40px;">
            <h2 style="color: #059669;">✓ Google Search Console Connected Successfully</h2>
            <p>Your read-only search performance integration is now active.</p>
            <p><a href="/" style="display: inline-block; background: #2563EB; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600;">Return to SEO Dashboard</a></p>
          </body>
        </html>
        """
    )


@app.post("/api/seo/search-console/oauth/callback")
def search_console_oauth_callback(
    req: GSCOAuthExchangeRequest,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "PLATFORM_ADMIN", "APPROVER"]))
):
    """Exchanges Google authorization code for server-side tokens."""
    from services.google_search_console_service import GoogleSearchConsoleService
    svc = GoogleSearchConsoleService()
    res = svc.exchange_code(req.code, redirect_uri=req.redirect_uri)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to exchange token"))
    return res


@app.get("/api/seo/search-console/verify")
def verify_search_console_property(
    site_url: Optional[str] = None,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]))
):
    """Explicitly verifies ownership and permissions for the target GSC website property."""
    from services.google_search_console_service import GoogleSearchConsoleService
    svc = GoogleSearchConsoleService(site_url=site_url)
    return svc.verify_site_property()


@app.post("/api/seo/search-console/refresh")
def refresh_search_console_token(
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "PLATFORM_ADMIN", "APPROVER"]))
):
    """Refreshes Google Search Console access token server-side."""
    from services.google_search_console_service import GoogleSearchConsoleService
    svc = GoogleSearchConsoleService()
    new_token = svc.refresh_access_token()
    if not new_token:
        raise HTTPException(status_code=400, detail="Could not refresh Google Search Console credentials.")
    return {"success": True, "message": "Google Search Console token refreshed successfully.", "status": svc.get_service_status()}


@app.get("/api/seo/search-console/performance")
def get_search_console_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    row_limit: int = 250,
    current_user: User = Depends(require_role(["CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"]))
):
    """Fetches organic search performance metrics mapped to Shopify products."""
    from services.google_search_console_service import GoogleSearchConsoleService
    from workflow.seo_optimization_workflow import SEOOptimizationWorkflow
    from datetime import datetime, timezone, timedelta

    # Default to past 28 days if unspecified
    if not end_date:
        end_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    svc = GoogleSearchConsoleService()
    gsc_res = svc.fetch_search_analytics(
        start_date=start_date,
        end_date=end_date,
        dimensions=["page", "query"],
        row_limit=row_limit
    )

    if not gsc_res.get("success"):
        return gsc_res

    # Map page URLs to Shopify catalogue
    try:
        shopify_products = SEOOptimizationWorkflow.fetch_all_products_paginated()
    except Exception as e:
        logger.warning("Could not fetch Shopify products for mapping: %s", e)
        shopify_products = []

    mapping = GoogleSearchConsoleService.map_search_console_to_shopify(
        gsc_rows=gsc_res.get("rows", []),
        shopify_products=shopify_products
    )

    return {
        "success": True,
        "status": gsc_res.get("status"),
        "site_url": gsc_res.get("site_url"),
        "date_range": gsc_res.get("date_range"),
        "summary": gsc_res.get("summary"),
        "top_queries": gsc_res.get("top_queries", []),
        "shopify_mapping": mapping,
        "disclaimer": gsc_res.get("disclaimer"),
    }


if __name__ == "__main__":

    # pyrefly: ignore [missing-import]
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
# Reload trigger comment to refresh env values