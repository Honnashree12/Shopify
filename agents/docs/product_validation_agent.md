# Product Validation Agent (`product_validation_agent.py`)

## 📌 Overview
The **Product Validation Agent** (`product_validation_agent`) is the central quality assurance authority in the platform. It executes a comprehensive **53-point catalog integrity checklist matrix** across 9 structured categories to evaluate whether a Shopify product is safe and ready for store launch.

---

## 🎯 Primary Purpose
- Evaluates active products fetched from the Shopify Admin REST API.
- Classifies validation checks into strict **Blockers** (must pass to launch) and **Warnings** (recommended improvements).
- Calculates a quantitative **Launch Readiness Score** (0 to 100) for every audited product.
- Identifies remediation items for automated or manual safe fixing via `services/remediation_engine.py`.

---

## 🛠️ Tools Exposed & Used
- **`fetch_validation_products_tool(tool_context)`**: Connects to the Shopify validation store, fetches all products, filters `ACTIVE` status products, and excludes `DRAFT` and `ARCHIVED` items from validation scope.
- **`validate_products_checklist_tool(tool_context)`**: Runs the 53-point matrix against every fetched product payload.

---

## 📐 The 53-Point Validation Matrix Structure

The 53 validation checks are grouped into 9 sections:

| Section | Check Range | Description |
|---|---|---|
| **A. Content** | Checks 01 – 07 | Title formula, description presence, min length, HTML formatting, brand copy framing |
| **B. Media** | Checks 08 – 13 | Image presence, count (≥3), featured image, 1:1 square aspect ratio, image alt text |
| **C. Pricing & Inventory** | Checks 14 – 24 | Price > 0, compare-at price, SKU formatting, stock level, physical weight, shipping flag |
| **D. Shipping & Logistics** | Checks 25 – 26 | Country of origin, HS code classification |
| **E. Taxonomy & Organization** | Checks 27 – 32 | Vendor attribution, product type, collection membership, tags (≥3) |
| **F. Search Engine Optimization** | Checks 33 – 38 | Clean handle, SEO title length (≤60), SEO meta description length (120-155), slug format |
| **G. Theme Layout & Display** | Checks 39 – 43 | Theme template suffix assignment, variant options, custom options |
| **H. Compliance & Safety** | Checks 44 – 48 | Age framing, safety notices, instructional compliance |
| **I. Channel Readiness** | Checks 49 – 53 | Storefront accessibility, cart integration, checkout readiness |

---

## 📥 Inputs & Workflow State Requirements
- **State Key Input**: `tool_context.state["validation_products"]` (Populated by `fetch_validation_products_tool`).
- **Product Fields Evaluated**: `title`, `body_html`, `images`, `variants`, `vendor`, `product_type`, `collections`, `tags`, `handle`, `seo_title`, `seo_description`, `template_suffix`.

---

## 📤 Outputs & State Results
Populates `tool_context.state["validation_results"]` with structured audit outputs per product:
```json
{
  "product_id": "15767726948512",
  "product_name": "KiddyPi Frog Bot DIY Robotics Kit",
  "status": "DRAFT",
  "score": 90.6,
  "launch_status": "LAUNCH_BLOCKED",
  "blockers_failed": 1,
  "warnings_failed": 8,
  "checks": {
    "11. Square Aspect Ratio": {
      "section": "B. Media",
      "severity": "Blocker",
      "status": "PASS",
      "explanation": "All product images are 1:1 square aspect ratio."
    }
  }
}
```

---

## ⚡ Special Logic & Edge Cases
- **Handle Validation**: Ignores numerical suffixes like `-1` if the title explicitly contains numbers (e.g. "Level 1", "Part 1"), preventing false-positive handle warnings.
- **Collection Detection**: Normalizes `/collects.json` assignments so products belonging to smart or custom collections pass Check 30 cleanly.
- **Status Preservation**: Audits preserve original product status (`DRAFT` remains `DRAFT`, `ACTIVE` remains `ACTIVE`).
