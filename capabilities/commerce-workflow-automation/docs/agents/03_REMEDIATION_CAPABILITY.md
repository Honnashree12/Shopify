# Remediation Capability

## Type
Supporting Capability

## Purpose
The Remediation Capability generates deterministic, automated, and human-guided fixes for product validation failures identified across the 53-check storewide audit matrix. It remediates catalog defects, standardizes product attributes, pads non-square images without pixel distortion, updates cached validation reports, and recalculates storewide launch readiness.

## What It Does
1. Analyzes product validation results and evaluates failed Blocker and Warning checks.
2. Classifies each failed check into one of four fix types: `SAFE_AUTO_FIX`, `REVIEW_REQUIRED`, `MANUAL_VERIFICATION`, or `NOT_FIXABLE`.
3. Generates deterministic SKU codes, SEO titles, SEO descriptions, tags, shipping weights, collection assignments, and template suffixes based on product title, category, and catalog metadata.
4. Performs PIL-based 1:1 square image padding for non-square product media without cropping, resampling, recoloring, or altering original pixel content.
5. Applies explicit updates against Shopify via `ShopifyClient` while recording audit logs for every remediation attempt.
6. Recalculates storewide launch readiness scores and updates cached JSON output reports (`validation_results.json`, `unified_validation_report.json`, `summary_report.json`).

## How It Works
1. **Remediation Generation (`generate_remediations_for_product`)**:
   - Inspects a product dictionary and its associated 53 validation checks.
   - Filters failed rules (`FAIL` or `WARNING`) and constructs a `RemediationItem` object containing rule details, current value, proposed value, field to change, fix type, and Shopify resource location.
2. **Fix Type Classification**:
   - `SAFE_AUTO_FIX`: Low-risk, deterministic fixes (e.g., generating SKUs under Rule 18, setting SEO title under Rule 34, setting SEO description under Rule 36, adding tags under Rule 32, setting weight under Rule 23, setting collection under Rule 30).
   - `REVIEW_REQUIRED`: High-risk or business-sensitive fixes requiring explicit merchant confirmation (e.g., price under Rule 14, compare-at price under Rules 15/16, inventory stock under Rule 22, product type under Rule 28, vendor under Rule 27, template under Rule 41, requires shipping flag under Rule 24).
   - `MANUAL_VERIFICATION`: Fixes requiring manual merchant inspection or external asset creation.
   - `NOT_FIXABLE`: Errors that cannot be remediated automatically due to missing underlying data.
3. **Deterministic Value Generators**:
   - `generate_deterministic_sku`: Generates SKUs with category prefixes (e.g., `KP-KIT-`, `KP-BK-`, `KP-CRS-`, `KP-ELE-`, `KP-TS-`, `KP-CMB-`) based on sanitized product title and category.
   - `transform_image_to_square_padded`: Loads image bytes/URL via PIL, calculates max dimension, pastes the original un-cropped image centered onto a 1:1 RGBA/RGB background, and returns formatted image bytes with preserved pixel integrity.
4. **Report & Score Synchronization (`update_saved_validation_result_for_product` & `_recalculate_summary_reports`)**:
   - Overwrites updated product results in cached output JSON files.
   - Recalculates total active products, launch ready count, launch blocked count, average validation score, and total passed/failed blocker and warning counts.

## Inputs
- `product`: Dictionary containing Shopify product details (ID, title, handle, category, variants, images, tags, SEO metadata, body HTML, template suffix, vendor, product type) and rule evaluation dictionary (`checks`).
- `image_source`: Image URL string or raw bytes for image padding transformations.
- `updated_product`: Dictionary of remediated product data for cache synchronization.

## Outputs
- `List[RemediationItem]`: List of structured remediation items with deterministic suggestions, fix types, and target Shopify resources.
- `Dict[str, Any]` (Image Pad Result): Transformed image bytes, before/after dimensions string, square confirmation flag, and preservation flags (`crop: None`, `pixels_preserved: True`).
- Updated JSON output reports (`validation_results.json`, `unified_validation_report.json`, `summary_report.json`).

## Important Business Rules
- **No Pixel Distortion**: Image square transformation MUST pad un-cropped original images with clean background colors and NEVER crop, rotate, resample, recolor, or alter original image pixels.
- **Strict Classification Boundaries**: Pricing (Rule 14), compare-at pricing (Rules 15/16), stock allocation (Rule 22), vendor (Rule 27), product type (Rule 28), template assignment (Rule 41), and shipping flags (Rule 24) MUST be classified as `REVIEW_REQUIRED` to preserve human control.
- **Active Products Only**: Remediation items are only generated and saved for active products; draft and archived products are excluded from storewide launch readiness recalculations.
- **Deterministic SKU Format**: SKUs must follow the format `KP-<CAT_CODE>-<NAME_PREFIX>-<VAR_SUFFIX>` to ensure consistency across the catalog.

## Safety Boundaries
- **Explicit Confirmation Flag**: Every `RemediationItem` maintains `requires_confirmation = True` by default to prevent unauthorized bulk mutations.
- **Audit Logging**: All remediation attempts, API failures, and report file updates are logged with exact error tracebacks.
- **Corrupted File Fallback**: Report file synchronization includes exception handling to catch corrupted JSON files and gracefully rebuild summary metrics without crashing.

## Implementation Files
- `backend/remediation_engine.py` (also implemented at `services/remediation_engine.py`)
