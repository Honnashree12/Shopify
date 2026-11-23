# Shopify API & Catalog Integration Research Summary

## 1. Purpose

The purpose of this research is to document how our backend system integrates with Shopify's catalog and inventory data structures, and to define the foundational concepts required for a future Seller Portal to Shopify automated inventory workflow.

---

## 2. Shopify API Overview

The backend integration relies on the official **Shopify Admin GraphQL API** to communicate with the Shopify store.

```text
Backend → Shopify Admin API → Shopify Store
```

The backend authenticates using Admin API credentials configured through environment variables:
- `SHOPIFY_STORE_URL` (e.g. `kinq5t-q5.myshopify.com`)
- `SHOPIFY_ACCESS_TOKEN` (Admin API access token)
- `SHOPIFY_API_VERSION` (e.g. `2025-07`)

*Note: All secrets, access tokens, and credentials remain strictly managed within secure configuration settings and are never hardcoded or exposed in source code.*

---

## 3. Query vs Mutation

In GraphQL, read and write operations are strictly divided:

```text
Query    = read data
Mutation = change data
```

### Shopify-Specific Examples:
- **GraphQL Query Example**: Retrieving a product, its variants, and its current stock:
  ```graphql
  query getProductVariants {
    products(first: 5) {
      edges {
        node {
          id
          title
          variants(first: 5) {
            edges {
              node {
                id
                sku
                inventoryQuantity
                inventoryItem {
                  id
                }
              }
            }
          }
        }
      }
    }
  }
  ```
- **GraphQL Mutation Example**: Updating inventory levels at a specified location:
  ```graphql
  mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
    inventorySetQuantities(input: $input) {
      inventoryAdjustmentGroup {
        reason
        changes {
          name
          delta
        }
      }
      userErrors {
        field
        message
      }
    }
  }
  ```

---

## 4. Catalog and Inventory Relationship

Shopify structures products and inventory through a hierarchical object graph:

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

### Why Product ID Alone Is Not Sufficient for Inventory Updates
In Shopify, a **Product** (`gid://shopify/Product/...`) is a top-level organizational container that holds one or more **Product Variants** (`gid://shopify/ProductVariant/...`). Inventory in Shopify is **not** tracked directly on the Product container. Instead:
1. Each **Product Variant** links 1-to-1 to a physical **Inventory Item** (`gid://shopify/InventoryItem/...`).
2. Inventory levels for an **Inventory Item** are tracked separately across specific physical **Locations** (`gid://shopify/Location/...`).

Therefore, updating inventory requires resolving down through the hierarchy to obtain the specific **Inventory Item ID** and **Location ID**.

---

## 5. Existing Project Integration

The existing backend module [`shopify_client.py`](file:///c:/Users/honnu/Downloads/shopify-launch-agent_shopify-live2/shopify-launch-agent/shopify-product-launch/shopify_client.py) provides built-in capabilities for product catalog administration.

### Existing Capabilities in `shopify_client.py`:
- **Product Lookup**: `get_product(product_id)`, `get_product_by_title(title)`
- **Variant/SKU Lookup**: `get_product_by_sku(sku)`
- **Product Management**: `create_product(**kwargs)`, `update_product(product_id, **kwargs)`
- **Media & Collections**: `upload_product_images(...)`, `get_or_create_custom_collection(...)`, `add_product_to_collection(...)`
- **GraphQL Fetching**: `fetch_all_products_graphql()`

### Capability Matrix:

| Requirement | Existing Support |
| :--- | :--- |
| Product lookup | Available |
| Variant/SKU lookup | Available |
| Product creation/update | Available |
| Inventory Item lookup | Needs dedicated support |
| Location lookup | Needs dedicated support |
| Inventory quantity read | Partially available |
| Inventory quantity update | Needs inventory mutation methods |

---

## 6. Required Shopify Permissions

Executing inventory-related GraphQL queries and mutations requires specific Admin API access scopes:

- **`read_products`**: Required to query product details, variants, and SKUs.
- **`read_inventory`**: Required to read `inventoryItemId` on variants and query location stock levels.
- **`write_inventory`**: Required to execute inventory mutations (`inventorySetQuantities`, `inventoryAdjustQuantities`).

---

## 7. Inventory APIs Identified

Shopify provides two distinct GraphQL mutations for updating inventory levels:

### 1. `inventorySetQuantities`
Used when the desired final absolute quantity is known.
- **Example**: Changing stock from `48` to `75`.
- **Meaning**: *"Set the available stock level to exactly 75."*
- **Official Reference**: [`inventorySetQuantities` Mutation Docs](https://shopify.dev/docs/api/admin-graphql/latest/mutations/inventorySetQuantities)

### 2. `inventoryAdjustQuantities`
Used when the stock delta or adjustment amount is known.
- **Example**: Adjusting stock by `+27` (from `48` to `75`).
- **Meaning**: *"Increase the available stock level by 27."*
- **Official Reference**: [`inventoryAdjustQuantities` Mutation Docs](https://shopify.dev/docs/api/admin-graphql/latest/mutations/inventoryAdjustQuantities)

*Note: Neither mutation is universally superior; the choice depends on the contract defined with the Seller Portal.*

---

## 8. Important Integration Flow

The conceptual end-to-end inventory synchronization sequence:

```text
Seller Portal (Stock Change Event)
      ↓
Identify Business / Store
      ↓
Identify Product / Variant
      ↓
Resolve Inventory Item ID
      ↓
Resolve Location ID
      ↓
Execute Shopify Inventory Mutation
      ↓
Verify Updated Quantity
      ↓
Return Success / Error to Seller Portal
```

---

## 9. Key Research Findings

1. **Hierarchy Dependence**: Stock updates cannot bypass `InventoryItem` and `Location` resolution.
2. **Read vs Write Division**: Product queries and inventory updates use distinct API patterns.
3. **Existing Client Gaps**: While product and SKU lookups exist in `shopify_client.py`, helper abstractions for `InventoryItem` GID retrieval, `Location` resolution, and inventory mutations are not yet built.

---

## 10. Open Integration Decisions

The following architectural items are **TBD / to be finalized** in consultation with the team:

- **Business/Store Grouping**: How multi-tenant business entities and store channels will be identified and mapped in the database.
- **Product Key Contract**: Whether the Seller Portal will send SKU, Variant ID, Product ID, or a custom business key.
- **Location Policy**: How the Shopify `Location` will be selected when a store operates across multiple physical warehouses.
- **Mutation Type**: Whether the Seller Portal will supply an absolute final stock quantity (`inventorySetQuantities`) or a relative stock delta (`inventoryAdjustQuantities`).

---

## 11. Conclusion

The Shopify Admin GraphQL API provides complete support for location-based inventory management. The existing system possesses strong foundation tools for product and SKU lookups, but dedicated backend abstractions for inventory item lookup, location selection, and inventory mutations must be implemented during the integration phase once the Seller Portal contract is finalized.
