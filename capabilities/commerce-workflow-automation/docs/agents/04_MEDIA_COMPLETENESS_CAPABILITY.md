# Media Completeness Capability

## Type
Supporting Capability

## Purpose
The Media Completeness Capability provides reusable, storewide media audit functionality (`MediaCompletenessValidationSkill`) to inspect Shopify product media against collection-specific media profiles. It verifies image counts, pixel dimensions, file formats, and required visual angles (e.g. Hero, Packaging, Contents Laid Out, Completed Project, Book Cover/Spine, Apparel Flat Lays/On-Model, Electronics Top-Down/45° Angle), generating downloadable multi-format audit reports.

## What It Does
1. Audits storewide product catalog media against centralized requirements defined in `MEDIA_REQUIREMENTS`.
2. Maps products to catalog profiles (`STEM Kits`, `Courses`, `Books`, `Apparel / T-Shirts`, `Electronics`).
3. Validates required image angles, minimum resolution thresholds (e.g., 1200x1200px for STEM Kits, 800x1200px portrait for Book Covers), file extensions (`jpg`, `jpeg`, `png`), and position fallbacks.
4. Identifies missing required shots, low-resolution media, non-standard image aspect ratios, and improper keyword alt text.
5. Generates downloadable audit reports in Excel (`.xlsx`), CSV (`.csv`), PDF (`.pdf`), and Markdown (`.md`) formats.

## How It Works
1. **Profile Mapping & Rule Evaluation**:
   - Matches a product's type, tags, title, or collection to a profile key in `MEDIA_REQUIREMENTS` (defaults to `STEM Kits`).
   - Iterates through the profile's required image definitions (e.g., `hero`, `packaging`, `contents`, `completed_project`).
   - For each requirement, inspects candidate product images matching specified keywords or position fallbacks.
2. **Dimension & Format Validation**:
   - Checks image width and height against mandatory target dimensions.
   - Evaluates orientation requirements (e.g., portrait for book front/back cover, landscape for interior spreads).
   - Validates file format compliance against allowed extensions (`jpg`, `jpeg`, `png`).
3. **Multi-Format Export Generation**:
   - **Excel Report (`export_to_excel`)**: Uses `openpyxl` with custom header styles, color fills, summary metric boxes, and auto-adjusted column widths.
   - **CSV Report (`export_to_csv`)**: Exports flat tabular rows for system integration.
   - **PDF Audit Report (`export_to_pdf`)**: Uses `ReportLab` platypus elements (`SimpleDocTemplate`, `Table`, `ParagraphStyle`) to render formatted executive summary boxes and media compliance tables.
   - **Markdown Summary (`export_to_markdown`)**: Generates structured Markdown text with tables and summary statistics.

## Inputs
- `products`: List of product dictionaries retrieved from Shopify GraphQL/REST API.
- `store_name`: Optional string identifier for target Shopify store.
- `output_dir`: Optional target directory path for saving generated report files.

## Outputs
- `Dict[str, Any]` (Audit Result): Detailed audit breakdown containing per-product media scores, missing required images, low-resolution warnings, and overall compliance status.
- Exported files:
  - Excel Report (`outputs/media_completeness_audit_<timestamp>.xlsx`)
  - CSV Report (`outputs/media_completeness_audit_<timestamp>.csv`)
  - PDF Report (`outputs/media_completeness_audit_<timestamp>.pdf`)
  - Markdown Report (`outputs/media_completeness_audit_<timestamp>.md`)

## Important Business Rules
- **Profile Specification Source of Truth**: `MEDIA_REQUIREMENTS` in `services/media_completeness_validator.py` serves as the central source of truth for all media quantity, dimension, and angle requirements.
- **STEM Kit Media Requirements**: STEM Kits require at least 4 distinct high-resolution images (1200x1200px): Hero/Featured, Kit Box/Packaging, Contents Laid Out, and Completed Working Project.
- **Book Media Requirements**: Books require portrait Front Cover (800x1200px), Back Cover (800x1200px), 2 Landscape Interior Pages (1200x900px), and Book Spine (200x1200px).
- **Read-Only Operation**: The Media Completeness Capability is strictly read-only and does not mutate Shopify product media directly.

## Safety Boundaries
- **No Direct Shopify Writes**: The audit skill fetches catalog metadata via `ShopifyClient` or cached JSON fixtures without modifying product images or shop settings.
- **Graceful Error Handling**: Missing image metadata or HTTP request failures when fetching remote image headers log warnings without aborting overall storewide audits.

## Implementation Files
- `backend/media_completeness_validator.py` (also implemented at `services/media_completeness_validator.py`)
