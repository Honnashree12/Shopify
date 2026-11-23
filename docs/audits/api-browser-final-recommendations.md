# API vs. Browser Final Recommendations Report

This document outlines strategic recommendations for integrating the **Playwright Browser Verification Layer** into the core **Shopify Product Validation Engine** without destabilizing existing audited validation metrics.

---

## Strategic Recommendations by Group

### A. Keep API Validator As-Is (45 Checks)
The current static API validator rules for **Checks 1–39, 41–42, 48–49, 52–53** are accurate, reliable, and match audited raw Shopify data.
- **Action**: Retain static API evaluations as the primary verification method.

### B. Improve API Validator (2 Checks)
- **Check 50 (Published to Social Channels)** & **Check 51 (In WhatsApp Catalogue)**:
  - **Issue**: API validator awarded `PASS` to products with `status == 'DRAFT'`.
  - **Fix Recommendation**: Update `agents/product_validation_agent.py` to check `if status.upper() == "ACTIVE"` before issuing `PASS`.

### C. Browser Should Be Authoritative (6 Checks)
Live storefront verification is essential for customer-facing rendering and template interactivity:
- **Check 40 (Single H1)**: Rendered DOM H1 count.
- **Check 43 (Live URL Loads)**: Real HTTP 200 storefront navigation.
- **Check 44 (Mobile Render)**: Real 390×844 mobile viewport layout verification without overflow.
- **Check 45 (Add to Cart)**: Interactive cart button operation.
- **Check 46 (Buy It Now)**: Checkout session initiation (`/checkouts/cn/...`).
- **Check 47 (Collection Card Render)**: Rendered product card on collection grid.

### D. API Should Remain Authoritative (47 Checks)
Shopify Admin API is the authoritative source for backend compliance:
- SKU, Pricing, Cost, Inventory, Weight, Customs, Tax Settings, Metafields, Product Status, and Channel Publication.

### E. Browser Verifier Enhancements (3 Recommendations)
1. **Collection Pagination**: Update `services/browser_verifier.py` for Check 47 to scan paginated pages (e.g. `?page=2`) if the product card is not on page 1 of `/collections/all`.
2. **Draft Product Guard**: Skip live storefront navigation for `DRAFT` items or mark them `NOT_VERIFIABLE` rather than reporting browser network timeouts.
3. **Custom Event Selector**: Support custom registration/booking button selectors for workshop and course product templates.

### F. Business-Rule & Template Guidance
- **Course / Workshop Templates**: Products without dynamic checkout buttons (Check 46) should be classified as `NOT_VERIFIABLE` rather than `FAIL` if Add to Cart operates cleanly.
