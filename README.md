# Shopify Product Launch & Validation Agent Platform

An enterprise agentic AI platform built with **Google Agent Development Kit (ADK)** and **FastAPI** to automate e-commerce product creation, 53-point catalog integrity validation, intelligent safe remediation, multi-channel growth marketing, and live Shopify storefront verification.

---

## 📋 Table of Contents
1. [Overview & Project Purpose](#-overview--project-purpose)
2. [Key Platform Features](#-key-platform-features)
3. [AI Agents Architecture](#-ai-agents-architecture)
4. [High-Level Architecture](#-high-level-architecture)
5. [Repository Structure](#-repository-structure)
6. [Prerequisites](#-prerequisites)
7. [Environment Configuration & Safety](#-environment-configuration--safety)
8. [Local Setup & Installation](#-local-setup--installation)
   - [Python Environment Setup](#1-python-backend-setup)
   - [Node.js Frontend Setup](#2-nodejs-frontend-setup)
9. [Running the Application](#-running-the-application)
   - [Starting Backend Server](#starting-the-backend-server)
   - [Starting Frontend Console](#starting-the-frontend-dashboard)
   - [Local Application URLs](#local-application-urls)
10. [Shopify Configuration Guide](#-shopify-configuration-guide)
11. [Running Automated Tests](#-running-automated-tests)
12. [Safety Controls & Status Preservation](#-safety-controls--status-preservation)
13. [Documentation Index](#-documentation-index)

---

## 🎯 Overview & Project Purpose
Launching products on Shopify requires flawless data hygiene—from title formulas and 1:1 square media ratios to inventory weights, SEO metadata, and collection assignments.

The **Shopify Product Launch Platform** automates this entire lifecycle using specialized AI agents. It ingests raw product details or local asset folders, generates optimized copy and commercial visual prompts, executes a **53-point validation checklist matrix**, auto-remediates safe catalog defects without cropping or modifying product status, and verifies storefront purchasability in real time.

---

## 🚀 Key Platform Features

### 1. 🔍 53-Check Product Validation Matrix Agent
- Audits active store products across **9 structured sections**: Content, Media, Pricing & Inventory, Shipping & Logistics, Taxonomy, SEO, Theme Display, Compliance, and Channel Readiness.
- Classifies errors into strict **Blockers** (must pass for launch) and **Warnings**.
- Calculates dynamic quantitative **Launch Readiness Scores** (0 to 100) per product andcatalog-wide.

### 2. ⚡ Intelligent Safe Remediation Engine
- Automatically remediates safe catalog issues:
  - **Rule 11 (Square Aspect Ratio)**: Resizes non-square images using 1:1 canvas padding (`1350x1350`) to preserve original pixels without cropping or AI generation.
  - **Rule 18 (SKU Generation)**: Generates category-aware deterministic SKUs.
  - **Rule 23 (Shipping Weight)**: Assigns physical category weights.
  - **Rule 30 (Collection Assignment)**: Automatically maps products to standard store collections.
  - **Rule 34 & 36 (SEO Metadata)**: Configures SEO meta titles and description snippets.

### 3. 🔄 Incremental Single Product Revalidation
- Re-runs validation audit against Shopify on a single product post-remediation.
- Recalculates `unified_summary_report.json` and dynamically updates the frontend dashboard KPIs in real time.

### 4. 🎓 Workshop Setup Agent & Template Engine
- Ingests STEM workshop inputs, matches existing Shopify products, resolves duplicate conflicts, generates registration form configs, and replicates Liquid theme page templates (`workshop-landing-page`).

### 5. 🛍️ Resilient Shopify API Integration (REST & GraphQL)
- Handles staged uploads for images and MP4 video files.
- Enforces strict **Admin Approval Boundaries** (`approved_to_publish == True`) before any mutation occurs on live Shopify stores.

### 6. 📣 Multi-Channel Growth Marketing Copywriter
- Generates structured HTML descriptions (`<h2>`, `<h3>`, `<ul>`), SEO tags, social media captions (Instagram, Facebook), WhatsApp promotional templates, and email newsletters.

---

## 🤖 AI Agents Architecture

The platform includes **17 AI Agents** powered by Google ADK (`gemini-2.5-flash`):

1. **`product_validation_agent`**: Evaluates 53 catalog integrity checks.
2. **`copywriter_agent`**: Formats structured HTML product copy.
3. **`seo_agent`**: Generates SEO titles, meta descriptions, keywords, and URL slugs.
4. **`strategist_agent`**: Formulates campaign target audience and core strategy.
5. **`image_prompt_agent`**: Formulates 8 photorealistic commercial 1:1 image prompts.
6. **`image_generator_agent`**: Coordinates image generation, padding, and quality checks.
7. **`publisher_agent`**: Pushes validated payloads, variants, and collections to Shopify.
8. **`verification_agent`**: Verifies post-publish price, variant visibility, and checkout status.
9. **`report_generator_agent`**: Compiles Markdown, JSON, and PDF audit reports.
10. **`marketing_agent`**: Generates multi-channel campaign copy (Social, Email, WhatsApp).
11. **`workshop_setup_agent`**: Manages workshop setup, registration, and Liquid templates.
12. **`folder_agents` (6 Sub-Agents)**: Automates folder batch ingestion pipelines (Ingestion, Validation, Creation, Media, Verification, Report).

*Detailed agent specifications are available in [`agents/docs/README.md`](agents/docs/README.md).*

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│              React + Vite Frontend Dashboard            │
│  (Validation Matrix, Guided Review, Audit Reports, UI) │
└───────────────────────────┬─────────────────────────────┘
                            │ REST APIs
┌───────────────────────────▼─────────────────────────────┐
│                   FastAPI Application                   │
│   (main.py - Endpoints, Authentication, CORS, Static)   │
└──────────────┬───────────────────────────┬──────────────┘
               │                           │
┌──────────────▼─────────────┐   ┌─────────▼──────────────┐
│  Google ADK Agents Engine  │   │  Remediation Engine & │
│ (Product Validation Agent) │   │ Single-Product Reval   │
└──────────────┬─────────────┘   └─────────┬──────────────┘
               │                           │
┌──────────────▼───────────────────────────▼──────────────┐
│             Shopify API Integration Client              │
│       (shopify_client.py - Admin REST & GraphQL API)    │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                    Shopify Storefront                   │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
shopify-product-launch/
├── agents/                  # ADK Agent python definitions
│   └── docs/                # Markdown context documentation for all 17 agents
├── tools/                   # ADK Tools (product_context, folder_tools, image_generator, etc.)
├── services/                # Backend services (remediation_engine, shopify_media_service, etc.)
├── models/                  # Pydantic domain schemas
├── data/                    # SQLite database scripts (database.py, launch_platform.db)
├── frontend/                # React + TypeScript + Vite web dashboard source
├── static/                  # Production-compiled static assets served by FastAPI
├── outputs/                 # Locally generated reports, audit PDFs, images, and email templates
├── docs/                    # Architecture reports, setup guides, and research docs
├── tests/                   # Automated test suite (Pytest & Unittest)
├── main.py                  # FastAPI application entry point & API routes
├── shopify_client.py        # Custom Shopify REST & GraphQL client
├── config.py                # Environment configuration settings (Pydantic Settings)
├── state.py                 # Pydantic schema for session state variables
├── requirements.txt         # Python 3.11 dependency manifest
└── .env.example             # Environment configuration template
```

---

## ⚡ Prerequisites

- **Python**: Version `3.11` or higher.
- **Node.js**: Version `18.0.0` or higher (with `npm`).
- **Shopify Store**: A Shopify Development Store or Admin Access Token (`shpat_...`).
- **Google AI Key**: Gemini API key (`GEMINI_API_KEY` or `GOOGLE_API_KEY`).

---

## 🔒 Environment Configuration & Safety

> [!IMPORTANT]
> **No Credentials Policy**: Credentials, private keys, or `.env` files are **never committed** to version control. The repository ignores `.env` via `.gitignore`.

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your store credentials and API keys.

### Required Environment Variables

| Variable | Description |
|---|---|
| `SHOPIFY_STORE_URL` | Your Shopify store URL (e.g. `my-store.myshopify.com`) |
| `SHOPIFY_ACCESS_TOKEN` | Admin API Access Token starting with `shpat_` |
| `SHOPIFY_CLIENT_ID` | Shopify Partner App Client ID (for OAuth flow) |
| `SHOPIFY_CLIENT_SECRET` | Shopify Partner App Client Secret (for OAuth flow) |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Google Gemini API key for ADK agents |
| `SHOPIFY_VALIDATION_STORE` | Optional store URL for validation audits |
| `SHOPIFY_VALIDATION_TOKEN` | Optional store token for validation audits |

---

## 🛠️ Local Setup & Installation

### 1. Python Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/shopify-product-launch.git
   cd shopify-product-launch
   ```

2. Create and activate a Python 3.11 virtual environment:
   - **Windows**:
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 2. Node.js Frontend Setup

1. Navigate to the `frontend` directory and install npm packages:
   ```bash
   cd frontend
   npm install
   ```

---

## 🖥️ Running the Application

### Starting the Backend Server

From the project root directory (with virtual environment activated):
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
*The backend startup validator checks for required `.env` variables and displays clean guidance if missing.*

### Starting the Frontend Dashboard

In a separate terminal window:
```bash
cd frontend
npm run dev
```

### Local Application URLs

- **Frontend Development Console**: `http://localhost:5173`
- **Product Validation Dashboard**: `http://localhost:5173/validation`
- **Backend API Server**: `http://127.0.0.1:8000`
- **Interactive OpenAPI Docs**: `http://127.0.0.1:8000/docs`

---

## 🛍️ Shopify Configuration Guide

The platform connects to Shopify via REST and GraphQL Admin APIs.

### Required Admin API Scopes
When creating a Shopify Custom App or Partner App, enable the following scopes:
- `read_products`, `write_products`
- `read_inventory`, `write_inventory`
- `read_themes`
- `read_locations`

For full setup instructions, error descriptions, and verification steps, see [`docs/SHOPIFY_CONFIGURATION.md`](docs/SHOPIFY_CONFIGURATION.md).

---

## 🧪 Running Automated Tests

Run the workshop platform integration test suite:
```bash
python run_tests.py
```

Run unit tests via Python Unittest:
```bash
python -m unittest discover tests
```

---

## 🛡️ Safety Controls & Status Preservation

- **Status Preservation Enforcement**: The remediation engine is strictly prohibited from altering a product's lifecycle status (`DRAFT` products remain `DRAFT`, `ACTIVE` products remain `ACTIVE`).
- **Non-Destructive Image Remediation**: Rule 11 image padding preserves 100% of original pixels without cropping or AI distortion.
- **Admin Approval Boundary**: Product publishing requires explicit approval (`approved_to_publish == True`).

---

## 📚 Documentation Index

- 📘 [**`docs/LOCAL_SETUP.md`**](docs/LOCAL_SETUP.md) — Detailed developer setup guide.
- 🛍️ [**`docs/SHOPIFY_CONFIGURATION.md`**](docs/SHOPIFY_CONFIGURATION.md) — Shopify API credential & scope configuration guide.
- 🌐 [**`docs/PROJECT_OVERVIEW.md`**](docs/PROJECT_OVERVIEW.md) — High-level platform overview & agent roles.
- 🤖 [**`agents/docs/README.md`**](agents/docs/README.md) — Complete 17-agent architecture specifications.

