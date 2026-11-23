# Current Architecture — AI Shopify Product Launch Agent

This document describes the system **as it actually exists in the repository today** (`shopify-product-launch/`), verified by reading the real source files. It is the baseline for the planned "AI Product Launch Cockpit" upgrade. Nothing in this document is aspirational — gaps are called out explicitly as gaps, not filled in with assumptions.

## 1. What this repository actually contains

It is **not just a Shopify product launch agent**. It's two coexisting products sharing one FastAPI process and one Shopify store:

1. **Product Launch Agent** — a Google ADK multi-agent pipeline that takes either (a) a raw product name/description ("Launch Campaign") or (b) an uploaded folder with `product.json` + media ("Create from Folder"), and turns it into a Shopify product. This is the part the request is about.
2. **Workshops Platform** — a separate, fully working mini-business system: a SQLite-backed workshop catalog, an admin console (`static/admin.html`, "Platform Control Center"), a public customer landing/registration page (`static/landing_page.html`), Shopify order webhook handling, and transactional email (`email_service.py`). It reuses the same Product Launch Agent pipeline internally to generate and publish workshop listings to Shopify.

Both are served by the same `main.py` FastAPI app, share the same in-memory `active_sessions` dict and the same ADK `Runner`s.

## 2. Backend architecture

**Entry point:** `main.py` (1317 lines), FastAPI app named "AI Shopify Product Launch Agent API".

**Process model:** single Python process, `uvicorn main:app`. No auth middleware, no database migrations framework, no background worker/queue — background work runs via FastAPI `BackgroundTasks` inside the same process.

**In-memory session store:** `active_sessions: Dict[str, ProductLaunchState] = {}` (main.py:90). This is the source of truth for "is my launch done yet" for both Campaign and Folder flows. It is wiped on every process restart/reload — there is no persistence layer for in-flight launch state.

**State schema:** `state.py` — a single flat Pydantic model `ProductLaunchState` used for both the Campaign workflow and the Folder workflow (~50 fields covering input, AI outputs, images, Shopify IDs, verification, reports, duplicate-detection, Firebase sync, and `errors: Dict[str,str]` / `failed_stage`).

## 3. Google ADK implementation

- `workflow/adk_runner.py` — creates one shared `InMemorySessionService` and two `Runner`s: `runner` (Campaign workflow) and `folder_runner` (Folder workflow). Both share the same session service and `APP_NAME = "shopify-product-launch"`.
- `workflow/session_manager.py` — `create_session()` seeds ADK session state with a large dict of default keys; `USER_ID = "default-user"` is a **hardcoded constant**, not derived from any authenticated user.
- `product_workflow.py` — defines the two `Workflow` DAGs:
  - `product_launch_workflow` (Campaign): `strategist → copywriter → seo → marketing → image_prompt → image_generator → publisher → verification → report_generator`
  - `folder_product_workflow` (Folder): `folder_ingestion → folder_validation → folder_creation → folder_media → folder_verification → folder_report`
- `workflow/dag.py` is dead code — an unused, skeletal 3-node DAG sketch, superseded by `product_workflow.py`. Should not be extended.
- Both flows are driven from `main.py` via `asyncio.run()` wrapping `runner.run_async()` (fixed this session — previously used the sync `runner.run()`, which silently swallowed tool exceptions in a background thread).

## 4. Agents (`agents/`)

Campaign pipeline: `strategist_agent.py`, `copywriter_agent.py`, `seo_agent.py`, `marketing_agent.py`, `image_prompt_agent.py`, `image_generator_agent.py`, `publisher_agent.py`, `verification_agent.py`, `report_generator_agent.py`.

Folder pipeline: `folder_agents.py` defines six `Agent`s (`FolderIngestionAgent`, `FolderValidationAgent`, `FolderCreationAgent`, `FolderMediaAgent`, `FolderVerificationAgent`, `FolderReportAgent`), each a thin Gemini-2.5-flash wrapper instructed to call exactly one tool.

All agents are single-tool, single-purpose — the "intelligence" is mostly in the tool code, not agent reasoning.

## 5. Tools

- `tools/folder_tools.py` (1046 lines) — the real logic for the Folder pipeline: `ingest_and_extract_folder_tool`, `validate_folder_data_tool`, `create_shopify_product_tool`, `upload_folder_media_tool`, `verify_folder_product_tool`, `generate_folder_reports_tool`. Also contains a `_debug_state()` diagnostic helper added during this session's incident investigation.
- `tools/file_extractor.py` — folder/file parsing (product.json, fallback .txt/.md fields, image/video detection).
- `tools/image_generator.py`, `tools/product_context.py`, `tools/workflow_context.py` — Campaign-pipeline support tools.

## 6. Shopify integration

- `shopify_client.py` (1223 lines) — hand-written Admin REST + GraphQL client. Reads `SHOPIFY_STORE_URL` / `SHOPIFY_ACCESS_TOKEN` / `SHOPIFY_API_VERSION` from environment only (`_get_config()`, main.py never touches these directly). Functions: `create_product`, `update_product`, `upload_product_image(s)`, `upload_product_media_files` (GraphQL staged uploads, used for both images and video), `get_product`, `get_product_by_sku`, `get_product_by_title` (duplicate detection), collection helpers.
- `services/shopify_media_service.py` — resilience wrapper around the client: `retry_upload` / `retry_upload_media` with exponential backoff, `verify_media` (GraphQL read-after-write check).
- `shopify_mock/` exists but is explicitly disconnected — `main.py` has a comment confirming the mock router was removed and all calls now hit the real Shopify Admin API.
- Credentials never appear in frontend code or API responses observed; they are read server-side only via `os.getenv`.
- Webhook: `POST /api/webhooks/orders/create` — the **only** authenticated endpoint in the app, verified via Shopify's HMAC-SHA256 signature (`SHOPIFY_API_SECRET`), used to detect workshop-registration orders and trigger confirmation emails.

## 7. Firebase / Firestore / Storage

- `services/firebase_service.py` — lazy-initializes `firebase_admin` from `FIREBASE_SERVICE_ACCOUNT_KEY` (a local file path env var). If unset or unreachable, **every function silently falls back** to writing JSON files under `outputs/mock_firestore/`. Collections actually used today: `products` (by product_id) and `stores/{id}/design_system`. No `users`, `roles`, `launches`, `approvals`, or `audit_logs` collections exist yet.
- `services/firebase_storage_service.py` — `upload_file(product_id, folder_name, file_path)` uploads to `products/{product_id}/{folder_name}/{filename}` in Firebase Storage, calls `blob.make_public()` (files become **publicly readable by anyone with the URL** — no Storage Security Rules layer exists in this repo to change that), falls back to copying into `outputs/mock_storage/` served directly by FastAPI static files if Firebase isn't configured.
- No Firestore Security Rules file exists in the repo. Since there are no client-side Firestore writes at all currently (all Firestore access is server-side via `firebase-admin`, which bypasses rules), this is a **latent** gap rather than an active hole — but it will become a real one the moment any client-side Firebase SDK usage is introduced (e.g. Firebase Auth on the frontend).

## 8. Authentication — **none**

Confirmed by reading all of `main.py`: no `Depends()` auth dependency, no session cookie, no JWT, no API key check, on any endpoint. `CORSMiddleware` is configured with `allow_origins=["*"]` **and** `allow_credentials=True` (main.py:49-55) — permissive even by the standard of an unauthenticated app, and normally an invalid/dangerous combination once credentials are introduced. `USER_ID = "default-user"` is hardcoded everywhere state is created. The only signature check anywhere in the app is the Shopify webhook HMAC check.

**Practical implication:** anyone who can reach the server (e.g. anyone on the same network, or the public internet if deployed without a reverse-proxy gate) can create launches, approve/publish to the live Shopify store, and read every session's full state via `GET /status/{id}` if they know or guess the UUID.

## 9. Authorization — **none**

There are no roles, no permissions, no concept of "who is allowed to approve a launch." `POST /api/folder-launch/{session_id}/approve` — the human-approval endpoint — accepts the approval from anyone who can send the request; it does not check identity at all.

## 10. Human-in-the-loop today

It exists, but only as a **binary flag**, not a workflow with named states or an audit trail:
- `preview_mode: bool` / `approved_to_publish: bool` on `ProductLaunchState`.
- Folder flow: `POST /launch-folder` with `preview=true` runs Ingest→Validate→Create in draft/dry-run intent, and the pipeline can pause; `POST /api/folder-launch/{session_id}/approve` resumes it toward Shopify publish.
- There is no record of *who* approved, no reviewable diff of AI-generated vs. human-edited fields, and status strings (`pending`, `running`, `awaiting_approval`, `completed`, `failed`) live only in the in-memory dict — nothing is written to Firestore/SQLite as an auditable event.

## 11. Frontend — three separate, unauthenticated HTML surfaces

1. **`static/index.html`** ("Launch Console") — 1297 lines, vanilla JS, the UI in the screenshots this session. Tabs for "Launch Campaign" and "Create from Folder". Talks directly to `/launch`, `/launch-folder`, `/status/{id}`, `/api/folder-launch/{id}/approve`, `/health`. This is the primary target of the requested Cockpit redesign.
2. **`static/admin.html`** ("Platform Control Center") — 2157 lines, the Workshops Platform admin UI (dashboard metrics, create-workshop wizard, workshop history). Talks to `/api/dashboard/metrics`, `/api/workshops*`.
3. **`static/landing_page.html`** — 1695 lines, public customer-facing workshop registration/checkout page. Talks to `/workshops/{handle}`, `/api/workshops/{id}/register`.

No shared design system, no shared nav/auth shell between the three today. No build step — these are static files served directly by FastAPI (`app.mount`/`FileResponse`), no bundler, no framework.

## 12. API endpoint inventory (from `main.py`)

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/` | GET | none | serves index.html |
| `/launch` | POST | none | start Campaign workflow |
| `/launch-folder` | POST | none | start Folder workflow (multipart upload) |
| `/api/folder-launch/{id}/approve` | POST | none | **human approval gate** |
| `/status/{id}` | GET | none | poll `ProductLaunchState` |
| `/api/dashboard/metrics` | GET | none | Workshops KPIs |
| `/api/workshops` | GET/POST | none | list/create workshops |
| `/api/workshops/{id}` | GET | none | workshop detail |
| `/api/workshops/{id}/generate` | POST | none | AI-generate workshop content |
| `/api/workshops/{id}/publish` | POST | none | publish workshop to Shopify |
| `/api/workshops/{id}/register` | POST | none | public customer registration |
| `/api/webhooks/orders/create` | POST | **HMAC** | Shopify order webhook |
| `/workshops/{handle}` | GET | none | public landing page |
| `/health` | GET | none | liveness check |

## 13. Existing tests (`tests/` + root-level)

`test_api.py`, `test_copywriter.py`, `test_folder_workflow.py`, `test_image_prompt.py`, `test_image_workflow.py`, `test_media_state_regression.py` (this session's regression suite for the Ingest/Media incident), `test_publisher.py`, `test_report_generator.py`, `test_seo.py`, `test_strategist.py`, `test_verification.py`, `test_customer_flow.py` / `test_workshop_platform.py` (Workshops Platform, currently erroring in the sandbox due to sqlite/permission environment issues, unrelated to app logic), `test_firebase_workflow.py`, `test_real_firebase*.py` (require a real local Firebase key file, skipped in this sandbox). Root also has `test_agents.py`, `test_imports.py`, `run_tests.py`, `run_image_tests.py`. **No auth/authz tests exist**, because there is no auth/authz to test yet.

## 14. Environment variables / secrets (names only, from `.env.example`)

`GOOGLE_API_KEY`, `GEMINI_API_KEY`, `SHOPIFY_STORE_URL`, `SHOPIFY_ACCESS_TOKEN`, `SHOPIFY_API_VERSION`, `SHOPIFY_API_SECRET`, `APP_PORT`, `APP_HOST`, `LOG_LEVEL`, `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `SALES_TEAM_EMAIL`, `SENDER_EMAIL`, `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`. Plus (used in code but not in `.env.example`): `FIREBASE_SERVICE_ACCOUNT_KEY`, `FIREBASE_STORAGE_BUCKET`. `.env` is correctly gitignored; only `.env.example` is tracked in git — no committed secrets found.

## 15. Security risks identified in this pass

1. **No authentication anywhere** — the single biggest gap; everything below is downstream of this.
2. **No authorization / RBAC** — publish-to-live-Shopify is reachable by anyone who can reach the process.
3. **CORS: `allow_origins=["*"]` + `allow_credentials=True`** — should never be combined; needs an explicit allow-list once auth/cookies exist.
4. **Firebase Storage objects are made public (`blob.make_public()`)** for all uploaded product media — acceptable for public product images, but there is no distinction today between public and restricted media.
5. **In-memory-only session state** — not a security bug per se, but means there is no durable audit trail of who launched/approved what; also means restarting the server silently drops all in-flight launches (this was mistaken for a code bug earlier in this same session).
6. **Session/launch IDs are UUIDv4 but `GET /status/{id}` has no ownership check** — anyone with the ID (which is returned in a plain POST response, not secret) can read the full state, including any AI-generated content and error details.
7. **No rate limiting** on any endpoint, including the multipart folder-upload endpoint.
8. **`errors` dict can contain full Python tracebacks** (paths, internals) and is currently returned as-is via `GET /status/{id}` with no distinction between what an ordinary user vs. an admin should see.

## 16. What this means for the planned Cockpit upgrade

The Folder/Campaign pipeline logic itself (agents, tools, Shopify client, Firebase fallback pattern) is solid, working, and should be preserved as-is. The gap the request describes — no user perception, no auth, no RBAC, no durable audit trail, developer-looking UI — is accurate and confirmed by this inspection. The Workshops Platform is a second, adjacent product sharing the same backend and must not be broken by this work, even though it's out of scope for the "Product Launch Cockpit" redesign itself.
