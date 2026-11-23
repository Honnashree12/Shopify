# Shopify Inventory API Test Report

## 1. Purpose

This document reports the live exploration and testing results of Shopify's Admin GraphQL inventory mutations (`inventorySetQuantities` and `inventoryAdjustQuantities`) conducted against the connected Shopify store (`kinq5t-q5.myshopify.com`).

---

## 2. Test Product

Live data retrieved from the Shopify store using the Admin GraphQL API:

| Field | Value |
| :--- | :--- |
| Product | `Computing & AI Workbook 1 (Scratch)` |
| Product ID | `gid://shopify/Product/15132292546720` |
| Variant ID | `gid://shopify/ProductVariant/52641880309920` |
| SKU | `500` |
| Inventory Item ID | `gid://shopify/InventoryItem/48211277152416` |
| Location | `Jayanagar` |
| Location ID | `gid://shopify/Location/76017664160` |
| Original stock | `48` |

---

## 3. Test 1 — inventorySetQuantities

`inventorySetQuantities` sets the absolute stock level at a target location.

### Execution Log:
```text
inventorySetQuantities

48 → 49
49 → 48
```

- **Step 1A (Increase)**: Executed `inventorySetQuantities` setting stock to `49`. The response returned `userErrors: []` and confirmed an adjustment delta of `+1` for `available` and `on_hand`.
- **Step 1B (Restore)**: Executed `inventorySetQuantities` setting stock back to `48`. The response returned `userErrors: []` and confirmed an adjustment delta of `-1`.

Both operations completed successfully with zero Shopify `userErrors`.

---

## 4. Test 2 — inventoryAdjustQuantities

`inventoryAdjustQuantities` adjusts stock levels by a specified delta amount at a target location.

### Execution Log:
```text
inventoryAdjustQuantities

48 → 49
49 → 48
```

- **Step 2A (Increase)**: Executed `inventoryAdjustQuantities` with `delta: 1`. Stock increased from `48` to `49` with `userErrors: []`.
- **Step 2B (Restore)**: Executed `inventoryAdjustQuantities` with `delta: -1`. Stock restored from `49` to `48` with `userErrors: []`.

Both operations completed successfully with zero Shopify `userErrors`.

---

## 5. Final Verification

Following the execution of Test 1 and Test 2, a GraphQL verification query (`productVariant(id)`) was executed to inspect live stock:

```text
Final verified quantity = 48
```

The stock count was confirmed to be 100% restored to the original baseline of 48.

---

## 6. Test Summary

| Test | Operation | Expected | Result |
| :--- | :--- | :--- | :--- |
| 1A | Set quantity | 48 → 49 | Passed |
| 1B | Restore quantity | 49 → 48 | Passed |
| 2A | Adjust +1 | 48 → 49 | Passed |
| 2B | Adjust -1 | 49 → 48 | Passed |
| Final | Verify stock | 48 | Passed |

---

## 7. What This Proves

- **API Compatibility**: Confirms that both `inventorySetQuantities` and `inventoryAdjustQuantities` GraphQL mutations are fully supported and functional on the store.
- **Identifier Chain**: Validates that resolving from Product $\rightarrow$ Variant $\rightarrow$ `InventoryItem` GID and `Location` GID is required and effective.
- **Scope Access**: Verifies that the configured API token possesses the `write_inventory` access scope necessary for stock operations.

---

## 8. Existing Code Gap Identified

> **IMPORTANT**: The live API test validates Shopify's inventory API behavior and the required identifiers. It does NOT mean the complete Seller Portal inventory integration has already been implemented.

The test was conducted using a temporary diagnostic script. The main production application code (`shopify_client.py`) currently lacks the following dedicated inventory methods:

- Inventory Item lookup method
- Location lookup method
- Inventory set method
- Inventory adjust method
- Inventory verification method
- Appropriate error handling

---

## 9. Recommended Backend Abstractions

To support future Seller Portal inventory automation, the following helper abstractions should be added to the backend client:

1. `get_inventory_item_id_by_sku(sku: str) -> str`
2. `get_primary_location_id() -> str`
3. `set_inventory_quantity(inventory_item_id: str, location_id: str, quantity: int) -> dict`
4. `adjust_inventory_quantity(inventory_item_id: str, location_id: str, delta: int) -> dict`
5. `verify_inventory_quantity(variant_id: str) -> int`

---

## 10. Conclusion

Live testing successfully demonstrated that inventory quantities can be set and adjusted via Shopify's GraphQL API without errors. The product stock was completely restored and verified. Future development will focus on implementing dedicated backend methods once the Seller Portal API contract is defined.
