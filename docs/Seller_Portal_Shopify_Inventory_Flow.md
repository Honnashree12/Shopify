# Seller Portal–Shopify Inventory Flow

## 1. Purpose

This document outlines the architectural design and integration flow for updating product inventory in Shopify when stock updates originate from an external Seller Portal. It defines component responsibilities, data payloads, identification logic, location resolution, verification routines, error handling strategies, and design decisions requiring finalization.

---

## 2. Objective

The primary objective of this integration flow is to ensure accurate, verified, multi-tenant inventory synchronization between the Seller Portal and Shopify stores. 

When stock level changes occur within the Seller Portal, those updates must trigger an automated workflow that identifies the target store, maps the product to its corresponding Shopify Inventory Item, selects the target location, executes the appropriate GraphQL inventory mutation, and verifies the resulting stock level prior to reporting success.

---

## 3. High-Level Flow

The end-to-end operational flow follows a structured execution path:

```text
Seller Portal
      ↓
Inventory Update Request
      ↓
Backend
      ↓
Identify Business / Store
      ↓
Identify Product / Variant
      ↓
Resolve Inventory Item
      ↓
Resolve Location
      ↓
Shopify Inventory Mutation
      ↓
Verify Inventory
      ↓
Return Success / Error
      ↓
Seller Portal
```

---

## 4. Catalog and Inventory Hierarchy

Shopify structures inventory across a hierarchical tree. Understanding this relationship is critical for mapping Seller Portal events to Shopify GraphQL entities:

```text
Business / Store
      ↓
Catalogue / Store grouping
      ↓
Product
      ↓
Variant
      ↓
SKU
      ↓
Inventory Item
      ↓
Location
      ↓
Inventory Quantity
```

> **Key Rule:** A Shopify Product ID alone is insufficient to perform an inventory update. Stock is attached directly to an **Inventory Item** at a specific **Location**, which is linked via a **Product Variant**.

---

## 5. Example Seller Portal Request

> [!NOTE]
> **Design Example:** The payload below is an illustrative design example used for architectural planning and does NOT represent the finalized Seller Portal API contract.

```json
{
  "business_id": "BIZ-KIDDYPI-001",
  "store_id": "kinq5t-q5",
  "sku": "500",
  "new_quantity": 48,
  "update_type": "SET",
  "location_id": "gid://shopify/Location/76017664160"
}
```

---

## 6. Product Identification

To map a incoming Seller Portal stock update to the correct Shopify inventory item, the system must resolve the target product variant using one of several potential candidate identifiers:

* **SKU (Stock Keeping Unit):** SKU is a practical candidate identifier because it is associated with a Shopify variant, but the final identifier should be agreed with the Seller Portal team.
* **Shopify Variant GID (`gid://shopify/ProductVariant/...`):** Directly identifies the variant, bypassing lookup steps if stored by the Seller Portal.
* **Shopify Product GID (`gid://shopify/Product/...`):** Identifies the parent product container; requires secondary resolution to select the target variant/SKU.
* **Product ID + SKU Combined:** Provides strict matching validation across parent product and variant level.
* **Seller Portal / Business Product ID:** Internal identifier requiring a lookup table/database mapping to Shopify GIDs.

---

## 7. Choosing the Inventory Operation

Shopify Admin API provides two distinct GraphQL mutation APIs for updating stock. Neither API is universally preferred; the choice depends on the final Seller Portal payload contract.

### Option A: `inventorySetQuantities` (Absolute Update)
* **When Used:** When the Seller Portal transmits the exact final stock count (e.g., stock count is set directly to 48).
* **Behavior:** Sets `available` stock at the specified location to the absolute target figure.
* **Idempotency:** Highly idempotent when handling out-of-order absolute stock notifications.

### Option B: `inventoryAdjustQuantities` (Delta Update)
* **When Used:** When the Seller Portal transmits a stock increment/decrement delta (e.g., stock increased by +5 or decreased by -2).
* **Behavior:** Adjusts existing `available` quantity by adding or subtracting the provided delta.
* **Idempotency:** Non-idempotent; requires sequence tracking to prevent duplicate adjustments.

---

## 8. Location Handling

Shopify inventory quantities are strictly location-specific. An Inventory Item can exist across multiple locations with independent stock counts.

* **Design Example Location:** `Jayanagar` (`gid://shopify/Location/76017664160`)
* **Policy Status:** **TBD / To Be Finalized.** The test location `Jayanagar` was utilized during live API validation, but must NOT automatically be assumed to be the production default location.
* **Future Options:** 
  1. Seller Portal explicitly specifies the target `location_id`.
  2. Backend looks up a default/primary fulfillment location configured per Business/Store.

---

## 9. Verification Flow

To guarantee data consistency between systems, every mutation must be followed by a post-update verification step before returning a final response to the Seller Portal:

```text
Seller Portal stock value = 75
        ↓
Execute Shopify GraphQL mutation
        ↓
Query Shopify Inventory Item & Location
        ↓
Verify read quantity == 75
        ↓
Return Success response to Seller Portal
```

If the verification read does not match the target value, an inventory verification mismatch error is generated and logged.

---

## 10. Error Handling

The integration flow must gracefully handle failure states at each step:

| Failure Scenario | Error Code / Cause | Recovery Action |
| :--- | :--- | :--- |
| **Business / Store Not Found** | Invalid `business_id` or `store_id` | Abort operation; return HTTP 404 / Invalid Store error to Seller Portal. |
| **Product / Variant Not Found** | SKU or Variant GID does not exist in store | Abort operation; log unmapped SKU error. |
| **Inventory Item Not Found** | Variant lacks `inventory_item` association | Abort operation; flag variant as non-inventoriable. |
| **Location Not Found** | Target Location ID is inactive or unmapped | Abort operation; return location configuration error. |
| **Shopify Mutation Error** | GraphQL `userErrors` returned by Shopify API | Abort operation; capture Shopify error code & user message. |
| **Verification Mismatch** | Post-mutation query returns value != expected | Mark status as `UNVERIFIED_MUTATION`; alert system/audit log. |

---

## 11. Proposed Component Responsibilities

```text
+-----------------------+     +-----------------------+     +-----------------------+     +-----------------------+
|     Seller Portal     |     |  Backend Automation   |     |    Shopify Client     |     |     Shopify Admin     |
+-----------------------+     +-----------------------+     +-----------------------+     +-----------------------+
| • Initiates update    |     | • Authenticates store |     | • Constructs GraphQL  |     | • Validates token &   |
| • Sends SKU/Quantity  | --> | • Resolves identifiers| --> |   queries/mutations   | --> |   permissions         |
| • Receives result     |     | • Coordinates flow    |     | • Executes HTTP calls |     | • Updates stock state |
|                       |     | • Verifies result     |     | • Parses errors       |     | • Returns updated data|
+-----------------------+     +-----------------------+     +-----------------------+     +-----------------------+
```

* **Seller Portal:** Originates inventory change events and consumes status responses.
* **Backend Automation Service:** Orchestrates business multi-tenancy, resolves catalog mappings, triggers inventory workflows, and executes stock verification.
* **Shopify Client (`shopify_client.py`):** Low-level GraphQL communication wrapper managing API calls, raw response parsing, and error formatting.
* **Shopify Platform:** Authoritative store catalog and inventory data store.

---

## 12. End-to-End Example

### Input Scenario
Seller Portal submits an absolute inventory update of **48 units** for SKU `"500"` under store `"kinq5t-q5"`.

### Execution Steps
1. **Request Intake:** Backend receives event `{ "store_id": "kinq5t-q5", "sku": "500", "new_quantity": 48 }`.
2. **Store Authentication:** Backend loads credentials for `kinq5t-q5`.
3. **Variant Resolution:** Backend queries Shopify GraphQL by SKU `"500"`, obtaining `InventoryItem/48211277152416`.
4. **Location Selection:** Backend selects configured location `Location/76017664160` (`Jayanagar`).
5. **Mutation Execution:** Backend calls `inventorySetQuantities` with quantity `48`.
6. **Verification Read:** Backend queries `InventoryItem/48211277152416` at `Location/76017664160` and reads `48`.
7. **Response Dispatch:** Backend returns `{ "success": true, "sku": "500", "quantity": 48, "status": "VERIFIED" }` to Seller Portal.

---

## 13. Sequence Diagram

```text
Seller Portal        Backend          Shopify Client        Shopify
     |                  |                    |                 |
     |-- stock update ->|                    |                 |
     |                  |-- identify ------->|                 |
     |                  |<-- variant info ---|                 |
     |                  |                    |                 |
     |                  |-- inventory query ----------------->|
     |                  |<-- inventory item/location ----------|
     |                  |                    |                 |
     |                  |-- inventory mutation -------------->|
     |                  |<-- mutation result ------------------|
     |                  |                    |                 |
     |                  |-- verify inventory ---------------->|
     |                  |<-- updated quantity -----------------|
     |                  |                    |                 |
     |<-- success/error-|                    |                 |
```

---

## 14. Important Design Decisions to Finalize

The following architectural items remain **TBD (To Be Finalized)** with stakeholders:

1. **Business/Store Identifier Strategy:** Standardizing multi-tenant resolution mapping between Seller Portal account IDs and Shopify Admin API credentials.
2. **Primary Product Identifier Contract:** Confirming whether Seller Portal will send SKU, Variant GID, Product GID, or a custom mapping ID.
3. **Location Selection & Fallback Policy:** Finalizing whether location is passed per request, resolved via business default, or distributed across multiple locations.
4. **Update Type Standardization:** Resolving whether Seller Portal will send absolute stock targets (`SET`) or relative deltas (`ADJUST`).

---

## 15. Current Status

### Completed & Validated
* ✅ Shopify GraphQL Admin API Catalog & Inventory relationship research complete.
* ✅ Live API testing of `inventorySetQuantities` completed successfully.
* ✅ Live API testing of `inventoryAdjustQuantities` completed successfully.
* ✅ Inventory restoration & verified stock read (48 units) completed.

### Next Stage (Proposed Implementation)
* ⏳ Finalize Seller Portal API payload contract with stakeholder team.
* ⏳ Implement dedicated inventory methods in backend service layer.
* ⏳ Add inventory GraphQL query/mutation helper methods to `shopify_client.py`.
* ⏳ Implement end-to-end automated integration and error recovery testing.

---

## 16. Conclusion

The proposed Seller Portal–Shopify Inventory Flow establishes a robust, extensible design for bi-directional inventory management. By adhering to Shopify's `InventoryItem` and `Location` hierarchy, supporting both `SET` and `ADJUST` mutations, enforcing strict verification loops, and defining explicit component boundaries, the system is primed for seamless backend implementation once final API contracts are agreed upon.
