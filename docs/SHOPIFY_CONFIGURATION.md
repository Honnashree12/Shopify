# Shopify API Configuration Guide (`docs/SHOPIFY_CONFIGURATION.md`)

This document details the Shopify API authentication mechanisms, required access scopes, environment variables, verification steps, and error diagnostics for the **Shopify Product Launch Platform**.

---

## 🔑 Authentication Modes Supported

The system supports **two authentication modes**:

### Mode 1: Custom App Admin Access Token (Recommended for single stores)
Uses a direct **Admin API Access Token** generated inside Shopify Admin under `Settings > Apps and sales channels > Develop apps`.

- **`SHOPIFY_STORE_URL`**: Your store domain (e.g., `my-store.myshopify.com`).
- **`SHOPIFY_ACCESS_TOKEN`**: Custom app token starting with `shpat_`.

### Mode 2: Partner App OAuth 2.0 Authorization Code Flow
Uses Shopify Partner App client credentials to dynamically authenticate store owners.

- **`SHOPIFY_CLIENT_ID`**: Partner App Client ID from Shopify Partner Dashboard.
- **`SHOPIFY_CLIENT_SECRET`**: Partner App Client Secret.
- **`SHOPIFY_APP_URL`**: Public URL of your backend (default `http://localhost:8000`).
- **`SHOPIFY_REDIRECT_URI`**: OAuth callback endpoint (`http://localhost:8000/api/shopify/callback`).

---

## 🔒 Required Admin API Scopes

When creating your Shopify App, grant the following **6 Admin API Access Scopes**:

| Scope Name | Access Level | Description / Usage in Application |
|---|---|---|
| `read_products` | Read | Fetch products for 53-check catalog validation audits |
| `write_products` | Read & Write | Create draft products, update copy, SEO titles, SKUs, and images |
| `read_inventory` | Read | Fetch variant stock levels across store locations |
| `write_inventory` | Read & Write | Update inventory quantities, SKU tracking, and physical weights |
| `read_themes` | Read | Inspect theme template suffixes (e.g. `template_suffix == 'workshop'`) |
| `read_locations` | Read | Query store location IDs to allocate inventory quantities |

---

## ⚙️ Environment Variables Summary

Define these variables in your root `.env` file:

```ini
# Primary Store
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_your_admin_access_token_here
SHOPIFY_API_VERSION=2025-07

# OAuth Credentials (If using embedded app flow)
SHOPIFY_CLIENT_ID=your_client_id_here
SHOPIFY_CLIENT_SECRET=your_client_secret_here
SHOPIFY_REDIRECT_URI=http://localhost:8000/api/shopify/callback

# Multi-Store Validation Override (Optional)
SHOPIFY_VALIDATION_STORE=your-validation-store.myshopify.com
SHOPIFY_VALIDATION_TOKEN=shpat_your_validation_token_here
```

---

## ✅ How to Verify Configuration

To test your Shopify connection and verify credentials:

1. Run backend server:
   ```bash
   python -m uvicorn main:app --port 8000
   ```
2. Open `http://127.0.0.1:8000/docs` in your browser.
3. Call the `GET /api/validation/summary` endpoint.
4. If configured correctly, the endpoint returns catalog validation metrics without HTTP 401 or 403 errors.

---

## ❌ Diagnostic Error Guide

| Error Message / Status | Root Cause | Resolution |
|---|---|---|
| `CRITICAL STARTUP ERROR: MISSING SHOPIFY CONFIGURATION` | `SHOPIFY_STORE_URL` or `SHOPIFY_ACCESS_TOKEN` / OAuth keys missing in `.env`. | Create `.env` from `.env.example` and set missing variables. |
| `ShopifyAPIError: 401 Unauthorized` | Invalid or expired Admin Access Token (`shpat_...`). | Re-generate API token in Shopify Admin and update `.env`. |
| `ShopifyAPIError: 403 Forbidden` | App is missing required scope (e.g. `write_products` or `write_inventory`). | Update app permissions in Shopify Admin and reinstall app. |
| `ShopifyConfigError: Missing store URL` | `SHOPIFY_STORE_URL` variable is empty or null. | Set `SHOPIFY_STORE_URL=yourstore.myshopify.com` in `.env`. |
