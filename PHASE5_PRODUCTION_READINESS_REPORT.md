# PHASE 5 — PRODUCTION READINESS REPORT

**Scope:** Production Hardening, Real Authentication, BOSS Alignment & Final Validation, building on Phases 1–4.
**Classification: READY WITH CONDITIONS.** The system is materially more secure and honest about its own state than at the start of this phase, but three concrete, human-owned prerequisites (below) must be resolved before a real production go-live — they are not code defects, they are business/infrastructure decisions this phase deliberately did not resolve on its own.

---

## 1. Executive Summary

This phase closed seven concrete gaps between the current implementation and a production-ready posture:

1. Added a real Firebase ID-token authentication path (`FirebaseAuthProvider`) as the primary identity mechanism, with the existing mock provider retained as an explicit, clearly-labeled dev/test fallback.
2. Fixed a critical unauthenticated data-exposure gap: the `/outputs` static mount served the entire `outputs/` directory — including raw Firestore-mock JSON (product data, audit logs with emails) and in-flight uploads — to anyone who could guess a path.
3. Found and fixed **three Workshop/Campaign endpoints with no authentication at all** (`POST /api/workshops`, `.../generate`, `.../publish`) — the last of which could publish a live Shopify product with zero auth and zero human approval.
4. Hardened CORS (was `allow_origins=["*"]` + `allow_credentials=True`, an invalid/insecure combination) to a configurable allowlist, with a startup guard that refuses to boot with a wildcard origin when `APP_ENV=production`.
5. Added file upload validation (size cap, count cap, extension allowlist, streaming writes) to `/launch-folder`, which previously accepted unlimited files of unlimited size and any type.
6. Made `/health`'s top-level status reflect actual Shopify/Firestore connectivity instead of hardcoding `"healthy"`.
7. Added a global 401 handler on the frontend (expired/invalid session → clear local state, redirect to Login) and relabeled the role-picker as an explicit development control rather than something that could be mistaken for production sign-in.

23 new automated tests were added covering all of the above; all pass. The full existing regression suite was re-run: **80 passed, 3 skipped, 0 new failures**, 8 pre-existing environment-only errors (unchanged from Phase 4, reproduced in isolation, not caused by this phase — see §20).

## 2. Scope & Explicit Boundaries

Per the governing instructions, this phase did **not**:
- Rewrite the Campaign/Workshop pipeline's architecture (its documented, pre-existing approval-skip design gap is called out again in §8, not silently fixed or hidden).
- Build a real Firebase Web SDK login UI on the frontend — there is no real Firebase project available in this sandbox to build or test that against honestly. The backend is ready for it (§3); the frontend piece is named explicitly as an open item in §21, not silently resolved.
- Redesign the Dashboard/BOSS-cockpit UI, which already implements the bulk of Part 3's role-based KPI/queue pattern well (My Drafts/Awaiting Review/Published Today/Needs Attention for Catalogue Admin, Awaiting Review/Recently Approved/Changes Requested for Approver, Active Pipeline/Shopify/Firestore/Warnings for Platform Admin). Only copy/labeling changes were made (§17).
- Remove or weaken any test. Two pre-existing tests (`test_api.py::test_health_check`, `test_phase1_foundation.py::test_health_check_endpoint`) asserted `status == "healthy"` unconditionally; their assertions were updated to `status in ("healthy", "degraded")` because the underlying behavior they check was *intentionally* changed in §6 to be accurate rather than hardcoded — this is a legitimate assertion update to match a deliberate, documented behavior change, not a deletion or weakening to force a pass.

## 3. Real Authentication (Part 1)

`services/auth_service.py` now has two identity providers:

- **`MockAuthProvider`** (unchanged): recognizes exactly `mock-admin-token` / `mock-approver-token` / `mock-catalogue-token`. Kept because this sandbox, CI, and local dev have no real Firebase project.
- **`FirebaseAuthProvider`** (new): verifies a bearer token via `firebase_admin.auth.verify_id_token()`, then looks up the caller's application role from Firestore at `users/{uid}.role`. A verified real identity with **no** matching `users/{uid}` document is rejected with 403, not given a default role — assigning a default role to an unrecognized real account would itself be a privilege-escalation hole.

`get_current_user()` routing logic: a token starting with `mock-` always goes to `MockAuthProvider` (real Firebase ID tokens are opaque signed JWTs and will never look like this, so there's no ambiguity). Any other token, when Firebase is actually configured in this environment (`initialize_firebase()` returns a client — the same check `services/firebase_service.py` already uses), is verified for real and **must** pass; it is never silently allowed to fall through to the mock provider on failure. When Firebase is not configured, non-mock tokens fall through to the mock provider, which will correctly 401 anything it doesn't recognize.

**What this delivers:** genuine real-auth capability, wired as the primary path, that starts working the moment a real Firebase project + service account key are configured — with zero further backend code changes. **What remains open (see §21):** (a) provisioning an actual Firebase project is a business/infra decision outside this codebase; (b) the frontend still only issues mock tokens via the role-picker — a real Firebase Web SDK sign-in flow was not built because there is no real project to build or test it against, and shipping an untestable, unverified login UI would be worse than being explicit about the gap; (c) `users/{uid}` role documents must be created for real accounts (by a Platform Admin, once real accounts exist) — there is intentionally no self-service role assignment.

## 4. Session Management & Expired/Invalid-Session Handling (Part 5)

`frontend/src/api/client.ts`'s `asJson()` now treats any `401` response as "this session is no longer valid": it clears `mock_user_key`/`mock_token` from `localStorage` and redirects to `/login`. A `403` is left alone (valid session, insufficient permission for one action — an in-page error, not a forced logout). Real Firebase ID tokens expire in ~1 hour by design, so once §3's remaining frontend work lands, this same handler transparently becomes the expired-session flow with no further changes needed. Session restoration on reload (reading `mock_user_key` from `localStorage` on mount) already existed and was not touched.

## 5. Identity Display (Part 4)

`AppShell.tsx`'s top bar already showed the current user's avatar and name. The dropdown next to it, however, doubles as a live role switcher reachable from every page — that's a legitimate dev/QA convenience but is easy to mistake for a production account-switching control. It's now labeled `DEV` with an explicit tooltip ("Development identity switcher — production sign-in uses real authenticated accounts, not this control"), and `Login.tsx`'s footer copy was updated from "No backend security credentials required" (no longer true — the backend independently verifies every mock token server-side, and can verify real ones) to explicitly state this is a development sign-in and that production uses Firebase Auth.

## 6. RBAC / Permission Matrix (Full Endpoint Audit)

| Endpoint | Method | Required role | Ownership scoping | Notes |
|---|---|---|---|---|
| `/launch` | POST | CATALOGUE_ADMIN | — | campaign pipeline (legacy) |
| `/launch-folder` | POST | CATALOGUE_ADMIN | — | + upload validation (§11) |
| `/api/folder-launch/{id}/approve` | POST | APPROVER | self-approval blocked | concurrency-locked |
| `/status/{id}` | GET | any authenticated | CATALOGUE_ADMIN restricted to own | stack trace redacted for non-admin |
| `/api/products/{id}/submit` | POST | CATALOGUE_ADMIN | owner only | |
| `/api/products/{id}/request-changes` | POST | APPROVER | self-review blocked | |
| `/api/products/{id}/approve` | POST | APPROVER | self-approval blocked | concurrency-locked |
| `/api/products/{id}/retry` | POST | PLATFORM_ADMIN | — | requires current, valid approval |
| `/api/products/{id}` | PATCH | CATALOGUE_ADMIN | owner only | bumps `product_version` |
| `/api/dashboard/metrics` | GET | any authenticated | — | |
| `/api/launches` | GET | any authenticated | CATALOGUE_ADMIN sees own only | |
| `/api/audit-logs` | GET | PLATFORM_ADMIN | — | |
| `/api/workshops` | POST | **CATALOGUE_ADMIN (fixed this phase — was open)** | — | |
| `/api/workshops/{id}/generate` | POST | **CATALOGUE_ADMIN (fixed this phase — was open)** | — | |
| `/api/workshops/{id}/publish` | POST | **APPROVER (fixed this phase — was open)** | — | see §8 for the deeper gap this doesn't fully close |
| `/api/workshops/{id}/register` | POST | *intentionally public* | — | customer-facing registration form |
| `/api/webhooks/orders/create` | POST | *intentionally public, HMAC-verified* | — | Shopify webhook signature, not user auth |
| `/workshops/{handle}` | GET | *intentionally public* | — | customer landing page |
| `/outputs/images/*` | GET | *intentionally public* | — | marketing images embedded in landing pages |
| `/outputs/mock_storage/*` | GET | *intentionally public* | — | mock substitute for public Firebase Storage URLs |
| `/health` | GET | none | — | contains no sensitive data |

`require_role()` gives `PLATFORM_ADMIN` an unconditional override on every role check — confirmed intentional (super-admin pattern), not a bug, left as-is.

## 7. IDOR & Unauthenticated Exposure — Findings and Fixes (Part 8)

**Finding 1 (critical, fixed):** `app.mount("/outputs", StaticFiles(...))` served all of `outputs/`, including `outputs/mock_firestore/` (raw product + audit-log JSON, with reviewer/customer emails), `outputs/temp_uploads/` (in-flight, not-yet-validated uploads), and `outputs/emails/` (sent customer/sales emails with PII) — to anyone, unauthenticated, who could guess or enumerate a path. Fixed by replacing the blanket mount with two explicit sub-mounts for only the genuinely public subfolders (`/outputs/images`, `/outputs/mock_storage`); everything else under `outputs/` now 404s. Verified with new tests (`test_outputs_mock_firestore_no_longer_publicly_served`, `_temp_uploads_`, `_emails_`).

**Finding 2 (critical, fixed):** three Workshop endpoints had no `Depends(...)` auth dependency at all (§6). `.../publish` is the most serious — it hardcodes `approved_to_publish=True` and immediately schedules a real Shopify publish. Gating it behind `APPROVER` means only an authenticated human reviewer can trigger it now, but it does **not** add the missing `awaiting_approval` human checkpoint this path structurally lacks (unlike the folder pipeline's `/api/products/{id}/approve`). That deeper redesign is a business decision (should Workshop publishing go through the same review queue as folder-based products?) that this phase does not silently resolve — flagged again in §21.

**Not an IDOR — verified by design:** `GET /status/{id}` for APPROVER/PLATFORM_ADMIN has no ownership restriction; this is intentional (reviewers need visibility across the whole queue, not just their own items).

## 8. Approval Security Re-Confirmation (Part 9)

Phase 4's two-layer Approval Gate (API-layer state-transition guard + `create_shopify_product_tool`'s independent `product_version`/`approved_at_version` staleness check) was re-read and is untouched by this phase. Self-approval protection, the publish concurrency lock, and the retry endpoint's "only resume an already-valid, still-current approval" rule are all intact and covered by Phase 4's existing tests. The one approval-security gap this phase surfaced is the Workshop `.../publish` path in §7, which is pre-existing (documented in the Phase 4 report as an out-of-scope, known issue in the Campaign pipeline) and is now at least role-gated rather than fully open.

## 9. Audit Trail (Part 10)

No changes needed or made — Phase 4's audit logging (`PRODUCT_CREATED`, `SUBMITTED_FOR_REVIEW`, `PRODUCT_APPROVED`, `CHANGES_REQUESTED`, `RETRY_TRIGGERED`, `PUBLISH_COMPLETED`/`PUBLISH_FAILED`, media/verification events) already covers every state-changing action with actor, role, timestamp, and description, written through `save_audit_log`. Confirmed still functioning via the full regression suite.

## 10. Security Hardening Checklist

| Item | Status |
|---|---|
| CORS restricted to configured origins, not `*` | ✅ Fixed |
| Wildcard CORS blocked at startup in production | ✅ Fixed |
| `/outputs` blanket unauthenticated exposure | ✅ Fixed |
| Unauthenticated write endpoints | ✅ Fixed (3 found and closed) |
| File upload size/count/type limits | ✅ Fixed |
| Path traversal protection on upload | ✅ Already present (`..` filter), confirmed |
| Stack traces hidden from non-admins | ✅ Already done in Phase 4, confirmed intact |
| Secrets masked in logs/repr | ✅ Already present (`Settings.__repr__`), confirmed |
| Webhook signature verification | ✅ Already present (HMAC-SHA256), confirmed |
| Self-approval / self-review protection | ✅ Already present, confirmed |
| Rate limiting | ❌ **Not implemented** — no rate-limiting dependency exists in this codebase; adding one is an infrastructure decision (in-process vs. reverse-proxy/API-gateway-level) not silently made here |
| Standard security response headers (`X-Content-Type-Options`, `X-Frame-Options`, HSTS) | ❌ **Not implemented** — flagged, not silently added without a decision on deployment topology (reverse proxy vs. app-level) |
| Dependency vulnerability scan | ❌ **Not run** — no scanning tool is configured in this repo |

## 11. File Upload Security (Part 11)

`/launch-folder` now rejects, before writing any bytes: more than `MAX_UPLOAD_TOTAL_FILES` (default 300) files, or any file whose extension isn't in an explicit allowlist (`.json .txt .md .png .jpg .jpeg .webp .gif .mp4 .mov .webm`). Each file is streamed to disk in 1MB chunks with a running byte count checked against `MAX_UPLOAD_FILE_SIZE_MB` (default 15MB) — a single oversized file is rejected and cleaned up mid-write rather than after being fully buffered in memory. Both limits are configurable via environment variables. Verified with three new tests (extension rejection, count rejection, size rejection).

## 12. Error Handling (Part 12)

Unchanged from Phase 4: `/status/{id}` redacts stack traces to a friendly first line for non-`PLATFORM_ADMIN` roles, on a deep-copied response object so the redaction never corrupts the shared in-memory session state for other viewers. Not fully re-audited across every single endpoint's error paths this phase (would require touching many handlers with no new concrete gap identified) — noted as a lower-priority follow-up, not a known defect.

## 13. Observability & Health Checks (Part 13)

`/health` previously always returned `"status": "healthy"` regardless of what `shopify_connectivity`/`firestore_connectivity` actually reported beneath it — useless for real monitoring. It now returns `"degraded"` whenever Shopify isn't `"connected"` (Shopify is required for the core publish path) or Firestore has outright `"failed"` (as opposed to the intentional, working `"mock"` fallback state, which is not itself unhealthy). Startup connectivity checks (already present from Phase 4, printing CONNECTED/NOT CONFIGURED for Firebase and Shopify) are unchanged.

## 14. Production Configuration (Part 14)

New settings in `config.py`: `CORS_ALLOWED_ORIGINS` (comma-separated allowlist, default `*` for dev convenience only), `MAX_UPLOAD_FILE_SIZE_MB` (default 15), `MAX_UPLOAD_TOTAL_FILES` (default 300). `validate_startup()` now raises at boot if `APP_ENV=production` and CORS is still wildcarded — fail fast and loud rather than silently deploying insecurely.

## 15. Firestore Consistency Under Concurrency (Part 15)

No new gap found or changed this phase. Phase 4's `product_version`/`approved_at_version` integrity mechanism and `workflow/progress_tracker.py`'s lock-guarded publish concurrency remain the enforcement points and were re-verified via the existing Phase 4 test suite (still passing).

## 16. Concurrency Scenarios (Part 16)

| Scenario | Coverage |
|---|---|
| Two approvers race to approve the same product | Covered — `try_acquire_publish_lock` ensures only one wins; loser gets 409 (Phase 4 test) |
| Retry triggered while a publish is already running | Covered — same lock (Phase 4 test) |
| Product edited mid-review, then approved | Covered — `approved_at_version` staleness check refuses a stale approval (Phase 4 test) |
| Double-approve on the same product | Covered — idempotency check on `status` (Phase 4 test) |
| Status polling during a state transition | Safe by construction — `/status/{id}` builds its response on a deep copy, read-only, no lock needed |
| Concurrent uploads to the same session | Not applicable — upload happens once, before any concurrency-sensitive state exists |
| Multiple app-server processes/workers sharing `active_sessions` | ⚠️ **Not safe today** — `active_sessions` is an in-process Python dict; this deployment model only tolerates a *single* backend process. Horizontal scaling would require moving session state into Firestore/Redis. This is a real architectural constraint, named here rather than silently left implicit. |

## 17. UI/UX Polish (Parts 17–18)

Left the Dashboard/role-based KPI and queue implementation as-is — it already matches the described BOSS-cockpit pattern closely (per-role KPI cards, per-role action queues, per-role welcome copy) and a redesign wasn't justified by any concrete gap. Changes made were limited to identity/auth-adjacent copy (§5) to keep the UI honest about what is and isn't real authentication.

## 18. Reviewer / Catalogue Admin / Publishing Experience (Parts 19–21 carryover)

`ProductDetail.tsx`'s Phase-4 additions (live stage indicator, Shopify result panel, working retry button, friendly non-admin failure messaging) were re-confirmed present and untouched; nothing in this phase's changes (CORS, auth, uploads, health, `/outputs`) alters that page's behavior.

## 19. Final Shopify Store Validation (Part 19)

Not independently re-run against a real Shopify store this phase — this sandbox has no real Shopify credentials configured (`shopify_connectivity` reports non-`connected` in `/health`, confirmed via the new health test). Recommend running the full publish flow against a real staging store before go-live, per §21.

## 20. Test Strategy & Results (Parts 22–24)

**New:** `tests/test_phase5_production_hardening.py` — 23 tests across real-auth verification, mock-auth non-regression, previously-open Workshop endpoints, `/outputs` exposure, CORS config, upload validation, and health status. All 23 pass.

**Updated:** two pre-existing health-check test assertions (`test_api.py`, `test_phase1_foundation.py`) to match the intentionally-changed, more accurate `/health` behavior (§13) — not a deletion or weakening.

**Full regression suite:** `80 passed, 3 skipped, 8 errors`. The 8 errors are `PermissionError`/`sqlite3.OperationalError: disk I/O error` in `test_customer_flow.py`, `test_firebase_workflow.py`, and `test_workshop_platform.py` — the same FUSE-mount environmental issue documented in the Phase 4 report, re-confirmed this phase by reproducing `test_workshop_platform.py`'s errors in isolation (2 errors, identical failure) with zero Phase 5 code involved in that file's failing setup path. Not caused by this phase's changes.

**Frontend:** `tsc -b` (typecheck) is clean. `vite build` inside the FUSE-mounted working directory crashed with `Bus error (core dumped)` — reproduced, then isolated by copying the frontend to a native (non-FUSE) filesystem path and rebuilding: **clean success, 38 modules transformed, `dist/` produced in 368ms.** This confirms the crash is the same class of FUSE-mount/native-binary incompatibility documented elsewhere in this project, not a code defect introduced by this phase.

## 21. Production Readiness Checklist & Final Recommendation

| # | Item | Status |
|---|---|---|
| 1 | Real backend auth path exists and is primary | ✅ PASS |
| 2 | Mock auth clearly labeled as dev-only | ✅ PASS |
| 3 | Real Firebase project provisioned | ⬜ **TBD — business/infra decision, not made here** |
| 4 | Frontend real sign-in flow (Firebase Web SDK) | ⬜ **TBD — cannot be built/tested without item 3** |
| 5 | `users/{uid}` role assignment process | ⬜ **TBD — needs a real Platform Admin workflow, not built this phase** |
| 6 | RBAC matrix audited, gaps closed | ✅ PASS |
| 7 | `/outputs` unauthenticated exposure | ✅ PASS |
| 8 | CORS hardened + prod startup guard | ✅ PASS |
| 9 | File upload limits | ✅ PASS |
| 10 | `/health` reflects real status | ✅ PASS |
| 11 | Rate limiting | ❌ FAIL — not implemented |
| 12 | Security response headers | ❌ FAIL — not implemented |
| 13 | Dependency vulnerability scan | ⬜ TBD — not run |
| 14 | Workshop pipeline approval checkpoint | ⬜ **TBD — pre-existing architectural gap, role-gated but not redesigned; business decision needed on whether it should share the folder pipeline's review queue** |
| 15 | Horizontal scaling of session state | ⬜ **TBD — single-process only today, documented, not silently assumed away** |
| 16 | Approval Gate / HITL integrity (folder pipeline) | ✅ PASS (Phase 4, re-confirmed) |
| 17 | Audit trail completeness | ✅ PASS |
| 18 | Automated test coverage for this phase's changes | ✅ PASS (23/23) |
| 19 | Full regression suite | ✅ PASS (80/80 runnable; 8 pre-existing env errors, reproduced as unrelated) |
| 20 | Frontend typecheck | ✅ PASS |
| 21 | Frontend production build | ✅ PASS (verified outside the FUSE mount) |
| 22 | Real Shopify store end-to-end validation | ⬜ TBD — no real store credentials in this environment |
| 23 | Secrets never logged/exposed | ✅ PASS (existing masking confirmed, no new logging of raw tokens added) |

**Recommendation:** the system is safe to deploy to a staging environment now — every closed-form security/correctness gap discovered this phase has been fixed and tested. It is **not yet ready for a real production go-live** until items 3, 4, 5, 22 (all genuine external/business dependencies, not engineering gaps) are resolved, and items 11–13, 14, 15 have an explicit owner decision.

Per the governing instructions for this phase: no Phase 6 work was started, no unnecessary architecture was introduced, no test was removed to force a pass, no TBD business decision was silently resolved, and no secret was exposed.
