# Agentic BOSS Integration Contract: Commerce Workflow Automation Trio

**Version:** 1.0.0 (Production Ready)  
**Date:** November 7, 2026  
**Target Service:** Commerce Automation Subsystem (`shopify-product-launch`)  
**Consumer:** Agentic BOSS Ecosystem (`pod-commerce-experience-ops` / Core BOSS Shell)  
**Security Level:** Production Enforced — Zero-Trust RBAC & Secret Masking  

---

## 1. Executive Summary & Architecture Overview

This integration contract defines the precise interaction boundaries, networking topologies, authentication protocols, and API schemas required for the Agentic BOSS ecosystem to consume and orchestrate the three core Commerce Workflow Automation features:

1. **SEO Optimization & Checklist Engine (SEO Dashboard)**
2. **Unified Product Validation & Quality Control (53-Check Engine)**
3. **Automated Product Launch Workflow (Multi-Asset Ingestion & Approval Pipeline)**

The Commerce application operates as an independent, stateless microservice exposed via FastAPI with a companion React/Vite cockpit. It communicates upstream with Shopify's GraphQL Admin API (`2025-07`), Firebase Authentication/Firestore, and Google Search Console APIs.

### System Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientLayer["Agentic BOSS Host Layer"]
        BossUI["Agentic BOSS Web Shell / Host UI"]
        BossNav["Global Navigation & PodDevShell"]
    end

    subgraph GatewayLayer["API Gateway & Ingress (Reverse Proxy)"]
        Nginx["Reverse Proxy / API Gateway"]
    end

    subgraph CommerceService["Commerce Automation Service (Port 8000)"]
        FastAPI["FastAPI Application (main.py)"]
        AuthService["Auth Middleware & RBAC (auth_service.py)"]
        SEOEngine["SEO Optimization Workflow (seo_agent)"]
        ValEngine["Unified Validation Engine (53 Checks)"]
        LaunchEngine["Product Launch Workflow (adk_runner)"]
        SQLiteDB[("Local Session Store (launch_platform.db)")]
    end

    subgraph ExternalServices["External Cloud & Enterprise Services"]
        ShopifyAPI["Shopify GraphQL Admin API (2025-07)"]
        FirebaseAuth["Firebase Auth & Firestore (RBAC Profiles)"]
        GSC["Google Search Console API v1"]
    end

    BossUI -->|1. Authenticated User Action| GatewayLayer
    BossNav -->|Mounts Sub-app / Calls APIs| GatewayLayer
    Nginx -->|2. Forwards Bearer JWT + Headers| FastAPI
    FastAPI --> AuthService
    AuthService -->|Verifies JWT & Roles| FirebaseAuth
    FastAPI --> SEOEngine
    FastAPI --> ValEngine
    FastAPI --> LaunchEngine
    LaunchEngine --> SQLiteDB
    SEOEngine -->|GraphQL Queries/Mutations| ShopifyAPI
    SEOEngine -->|Search Traffic Analytics| GSC
    ValEngine -->|Catalog Inspection| ShopifyAPI
    LaunchEngine -->|Product Creation| ShopifyAPI
```

---

## 2. Authentication & Authorization Contract

All endpoints across the trio features (except `/health` and static documentation) require explicit authentication via OAuth2/Bearer JSON Web Tokens issued by Firebase Authentication.

### 2.1 Token Format & Verification
- **Header:** `Authorization: Bearer <FIREBASE_ID_TOKEN>`
- **Token Type:** Cryptographically signed RS256 JWT issued by `https://securetoken.google.com/<FIREBASE_PROJECT_ID>`.
- **Expected Claims:**
  - `iss`: `https://securetoken.google.com/<FIREBASE_PROJECT_ID>`
  - `aud`: `<FIREBASE_PROJECT_ID>`
  - `sub` / `uid`: Unique Firebase User Identifier
  - `email`: Authenticated user email address
  - `exp`: Non-expired epoch timestamp

### 2.2 Role-Based Access Control (RBAC)
User roles are maintained server-side in Firestore under `/users/{uid}` with fields:
`{ role: string, active: boolean, name: string }`.

| Role Identifier | Permissions & Capabilities |
| :--- | :--- |
| `CATALOGUE_ADMIN` | Inspect SEO audits, generate SEO proposals, run validation audits, upload product launch folders, trigger catalog remediations. |
| `APPROVER` | All `CATALOGUE_ADMIN` permissions, plus approve/reject launch workflows, apply live SEO changes, approve product changes. |
| `PLATFORM_ADMIN` | Full superuser access: manage users, retry failed executions, override configurations, apply catalog-wide remediations. |

### 2.3 Production Security Strictness
When `APP_ENV=production`:
- Any token starting with `mock-` is immediately rejected with `401 Unauthorized`.
- Fallback bypass (`ALLOW_AUTH_FALLBACK=True`) is disabled.
- Wildcard CORS (`*`) causes the backend to refuse startup.

---

## 3. Comprehensive API Catalog

### Feature 1: SEO Optimization & Performance Dashboard

#### 1. Fetch Catalogue SEO Audit
- **Method / Path:** `GET /api/seo/audit`
- **Execution:** Synchronous (reads cached state or queries Shopify GraphQL).
- **Required Roles:** `CATALOGUE_ADMIN`, `APPROVER`, `PLATFORM_ADMIN`
- **Query Parameters:**
  - `search` (string, optional): Filter by title or handle.
  - `severity` (string, optional): Filter by `CRITICAL`, `WARNING`, `INFO`, `ALL`.
  - `status` (string, optional): Filter by `OPTIMIZED`, `CAN_IMPROVE`, `NEEDS_WORK`, `ALL`.
- **Response `200 OK` (JSON):**
```json
{
  "total_audited": 29,
  "products_with_issues": 12,
  "optimized_products": 17,
  "average_score": 84.5,
  "draft_excluded_count": 2,
  "products": [
    {
      "product_id": "gid://shopify/Product/1234567890",
      "title": "Robotics Explorer Kit",
      "handle": "robotics-explorer-kit",
      "status": "CAN_IMPROVE",
      "seo_score": 75,
      "issues": [
        {
          "code": "TITLE_MISSING_KEYWORDS",
          "severity": "WARNING",
          "field": "title",
          "message": "Title lacks primary category keywords.",
          "recommendation": "Append STEM / Robotics keywords."
        }
      ],
      "current_seo": {
        "title": "Robotics Kit",
        "description": "Fun kit for kids.",
        "tags": ["stem", "kits"]
      }
    }
  ]
}
```

#### 2. Generate SEO Optimization Proposals
- **Method / Path:** `POST /api/seo/proposals`
- **Execution:** Synchronous
- **Required Roles:** `CATALOGUE_ADMIN`, `APPROVER`, `PLATFORM_ADMIN`
- **Request Body:**
```json
{
  "product_ids": ["gid://shopify/Product/1234567890"]
}
```
- **Response `200 OK` (JSON):**
```json
{
  "generated_count": 1,
  "proposals": [
    {
      "product_id": "gid://shopify/Product/1234567890",
      "proposed_title": "Robotics Explorer Kit | STEM Learning Kit for Kids",
      "proposed_description": "Comprehensive robotics explorer STEM kit designed for young builders.",
      "proposed_tags": ["STEM", "Robotics", "Kids Educational Toys"],
      "proposed_handle": "robotics-explorer-kit",
      "rationale": "Improved keyword density and SERP length optimization."
    }
  ]
}
```

#### 3. Apply SEO Proposals (Dry-Run or Live)
- **Method / Path:** `POST /api/seo/apply`
- **Execution:** Synchronous
- **Required Roles:** `APPROVER`, `PLATFORM_ADMIN`
- **Request Body:**
```json
{
  "approved_proposals": [
    {
      "product_id": "gid://shopify/Product/1234567890",
      "proposed_title": "Robotics Explorer Kit | STEM Learning Kit for Kids",
      "proposed_description": "Comprehensive robotics explorer STEM kit designed for young builders.",
      "proposed_tags": ["STEM", "Robotics", "Kids Educational Toys"],
      "proposed_handle": "robotics-explorer-kit"
    }
  ],
  "dry_run": true,
  "preserve_handles": true
}
```
- **Response `200 OK` (JSON):**
```json
{
  "dry_run": true,
  "preserve_handles": true,
  "total_requested": 1,
  "successful_updates": 1,
  "failed_updates": 0,
  "details": [
    {
      "product_id": "gid://shopify/Product/1234567890",
      "status": "SIMULATED_SUCCESS",
      "fields_to_update": {
        "title": "Robotics Explorer Kit | STEM Learning Kit for Kids"
      }
    }
  ]
}
```

#### 4. Search Console OAuth & Performance Metrics
- `GET /api/seo/search-console/status` (Get GSC connection status & verified domain)
- `GET /api/seo/search-console/auth-url` (Get Google OAuth authorization redirect URL)
- `GET /api/seo/search-console/performance?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` (Fetch Google clicks, impressions, CTR, queries mapped to Shopify URLs)

---

### Feature 2: Product Validation & Quality Control (53-Check Engine)

#### 1. Fetch Validation Summary
- **Method / Path:** `GET /api/validation/summary`
- **Execution:** Synchronous (reads `outputs/unified_summary_report.json`)
- **Required Roles:** Any authenticated user
- **Response `200 OK` (JSON):**
```json
{
  "summary": {
    "total_products": 31,
    "total_checks": 53,
    "total_evaluations": 1643,
    "blockers_passed": 1220,
    "blockers_failed": 423,
    "average_score": 74.26,
    "launch_ready": 5,
    "launch_blocked": 26
  },
  "last_validated": "2026-11-07T11:57:00Z",
  "status": "idle"
}
```

#### 2. Fetch Audited Products Matrix
- **Method / Path:** `GET /api/validation/products`
- **Execution:** Synchronous (reads `outputs/unified_validation_report.json`)
- **Response `200 OK` (JSON):** Array of 31 audited product objects with full 53 check breakdown.

#### 3. Trigger Full Background Validation Audit
- **Method / Path:** `POST /api/validation/run`
- **Execution:** Asynchronous (Background Worker)
- **Response `202 Accepted` (JSON):**
```json
{
  "status": "started",
  "message": "Initiated unified 53-check audit across all active catalog products."
}
```

#### 4. Poll Audit Execution Status
- **Method / Path:** `GET /api/validation/status`
- **Execution:** Synchronous
- **Response `200 OK` (JSON):**
```json
{
  "status": "running",
  "message": "Evaluating Check 34/53 across catalog...",
  "progress_percent": 64
}
```

#### 5. Export Validation PDF Report
- **Method / Path:** `POST /api/validation/export-pdf`
- **Request Body:**
```json
{
  "product_ids": ["gid://shopify/Product/1234567890"],
  "assignee_name": "Rachana"
}
```
- **Response `200 OK`:** Binary PDF Stream (`application/pdf`) with attachment header.

---

### Feature 3: Product Launch Workflow (ADK Multi-Agent Ingestion)

#### 1. Ingest Product Asset Folder
- **Method / Path:** `POST /launch-folder`
- **Execution:** Asynchronous (triggers ADK Runner workflow)
- **Payload:** `multipart/form-data` with fields:
  - `files`: File list containing metadata CSV/Excel, imagery, certificates.
  - `preview`: boolean ("true" for dry-run extraction, "false" for staging).
- **Response `200 OK` (JSON):**
```json
{
  "session_id": "session-prod-launch-84920",
  "status": "extracting",
  "message": "Folder ingestion initiated with 8 files."
}
```

#### 2. Poll Launch Workflow Status
- **Method / Path:** `GET /status/{session_id}`
- **Execution:** Synchronous
- **Response `200 OK` (JSON):**
```json
{
  "session_id": "session-prod-launch-84920",
  "status": "pending_approval",
  "progress": 75,
  "stage": "QUALITY_GATE_VALIDATION",
  "product_data": {
    "title": "Solar Powered Mars Rover STEM Kit",
    "price": 1499.00,
    "sku": "ROVER-MARS-01",
    "validation_score": 92
  },
  "validation_results": {
    "blockers_count": 0,
    "warnings_count": 1
  }
}
```

#### 3. Submit Approval to Publish Live
- **Method / Path:** `POST /api/folder-launch/{session_id}/approve`
- **Required Roles:** `APPROVER`, `PLATFORM_ADMIN`
- **Request Body:**
```json
{
  "approved_to_publish": true,
  "product_name": "Solar Powered Mars Rover STEM Kit",
  "product_price": 1499.00,
  "duplicate_action": "REPLACE_EXISTING"
}
```
- **Response `200 OK` (JSON):**
```json
{
  "session_id": "session-prod-launch-84920",
  "status": "published",
  "message": "Product successfully pushed to Shopify Live catalog.",
  "shopify_product_id": "gid://shopify/Product/987654321"
}
```

---

## 4. Reverse Proxy & Gateway Configuration

When hosting the Commerce backend behind the BOSS API gateway (Nginx, Traefik, Envoy, or Cloud Run Ingress):

### 4.1 Required Forwarded Headers
The gateway must preserve and pass the following headers to Commerce on Port 8000:

| Header | Description | Required Value |
| :--- | :--- | :--- |
| `Authorization` | Firebase Auth ID Token | `Bearer <token>` |
| `X-Forwarded-For` | Client IP address for audit logs | `<client-ip>` |
| `X-Forwarded-Proto`| Protocol scheme | `https` |
| `X-Request-ID` | Tracing identifier | UUID or BOSS trace string |

### 4.2 Nginx Reverse Proxy Example Block
```nginx
location /api/commerce/ {
    proxy_pass http://commerce-service:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Authorization $http_authorization;
    proxy_pass_header Authorization;
    proxy_read_timeout 120s;
    client_max_body_size 50M;
}
```

### 4.3 CORS Configuration for BOSS
In `Commerce` environment, set:
```bash
APP_ENV=production
CORS_ALLOWED_ORIGINS=https://boss.company.internal,https://experience-ops.company.internal
```

---

## 5. Frontend Integration Options for the BOSS Team

The BOSS team can mount these three capabilities into the Agentic BOSS host application using either of the two standard enterprise approaches:

### Option A: Sub-Route Proxy / Micro-Frontend Shell (Recommended)
Mount the Commerce frontend build directly at a BOSS sub-path:
- Route `/commerce/seo` &rarr; mounts Commerce `SEODashboard.tsx`
- Route `/commerce/validation` &rarr; mounts Commerce `Validation.tsx`
- Route `/commerce/launches` &rarr; mounts Commerce `Launches.tsx`

Configure the frontend build with:
```bash
VITE_API_BASE_URL=/api/commerce
```

### Option B: Native Boss React Component Ingestion
Import the feature views directly from `capabilities/commerce-workflow-automation/frontend/src/pages/`:
1. Use the pre-aligned AX Design System v2 CSS variables (`--color-primary-blue`, `--color-ai-violet`, `--color-deep-indigo`).
2. Provide standard `AuthContext` supplying the current user's Firebase token.
3. Call `api` client methods from `src/api/client.ts`.

---

## 6. Production Readiness & Configuration Reference

| Environment Variable | Required | Default / Example | Purpose |
| :--- | :---: | :--- | :--- |
| `APP_ENV` | **Yes** | `production` | Enforces zero-trust token verification and strict CORS. |
| `CORS_ALLOWED_ORIGINS` | **Yes** | `https://boss.company.internal` | Approved browser origins (wildcard disallowed in prod). |
| `SHOPIFY_STORE_URL` | **Yes** | `kinq5t-q5.myshopify.com` | Target Shopify store domain. |
| `SHOPIFY_ACCESS_TOKEN` | **Yes** | `shpat_************************` | Admin API token with product read/write scopes. |
| `FIREBASE_SERVICE_ACCOUNT_KEY`| **Yes** | `/etc/secrets/firebase.json` | Path to Firebase credentials for token verification. |
| `GOOGLE_APPLICATION_CREDENTIALS`| Optional | `/etc/secrets/gcp.json` | Used for GSC and Vertex AI ADK agents. |
| `SEARCH_CONSOLE_SITE_URL` | Optional | `https://your-store.myshopify.com` | Search Console verified property URL. |
| `VITE_API_BASE_URL` | Optional | `""` (relative) or gateway URL | Base API prefix for frontend HTTP requests. |

---

## 7. QA Verification Summary

- **FastAPI Core Endpoints:** Verified 100% functional via TestClient.
- **Shopify Live Integration:** Verified against active catalog (29 live products, 31 active validations).
- **Unified 53-Check Engine:** Passed 1,643 individual check assertions with 0 unexpected regressions.
- **Frontend Assets:** Compiled with zero errors under Vite 8 and TypeScript strict typechecks.
- **Security:** Verified zero secrets tracked in git, zero secrets output in server logs, wildcard CORS and mock auth tokens refused on production startup.

