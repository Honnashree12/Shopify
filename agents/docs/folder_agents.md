# Folder Batch Pipeline Sub-Agents (`folder_agents.py`)

## 📌 Overview
`folder_agents.py` defines **6 specialized sub-agents** designed to automate batch processing of product directories on disk (containing raw copy, images, PDFs, and video assets).

---

## 🤖 Sub-Agent Roster & Tool Contracts

### 1. Folder Ingestion Agent (`folder_ingestion_agent`)
- **Tool**: `ingest_and_extract_folder_tool()`
- **Function**: Scans specified product directory, parses text/JSON manifests, and extracts raw product fields (`name`, `description`, `price`, `images`).

### 2. Folder Validation Agent (`folder_validation_agent`)
- **Tool**: `validate_folder_data_tool()`
- **Function**: Validates extracted folder data against standard catalog schemas before Shopify API interaction.

### 3. Folder Creation Agent (`folder_creation_agent`)
- **Tool**: `create_shopify_product_tool()`
- **Function**: Calls Shopify API to create draft product resource from validated folder data.

### 4. Folder Media Agent (`folder_media_agent`)
- **Tool**: `upload_folder_media_tool()`
- **Function**: Processes all images and videos found in the product folder, verifies 1:1 square ratio, and uploads media assets to the created Shopify product.

### 5. Folder Verification Agent (`folder_verification_agent`)
- **Tool**: `verify_folder_product_tool()`
- **Function**: Verifies created Shopify product resource to confirm all media and fields attached cleanly.

### 6. Folder Report Agent (`folder_report_agent`)
- **Tool**: `generate_folder_reports_tool()`
- **Function**: Compiles final batch launch audit report and writes summary logs.
