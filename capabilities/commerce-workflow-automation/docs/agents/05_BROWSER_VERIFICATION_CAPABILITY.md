# Browser Verification Capability

## Type
Supporting Capability

## Purpose
The Browser Verification Capability executes automated Playwright Chromium end-to-end storefront validation to verify real customer-facing page loading, mobile visual responsiveness, single H1 HTML header hierarchy, Add-To-Cart CTA interactive execution, price alignment, and visual layout rendering across the product catalog.

## What It Does
1. Launches a headless Playwright Chromium browser instance to navigate to live Shopify storefront URLs (`https://<store_url>/products/<handle>`).
2. Automatically detects and dismisses theme intro/boot overlays (e.g. `.boot-skip`, `.boot-power`, `SKIP INTRO`).
3. Executes real-browser evaluations for Checks 40, 43, 44, 45, 46, 47, 50, and 51:
   - **Check 43 (Live URL Loads)**: Verifies HTTP 200 response, non-404 title, and matching URL handle.
   - **Check 40 (Single H1)**: Verifies exact presence of 1 visible `<h1>` element on the rendered DOM.
   - **Check 44 (Mobile Render)**: Emulates mobile viewport (390 x 844 px), verifies non-overflow (`scrollWidth <= clientWidth + 5`), and captures mobile layout screenshot.
   - **Check 45 (Add to Cart)**: Interacts with cart buttons (`button[name="add"]`, form submit), triggers click, and verifies cart counter increment or drawer presentation (exempts Workshop products).
   - **Check 46 (Price Alignment)**: Validates rendered storefront price against backend product API price data.
   - **Check 47 & 50/51**: Verifies image grid rendering and interactive elements.
4. Captures full-page and element PNG screenshots saved to `docs/audits/screenshots/` for audit evidence.

## How It Works
1. **Headless Browser Orchestration (`verify_product_with_browser`)**:
   - Initializes `playwright.sync_api.sync_playwright()` and launches a Chromium browser context.
   - Constructs target URL from store domain and product handle.
2. **Desktop Viewport Navigation & Overlay Dismissal**:
   - Opens a desktop page (1280 x 800 px) and navigates with `wait_until="domcontentloaded"`.
   - Executes `dismiss_intro_overlay_if_present` to clear modal overlays before element queries.
3. **DOM & CTA Execution**:
   - Queries visible `<h1>` tags and verifies single H1 count.
   - Locates cart button via CSS selectors (`button[name="add"]`, `form[action*="/cart/add"] button`), simulates user click, waits 3000ms, and verifies cart updates.
4. **Mobile Responsiveness Emulation**:
   - Creates a isolated mobile browser context (`viewport={"width": 390, "height": 844}`, `is_mobile=True`).
   - Evaluates layout overflow via JavaScript DOM metrics (`documentElement.scrollWidth` vs `clientWidth`).
5. **Evidence Collection**:
   - Saves PNG screenshots for live URL loading (`<slug>-check-43-live-url.png`), mobile layout (`<slug>-check-44-mobile.png`), and Add To Cart interaction (`<slug>-check-45-add-to-cart.png`).

## Inputs
- `product_data`: Dictionary containing product title, handle, ID, price, product_type, tags, and collection details.
- `store_url`: Optional target Shopify store URL string (defaults to `SHOPIFY_VALIDATION_STORE` environment variable or fallback myshopify URL).

## Outputs
- `Dict[str, Any]` (Browser Verification Results): Structured dictionary containing check results for Rules 40, 43, 44, 45, 46, 47, 50, and 51. Each check result includes status (`PASS`, `FAIL`, `NOT_APPLICABLE`), severity, evidence dictionary (status code, page title, H1 texts, viewport dimensions, overflow metrics, screenshot file paths), and natural language explanation.

## Important Business Rules
- **Zero Shopify Mutations**: Browser verification MUST NOT edit store settings, modify inventory levels, create live orders, or perform payment transactions.
- **Workshop Product ATC Exemption**: Products classified as Workshops (via `product_type`, tags, title, or collection name) are exempt from mandatory Add To Cart button checks (`result: NOT_APPLICABLE`) because workshops utilize event registration flows.
- **Strict Single H1 Rule**: SEO best practices mandate exactly one visible `<h1>` header per rendered product page.
- **Mobile Horizontal Overflow Threshold**: Mobile rendering (390 x 844 px) fails if `scrollWidth` exceeds `clientWidth + 5`, detecting unwanted horizontal scrolling.

## Safety Boundaries
- **Headless Execution Only**: Browser runs in headless mode to prevent desktop popups during background automated runs.
- **Navigation Timeouts**: All browser page navigation calls enforce strict 20000ms timeouts to prevent infinite hanging.
- **Non-Blocking Exception Handling**: Individual check failures catch Playwright timeouts and DOM errors gracefully, recording structured `FAIL` evidence without crashing the overall validation suite.

## Implementation Files
- `backend/browser_verifier.py` (also implemented at `services/browser_verifier.py`)
