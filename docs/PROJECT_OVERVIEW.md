# Platform & Agents Overview (`docs/PROJECT_OVERVIEW.md`)

The **Shopify Product Launch & Validation Agent Platform** is an enterprise agentic AI system designed to manage the entire lifecycle of e-commerce catalog publishing, quality assurance, multi-channel growth marketing, and live store verification.

---

## 🏛️ System Core Modules

### 1. Product Validation Matrix Engine (`agents/product_validation_agent.py`)
- Audits store catalog products across **53 distinct rules** divided into 9 operational categories.
- Assigns severity classifications (**Blocker** vs **Warning**) and computes a **Launch Readiness Score** (0–100).
- Tracks blockers passed/failed to determine overall launch status (`READY_TO_LAUNCH` vs `LAUNCH_BLOCKED`).

### 2. Intelligent Remediation & Auto-Fix Engine (`services/remediation_engine.py`)
- Provides deterministic safe auto-fixes for catalog defects:
  - **Rule 11 (Square Aspect Ratio)**: Resizes non-square images using 1:1 canvas padding (`1350x1350`) to preserve original pixels without cropping or AI distortion.
  - **Rule 18 (SKU Generation)**: Generates category-based deterministic SKUs.
  - **Rule 23 (Weight)**: Assigns shipping weights based on product category.
  - **Rule 30 (Collection Assignment)**: Automatically maps products to standard store collections.
  - **Rule 34 & 36 (SEO Titles & Descriptions)**: Generates compliant meta tags.
- Enforces strict **Status Preservation**: Modifying product attributes never alters product lifecycle status (`DRAFT` remains `DRAFT`, `ACTIVE` remains `ACTIVE`).

### 3. Single Product Revalidation Engine
- Executes incremental single-product revalidation immediately after remediations are applied.
- Purges deleted media from refreshed payloads to clear transient API caching delays.
- Recalculates catalog-wide summary reports (`unified_summary_report.json`, `summary_report.json`) and binds live metrics to the frontend dashboard KPI cards in real time.

### 4. Workshop Setup & Template Replication (`agents/workshop_setup_agent.py`)
- Processes workshop event inputs, checks asset completeness, searches Shopify catalog for duplicates, generates registration form configurations, and replicates Liquid theme templates (`workshop-landing-page`).

### 5. Multi-Channel Growth Copywriting (`agents/marketing_agent.py`)
- Formulates multi-channel campaign copy:
  - HTML Product Descriptions (`<h2>`, `<h3>`, `<ul>`)
  - SEO Meta Titles, Descriptions, Keywords & Slugs
  - Social Media Captions (Facebook, Instagram)
  - Direct Messaging Copy (WhatsApp)
  - Promotional Email Newsletters & Subject Lines

---

## 🤖 AI Agent Roster (17 Agents)

All 17 AI Agents are built on the **Google Agent Development Kit (ADK)**:

1. **`product_validation_agent`**: Evaluates the 53-point catalog integrity matrix.
2. **`copywriter_agent`**: Generates formatted HTML product descriptions.
3. **`seo_agent`**: Generates SEO titles, meta descriptions, keywords, and URL slugs.
4. **`strategist_agent`**: Formulates campaign strategy and target audience definition.
5. **`image_prompt_agent`**: Formulates 8 commercial 1:1 photorealistic image prompts.
6. **`image_generator_agent`**: Coordinates image generation, padding, and quality checks.
7. **`publisher_agent`**: Pushes validated product payloads to Shopify Admin API.
8. **`verification_agent`**: Verifies post-publish price, status, and purchasability.
9. **`report_generator_agent`**: Compiles Markdown, JSON, and PDF audit reports.
10. **`marketing_agent`**: Creates multi-channel promotional copy.
11. **`workshop_setup_agent`**: Orchestrates workshop setup and Liquid theme templates.
12–17. **Folder Batch Sub-Agents (6 Agents)**: Manages automated batch folder ingestion pipelines (`folder_ingestion_agent`, `folder_validation_agent`, `folder_creation_agent`, `folder_media_agent`, `folder_verification_agent`, `folder_report_agent`).

*For full specifications of individual agents, see [`agents/docs/README.md`](file:///c:/Users/honnu/Downloads/shopify-launch-agent_shopify-live2/shopify-launch-agent/shopify-product-launch/agents/docs/README.md).*
