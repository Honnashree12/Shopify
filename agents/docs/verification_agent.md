# Verification Agent (`verification_agent.py`)

## 📌 Overview
The **Verification Agent** (`verification_agent`) conducts post-publish inspection of published Shopify products to confirm that API creation succeeded without data corruption or mismatched pricing.

---

## 🎯 Primary Purpose
- Connects to Shopify via `get_product(shopify_product_id)`.
- Verifies that the product exists on Shopify.
- Validates that actual variant price matches expected workflow price within a `₹0.01` tolerance.
- Confirms the product has active variant options and is purchasable.

---

## 🛠️ Tools Exposed & Used
- **`verify_product_listing(tool_context)`**: Performs verification checks and logs results into `tool_context.state["verification_result"]`.

---

## 📤 Output Verification State Schema

```json
{
  "verification_result": {
    "product_exists": true,
    "status_active": false,
    "price_matched": true,
    "purchasable": true,
    "errors": []
  }
}
```
