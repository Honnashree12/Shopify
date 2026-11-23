# implementation-plan.md — Kiddypi Shopify Product Launch System

Source of truth: all ten preceding documents (`requirements.md`, `architecture.md`, `agents.md`,
`workflow.md`, `security.md`, `ui-spec.md`, `data-model.md`, `api-spec.md`, `testing.md`,
`deployment.md`). This is a sequencing plan, not code. No phase below authorizes writing
application code as part of producing this document — it defines what implementation work should
look like once undertaken.

---

## Phase 0 — Requirements Validation

**Objective:** Resolve enough open questions that implementation can start without guessing.

**Prerequisites:** None.

**Files affected:** None (decisions only).

**Dependencies:** None.

**Expected output:** Written confirmation (from Sandeep/business stakeholders) on the unresolved
items below, collected from every document produced so far:

1. Authentication/identity provider (`security.md` §22).
2. Deployment target — Cloud Run vs. Vertex AI Reasoning Engine (`deployment.md` §15 item 1).
3. Campaign pipeline in/out of scope (`architecture.md` §19).
4. Self-approval policy — confirm default-deny (`requirements.md` §24).
5. Retry semantics on publish failure (`workflow.md` §14).
6. Shopify rate-limit handling (`architecture.md` §19).
7. Data/audit log retention duration (`data-model.md` §15).
8. Workflow History vs. Audit Log scope (`ui-spec.md` §24 — already proposed, needs sign-off).
9. Product Media storage shape — subcollection vs. embedded array (`data-model.md` §16).
10. Mobile approval support (`ui-spec.md` §24).
11. Notification channel — in-app only vs. email (`data-model.md` §10).
12. Shopify API scopes required (`deployment.md` §15 item 4).

**Tests required:** None (documentation phase).

**Acceptance criteria:** Each item above has either a confirmed decision or an explicit "deferred to
post-launch" designation from the business stakeholder.

---

## Phase 1 — Environment & Tooling Setup

**Objective:** Establish the development environment without touching the working pipeline.

**Prerequisites:** Phase 0 substantially complete (at minimum items 1–2).

**Files affected:** New `.env.example` (categories only, no secrets), CI configuration (if none
exists today).

**Dependencies:** Phase 0.

**Expected output:** A developer can run the existing backend locally in mock-fallback mode
unchanged, plus a scaffolded location for new modules (auth, approval gate) that doesn't touch
existing files.

**Tests required:** Smoke test confirming existing `/health`, `/launch-folder`, `/status/{id}`
endpoints still function identically post-setup.

**Acceptance criteria:** Zero changes to existing pipeline behavior; new scaffolding present but
inert.

---

## Phase 2 — Data Model Implementation

**Objective:** Implement the Firestore collections and fields defined in `data-model.md`.

**Prerequisites:** Phase 0 items 7, 9, 11 resolved.

**Files affected:** New Firestore schema/model definitions; no changes to existing `state.py`.

**Dependencies:** Phase 1.

**Expected output:** `users`, `products`, `workflow_runs`, `audit_logs`, `notifications`
collections exist and are writable/readable in a test Firestore project, matching `data-model.md`
§2–§10 field-for-field.

**Tests required:** Schema validation tests per collection; the `ProductLaunchState`-to-`WorkflowRun`
field mapping (`data-model.md` §8) verified against real existing state objects.

**Acceptance criteria:** No existing `ProductLaunchState` field is dropped or renamed; all new
fields are additive.

---

## Phase 3 — Authentication Layer

**Objective:** Implement the identity/auth mechanism confirmed in Phase 0.

**Prerequisites:** Phase 0 item 1 resolved.

**Files affected:** New auth middleware/module; `main.py` extended (not rewritten) to require
tokens on new endpoints.

**Dependencies:** Phase 2 (`users` collection).

**Expected output:** Every request except `/health` and the Shopify webhook requires a valid
token, verified per `api-spec.md` §2.

**Tests required:** `testing.md` §7 (Authentication Testing) in full.

**Acceptance criteria:** 401 on missing/invalid tokens across all protected endpoints; existing
unauthenticated endpoints (`/health`, webhook) remain unauthenticated as designed.

---

## Phase 4 — Authorization / RBAC Layer

**Objective:** Implement role resolution and per-endpoint permission checks.

**Prerequisites:** Phase 3 complete.

**Files affected:** New authorization module; `main.py` extended.

**Dependencies:** Phase 3.

**Expected output:** Role checked server-side from `users/{uid}.role` on every protected endpoint,
per `api-spec.md` §3 and the full table in §10.

**Tests required:** `testing.md` §8 (Authorization Testing) in full, especially the negative cases
(Catalogue Admin cannot approve, cannot bypass publish).

**Acceptance criteria:** Every authorization test in `testing.md` §8 passes; no endpoint trusts a
client-supplied role claim.

---

## Phase 5 — Approval Gate (Authorization Service)

**Objective:** Build the one new core component this project requires — the backend Approval Gate,
explicitly not an ADK Agent (`agents.md` §3).

**Prerequisites:** Phases 2–4 complete; Phase 0 item 4 resolved.

**Files affected:** New approval-gate module, called from the Approve endpoint and, as
defense-in-depth, from inside `create_shopify_product_tool` (existing file, extended with a guard
check — not rewritten).

**Dependencies:** Phase 4.

**Expected output:** A product cannot reach `PUBLISHING` without passing every check in
`security.md` §5: product ID, workflow ID, current `product_version`, approval status, approver
identity, approver role, approval timestamp, version match.

**Tests required:** `testing.md` §4 (Human-in-the-Loop Testing) in full, plus the direct-tool-call
negative test in `testing.md` §3.

**Acceptance criteria:** No code path — API or direct tool invocation — reaches Shopify product
creation without a prior successful Approval Gate pass.

---

## Phase 6 — Product Lifecycle APIs

**Objective:** Implement the Product/Review APIs from `api-spec.md` §4, §7, §10 rows 1–7.

**Prerequisites:** Phase 5 complete.

**Files affected:** New route handlers in/around `main.py`; existing `/launch-folder` endpoint
extended with auth, not replaced.

**Dependencies:** Phase 5.

**Expected output:** Full Draft → Submit → Review → Approve/Request Changes cycle functions against
a Shopify sandbox store, matching `workflow.md` §2 end-to-end.

**Tests required:** `testing.md` §11 scenarios A, B, C, D, F, G, J.

**Acceptance criteria:** State transitions match `workflow.md` §3/§4 exactly; no shortcut path to
`PUBLISHED`.

---

## Phase 7 — Publishing Integration

**Objective:** Wire the existing, unmodified publish pipeline (Create → Media → Verify → Report) to
trigger only as a side effect of a successful Approve call.

**Prerequisites:** Phase 6 complete; Phase 0 items 5, 6 resolved (or explicitly deferred).

**Files affected:** Approve endpoint handler extended to invoke the existing
`folder_runner.run_async()` path; no changes to the agents themselves.

**Dependencies:** Phase 6.

**Expected output:** Approving a product triggers the real, existing publish pipeline, with
accurate `failed_stage` reporting on any failure.

**Tests required:** `testing.md` §5 (Shopify Integration), §10 (State Propagation), §11 scenario E.

**Acceptance criteria:** The two named regressions in `testing.md` §12 remain fixed; no new
regression introduced.

---

## Phase 8 — Audit & Notification APIs

**Objective:** Implement audit logging (`data-model.md` §9) and in-app notifications (§10).

**Prerequisites:** Phase 6 complete; Phase 0 item 8, 11 resolved.

**Files affected:** New audit-log write calls at every state-changing endpoint; new notifications
module.

**Dependencies:** Phase 6.

**Expected output:** Every action in `security.md` §14's event list produces a corresponding audit
entry; Workflow History (per-product) and system-wide Audit Log (Platform Admin only) are
distinctly accessible per `api-spec.md` §8.

**Tests required:** `testing.md` §11 scenario H; audit event completeness check against
`data-model.md` §9's canonical list.

**Acceptance criteria:** No state-changing action occurs without a corresponding audit entry.

---

## Phase 9 — Frontend: Core Cockpit Shell

**Objective:** Build the authenticated app shell, navigation, and role-scoped views per
`ui-spec.md` §2–§5, §20.

**Prerequisites:** Phases 3, 4 complete (auth/RBAC must exist for the frontend to integrate
against).

**Files affected:** `frontend/` (existing partial scaffold from this session — `AppShell.tsx`,
`Dashboard.tsx`, `Launches.tsx`, `NewLaunch.tsx` — completed and extended, not restarted).

**Dependencies:** Phase 4.

**Expected output:** Authenticated shell showing role-appropriate navigation; catalogue list view
functioning against real APIs from Phase 6.

**Tests required:** Manual UI walkthrough against `ui-spec.md` §22 user journeys 1–2.

**Acceptance criteria:** UI never shows an action a role cannot perform, though this is UX
convenience only — backend authorization (Phase 4) remains the actual control.

---

## Phase 10 — Frontend: Review & Approval Workspace

**Objective:** Build the Review/Approval screens, the highest-stakes UI in the system
(`ui-spec.md` §8, §9).

**Prerequisites:** Phase 9 complete; Phase 5 complete.

**Files affected:** New `LaunchWorkspace.tsx` (in progress, incomplete from this session) and
related components.

**Dependencies:** Phase 9, Phase 5.

**Expected output:** Sandeep can review a submitted product (info, pricing, images/video,
presentation) and Approve or Request Changes, with the approval action calling the real Approve
endpoint and showing the resulting state change.

**Tests required:** `ui-spec.md` §22 journey 3; `testing.md` §11 scenarios A–C manually walked
through via the UI.

**Acceptance criteria:** The Approve button is disabled/hidden for non-Reviewer roles (UX layer),
and calling it as any other role still returns 403 (defense-in-depth confirmed).

---

## Phase 11 — Frontend: Publishing Status & Audit Views

**Objective:** Build the Agent Execution/Publishing Status, Notifications, and Audit UI
(`ui-spec.md` §10–§13, §16).

**Prerequisites:** Phases 7, 8 complete.

**Files affected:** New status/timeline components.

**Dependencies:** Phase 10.

**Expected output:** Real-time (or polled) visibility into publish progress, accurate failure
reporting, and role-scoped audit/history views.

**Tests required:** `testing.md` §11 scenarios E, H, I.

**Acceptance criteria:** Failure states shown to users always reflect the real, specific error
(`api-spec.md` §11), never a generic or misleading one.

---

## Phase 12 — Security Hardening & Deployment Prep

**Objective:** Complete the Security Checklist (`deployment.md` §13) before any production
exposure.

**Prerequisites:** Phases 3–11 complete; Phase 0 item 2 resolved.

**Files affected:** CORS configuration (existing `allow_origins=["*"]` restricted), logging
configuration, secrets management setup.

**Dependencies:** All prior phases.

**Expected output:** All six items in `deployment.md` §13 verified.

**Tests required:** Full `testing.md` suite, including regression tests (§12).

**Acceptance criteria:** `deployment.md` §14 Production Readiness Checklist fully satisfied.

---

## Phase 13 — End-to-End Validation

**Objective:** Full-system validation against a Shopify sandbox store before production rollout.

**Prerequisites:** Phase 12 complete.

**Files affected:** None (validation only).

**Dependencies:** Phase 12.

**Expected output:** All ten scenarios in `testing.md` §11 pass; all Acceptance Criteria in
`requirements.md` §22 verified against the running system.

**Tests required:** Complete `testing.md` suite, end to end, including a full run of the real
folder-based bulk import path (scenario J) to confirm the legacy pipeline is genuinely unchanged.

**Acceptance criteria:** System is ready for a production deployment decision by the business
stakeholder — this document does not itself authorize that decision.

---

## Definition of Done

A phase is done when: its expected output is demonstrated against a Shopify sandbox store (not
just unit tests), its required tests pass, and no acceptance criterion is left unverified. The
project as a whole is done when Phase 13 is complete and every open question logged in Phase 0
has either a confirmed answer or an explicit, stakeholder-approved deferral.

---

## Documentation Consistency Report

Synthesis across all eleven documents: `requirements.md`, `architecture.md`, `agents.md`,
`workflow.md`, `security.md`, `ui-spec.md`, `data-model.md`, `api-spec.md`, `testing.md`,
`deployment.md`, `implementation-plan.md`.

### Confirmed Consistent Areas

- **Roles and responsibilities** — Sandeep (Approver/Reviewer), Lakshmi (Catalogue Admin),
  Platform Admin, AI Publish Agent are named and scoped identically across every document that
  discusses roles.
- **The core rule** — the AI agent never makes the business decision to publish; a human approval
  is always required first — appears verbatim or near-verbatim in `requirements.md`,
  `architecture.md`, `agents.md`, `workflow.md`, `security.md`, `ui-spec.md`, `api-spec.md`, and
  `testing.md`, with no contradicting statement anywhere.
- **Product state names** — `DRAFT`, `READY_FOR_REVIEW`/`VALIDATING`, `IN_REVIEW`/`UNDER_REVIEW`,
  `CHANGES_REQUESTED`, `APPROVED`, `PUBLISHING`, `PUBLISHED`, plus failure states — used
  consistently from `requirements.md` through `data-model.md`, with `workflow.md`'s refinement of
  `PUBLISHING` into `PUBLISHING`→`MEDIA_UPLOAD`→`VERIFYING` explicitly documented as a detail
  refinement, not a contradiction.
- **Approval Gate design** — the same single non-agent authorization service, enforced at both the
  API layer and inside `create_shopify_product_tool`, described identically in `security.md`,
  `agents.md`, `api-spec.md`, and `implementation-plan.md` Phase 5.
- **Approval Versioning mechanism** — `product_version` + `approved_at_version` — consistent from
  `workflow.md` §6 through `data-model.md` §4 and `testing.md` §4.
- **Existing pipeline preservation** — every document agrees the existing Create→Media→Verify→
  Report ADK pipeline is unmodified; `AGENTS.md`'s Existing Code Mapping table is reused without
  contradiction in `api-spec.md`, `testing.md`, and `implementation-plan.md`.
- **Firestore collection design** (5 collections, no fragmentation) — consistent from
  `architecture.md` Decision D5 through `data-model.md` §12 and `deployment.md` §5.
- **Audit event vocabulary** — `data-model.md` §9's canonical list (security.md's set plus
  `USER_LOGIN`/`USER_LOGOUT`/`USER_ROLE_CHANGED`) is used without contradiction in `api-spec.md`
  §8 and `testing.md` §11 scenario H.

### Conflicts Found

1. **Deployment target** — `Dockerfile`/`cloudbuild.yaml` (Cloud Run) vs. `adk.yaml` (Vertex AI
   Reasoning Engine, placeholder values) — the strongest, most concrete unresolved conflict in the
   entire documentation set. First surfaced in `architecture.md` §19, carried unresolved through
   `deployment.md` §15 and `implementation-plan.md` Phase 0 item 2. **No document silently picked
   one** — all defer to business/technical confirmation.
2. **Workflow History vs. Audit Log scope** — originally flagged as ambiguous in `ui-spec.md` §24;
   `data-model.md` §9 and `api-spec.md` §8 both adopted the same proposed resolution (per-product
   friendly history vs. Platform-Admin-only raw log) but this resolution itself is still marked
   proposed, not confirmed by the business stakeholder.

### Missing Decisions

These are gaps where no document — not even as a proposal — commits to an answer:

1. Authentication/identity provider (mechanism entirely unconfirmed; only "some bearer-token
   scheme" is proposed).
2. Shopify API scopes required for any new operations.
3. Data/audit retention duration.
4. Retry semantics after a publish failure (automatic vs. manual).
5. Shopify rate-limit (429) backoff behavior.
6. Whether an "unpublish" workflow exists at all.

### TBD Items (Full List, Consolidated)

All items below are marked `TBD — Requires Confirmation` in at least one source document; none has
been resolved by inference or assumption in any other document:

1. Authentication/identity provider (`security.md`, `api-spec.md`, `deployment.md`)
2. Deployment target (`architecture.md`, `deployment.md`)
3. Campaign pipeline in/out of scope (`architecture.md`, `testing.md`)
4. Self-approval policy — confirmed default-deny assumption, not a final decision
   (`requirements.md`, `workflow.md`, `security.md`, `testing.md`)
5. Retry semantics on failure (`workflow.md`, `security.md`, `testing.md`, `deployment.md`)
6. Shopify rate-limit handling (`architecture.md`, `testing.md`)
7. Data/audit retention duration (`data-model.md`, `deployment.md`)
8. Workflow History vs. Audit Log scope — proposed resolution, unconfirmed (`ui-spec.md`,
   `data-model.md`, `api-spec.md`)
9. Product Media storage shape — subcollection vs. embedded (`data-model.md`)
10. Mobile approval support (`ui-spec.md`)
11. Notification channel — in-app only vs. email (`data-model.md`, `ui-spec.md`)
12. Shopify API scopes (`deployment.md`)
13. Staging environment existence (`deployment.md`)
14. Firestore security rules as a second enforcement layer (`security.md`, `deployment.md`)
15. Rate limiting on product-creation endpoints (`api-spec.md`, proposed only)
16. Unified vs. separate product-creation endpoints for manual vs. folder intake (`api-spec.md`)
17. Unpublish workflow existence (`deployment.md`)

### Recommended Order for Resolving TBDs

1. **Deployment target** (#2) — blocks infrastructure setup (Phase 1) and cannot be worked around.
2. **Authentication/identity provider** (#1) — blocks Phases 3–4, which nearly everything else
   depends on.
3. **Self-approval policy confirmation** (#4) — low effort to confirm, high importance to the
   Approval Gate's correctness (Phase 5).
4. **Campaign pipeline scope** (#3) — determines whether Phases 3–8's security work must be
   duplicated for a second pipeline.
5. **Workflow History vs. Audit Log scope sign-off** (#8) — already has a working proposal; needs
   only stakeholder confirmation, not new design work.
6. **Product Media storage shape** (#9) and **notification channel** (#11) — needed before Phase 2
   schema work is finalized, but low business risk either way.
7. **Retry semantics** (#5) and **Shopify rate-limit handling** (#6) — needed before Phase 7, not
   before.
8. **Everything else** (#7, #10, #12–17) — can be deferred to post-Phase-13 without blocking core
   implementation, but should not be forgotten before production rollout.
