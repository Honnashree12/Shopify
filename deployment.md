# deployment.md — Kiddypi Shopify Product Launch System

Source of truth: all eight existing documents. Describes how the system is deployed and operated —
no application code, no real secrets, no invented infrastructure.

---

## 1. Environments

| Environment | Purpose |
|---|---|
| Local/Dev | Developer machines, mock Firebase/Firestore fallback (existing `outputs/mock_storage/`, `outputs/mock_firestore/`), Shopify sandbox store |
| Staging **[PROPOSED]** | Pre-production verification against real Firebase project (test) and Shopify sandbox store — not confirmed to exist today |
| Production | Real Firebase project, real Kiddypi Shopify store — existing, already in use for the current working pipeline |

Staging is proposed, not confirmed — no source document establishes whether a staging tier exists
today (**TBD — Requires Confirmation**).

---

## 2. Application Components

| Component | Status |
|---|---|
| FastAPI backend (`main.py` + modules) | Existing, extended (not rewritten) per this documentation set |
| ADK agent runner (`workflow/adk_runner.py`, `workflow/session_manager.py`) | Existing, unmodified |
| React/Vite/TypeScript frontend | New, per `ui-spec.md` (frontend scaffold begun this session, incomplete) |
| Firestore | Existing mock fallback; real Firestore usage extended per `data-model.md` §12 |
| Firebase Storage | Existing mock fallback; real usage for media, per `agents.md` §16 |
| Shopify Admin API integration | Existing, unmodified (`shopify_client.py`, `services/shopify_media_service.py`) |

---

## 3. Environment Variables

Categories only — no real values, per Global Rules:

| Category | Purpose |
|---|---|
| `SHOPIFY_*` | Store domain, API access token, API version — existing |
| `FIREBASE_*` | Project ID, service account credentials path, storage bucket — existing (mock-fallback used when absent) |
| `AI_MODEL_*` | ADK/model provider configuration — existing |
| `AUTH_*` **[PROPOSED]** | Identity provider configuration — depends entirely on the still-unconfirmed auth mechanism (`security.md` §22) |
| `APP_ENV` **[PROPOSED]** | Environment selector (local/staging/production) |

No secret values appear in this document, in logs (§9), or in any API response (`api-spec.md` §14).

---

## 4. Secrets Management

- Existing pattern: environment variables loaded at process start, never committed to the
  repository.
- **[PROPOSED]** Production secrets sourced from a managed secret store (e.g. Google Secret
  Manager) rather than plain environment files, consistent with the Firebase/Cloud Run direction
  implied by the existing `Dockerfile`/`cloudbuild.yaml` — not confirmed as the final approach.
- Shopify access token and Firebase service account key are the two highest-sensitivity secrets
  (`security.md` §13, Secret classification tier) and require the strictest handling of any
  configuration value in the system.

---

## 5. Firebase Deployment

- Firestore: existing 5-collection design (`data-model.md` §12) deployed via standard Firestore
  provisioning; composite indexes proposed in `data-model.md` §12 must be created before the
  corresponding queries (e.g. filtered product lists) are used in production.
- Firebase Storage: existing bucket configuration, extended only to store product media consistent
  with the current mock-storage fallback's real-storage equivalent.
- Firestore security rules: **TBD — Requires Confirmation** whether used as a second enforcement
  layer alongside backend authorization (`security.md` §10) — not assumed here.

---

## 6. Shopify Configuration

- Existing Admin API integration, existing scopes — **no new Shopify API scopes are invented or
  assumed in this document.** Any scope changes required by future work are **TBD — Requires
  Confirmation**, to be determined against the real Shopify app configuration, not guessed here.
- Sandbox/test store used for all non-production testing (`testing.md` §5, §13).
- Webhook endpoint (`/api/webhooks/orders/create`) — existing, HMAC-verified, unrelated to the
  product launch workflow (Workshops order flow), unchanged by this design.

---

## 7. Agent Runtime

- ADK agents run in-process within the FastAPI backend, as they do today — this design introduces
  no separate agent runtime or microservice (`architecture.md` Decision D6).
- Deployment target for the backend process itself is an open question — see §15 Cross-Document
  Issues; this document does not resolve it, only surfaces it clearly since it is the most
  concrete conflict found across all eight documents.

---

## 8. Database

- Firestore is the single system of record for all pre-publish and workflow data (`data-model.md`
  §12) — no additional database is introduced.
- Mock-fallback mode remains available for local development, unchanged.
- Backup/retention policy for Firestore data: **TBD — Requires Confirmation** (`data-model.md`
  §15 — no source document specifies a retention duration).

---

## 9. Logging

- Existing application logging retained.
- **No secret value is ever logged** — Shopify access tokens, Firebase service account keys, and
  any future auth tokens are excluded from all log output, extending the existing implicit
  practice into an explicit, permanent requirement (`security.md` §8).
- Error logs include `correlation_id` (`api-spec.md` §11) to allow tracing a failure from a log line
  back to a specific `workflow_run_id` and audit trail, without needing to log sensitive payload
  contents.

---

## 10. Monitoring

- **[PROPOSED]** Health check endpoint — extends the existing real `/health` endpoint
  (`api-spec.md` §10 row 13), which already reports `adk_ready`/`runner` status.
- **[PROPOSED]** Alerting on repeated publish failures (`failed_stage` patterns) and on Approval
  Gate rejections at unusual volume (possible bypass attempts, `security.md` §18 threat model).
- No specific monitoring platform is assumed or invented — selection is **TBD — Requires
  Confirmation**.

---

## 11. Failure Recovery

- A failed publish attempt leaves the product in a clearly failed state with `failed_stage`
  populated accurately (`workflow.md` §14, already fixed once for the Media stage via
  `_derive_folder_failed_stage()`, this document requires the fix's coverage extend to every
  stage).
- Retry semantics (automatic vs. manual re-submission after failure) remain **TBD — Requires
  Confirmation** — flagged consistently across `workflow.md`, `security.md`, and `testing.md`; not
  resolved here either.
- Partial media upload failure does not require re-uploading already-successful files, per the
  existing per-file tracking in `services/shopify_media_service.py` (`api-spec.md` §13).

---

## 12. Rollback

- Application code rollback: standard redeploy of the previous known-good backend/frontend build —
  no data migration is implied by a rollback since this design adds no destructive schema changes
  to existing Firestore data.
- A published Shopify product is not automatically unpublished by a code rollback — reverting a bad
  deployment does not retroactively revert live Shopify listings; any such action remains a manual,
  human decision, consistent with the human-in-the-loop principle applying to unpublishing as much
  as publishing (**TBD — Requires Confirmation**: no source document defines an "unpublish" workflow
  at all).

---

## 13. Security Checklist

Pre-deployment, drawn directly from `security.md`:
1. No endpoint except `/health` and the Shopify webhook is unauthenticated.
2. Every state-changing endpoint enforces the correct role (`api-spec.md` §10).
3. Approval Gate checks are present at both the API layer and inside
   `create_shopify_product_tool` (defense-in-depth, `security.md` §5).
4. No secret appears in logs, error responses, or committed configuration.
5. CORS is no longer `allow_origins=["*"]` with `allow_credentials=True` — the existing
   configuration flagged as a security risk in `docs/CURRENT_ARCHITECTURE.md` §15 must be
   restricted to known origins before production use.
6. Self-approval is denied by default, pending explicit confirmation otherwise.

---

## 14. Production Readiness Checklist

1. All items in §13 Security Checklist verified.
2. All End-to-End scenarios in `testing.md` §11 passing against a Shopify sandbox store.
3. All Acceptance Criteria in `testing.md` §14 met.
4. Firestore composite indexes (`data-model.md` §12) created.
5. Authentication provider selected and confirmed (currently TBD).
6. Deployment target confirmed (currently conflicting — see §15).
7. Monitoring and alerting in place for publish failures and Approval Gate rejections.

---

## 15. Cross-Document Issues

## Cross-Document Issues Requiring Confirmation

1. **Deployment target conflict — the most concrete conflict found across all eight documents.**
   The repository contains both a `Dockerfile`/`cloudbuild.yaml` (suggesting Cloud Run,
   `architecture.md` §19 open question 2) and an `adk.yaml` (suggesting Vertex AI Reasoning Engine,
   with placeholder values, per `docs/CURRENT_ARCHITECTURE.md`). No source document declares which
   is the intended production target, and the two imply materially different deployment models
   (containerized HTTP service vs. managed agent runtime). This must be resolved before §7/§10/§14
   can be finalized.
2. **Staging environment existence** (§1) is assumed possible but not confirmed by any source
   document.
3. **Firestore retention/backup policy** (§8) — carried forward from `data-model.md` §15, still
   unresolved here.
4. **Shopify API scopes** (§6) — not enumerated in any source document; must be confirmed against
   the real Shopify app configuration before deployment, not assumed from this document.

No other deployment-level conflicts were found between the eight source documents.
