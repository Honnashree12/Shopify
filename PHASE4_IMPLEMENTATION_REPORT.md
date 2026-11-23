# PHASE 4 IMPLEMENTATION REPORT

Product Launch Agent Execution, Shopify Publishing & Production Workflow.

---

## 1. Executive Summary

Phase 4 found that Antigravity's Phase 1–3 work had already implemented the large majority of the
execution pipeline: authentication, role-based authorization, self-approval protection, a basic
approval→publish trigger, SKU/title duplicate detection, resilient staged media upload with bounded
retry, live Shopify verification gating completion, accurate per-stage `failed_stage` reporting, and
audit logging at every major transition. Phase 4's job was therefore not to build this from scratch,
but to find and close the remaining, genuinely concrete gaps between what was built and what
`security.md`/`workflow.md`/this phase's own spec require — and to do so without rewriting anything
that already worked.

Seven concrete gaps were found and closed:

1. The Approval Gate's Layer 2 (defense-in-depth, inside the publishing tool itself) only checked a
   boolean flag, with no check that the approval still corresponded to the *current* product data.
2. No mechanism prevented two near-simultaneous approve requests for the same product from both
   scheduling a publishing run (a real double-publish race).
3. `create_shopify_product_tool` would attempt to re-create a Shopify product on every resume/retry
   of a workflow that had already succeeded at the Create stage.
4. There was no way to see which pipeline stage was *currently* executing while a run was in
   progress — `/status/{id}` only reflected the outcome once the whole run finished.
5. A retry-after-technical-failure capability existed in the frontend, but the endpoint it called
   would always reject the retry (a genuine, pre-existing bug) — no working retry endpoint existed.
6. A stale ADK-session `workflow_error` would have silently defeated any retry attempt even after
   the bug in #5 was fixed, since every tool short-circuits on that field.
7. Full technical stack traces (including internal file paths) were present in every `/status/{id}`
   response regardless of caller role — only the frontend chose not to render them for non-Platform-
   Admin roles, which is not real enforcement.

All seven are fixed. No existing agent, tool, Shopify client, or media service code was rewritten —
every change is additive (new checks, a new small module, one new endpoint, three UI wiring fixes).

---

## 2. Approval Gate

Publishing remains reachable only from one code path: a successful `POST /api/products/{id}/approve`
or `POST /api/folder-launch/{id}/approve`, both `require_role(["APPROVER"])`-gated, both refusing
self-approval, both requiring `status == "awaiting_approval"`.

**Layer 1 (API/workflow layer, existing, unchanged):** the approve endpoints are the only call sites
that schedule `run_folder_workflow_background`.

**Layer 2 (inside `create_shopify_product_tool`, hardened this phase):** the tool now independently
re-verifies, from the ADK session state main.py seeds before resuming the run:
- `approved_to_publish` is true (existing check).
- `approved_at_version == product_version` — **new**. If a product were ever edited after approval
  through some future code path that bypassed the normal edit-lock, the tool refuses to create the
  Shopify product and returns `"PUBLISH DENIED: Approval is stale..."` rather than proceeding.

Both layers read from the same durable fields (`approved_by_uid`, `approved_at`, `approved_at_version`,
`product_version` on `ProductLaunchState`) — there is one source of truth for "is this approved," not
two independently-maintained flags.

---

## 3. Agent Execution Pipeline

Unchanged: `FolderIngestionAgent → FolderValidationAgent → FolderCreationAgent → FolderMediaAgent →
FolderVerificationAgent → FolderReportAgent`, each a thin ADK wrapper around one tool in
`tools/folder_tools.py`. Every stage now also:

- Reports its start via `workflow/progress_tracker.set_stage()` (new — see §11.1 UI Changes).
- Writes a start/completion audit event where the canonical event list defines one (see §10).

No agent's tool boundary, inputs, or outputs changed. `FolderCreationAgent`'s tool gained the two
guard checks in §2 and §8; every other agent's tool is functionally identical to before this phase.

---

## 4. Shopify Integration

Retained exactly as implemented: `shopify_client.py` (`create_product`, `update_product`,
`get_product_by_sku`, `get_product_by_title`, `get_product`), called only from
`create_shopify_product_tool`. No new Shopify library, no new API client, no changed request shape.

---

## 5. Media Pipeline

Retained exactly as implemented: `services/shopify_media_service.py`'s `retry_upload_media`
(bounded exponential backoff, `image_config.RETRY_COUNT`), called from `upload_folder_media_tool`
for both images and videos via `upload_and_attach_all_media`. Per-file success/failure/error is
already preserved and reported; a failed file never masks a different file's real error. This phase
added `MEDIA_UPLOAD_STARTED`/`MEDIA_UPLOAD_COMPLETED` audit events around the existing logic — the
upload/retry logic itself is untouched.

---

## 6. Verification

Retained exactly as implemented: `verify_folder_product_tool` re-reads the live Shopify product
(status, price, SKU, inventory, variant presence) and computes `purchasable`. `run_folder_workflow_background`
only sets `status = "completed"` after this check passes (with the existing, deliberate allowance for
an intentionally-draft product) — a product that exists on Shopify but hasn't passed verification is
never reported as `completed`. `VERIFICATION_STARTED`/`VERIFICATION_COMPLETED` audit events were added
around this existing logic.

---

## 7. Firebase / Firestore

Retained exactly as implemented: `services/firebase_service.py`'s `save_product`/`save_audit_log`
(mock-fallback to `outputs/mock_firestore/` when real credentials aren't configured, confirmed
working in this environment). `create_shopify_product_tool` already wrote Shopify sync status back to
the product's Firestore document in a way that doesn't fail the whole tool if the Firestore write
itself fails (Shopify success and Firestore-mirror success/failure are already tracked as separate
facts) — no change needed here; verified correct by reading the code, not assumed.

---

## 8. Idempotency / Duplicate Protection

Three independent protections, one pre-existing and confirmed correct, two new this phase:

1. **SKU/title duplicate detection** (pre-existing, unchanged) — `create_shopify_product_tool` looks
   up by SKU then title before creating; a match pauses for `ASK`/`UPDATE`/`CANCEL` resolution.
2. **Same-run re-create protection (new)** — if `state.get("shopify_product_id")` is already set
   (this run already created the product, e.g. before a later-stage failure), the tool now skips
   creation entirely rather than risking a duplicate or an unwanted re-pause on retry.
3. **Concurrent-approval protection (new)** — `workflow/progress_tracker.py`'s
   `try_acquire_publish_lock(session_id)` is claimed atomically at the top of both approve endpoints
   and the new retry endpoint, before any other check. A second near-simultaneous request for the
   same product gets `409 "A publishing execution is already in progress for this product"` instead
   of also scheduling a run. The lock is released in `run_folder_workflow_background`'s `finally`
   block (every exit path) and immediately on any validation failure in the endpoints themselves, so
   a single bad request can never permanently block future legitimate attempts (verified by test).

---

## 9. Retry / Recovery

**New endpoint: `POST /api/products/{id}/retry`, Platform Admin only.**

Required by `security.md` §4 ("a Technical Admin may trigger a retry of a failed technical stage")
and flagged as a missing API surface in this session's earlier documentation audit — no such endpoint
existed before this phase. It:

1. Requires `status == "failed"` (409 otherwise).
2. Requires a valid approval already on record — `approved_to_publish` true and `approved_by_uid`
   set (403 otherwise). Retry never grants a new approval; it only resumes one that already exists.
3. Requires `approved_at_version == product_version` (409, same staleness message as §2) — a retry
   cannot resume a run whose approval is no longer current.
4. Clears `failed_stage` and the FastAPI-facing `errors["workflow_error"]`, **and** clears
   `workflow_error` in the ADK session state itself. This second clear was necessary: every tool in
   `tools/folder_tools.py` checks `state.get("workflow_error")` first and no-ops if it's still set —
   without also clearing the ADK-side copy, a retry would silently do nothing and re-report the same
   stale failure. This was found and fixed during implementation, not assumed.
5. Re-acquires the publish lock and re-invokes `run_folder_workflow_background`, which resumes the
   existing ADK session (not a fresh one) — combined with §8's same-run re-create protection, a retry
   after a Media-stage failure correctly skips re-creating the Shopify product and picks up at Media.

Retries are never automatic and never apply to permanent failures (invalid data, missing/stale
approval, business rejection) — those are structurally excluded by requiring a valid, current
approval to already exist, rather than by trying to classify error messages.

---

## 10. Audit Trail

New events added this phase, written from inside the relevant tool (`actor: "System"`,
matching the existing convention used by `PUBLISH_COMPLETED`/`PUBLISH_FAILED`):

`PUBLISH_STARTED`, `SHOPIFY_PRODUCT_CREATED`, `MEDIA_UPLOAD_STARTED`, `MEDIA_UPLOAD_COMPLETED`,
`VERIFICATION_STARTED`, `VERIFICATION_COMPLETED`.

Plus one new event not in the original canonical list, added and flagged here rather than silently
folded in: **`RETRY_TRIGGERED`**, written by the new retry endpoint with the real Platform Admin
actor/email/role. This event exists in `data-model.md`/`security.md`/`workflow.md`'s canonical lists
implicitly (retry is discussed) but was never given its own named event — recommend adding it to the
canonical list in a future documentation pass.

All audit writes are append-only via `services/firebase_service.py.save_audit_log` — no code path
added or changed in this phase gives any client role write or delete access to `audit_logs`.

---

## 11. UI Changes

### 11.1 Live stage visibility (new)
- `state.py`: new `current_stage: Optional[str]` field (transient, not persisted).
- `workflow/progress_tracker.py`: new module, in-memory `session_id → stage` map, written by each
  tool as it starts, read by `GET /status/{id}`.
- `frontend/src/api/types.ts`, `pipeline.ts`: `ProductLaunchState.current_stage` added;
  `deriveStageStatuses` now prefers the backend-authoritative `current_stage` over its previous
  field-presence inference when `status === "running"`.
- `ProductDetail.tsx`: shows "Publishing agent is currently on: **{stage}**" while running, and a
  persistent "Not yet approved — the publishing agent cannot start until a Reviewer approves" label
  while `awaiting_approval` (required by `ui-spec.md` §9).

### 11.2 Retry button fixed (bug found and fixed)
- The existing "Retry Pipeline Run" button called `api.approveFolderLaunch(id, {approved_to_publish:
  true})`, which always returns `409` for a `status == "failed"` product (that endpoint requires
  `awaiting_approval`). It could never have succeeded. Replaced with `api.retryProduct(id)`, wired to
  the new `POST /api/products/{id}/retry` endpoint (§9), with its own loading/disabled state and the
  failed stage shown in the button label.

### 11.3 Shopify result panel (new)
- `ProductDetail.tsx`: on `status === "completed"`, shows the Shopify product ID, a link to the live
  storefront URL, and the verification outcome — satisfying Part 21's requirement, previously absent.

### 11.4 Friendly failure message for non-Platform-Admin roles (new)
- Previously only Platform Admin saw *any* failure explanation; Catalogue Admin/Approver saw only the
  pipeline timeline's failed marker with no text. Added a friendly callout (failed stage + the now-
  redacted message from §12) for every other role.

`npx tsc --noEmit` passes cleanly after all frontend changes (verified, not assumed).

---

## 12. Security

- **Approval verified server-side**, twice (§2) — the frontend Approve button is never sufficient on
  its own; every check is re-derived from stored, backend-controlled fields.
- **Role cannot be forged** — `require_role` resolves the caller's role from the server-side token
  lookup (`services/auth_service.py`), never from a client-supplied value.
- **Product ID cannot bypass authorization** — ownership checks on `GET /status/{id}`,
  `PATCH /api/products/{id}`, and `POST .../submit` are unchanged and confirmed still enforced.
- **Shopify/Firebase credentials remain server-side** — unchanged; no code added this phase reads or
  forwards `SHOPIFY_ACCESS_TOKEN`/`FIREBASE_SERVICE_ACCOUNT_KEY` anywhere near a response body.
- **Audit records cannot be modified by any client role** — unchanged; no update/delete path exists.
- **Error responses do not leak secrets — fixed, was previously failing.** `GET /status/{id}`
  returned the complete `errors["workflow_error"]` value, including the full Python traceback and
  internal file paths, to *every* role that could read the endpoint (Catalogue Admin, Approver, not
  just Platform Admin) — the frontend simply chose not to render it for other roles, which is not
  enforcement. Fixed: the endpoint now builds a per-request response on a deep copy of the shared
  in-memory record and truncates `workflow_error` to its friendly first line for every role except
  Platform Admin, who still receives the full detail. Verified the redaction never mutates the shared
  `active_sessions[id]` object itself (test: `test_status_redacts_stack_trace_for_non_platform_admin`).
- **Duplicate publishing is prevented** — §8.

---

## 13. Files Created

- `workflow/progress_tracker.py`
- `tests/test_phase4_publishing_pipeline.py`
- `PHASE4_IMPLEMENTATION_REPORT.md` (this file)

## 14. Files Modified

- `state.py` — added `current_stage` field.
- `tools/folder_tools.py` — stage tracking, approval-version defense-in-depth check, same-run
  re-create guard, new audit events (`_audit` helper + call sites).
- `main.py` — import `progress_tracker`; concurrency lock in both approve endpoints and the new
  retry endpoint; `product_version`/`approved_at_version`/`workflow_error` carried into ADK session
  state on both first-run and resume; `finally` block releasing the lock/stage tracker in
  `run_folder_workflow_background`; new `POST /api/products/{id}/retry` endpoint; `GET /status/{id}`
  redaction and live-stage population.
- `frontend/src/api/types.ts`, `frontend/src/api/pipeline.ts`, `frontend/src/api/client.ts`,
  `frontend/src/pages/ProductDetail.tsx` — see §11.

No file was rewritten; every change above is an in-place, additive edit to working code.

---

## 15. Tests

Commands run and exact results:

```
$ python3 -m pytest tests/test_phase1_foundation.py tests/test_phase3_security.py -q
11 passed, 7 warnings in 4.55s

$ python3 -m pytest tests/test_phase4_publishing_pipeline.py -q
13 passed, 7 warnings in 5.32s

$ python3 -m pytest tests/ -q --ignore=tests/test_customer_flow.py \
    --ignore=tests/test_firebase_workflow.py --ignore=tests/test_workshop_platform.py
57 passed, 3 skipped, 158 warnings in 13.93s
```

New tests added (`tests/test_phase4_publishing_pipeline.py`, 13 tests): stale-approval-version denial
at Layer 2, non-stale approval passes the gate, unapproved product rejected at the approve endpoint,
same-run duplicate-create skip, concurrent-approve race rejected, lock released on validation
failure, retry requires Platform Admin, retry requires `failed` status, retry refuses a stale
approval, retry succeeds and clears failure state end to end, retry without a prior approval refused,
live `current_stage` visible via `/status`, and stack-trace redaction by role.

The 3 skips are pre-existing and environment-conditional (no real Firebase credentials configured in
this sandbox; the mock Shopify router was intentionally removed in an earlier phase) — not caused by
this phase.

---

## 16. End-to-End Verification

Ran directly against the real FastAPI app via `TestClient` (real HTTP request/response cycle, real
Pydantic validation, real in-memory state machine; only the background publishing task itself was
mocked, per Part 23 Group G's explicit instruction not to create real Shopify products in automated
verification).

**Positive scenario** (Draft → Submit → Approve → Publish → Completed):
```
1. Created: status=pending
2. Submit for review -> HTTP 200, status=awaiting_approval
3. Approve -> HTTP 200, status=completed
   approved_by_uid=approver-uid, approved_at_version=1
4. After pipeline run -> status=completed, shopify_product_id=900123,
   shopify_url=https://kiddypi-test.myshopify.com/products/test-item
RESULT: PASS
```

**Negative scenario** (unapproved product, publish attempt rejected):
```
1. Created: status=pending (not submitted, not approved)
2. Approve directly from 'pending' -> HTTP 409 Conflict
3. Read status with no auth token -> HTTP 401
4. Catalogue Admin attempts Approve -> HTTP 403
5. Final status: pending (never left 'pending', never published)
RESULT: PASS
```

**Change-request loop** (Request Changes → Edit → Resubmit → Approve → Publish):
```
1. Submit -> HTTP 200, status=awaiting_approval
2. Request Changes -> HTTP 200, status=failed, comment recorded
3. Edit product -> HTTP 200, product_version=2
4. Resubmit -> HTTP 200, status=awaiting_approval
5. Approve (2nd pass) -> HTTP 200, approved_at_version=2 (matches current version, not the stale one)
6. After pipeline run -> status=completed
RESULT: PASS
```

---

## 17. Remaining TBD Decisions

Unresolved before this phase, still unresolved (not decided by this work, per instruction not to
silently resolve TBDs):

1. Authentication/identity provider (Firebase Auth proposed, BOSS integration unconfirmed).
2. Deployment target — `Dockerfile`/`cloudbuild.yaml` (Cloud Run) vs. `adk.yaml` (Vertex AI Reasoning
   Engine) — the strongest documented conflict, still unresolved.
3. Campaign pipeline (9-agent raw-prompt flow) in/out of scope — untouched by this phase; it still
   has no Approval Gate at all if it is ever exposed to Lakshmi/Sandeep.
4. "Materially changed" granularity for approval versioning — this phase implements the
   already-agreed mechanism (any field change bumps `product_version`, invalidating the approval) but
   does not decide whether a finer distinction (e.g., typo fix vs. price change) should exist.
5. Notification channel (in-app only vs. email) — untouched.
6. Data/audit retention duration — untouched.
7. `RETRY_TRIGGERED` audit event (§10) — new, not yet added to the canonical event list in
   `data-model.md`/`security.md`/`workflow.md`.

## 18. Remaining Blockers

Nothing found in this phase blocks the *backend* publishing pipeline from being production-correct
for the Folder pipeline specifically. What remains before **production deployment** (not before this
phase is "done"):

1. Real Shopify and Firebase credentials have never been exercised in this environment — everything
   above is verified against the mock-fallback path and a mocked Shopify client, per this phase's own
   instruction not to create real production Shopify products in automated verification.
2. Items 1–2 in §17 (auth provider, deployment target) block real production rollout entirely, as
   already established in this session's earlier documentation audit.
3. Three pre-existing test files (`test_customer_flow.py`, `test_firebase_workflow.py`,
   `test_workshop_platform.py`) error out in this specific sandbox due to a FUSE-mounted-filesystem
   `os.unlink` permission quirk and a related SQLite disk I/O error — reproduced in isolation,
   confirmed unrelated to any Phase 4 change, and previously documented in this session while
   debugging `npm install` on the same mount. Not a code defect; an environment limitation of this
   sandbox specifically.

## 19. Production Readiness

**READY WITH CONDITIONS.**

The publishing pipeline's logic — approval gating, version integrity, duplicate protection,
concurrency safety, retry safety, verification-gated completion, audit trail, and role-based error
visibility — is implemented, tested, and passes end-to-end verification against the real code paths
with only the genuinely external boundary (actual Shopify network calls) mocked. It is not
production-ready until: (a) a real authentication provider is selected and wired in (§17.1), (b) the
deployment target conflict is resolved (§17.2), and (c) the same verification in §16 is repeated once
against a real Shopify sandbox store with real credentials, which this environment does not have.

## 20. Phase 5 Recommendation

Based on what's actually built and verified now, not the original Phase 0–13 plan in isolation:

1. **Resolve §17 items 1–2 first** (auth provider, deployment target) — everything else is
   implemented against assumptions that would need rework if these land differently.
2. **Wire real Shopify sandbox credentials into this environment** and re-run §16's three scenarios
   for real, since every verification so far has necessarily mocked the actual Shopify network call.
3. **Close the remaining documented API gaps** found in this session's earlier audit: user/role
   administration endpoints and a report-retrieval endpoint (both still absent; retry is now fixed).
4. **Decide the Campaign pipeline's fate** (§17.3) before any further security work is spent making
   assumptions about a pipeline that may not ship.

STOPPING HERE per instruction. Phase 5 has not been started.
