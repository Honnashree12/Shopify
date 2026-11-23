"""Regression tests for the "'NoneType' object has no attribute 'state'" failure.

Root cause (reproduced): the old run_folder_workflow_background treated a
None return from InMemorySessionService.get_session() as an existing session
(session_exists was set unconditionally) and then called session.state.update()
on None. These tests lock in the fixed behaviour and cover the Media stage:

A. images only
B. images + video
C. no media
D. media upload failure
E. staged upload failure
F. Create -> Media session/state propagation
G. actual Create from Folder workflow (real ADK runner, preview + resume)

SECOND root cause (found after the above fix, reproduced): the sync
Runner.run() google-adk provides drives the workflow inside a plain
threading.Thread with no exception capture (verified by reading
google/adk/runners.py and google/adk/platform/thread.py). If a tool raises
inside that thread, the exception prints to stderr and the thread dies, but
it never reaches run_folder_workflow_background's own except block -- so a
real bug anywhere in Ingest/Validate/Create/Media/Verify/Report was silently
swallowed and the dashboard fell through to unrelated downstream messages
instead of the real error. Fixed by driving run_async() directly via
asyncio.run() in the same thread, so tool/ADK exceptions propagate normally.

H. a tool exception during Ingest is caught with a full traceback, not
   silently swallowed by the Runner.run() thread/queue transport
I. get_session() returning None (documented, see bottom of file)
"""

import collections
import collections.abc
collections.Mapping = collections.abc.Mapping
collections.MutableMapping = collections.abc.MutableMapping
collections.Sequence = collections.abc.Sequence
collections.MutableSequence = collections.abc.MutableSequence
collections.Iterable = collections.abc.Iterable

import json
import os
import uuid
import pytest
from unittest.mock import patch, MagicMock

from tools.folder_tools import (
    create_shopify_product_tool,
    upload_folder_media_tool,
)
from services.shopify_media_service import ShopifyMediaService
from shopify_client import ShopifyAPIError


class MockToolContext:
    def __init__(self, state):
        self.state = state


def _media_state(tmp_path, images=0, videos=0, product_id=555001):
    imgs, vids = [], []
    for i in range(images):
        p = tmp_path / f"img_{i}.png"
        p.write_bytes(b"fakepng")
        imgs.append(str(p))
    for i in range(videos):
        p = tmp_path / f"vid_{i}.mp4"
        p.write_bytes(b"fakemp4")
        vids.append(str(p))
    return {
        "shopify_product_id": product_id,
        "approved_to_publish": True,
        "preview_mode": False,
        "detected_images": imgs,
        "detected_videos": vids,
    }


def _ok_upload(product_id, file_paths):
    return [
        {"success": True, "file_path": p, "media_id": f"gid://shopify/MediaImage/{i}"}
        for i, p in enumerate(file_paths)
    ]


# =====================================================================
# A. Images only
# =====================================================================
@patch.object(ShopifyMediaService, "verify_media", return_value=[{"id": "m1", "status": "READY"}])
@patch.object(ShopifyMediaService, "upload_and_attach_all_media", side_effect=_ok_upload)
def test_a_media_images_only(mock_upload, mock_verify, tmp_path):
    state = _media_state(tmp_path, images=2)
    res = upload_folder_media_tool(MockToolContext(state))

    assert "NoneType" not in res
    assert "successfully" in res
    assert len(state["media_upload_results"]) == 2
    assert state["shopify_media"] == [{"id": "m1", "status": "READY"}]


# =====================================================================
# B. Images + video
# =====================================================================
@patch.object(ShopifyMediaService, "verify_media", return_value=[])
@patch.object(ShopifyMediaService, "upload_and_attach_all_media", side_effect=_ok_upload)
def test_b_media_images_and_video(mock_upload, mock_verify, tmp_path):
    state = _media_state(tmp_path, images=2, videos=1)
    res = upload_folder_media_tool(MockToolContext(state))

    assert "NoneType" not in res
    assert "Uploaded 3 files" in res
    assert len(state["media_upload_results"]) == 3


# =====================================================================
# C. No media
# =====================================================================
@patch.object(ShopifyMediaService, "verify_media", return_value=[])
@patch.object(ShopifyMediaService, "upload_and_attach_all_media", side_effect=_ok_upload)
def test_c_no_media(mock_upload, mock_verify, tmp_path):
    state = _media_state(tmp_path, images=0, videos=0)
    res = upload_folder_media_tool(MockToolContext(state))

    assert "NoneType" not in res
    assert "Uploaded 0 files" in res
    assert state["media_upload_results"] == []


# =====================================================================
# D. Media upload failure -> real error surfaced, not a NoneType error
# =====================================================================
@patch.object(ShopifyMediaService, "verify_media", return_value=[])
@patch.object(
    ShopifyMediaService,
    "upload_and_attach_all_media",
    side_effect=lambda pid, paths: [
        {"success": False, "file_path": p, "error": "HTTP 500 from Shopify"} for p in paths
    ],
)
def test_d_media_upload_failure(mock_upload, mock_verify, tmp_path):
    state = _media_state(tmp_path, images=2)
    res = upload_folder_media_tool(MockToolContext(state))

    assert "NoneType" not in res
    assert "partial failures" in res
    assert "Uploaded 0/2" in res


# =====================================================================
# E. Staged upload failure -> retry wrapper returns a dict, never None
# =====================================================================
@patch(
    "services.shopify_media_service.upload_product_media_files",
    side_effect=ShopifyAPIError("stagedUploadsCreate did not return stagedTargets."),
)
def test_e_staged_upload_failure(mock_staged, tmp_path):
    p = tmp_path / "img.png"
    p.write_bytes(b"fakepng")

    result = ShopifyMediaService.retry_upload_media(555001, str(p), retries=1)

    assert result is not None
    assert result["success"] is False
    assert "stagedTargets" in result["error"]

    # And at tool level the workflow reports the real error, no NoneType.
    state = _media_state(tmp_path, images=0)
    state["detected_images"] = [str(p)]
    with patch.object(ShopifyMediaService, "verify_media", return_value=[]):
        res = upload_folder_media_tool(MockToolContext(state))
    assert "NoneType" not in res
    assert "partial failures" in res


# =====================================================================
# F. Create -> Media session/state propagation (same tool context)
# =====================================================================
@patch("tools.folder_tools.get_product_by_title", return_value=None)
@patch("tools.folder_tools.get_product_by_sku", return_value=None)
@patch("tools.folder_tools.create_product")
@patch.object(ShopifyMediaService, "verify_media", return_value=[])
@patch.object(ShopifyMediaService, "upload_and_attach_all_media", side_effect=_ok_upload)
def test_f_create_to_media_state_propagation(
    mock_upload, mock_verify, mock_create, mock_by_sku, mock_by_title, tmp_path, monkeypatch
):
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_KEY", raising=False)
    mock_create.return_value = {
        "id": 987654,
        "title": "Propagation Kit",
        "status": "draft",
        "price": 100.0,
        "url": "https://store/products/propagation-kit",
        "variants": [{"id": 1, "price": "100.0"}],
    }

    img = tmp_path / "hero.png"
    img.write_bytes(b"fakepng")
    state = {
        "product_name": "Propagation Kit",
        "product_description": "desc",
        "product_price": 100.0,
        "approved_to_publish": True,
        "approved_by_uid": "approver-uid",
        "approved_at": "2026-08-12T00:00:00Z",
        "approved_at_version": 1,
        "product_version": 1,
        "preview_mode": False,
        "duplicate_action": "CREATE",
        "detected_images": [str(img)],
        "detected_videos": [],
    }
    context = MockToolContext(state)

    create_res = create_shopify_product_tool(context)
    assert "NoneType" not in create_res
    assert state["shopify_product_id"] == 987654

    media_res = upload_folder_media_tool(context)
    assert "NoneType" not in media_res
    assert "successfully" in media_res
    # Media stage must receive the product id created by the Create stage.
    assert mock_upload.call_args_list[0][0][0] == 987654


# =====================================================================
# G. Actual Create from Folder workflow (real ADK runner, preview+resume)
# =====================================================================
def _install_fake_llm():
    """Deterministic Gemini replacement: each folder agent calls its tool once."""
    from google.adk.models import google_llm
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types as gtypes

    async def fake_generate_content_async(self, llm_request, stream=False):
        contents = llm_request.contents or []
        last = contents[-1] if contents else None
        has_fr = bool(
            last is not None
            and last.parts
            and any(getattr(p, "function_response", None) is not None for p in last.parts)
        )
        tool_names = []
        if llm_request.config and llm_request.config.tools:
            for t in llm_request.config.tools:
                for d in getattr(t, "function_declarations", None) or []:
                    tool_names.append(d.name)
        if has_fr or not tool_names:
            yield LlmResponse(
                content=gtypes.Content(role="model", parts=[gtypes.Part(text="Done.")])
            )
        else:
            yield LlmResponse(
                content=gtypes.Content(
                    role="model",
                    parts=[
                        gtypes.Part(
                            function_call=gtypes.FunctionCall(name=tool_names[0], args={})
                        )
                    ],
                )
            )

    return patch.object(google_llm.Gemini, "generate_content_async", fake_generate_content_async)


FAKE_MANIFEST = {
    "title": "Dummy STEM Kit",
    "description": "A dummy product for regression.",
    "price": 1499.0,
    "category": "Toys",
    "product_type": "Toys",
    "vendor": "DummyCo",
    "sku": "REGRESSION-01",
    "inventory_quantity": 5,
    "status": "DRAFT",
    "tags": ["stem"],
    "confidence": {},
    "conflicts": [],
    "missing_fields": [],
    "media_ranking": [],
}


def _fake_genai_client():
    client = MagicMock()
    resp = MagicMock()
    resp.text = json.dumps(FAKE_MANIFEST)
    client.models.generate_content.return_value = resp
    return client


def test_g_actual_create_from_folder_workflow(tmp_path, monkeypatch):
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_KEY", raising=False)

    import main
    from state import ProductLaunchState

    # Build a real product folder like the dashboard upload endpoint does.
    folder = tmp_path / "dummy_shopify_product"
    (folder / "images").mkdir(parents=True)
    (folder / "product.json").write_text(
        json.dumps({"title": "Dummy STEM Kit", "price": 1499.0, "sku": "REGRESSION-01"}),
        encoding="utf-8",
    )
    import base64
    (folder / "images" / "hero.png").write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
    )

    created = {
        "id": 424242,
        "title": "Dummy STEM Kit",
        "status": "draft",
        "price": 1499.0,
        "url": "https://store/products/dummy-stem-kit",
        "variants": [
            {"id": 1, "price": "1499.0", "sku": "REGRESSION-01", "inventory_quantity": 5}
        ],
    }

    session_id = str(uuid.uuid4())
    main.active_sessions[session_id] = ProductLaunchState(
        product_name="Folder Ingestion",
        raw_description="Ingesting product from folder...",
        product_folder_path=str(folder),
        status="pending",
        preview_mode=True,
        approved_to_publish=False,
    )

    with _install_fake_llm(), \
            patch("tools.folder_tools.get_genai_client", return_value=_fake_genai_client()), \
            patch("tools.folder_tools.get_product_by_sku", return_value=None), \
            patch("tools.folder_tools.get_product_by_title", return_value=None), \
            patch("tools.folder_tools.create_product", return_value=created), \
            patch("tools.folder_tools.get_product", return_value=created), \
            patch.object(ShopifyMediaService, "upload_and_attach_all_media", side_effect=_ok_upload), \
            patch.object(
                ShopifyMediaService,
                "verify_media",
                return_value=[{"id": "m1", "status": "READY", "mediaContentType": "IMAGE"}],
            ):
        # --- RUN 1: preview. The EXACT original failure happened here:
        # get_session() returns None for a fresh id and the old code called
        # None.state.update(). The fixed code must create the session instead.
        main.run_folder_workflow_background(session_id)
        state = main.active_sessions[session_id]
        err = json.dumps(state.errors)
        assert "'NoneType' object has no attribute 'state'" not in err, err
        assert state.status == "awaiting_approval", (state.status, err)

        # --- RUN 2: approve / resume on the same session id.
        state.status = "running"
        state.approved_to_publish = True
        state.approved_by_uid = "approver-uid"
        state.approved_at = "2026-08-12T00:00:00Z"
        state.approved_at_version = state.product_version
        state.duplicate_action = "CREATE"
        main.run_folder_workflow_background(session_id)

        state = main.active_sessions[session_id]
        err = json.dumps(state.errors)
        assert "'NoneType' object has no attribute 'state'" not in err, err
        assert state.status == "completed", (state.status, err)
        assert state.shopify_product_id == 424242
        # Media stage must actually have run and produced verified media.
        assert state.shopify_media, "media stage did not run"
        assert state.shopify_media[0]["status"] == "READY"

    main.active_sessions.pop(session_id, None)


# =====================================================================
# Root-cause documentation test: get_session returns None (does not raise)
# for unknown ids — the workflow must treat that as "no session yet".
# =====================================================================
def test_get_session_none_is_handled():
    import asyncio
    from workflow.adk_runner import session_service, APP_NAME
    from workflow.session_manager import USER_ID

    missing = asyncio.run(
        session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id="does-not-exist-" + str(uuid.uuid4())
        )
    )
    # This is the exact condition that triggered the original bug.
    assert missing is None


# =====================================================================
# H. A tool exception during Ingest must be caught with a full traceback,
# not silently swallowed by the Runner.run() thread/queue transport.
#
# This reproduces the SECOND bug: even after fixing the get_session()/None
# issue, a real exception raised inside any folder tool (ingest, validate,
# create, media, verify, report) never reached
# run_folder_workflow_background's own except block, because Runner.run()
# drives the workflow in a bare threading.Thread with no exception
# propagation back to the caller. The fix drives run_async() directly via
# asyncio.run() in the same thread instead.
# =====================================================================
def test_h_ingest_tool_exception_is_not_swallowed(tmp_path, monkeypatch):
    """Exercises main.run_folder_workflow_background's actual asyncio.run()
    consumption pattern (not the production folder_tools functions -- those
    have no bug of their own) against a throwaway Agent/Workflow/Runner whose
    single tool always raises. This isolates and locks in the FIX to the
    transport bug: main.py must catch the exception with a full traceback,
    not silently lose it the way Runner.run()'s bare-thread wrapper does.
    """
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_KEY", raising=False)

    import main
    from state import ProductLaunchState
    from google.adk import Agent, Workflow
    from google.adk.runners import Runner

    def _broken_tool(tool_context) -> str:
        x = None
        return x.state  # AttributeError: 'NoneType' object has no attribute 'state'

    broken_agent = Agent(
        name="BrokenIngestAgent",
        model="gemini-2.5-flash",
        instruction="Call _broken_tool().",
        tools=[_broken_tool],
    )
    broken_workflow = Workflow(name="BrokenFolderWorkflow", edges=[("START", broken_agent)])
    broken_runner = Runner(
        app_name=main.APP_NAME,
        agent=broken_workflow,
        session_service=main.session_service,
    )

    folder = tmp_path / "broken_ingest_product"
    folder.mkdir()
    (folder / "product.json").write_text(
        json.dumps({"title": "Broken Ingest", "price": 10.0}), encoding="utf-8"
    )

    session_id = str(uuid.uuid4())
    main.active_sessions[session_id] = ProductLaunchState(
        product_name="Folder Ingestion",
        raw_description="Ingesting product from folder...",
        product_folder_path=str(folder),
        status="pending",
        preview_mode=True,
        approved_to_publish=False,
    )

    with _install_fake_llm(), patch.object(main, "folder_runner", broken_runner):
        main.run_folder_workflow_background(session_id)

    state = main.active_sessions.pop(session_id)
    err = state.errors.get("workflow_error", "")

    # The real error must be present ...
    assert state.status == "failed"
    assert "NoneType" in err
    # ... AND it must carry a full traceback -- proof the exception was
    # actually caught by run_folder_workflow_background's except block,
    # not silently swallowed by the Runner.run() background thread.
    assert "Stack Trace:" in err, (
        "the tool exception was swallowed again -- Runner.run()'s thread "
        "transport regressed"
    )
    assert "_broken_tool" in err or "AttributeError" in err
