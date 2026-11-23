# 53-Check Validation Capability Matrix

This matrix establishes the authoritative source of truth for each of the 53 Shopify Product Validation checks across the **Shopify API Validator** and the **Playwright Browser Verification Layer**.

---

## Authority & Capability Matrix

| Check | Check Name | Section | Severity | Current Method | Can API Prove It? | Can Browser Prove It? | Recommended Authority |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| **01** | Product Title | A. Content | Blocker | API Metadata | **Yes** | Yes | **Shopify API** |
| **02** | Title Formula | A. Content | Warning | API Regex | **Yes** | Yes | **Shopify API** |
| **03** | Title Length | A. Content | Warning | API String Length | **Yes** | Yes | **Shopify API** |
| **04** | Description Present | A. Content | Blocker | API Metadata | **Yes** | Yes | **Shopify API** |
| **05** | Description Standard | A. Content | Blocker | API String Length | **Yes** | Yes | **Shopify API** |
| **06** | Description Formatting | A. Content | Warning | API HTML Regex | **Yes** | Yes | **Shopify API** |
| **07** | Brand Framing | A. Content | Warning | API Keyword Match | **Yes** | Yes | **Shopify API** |
| **08** | Images Present | B. Media | Blocker | API Array Count | **Yes** | Yes | **Shopify API** |
| **09** | Image Count | B. Media | Warning | API Array Count | **Yes** | Yes | **Shopify API** |
| **10** | Featured Image | B. Media | Blocker | API Object Check | **Yes** | Yes | **Shopify API** |
| **11** | Square Aspect Ratio | B. Media | Blocker | API Image Dimensions | **Yes** | Yes | **Shopify API** |
| **12** | Image Alt Text | B. Media | Warning | API Metadata | **Yes** | Yes | **Shopify API** |
| **13** | Image File Size | B. Media | Warning | API File Size Check | **Yes** | Yes | **Shopify API** |
| **14** | Price | C. Pricing & Variants | Blocker | API Variant Price | **Yes** | Yes | **Shopify API** |
| **15** | Compare-at Price Set | C. Pricing & Variants | Warning | API Variant Price | **Yes** | Yes | **Shopify API** |
| **16** | Compare-at Greater Than Price | C. Pricing & Variants | Blocker | API Math Comparison | **Yes** | Yes | **Shopify API** |
| **17** | Margin / Profit Target | C. Pricing & Variants | Warning | API Cost Check | **Yes** | No | **Shopify API** |
| **18** | SKU | C. Pricing & Variants | Blocker | API SKU String | **Yes** | Yes | **Shopify API** |
| **19** | Variant Option Names | C. Pricing & Variants | Warning | API Options Array | **Yes** | Yes | **Shopify API** |
| **20** | Barcode / GTIN | C. Pricing & Variants | Warning | API Barcode String | **Yes** | No | **Shopify API** |
| **21** | Track Inventory Flag | D. Inventory & Fulfilment | Blocker | API Management Flag | **Yes** | No | **Shopify API** |
| **22** | Stock Available | D. Inventory & Fulfilment | Blocker | API Inventory Quantity | **Yes** | No | **Shopify API** |
| **23** | Weight | D. Inventory & Fulfilment | Blocker | API Weight Metric | **Yes** | No | **Shopify API** |
| **24** | Requires Shipping Flag | D. Inventory & Fulfilment | Blocker | API Fulfillment Flag | **Yes** | No | **Shopify API** |
| **25** | Country of Origin | D. Inventory & Fulfilment | Warning | API Customs Object | **Yes** | No | **Shopify API** |
| **26** | Tax Setting | D. Inventory & Fulfilment | Blocker | API Taxable Flag | **Yes** | No | **Shopify API** |
| **27** | Product Type | E. Organisation | Blocker | API String Check | **Yes** | Yes | **Shopify API** |
| **28** | Vendor | E. Organisation | Blocker | API Vendor String | **Yes** | Yes | **Shopify API** |
| **29** | Tags | E. Organisation | Blocker | API Tags String | **Yes** | No | **Shopify API** |
| **30** | In a Collection | E. Organisation | Blocker | API Collect Object | **Yes** | No | **Shopify API** |
| **31** | Taxonomy Category | E. Organisation | Warning | API Standardized Taxonomy | **Yes** | No | **Shopify API** |
| **32** | Search Terms / Keywords | E. Organisation | Warning | API Tag/Metafield Search | **Yes** | No | **Shopify API** |
| **33** | Handle | F. Search Listing | Blocker | API Handle String | **Yes** | Yes | **Shopify API** |
| **34** | SEO Title Configured | F. Search Listing | Blocker | API Meta Title | **Yes** | Yes | **Shopify API** |
| **35** | SEO Title Length | F. Search Listing | Warning | API String Length | **Yes** | Yes | **Shopify API** |
| **36** | SEO Description Configured | F. Search Listing | Blocker | API Meta Description | **Yes** | Yes | **Shopify API** |
| **37** | SEO Description Length | F. Search Listing | Warning | API String Length | **Yes** | Yes | **Shopify API** |
| **38** | Indexable / In Sitemap | F. Search Listing | Blocker | API Publication Status | **Yes** | Yes | **Shopify API** |
| **39** | Structured Data | F. Search Listing | Warning | API Field Validation | Partial | **Yes** | **Playwright Browser** |
| **40** | Single H1 | F. Search Listing | Warning | Rendered DOM Inspection | No | **Yes** | **Playwright Browser** |
| **41** | Template Assigned | G. Template & Rendering | Blocker | API Template Suffix | **Yes** | Yes | **Shopify API** |
| **42** | Metafields Populated | G. Template & Rendering | Blocker | API Metafields Object | **Yes** | No | **Shopify API** |
| **43** | Live URL Loads | G. Template & Rendering | Blocker | Live HTTP Navigation | No | **Yes** | **Playwright Browser** |
| **44** | Mobile Render | G. Template & Rendering | Blocker | Mobile Viewport Simulation | No | **Yes** | **Playwright Browser** |
| **45** | Add to Cart | G. Template & Rendering | Blocker | Storefront Cart Interaction | No | **Yes** | **Playwright Browser** |
| **46** | Buy It Now | G. Template & Rendering | Blocker | Dynamic Checkout Session | No | **Yes** | **Playwright Browser** |
| **47** | Collection Card Render | G. Template & Rendering | Blocker | Live Collection Page DOM | No | **Yes** | **Playwright Browser** |
| **48** | Status Active | H. Channels | Blocker | API Product Status | **Yes** | No | **Shopify API** |
| **49** | Published to Online Store | H. Channels | Blocker | API Publication Channel | **Yes** | No | **Shopify API** |
| **50** | Published to Social Channels | H. Channels | Warning | API Publication Channel | **Yes** | No | **Shopify API** |
| **51** | In WhatsApp Catalogue | H. Channels | Warning | API Publication Channel | **Yes** | No | **Shopify API** |
| **52** | No Fake Social Proof | I. Policy | Blocker | API Body Content Scan | **Yes** | Yes | **Shopify API** |
| **53** | Claims Match Reality | I. Policy | Blocker | API Specs Verification | **Yes** | No | **Shopify API** |

---

## Authority Summary
- **Shopify API Authoritative (41 Checks)**: Checks 1–38, 41–42, 48–53.
- **Playwright Browser Authoritative (6 Checks)**: Checks 40, 43, 44, 45, 46, 47.
- **Combined / Hybrid Verification (6 Checks)**: Checks 39, 40, 43, 44, 45, 47.
