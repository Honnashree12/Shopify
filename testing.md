# testing.md — Kiddypi Shopify Product Launch System

Source of truth: all seven existing documents (`requirements.md`, `architecture.md`, `agents.md`,
`workflow.md`, `security.md`, `ui-spec.md`, `data-model.md`, `api-spec.md`). Describes what must be
tested and why — not test code.

---

## 1. Testing Objectives

1. Prove the human approval gate cannot be bypassed under any code path (the single highest-priority
   objective — `security.md` §5, `agents.md` §3).
2. Prove the existing, working publish pipeline (Create → Media → Verify → Report) is unchanged in
   behavior by anything added around it.
3. Prevent regression of the two real incidents already fixed this project: (a) the
   `Runner.run()`/background-thread swallowed-exception bug, (b) the hardcoded `"Media"`
   `failed_stage` bug now fixed by `_derive_folder_failed_stage()`.
4. Confirm role-based access control matches `security.md` §4 exactly, for every endpoint in
   `api-spec.md` §10.
5. Confirm state transitions match `workflow.md` §3/§4 exactly — no product can reach `PUBLISHED`
   without having passed through `APPROVED`.

---

## 2. Unit Testing

Existing, real, unmodified units to cover:
- `state.py` — `ProductLaunchState` field defaults and validation.
- `main.py` — `_derive_folder_failed_stage()`, request/response shaping for existing endpoints.
- `tools/folder_tools.py` — manifest parsing, missing-field detection, conflict detection.
- `services/shopify_media_service.py` — `retry_upload_media`, `verify_media`, per-file
  success/attempts tracking.
- `shopify_client.py` — product create/update payload construction.

New units required by this design (not yet implemented, per `implementation-plan.md`):
- Approval Gate checks (§5 `security.md`) — product ID, workflow ID, current `product_version`,
  approval status, approver identity, approver role, approval timestamp, version match — each as an
  isolated, independently testable check.
- Role resolution (token → `users/{uid}.role`) — never trusting a client-supplied role.
- Audit log event construction — one test per event type in `data-model.md` §9.

---

## 3. Agent Testing

Scope: the existing ADK agents in `agents/folder_agents.py`, `agents/publisher_agent.py`,
`agents/verification_agent.py` — unchanged by this design (`agents.md` §3, §16).

- Each agent's tool-boundary contract (inputs/outputs) tested in isolation, independent of the full
  pipeline, matching `agents.md` §7 (Tool Boundaries).
- The full `folder_product_workflow` DAG tested end-to-end against a mock Shopify client, confirming
  stage order Create → Media → Verify → Report is preserved.
- Confirm no agent call path exists that reaches `create_shopify_product_tool` without an upstream
  Approval Gate pass — this is the defense-in-depth check from `security.md` §5, and must be tested
  as a negative case (attempt to call the tool directly, without approval, and confirm rejection).
- The Campaign pipeline (`product_launch_workflow`, 9 agents) remains **TBD — Requires
  Confirmation** for in-scope status (`architecture.md` §19); if it remains in the shipped system, it
  requires the same Approval Gate testing as the Folder pipeline before it can be considered secure.

---

## 4. Human-in-the-Loop Testing

The core, non-negotiable test category (`requirements.md` primary goal; `agents.md` §3):

- A product cannot transition to `PUBLISHING` without a corresponding `PRODUCT_APPROVED` audit
  event carrying a real approver `user_id` with role `APPROVER`/Reviewer.
- Sandeep (or any Reviewer) can Approve and Request Changes; Lakshmi (or any Catalogue Admin) cannot
  call Approve, tested as an explicit 403 case (`security.md` §4).
- Self-approval: submitter approving their own product — default-denied per every document that
  touches this (`requirements.md` §24, `security.md`, `workflow.md`), tested as a 403 case unless a
  future confirmation overrides it.
- A product edited after approval but before publishing completes must invalidate the stale
  approval (`product_version` vs `approved_at_version` mismatch, `data-model.md` §4) — tested as a
  409 on the Approval Gate.
- Request Changes always requires a non-empty comment (`api-spec.md` §10 row 6) and always returns
  the product to `CHANGES_REQUESTED`, never silently to `DRAFT`.

---

## 5. Shopify Integration Testing

- Product create/update against a Shopify test/sandbox store (never production) — confirming SKU/
  title duplicate detection still functions as it does today.
- Media upload success and failure paths (`services/shopify_media_service.py`), including partial
  failure (some files succeed, some fail) — confirming `failed_stage` reports `"media"` accurately,
  not hardcoded.
- Rate-limit (`429`) handling — currently unspecified for retry/backoff, per `architecture.md` §19,
  open question 5; testing here is blocked until that behavior is confirmed.
- Verification stage (`verification_agent.py`) confirming the product is actually live and matches
  submitted data before `PUBLISHED` is set.

---

## 6. Firebase/Firestore Testing

- Mock-fallback mode (`outputs/mock_firestore/`, `outputs/mock_storage/`) continues to function
  identically for local/dev testing when real Firebase isn't configured — this existing behavior
  must not regress.
- Real Firestore writes for all five collections (`data-model.md` §12) — schema/field-level
  validation on write.
- Concurrent-write scenario: two reviewers attempting to act on the same product simultaneously —
  confirming `product_version` check prevents a lost-update/double-approval race.
- Firestore security rules (if used as a second enforcement layer, still **TBD — Requires
  Confirmation** per `security.md` §10) tested independently of backend-level checks, if implemented.

---

## 7. Authentication Testing

Authentication mechanism itself remains **TBD — Requires Confirmation** (`security.md` §22), so this
section tests the *contract*, not a specific provider:

- Missing token → 401 on every protected endpoint.
- Expired/invalid token → 401.
- Valid token, unknown/deleted user → 401 (not 403 — user doesn't exist to have a role).
- Token replay/reuse after logout — behavior depends on chosen provider; tracked as TBD until
  provider is confirmed.

---

## 8. Authorization Testing

The most important negative-test category in this document:

- **A Catalogue Admin cannot call Approve** — direct API call, not just UI-hidden — confirmed 403.
- **A user cannot publish directly**, bypassing Approve — there is no publish endpoint to call
  (`api-spec.md` §6), but this must still be tested by attempting to invoke the internal publish
  path without a preceding successful Approval Gate check, confirming rejection.
- **A Technical/Platform Admin cannot approve products** unless explicitly granted Reviewer
  permissions — role scope must match `security.md` §4 exactly, not be broadened for convenience.
- Ownership checks on `GET /api/products/{id}` and `/workflow` — a Catalogue Admin cannot view
  another Catalogue Admin's product unless also a Reviewer/Platform Admin (`api-spec.md` §10 rows
  2, 8).
- Audit log (`/api/audit-logs`) restricted to Platform Admin only — every other role gets 403.

---

## 9. Error Testing

Explicitly includes the exact regression class already seen once in this codebase:

- **NoneType regression class**: any code path where a tool or service can return `None` /
  `null` unexpectedly must be tested to confirm the *real* originating error (e.g. "Shopify media
  upload failed: HTTP 429") propagates in `error.message`, never masked by a downstream
  `'NoneType' object has no attribute ...` error. This is a permanent regression test, not a
  one-time fix verification.
- Malformed request bodies → 400, with the structured error shape from `api-spec.md` §11, never a
  bare 500.
- Upstream Shopify/Firestore unavailability → 503, not misreported as a validation or auth error.
- Every error surfaced to a non-Platform-Admin caller must have `technical_detail: null`
  (`security.md` §15) — tested as an explicit assertion, not an assumption.

---

## 10. State Propagation Tests

- `failed_stage` on a `WorkflowRun` accurately reflects which real stage failed (Create, Media,
  Verify, Report) — direct regression test for `_derive_folder_failed_stage()`, extended to cover
  every stage, not just Media.
- Product status and `WorkflowRun` status never diverge in a way the UI can't reconcile — e.g. a
  product showing `PUBLISHED` while its most recent `WorkflowRun` shows `FAILED` is an invalid state
  and must be tested as unreachable.
- `product_version` increments exactly once per edit, never skipped or double-incremented across
  concurrent requests.

---

## 11. End-to-End Testing

| # | Scenario |
|---|---|
| A | Lakshmi creates a product (folder upload), submits, Sandeep approves, product publishes successfully, report generated |
| B | Lakshmi creates a product, submits, Sandeep requests changes, Lakshmi edits and resubmits, Sandeep approves, publishes |
| C | Sandeep requests changes twice before approving (multiple round-trips) |
| D | A Catalogue Admin attempts to call Approve directly via API — rejected |
| E | Media upload fails mid-publish — product moves to a failure state, `failed_stage: "media"`, error message is the real Shopify error, not NoneType |
| F | Product is edited after approval but before the async publish step completes — approval invalidated, publish blocked |
| G | Two reviewers attempt to approve the same product concurrently — only one succeeds, second gets 409 |
| H | Platform Admin views the full system-wide audit log; a Catalogue Admin cannot |
| I | Notification is created on status change and appears in the recipient's in-app notification list only |
| J | Full folder-based bulk import path (existing `/launch-folder` pattern) end-to-end through to `PUBLISHED`, confirming the legacy intake path still works unmodified |

---

## 12. Regression Testing

Explicitly required, tied to real prior incidents in this codebase:

1. **`Runner.run()` background-thread silent-exception bug** — regression test confirms tool
   exceptions always propagate to the caller/response, never silently swallowed.
2. **Hardcoded `"Media"` `failed_stage`** — regression test confirms `failed_stage` is dynamically
   derived for every possible stage, not defaulted to one value.
3. Any future fix follows the same pattern: a regression test is added alongside the fix, not just a
   manual verification.

---

## 13. Test Data

- Use Shopify test/sandbox store credentials only — never production credentials in any test run
  (`security.md` §8).
- Synthetic product data only, matching the real field shapes in `data-model.md` §3 — no real
  customer or business-sensitive data in test fixtures.
- Mock Firebase/Firestore fallback (`outputs/mock_firestore/`) used for fast local test runs; real
  Firestore test project used for integration-level runs.

---

## 14. Acceptance Criteria

Testing is considered sufficient for a release when:
1. Every Acceptance Criterion in `requirements.md` §22 has at least one corresponding automated
   test.
2. Every negative authorization case in §8 above passes (returns the correct 401/403), with no
   exceptions.
3. The two named regressions (§12) have dedicated, passing regression tests.
4. All ten end-to-end scenarios (§11) pass against a Shopify sandbox store.
5. No test suite run requires real production Shopify or Firebase credentials.

---

## 15. Cross-Document Issues

## Cross-Document Issues Requiring Confirmation

1. **Shopify rate-limit retry/backoff behavior** is undefined by any source document
   (`architecture.md` §19 open question 5) — integration tests for this scenario (§5 above) cannot
   be finalized until that behavior is confirmed.
2. **Campaign pipeline in/out of scope** (`architecture.md` §19) — if it ships, it requires the full
   Approval Gate test suite in §3/§4/§8 applied to it as well; this has not been scoped into any
   estimate because the pipeline's inclusion itself is unconfirmed.

No other testing-level conflicts were found between the eight source documents.
