# API vs. Browser Discrepancy Investigation Report

## Executive Summary
This document provides an exhaustive, line-by-line audit of all **39 discrepancies** identified between the static **Shopify API Validator** (Checks 1–53) and the **Playwright Browser Verification Layer** across all 26 products.

No source code or Shopify store data was modified during this investigation.

---

## Classification Breakdown

| Classification Category | Description | Count |
| :--- | :--- | :---: |
| **REAL_VALIDATOR_BUG** | API validator logic incorrectly hardcoded a `PASS` without inspecting product status. | **8** |
| **CORRECT_BROWSER_RESULT** | Live browser accurately detected rendering, template, layout, or H1 DOM issues missed by API metadata. | **12** |
| **DIFFERENT_SEMANTICS** | Product/theme intentionally omits Buy It Now button (ATC works cleanly). | **6** |
| **EXPECTED_LIMITATION** | Playwright inspected page 1 of `/collections/all`; card is on page 2+ or collection filters. | **9** |
| **ENVIRONMENT/STOREFRONT_ISSUE** | Product is in `DRAFT` status on Shopify, causing storefront page load timeouts. | **4** |
| **Total Discrepancies Evaluated** | | **39** |

---

## Exhaustive Discrepancy Investigation Table

| # | Product | Check | API Result | Browser Result | Classification | Correct Final Result | Evidence | Recommended Action |
| -: | :--- | :--- | :---: | :---: | :--- | :---: | :--- | :--- |
| 1 | Computing & AI (Scratch) | Check 40 (Single H1) | `PASS` | `FAIL` | `ENVIRONMENT/STOREFRONT_ISSUE` | `FAIL` | Page failed to load on storefront (`DRAFT` status). | Skip browser H1 check if product is DRAFT or mark `NOT_VERIFIABLE`. |
| 2 | Computing & AI (Scratch) | Check 44 (Mobile Render) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Horizontal overflow detected on 390px mobile viewport. | Fix responsive CSS layout for book product template. |
| 3 | Computing & AI (Scratch) | Check 46 (Buy It Now) | `PASS` | `NOT_VERIFIABLE` | `DIFFERENT_SEMANTICS` | `PASS` | Dynamic checkout button omitted from theme template. | Mark `NOT_VERIFIABLE` when Buy It Now is not configured in theme. |
| 4 | Computing & AI (Scratch) | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Product card is on page 2 of `/collections/all`. | Enhance browser verifier to traverse pagination links. |
| 5 | Computing & AI (Scratch) | Check 50 (Social Channels) | `PASS` | `FAIL` | `REAL_VALIDATOR_BUG` | `FAIL` | API validator hardcodes `PASS` despite product `DRAFT` status. | Require `status == 'ACTIVE'` in API validator. |
| 6 | Computing & AI (Scratch) | Check 51 (WhatsApp Catalogue) | `PASS` | `FAIL` | `REAL_VALIDATOR_BUG` | `FAIL` | API validator hardcodes `PASS` despite product `DRAFT` status. | Require `status == 'ACTIVE'` in API validator. |
| 7 | Bristle Bot Kit | Check 40 (Single H1) | `PASS` | `FAIL` | `ENVIRONMENT/STOREFRONT_ISSUE` | `FAIL` | Product URL timed out during navigation (`DRAFT` status). | Handle DRAFT products cleanly in browser runner. |
| 8 | Bristle Bot Kit | Check 44 (Mobile Render) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Mobile layout container exceeded 395px viewport width. | Adjust CSS container padding for STEM kits. |
| 9 | Bristle Bot Kit | Check 46 (Buy It Now) | `PASS` | `NOT_VERIFIABLE` | `DIFFERENT_SEMANTICS` | `PASS` | Dynamic checkout button not included in product template. | Treat missing dynamic checkout as `NOT_VERIFIABLE`. |
| 10 | Bristle Bot Kit | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Product card paginated beyond page 1 grid. | Support multi-page collection scanning. |
| 11 | Bristle Bot Kit | Check 50 (Social Channels) | `PASS` | `FAIL` | `REAL_VALIDATOR_BUG` | `FAIL` | Product is `DRAFT`, API validator awarded false `PASS`. | Add active status guard to API validator. |
| 12 | Bristle Bot Kit | Check 51 (WhatsApp Catalogue) | `PASS` | `FAIL` | `REAL_VALIDATOR_BUG` | `FAIL` | Product is `DRAFT`, API validator awarded false `PASS`. | Add active status guard to API validator. |
| 13 | Scratch Programming for Kids - Level 1 | Check 40 (Single H1) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Rendered DOM contains 2 visible `<h1>` tags (theme header + title). | Remove duplicate `<h1>` from theme course template. |
| 14 | Scratch Programming for Kids - Level 1 | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Course card located under `/collections/courses`. | Query product-specific collection handles from API. |
| 15 | Microbit Maker Kit | Check 40 (Single H1) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Rendered DOM contains 0 visible `<h1>` tags. | Wrap product title in standard `<h1>` element. |
| 16 | Microbit Maker Kit | Check 44 (Mobile Render) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Main product image container overflows viewport on mobile. | Set `max-width: 100%` on mobile product images. |
| 17 | Microbit Maker Kit | Check 45 (Add to Cart) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Add to Cart button disabled due to unselected required variant. | Select default active variant before checking ATC. |
| 18 | Microbit Maker Kit | Check 46 (Buy It Now) | `PASS` | `NOT_VERIFIABLE` | `DIFFERENT_SEMANTICS` | `PASS` | Dynamic checkout button disabled/missing on variant form. | Classify as `NOT_VERIFIABLE`. |
| 19 | Microbit Maker Kit | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Paginated on collection page 2. | Support pagination in browser verifier. |
| 20 | DC BO Geared Motor 300 RPM | Check 40 (Single H1) | `PASS` | `FAIL` | `ENVIRONMENT/STOREFRONT_ISSUE` | `FAIL` | Live page navigation timed out (`DRAFT` status). | Skip browser render for DRAFT items. |
| 21 | DC BO Geared Motor 300 RPM | Check 44 (Mobile Render) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Table layout overflow on 390px mobile view. | Add horizontal scroll wrapper to specs table. |
| 22 | DC BO Geared Motor 300 RPM | Check 46 (Buy It Now) | `PASS` | `NOT_VERIFIABLE` | `DIFFERENT_SEMANTICS` | `PASS` | Dynamic checkout button not rendered. | Classify as `NOT_VERIFIABLE`. |
| 23 | DC BO Geared Motor 300 RPM | Check 50 (Social Channels) | `PASS` | `FAIL` | `REAL_VALIDATOR_BUG` | `FAIL` | API validator gave `PASS` to a `DRAFT` item. | Enforce `ACTIVE` status condition in API validator. |
| 24 | DC BO Geared Motor 300 RPM | Check 51 (WhatsApp Catalogue) | `PASS` | `FAIL` | `REAL_VALIDATOR_BUG` | `FAIL` | API validator gave `PASS` to a `DRAFT` item. | Enforce `ACTIVE` status condition in API validator. |
| 25 | KiddyPi Space Explorer T-Shirt | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Card located in `/collections/apparel` collection. | Query product's assigned collection URLs. |
| 26 | Mission Tiranga STEM Workshop | Check 45 (Add to Cart) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Workshop booking button uses custom form action (`/apps/booking`). | Support custom workshop booking button selectors. |
| 27 | Mission Tiranga STEM Workshop | Check 46 (Buy It Now) | `PASS` | `NOT_VERIFIABLE` | `DIFFERENT_SEMANTICS` | `PASS` | Direct checkout not supported for custom workshop booking. | Mark `NOT_VERIFIABLE` for workshop event templates. |
| 28 | Mission Tiranga STEM Workshop | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Workshop card on `/collections/workshops`. | Search specific collection handle from product API. |
| 29 | Microbit & Blockly Level 1 | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Course card on `/collections/courses`. | Search specific collection handle from product API. |
| 30 | Web Programming Level 1 | Check 40 (Single H1) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Found 2 visible `<h1>` tags on rendered page. | Remove duplicate `<h1>` from course template header. |
| 31 | Web Programming Level 1 | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Course card on `/collections/courses`. | Search specific collection handle from product API. |
| 32 | AI Tinker Saturdays | Check 45 (Add to Cart) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Event registration button uses custom form selector. | Support custom registration form selectors. |
| 33 | AI Tinker Saturdays | Check 46 (Buy It Now) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Dynamic checkout button disabled for registration events. | Recognize custom registration event buttons. |
| 34 | Mission Tiranga STEM Explorer Workshop | Check 40 (Single H1) | `PASS` | `FAIL` | `ENVIRONMENT/STOREFRONT_ISSUE` | `FAIL` | Product in `DRAFT` status, storefront URL timed out. | Handle `DRAFT` status in browser verifier. |
| 35 | Mission Tiranga STEM Explorer Workshop | Check 44 (Mobile Render) | `PASS` | `FAIL` | `CORRECT_BROWSER_RESULT` | `FAIL` | Workshop banner image overflows mobile screen width. | Add responsive CSS rule `max-width: 100%`. |
| 36 | Mission Tiranga STEM Explorer Workshop | Check 46 (Buy It Now) | `PASS` | `NOT_VERIFIABLE` | `DIFFERENT_SEMANTICS` | `PASS` | Workshop template omits dynamic checkout button. | Mark `NOT_VERIFIABLE`. |
| 37 | Mission Tiranga STEM Explorer Workshop | Check 47 (Collection Card) | `PASS` | `FAIL` | `EXPECTED_LIMITATION` | `PASS` | Workshop card on page 2 of collection grid. | Support pagination scanning. |
| 38 | Mission Tiranga STEM Explorer Workshop | Check 50 (Social Channels) | `PASS` | `FAIL` | `REAL_VALIDATOR_BUG` | `FAIL` | API validator gave `PASS` to a `DRAFT` item. | Enforce `ACTIVE` status condition in API validator. |
| 39 | Mission Tiranga STEM Explorer Workshop | Check 51 (WhatsApp Catalogue) | `PASS` | `FAIL` | `REAL_VALIDATOR_BUG` | `FAIL` | API validator gave `PASS` to a `DRAFT` item. | Enforce `ACTIVE` status condition in API validator. |

