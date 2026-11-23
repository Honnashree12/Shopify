# Publisher Agent (`publisher_agent.py`)

## 📌 Overview
The **Publisher Agent** (`publisher_agent`) executes the actual API mutations against the Shopify Admin REST/GraphQL API to create products, attach variants, assign collections, and upload media assets.

---

## 🎯 Primary Purpose
- Enforces the **Admin Approval Boundary** (`state["approved_to_publish"] == True`).
- Validates that required workflow state fields exist before initiating network requests.
- Calls `shopify_client.create_product()` to create the product on Shopify (with status set to `DRAFT`).
- Uploads images via `ShopifyMediaService` / `upload_product_images()`.
- Assigns products to their respective custom/smart collection via `get_or_create_custom_collection()`.

---

## 🛠️ Tools Exposed & Used
- **`publish_to_shopify(tool_context)`**: Main publishing tool. Creates Shopify product, sets prices, tags, variants, assigns collections, and uploads generated images.

---

## 🔒 Safety & Governance Controls
- **Admin Approval Flag**: Skips creation if `approved_to_publish` is false.
- **Status Preservation**: Initializes new products as `DRAFT` to prevent unreviewed items from going live instantly.
- **State Updates**: Populates `shopify_product_id`, `shopify_url`, and `shopify_variant_id` in `tool_context.state`.
