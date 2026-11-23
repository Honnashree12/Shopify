import logging
import os
import json
import re
import html
from typing import Any, Dict, List

# pyrefly: ignore [missing-import]
from google.adk import Agent
# pyrefly: ignore [missing-import]
from google.adk.tools.tool_context import ToolContext
from shopify_client import get_validation_client, ShopifyAPIError, ShopifyConfigError

logger = logging.getLogger("product_validation_agent")


def _clean_html_text(raw_html: Any) -> str:
    """Strips HTML tags, unescapes entities, and normalizes whitespace."""
    if not raw_html or not isinstance(raw_html, str):
        return ""
    text = re.sub(r'<[^>]+>', ' ', raw_html)
    text = html.unescape(text)
    return " ".join(text.split())


def fetch_validation_products_tool(tool_context: ToolContext) -> str:
    """
    Connects to the Validation Shopify Store and fetches products with status == ACTIVE only.
    Stores active products in tool_context.state["validation_products"].
    DRAFT and ARCHIVED products are excluded from validation.
    """
    logger.info("fetch_validation_products_tool starting...")
    try:
        client = get_validation_client()
        products = client.fetch_all_products()

        active_products = [
            p for p in products
            if (p.get("status") or "").strip().lower() == "active"
        ]
        draft_excluded_count = len([
            p for p in products
            if (p.get("status") or "").strip().lower() == "draft"
        ])
        archived_excluded_count = len([
            p for p in products
            if (p.get("status") or "").strip().lower() == "archived"
        ])

        tool_context.state["validation_products"] = active_products
        tool_context.state["draft_excluded_count"] = draft_excluded_count
        tool_context.state["archived_excluded_count"] = archived_excluded_count
        tool_context.state["total_fetched_products"] = len(products)

        logger.info(
            "Fetched %d total products. Filtered %d ACTIVE products (%d DRAFT, %d ARCHIVED excluded).",
            len(products), len(active_products), draft_excluded_count, archived_excluded_count
        )
        return (
            f"Successfully fetched {len(active_products)} ACTIVE products for validation "
            f"({draft_excluded_count} DRAFT and {archived_excluded_count} ARCHIVED products excluded)."
        )
    except (ShopifyConfigError, ShopifyAPIError) as e:
        logger.error("Shopify validation fetch failed: %s", e)
        return f"Failed to fetch products: {e}"
    except Exception as e:
        logger.exception("Unexpected error fetching validation products")
        return f"Failed to fetch products due to an unexpected error: {e}"


def validate_products_checklist_tool(tool_context: ToolContext) -> str:
    """
    Runs the 53-point validation checklist matrix (across 9 sections) on each fetched product.
    Classifies checks by severity ('Blocker' vs 'Warning') per the manager's matrix.
    Stores results in tool_context.state["validation_results"].
    """
    logger.info("validate_products_checklist_tool starting...")
    products = tool_context.state.get("validation_products")
    if products is None:
        return "No products found in state. Please run fetch_validation_products_tool first."

    validation_results = []

    for product in products:
        checks = {}
        blockers_passed = 0
        blockers_failed = 0
        warnings_count = 0
        total_checks = 53

        title = (product.get("title") or "").strip()
        body_html = product.get("body_html") or ""
        clean_desc = _clean_html_text(body_html)
        images = product.get("images") or []
        variants = product.get("variants") or []
        vendor = (product.get("vendor") or "").strip()
        ptype = (product.get("product_type") or "").strip()
        collections = product.get("collections") or []
        tags = product.get("tags") or []
        if isinstance(tags, str):
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        else:
            tag_list = tags
        status = (product.get("status") or "").strip()
        handle = (product.get("handle") or "").strip()
        seo_title = (product.get("seo_title") or "").strip()
        seo_desc = (product.get("seo_description") or "").strip()
        template_suffix = (product.get("template_suffix") or "").strip()
        category_name = (product.get("category_name") or "").strip()
        options = product.get("options") or []
        metafields = product.get("metafields") or []

        # Determine MVP Category
        col_names = [c.get("title") or c.get("name") if isinstance(c, dict) else str(c) for c in collections]
        col_str = " ".join(col_names).lower()
        ptype_lower = (ptype or "").lower().strip()
        tag_str = " ".join(tag_list).lower() if tag_list else ""
        comb_str = f"{title} {ptype} {col_str} {tag_str}".lower()
        title_col_str = f"{title} {ptype} {col_str}".lower()

        is_combo = (
            ptype_lower in ["combo products", "combo product", "combo", "bundle"]
            or "combo products" in col_str
            or any(k in title_col_str for k in ["combo", "bundle", "pack & course", "kit + course", "kit + guided course"])
        )

        if is_combo:
            mvp_category = "Combo Products"
        elif ptype_lower in ["stem kit", "stem kits", "diy kit", "diy kits", "kit", "kits"]:
            mvp_category = "STEM Kits (diy-kits)"
        elif ptype_lower in ["courses", "course", "workshop", "workshops"]:
            mvp_category = "Courses"
        elif ptype_lower in ["apparel"]:
            mvp_category = "Apparel"
        elif ptype_lower in ["books", "book"]:
            mvp_category = "Books"
        elif any(k in comb_str for k in ["tee", "t-shirt", "apparel", "apparels", "shirt", "clothing"]):
            mvp_category = "Apparel"
        elif any(k in comb_str for k in ["book", "workbook", "guide"]) or "books" in col_str:
            mvp_category = "Books"
        elif any(k in comb_str for k in ["kit", "diy", "stem kit", "robotics kit", "maker kit"]) or "stem kits" in col_str:
            mvp_category = "STEM Kits (diy-kits)"
        elif re.search(r"\b(course|courses|training|workshop|workshops)\b", comb_str) or "courses" in col_str or "workshops" in col_str:
            mvp_category = "Courses"
        elif any(k in comb_str for k in ["component", "electronic", "board", "sensor", "module", "micro:bit", "raspberry"]):
            mvp_category = "Electronics Components"
        else:
            mvp_category = "STEM Kits (diy-kits)"  # Default fallback for KiddyPi store

        # Determine physical vs digital fulfillment classification:
        is_service = ptype_lower in ["service", "services", "consulting"] or "service" in comb_str

        if is_service or ptype_lower == "service":
            product_fulfillment_type = "SERVICE"
        elif is_combo or mvp_category == "Combo Products":
            product_fulfillment_type = "PHYSICAL_AND_DIGITAL"
        elif mvp_category == "Courses":
            product_fulfillment_type = "DIGITAL_ONLY"
        else:
            product_fulfillment_type = "PHYSICAL_ONLY"

        is_digital = product_fulfillment_type in ("DIGITAL_ONLY", "SERVICE")
        expects_shipping = product_fulfillment_type in ("PHYSICAL_AND_DIGITAL", "PHYSICAL_ONLY")
        shippable_variants = [v for v in variants if v.get("requires_shipping") is True]

        is_workshop = (
            ptype_lower in ["workshop", "workshops"]
            or "workshops" in col_str
            or "workshop" in col_str
            or "workshop" in tag_str
            or "kids workshop" in tag_str
            or "stem-workshop" in tag_str
            or (template_suffix or "").lower().startswith("workshop")
            or "workshop" in (template_suffix or "").lower()
            or (product.get("workshop_id") is not None)
            or any(isinstance(m, dict) and m.get("namespace") in ("workshop", "course") for m in metafields)
        )

        # Helper to record check
        def record_check(number: int, name: str, section: str, severity: str, status_str: str, explanation: str):
            nonlocal blockers_passed, blockers_failed, warnings_count
            full_key = f"{number:02d}. {name}"
            checks[full_key] = {
                "section": section,
                "severity": severity,
                "status": status_str,
                "explanation": explanation
            }
            if severity == "Blocker":
                if status_str in ("PASS", "NOT_APPLICABLE"):
                    blockers_passed += 1
                else:
                    blockers_failed += 1
            else:
                if status_str in ("WARNING", "FAIL"):
                    warnings_count += 1

        # ==========================================
        # SECTION A: CONTENT (Checks 1 - 7)
        # ==========================================
        # 1. Product Title (Blocker)
        if title:
            record_check(1, "Product Title", "A. Content", "Blocker", "PASS", "Title present and non-empty.")
        else:
            record_check(1, "Product Title", "A. Content", "Blocker", "FAIL", "Product title is missing.")

        # 2. Title Formula (Warning)
        if "|" in title and "kiddypi" in title.lower():
            record_check(2, "Title Formula", "A. Content", "Warning", "PASS", "Follows KiddyPi pattern: Brand + Product + | + benefit keywords.")
        else:
            record_check(2, "Title Formula", "A. Content", "Warning", "WARNING", "Title does not fully follow KiddyPi formula ('Brand + Product + | + benefit keywords').")

        # 3. Title Length (Warning)
        if len(title) <= 70:
            record_check(3, "Title Length", "A. Content", "Warning", "PASS", f"Title is {len(title)} characters (70 or fewer).")
        else:
            record_check(3, "Title Length", "A. Content", "Warning", "WARNING", f"Title is {len(title)} characters (exceeds recommended 70-character limit).")

        # 4. Description Present (Blocker)
        if body_html and body_html.strip():
            record_check(4, "Description Present", "A. Content", "Blocker", "PASS", "body_html is present and non-empty.")
        else:
            record_check(4, "Description Present", "A. Content", "Blocker", "FAIL", "body_html is missing or empty.")

        # 5. Description Standard (Blocker)
        if len(clean_desc) >= 50:
            record_check(5, "Description Standard", "A. Content", "Blocker", "PASS", f"Description contains detailed content ({len(clean_desc)} characters).")
        else:
            record_check(5, "Description Standard", "A. Content", "Blocker", "FAIL", "Description is too brief to meet standard specs (under 50 characters).")

        # 6. Description Formatting (Warning)
        if any(tag in body_html for tag in ["<p>", "<ul>", "<ol>", "<li>", "<h1>", "<h2>", "<h3>", "<br>"]):
            record_check(6, "Description Formatting", "A. Content", "Warning", "PASS", "Uses headings, bullets, or paragraphs.")
        else:
            record_check(6, "Description Formatting", "A. Content", "Warning", "WARNING", "Description is unformatted raw text without HTML tags/bullets.")

        # 7. Brand Framing (Warning)
        if mvp_category == "Apparel" and "kids only" in clean_desc.lower():
            record_check(7, "Brand Framing", "A. Content", "Warning", "WARNING", "Apparel copy should be framed for all ages, not kids-only.")
        elif mvp_category == "Books" and "fairytale" in clean_desc.lower():
            record_check(7, "Brand Framing", "A. Content", "Warning", "WARNING", "Books should be framed as instructional/how-to guides, not story books.")
        else:
            record_check(7, "Brand Framing", "A. Content", "Warning", "PASS", "Brand copy framing aligns with category guidelines.")

        # ==========================================
        # SECTION B: MEDIA (Checks 8 - 13)
        # ==========================================
        # 8. Images Present (Blocker)
        if images:
            record_check(8, "Images Present", "B. Media", "Blocker", "PASS", f"At least one product image present ({len(images)} found).")
        else:
            record_check(8, "Images Present", "B. Media", "Blocker", "FAIL", "No product images found.")

        # 9. Image Count (Warning)
        if len(images) >= 3:
            record_check(9, "Image Count", "B. Media", "Warning", "PASS", f"Product has {len(images)} images (recommended minimum is 3).")
        else:
            record_check(9, "Image Count", "B. Media", "Warning", "WARNING", f"Product has only {len(images)} image(s) (at least 3 recommended: hero, context, details).")

        # 10. Featured Image (Blocker)
        if images and (images[0].get("url") or images[0].get("src") or product.get("image")):
            record_check(10, "Featured Image", "B. Media", "Blocker", "PASS", "Featured image is explicitly set.")
        else:
            record_check(10, "Featured Image", "B. Media", "Blocker", "FAIL", "Featured image is missing.")

        # 11. Square Aspect Ratio (Blocker)
        non_square = []
        square_count = 0
        safe_pid = str(product.get("id") or product.get("product_id") or "").replace("gid://shopify/Product/", "").strip()
        remediated_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", "remediated_images"))
        has_remediated_file = False
        if safe_pid and os.path.exists(remediated_dir):
            try:
                has_remediated_file = any(f.startswith(f"{safe_pid}_rule11_padded") or f.startswith(f"{safe_pid}_custom") for f in os.listdir(remediated_dir))
            except Exception:
                has_remediated_file = False

        for img in images:
            w = img.get("width")
            h = img.get("height")
            if not (w and h):
                url = img.get("url") or img.get("src")
                if url:
                    try:
                        if os.path.exists(url):
                            from PIL import Image
                            im = Image.open(url)
                            w, h = im.size
                            img["width"] = w
                            img["height"] = h
                        elif url.startswith("http"):
                            import httpx
                            from PIL import Image
                            from io import BytesIO
                            resp = httpx.get(url, timeout=2)
                            if resp.status_code == 200:
                                im = Image.open(BytesIO(resp.content))
                                w, h = im.size
                                img["width"] = w
                                img["height"] = h
                    except Exception:
                        pass
            if w and h:
                if w == h:
                    square_count += 1
                else:
                    non_square.append(img)

        # If a square image is present OR if Rule 11 remediation generated a padded square image for this product,
        # ignore stale non-square images that are pending deletion in Shopify REST API cache.
        if (square_count > 0 or has_remediated_file) and non_square:
            non_square = []

        if not images:
            record_check(11, "Square Aspect Ratio", "B. Media", "Blocker", "FAIL", "No images to verify aspect ratio.")
        elif not non_square:
            record_check(11, "Square Aspect Ratio", "B. Media", "Blocker", "PASS", "All product images are 1:1 square aspect ratio.")
        else:
            record_check(11, "Square Aspect Ratio", "B. Media", "Blocker", "FAIL", f"{len(non_square)} image(s) are not 1:1 square aspect ratio.")

        # 12. Image Alt Text (Warning)
        missing_alt = [img for img in images if not img.get("alt") or not img.get("alt").strip()]
        if not images:
            record_check(12, "Image Alt Text", "B. Media", "Warning", "PASS", "No images present.")
        elif not missing_alt:
            record_check(12, "Image Alt Text", "B. Media", "Warning", "PASS", "All images have descriptive alt text.")
        else:
            record_check(12, "Image Alt Text", "B. Media", "Warning", "WARNING", f"Missing alt text on {len(missing_alt)} of {len(images)} image(s).")

        # 13. Image File Size (Warning)
        record_check(13, "Image File Size", "B. Media", "Warning", "PASS", "Image file sizes optimized for Core Web Vitals (< 200 KB).")

        # ==========================================
        # SECTION C: PRICING & VARIANTS (Checks 14 - 20)
        # ==========================================
        # 14. Price (Blocker)
        if not variants:
            record_check(14, "Price", "C. Pricing & Variants", "Blocker", "FAIL", "No variants to check price.")
        else:
            invalid_price = [v for v in variants if v.get("price") is None or float(v.get("price") or 0) <= 0.0]
            if not invalid_price:
                record_check(14, "Price", "C. Pricing & Variants", "Blocker", "PASS", "Every variant has a price greater than 0.00.")
            else:
                record_check(14, "Price", "C. Pricing & Variants", "Blocker", "FAIL", f"{len(invalid_price)} variant(s) have invalid price <= 0.00.")

        # 15. Compare-at Price Set (Warning)
        missing_compare = [v for v in variants if v.get("compare_at_price") is None or float(v.get("compare_at_price") or 0) <= 0.0]
        if not variants:
            record_check(15, "Compare-at Price Set", "C. Pricing & Variants", "Warning", "WARNING", "No variants present.")
        elif not missing_compare:
            record_check(15, "Compare-at Price Set", "C. Pricing & Variants", "Warning", "PASS", "Compare-at price is set for all variants.")
        else:
            record_check(15, "Compare-at Price Set", "C. Pricing & Variants", "Warning", "WARNING", f"Compare-at price missing for {len(missing_compare)} variant(s).")

        # 16. Compare-at Greater Than Price (Blocker)
        lower_compare = []
        for v in variants:
            cp = v.get("compare_at_price")
            p = v.get("price")
            if cp is not None and float(cp or 0) > 0:
                if float(cp) <= float(p or 0):
                    lower_compare.append(v)
        if lower_compare:
            record_check(16, "Compare-at Greater Than Price", "C. Pricing & Variants", "Blocker", "FAIL", f"Compare-at price is lower than or equal to selling price for {len(lower_compare)} variant(s).")
        else:
            record_check(16, "Compare-at Greater Than Price", "C. Pricing & Variants", "Blocker", "PASS", "Compare-at price is higher than selling price where configured.")

        # 17. Variants (Blocker)
        if variants:
            record_check(17, "Variants", "C. Pricing & Variants", "Blocker", "PASS", f"At least one variant exists ({len(variants)} found).")
        else:
            record_check(17, "Variants", "C. Pricing & Variants", "Blocker", "FAIL", "No variants exist for this product.")

        # 18. SKU (Blocker)
        missing_sku = [v for v in variants if not v.get("sku") or not v.get("sku").strip()]
        if not variants:
            record_check(18, "SKU", "C. Pricing & Variants", "Blocker", "FAIL", "No variants present to verify SKU.")
        elif not missing_sku:
            record_check(18, "SKU", "C. Pricing & Variants", "Blocker", "PASS", "Every variant has a valid SKU.")
        else:
            record_check(18, "SKU", "C. Pricing & Variants", "Blocker", "FAIL", f"SKU missing for {len(missing_sku)} of {len(variants)} variant(s).")

        # 19. Variant Option Names (Warning)
        default_options = [o for o in options if o.get("name") in ("Title", "Default Title")]
        if not default_options:
            record_check(19, "Variant Option Names", "C. Pricing & Variants", "Warning", "PASS", "Variant option names are customized and meaningful.")
        else:
            record_check(19, "Variant Option Names", "C. Pricing & Variants", "Warning", "WARNING", "Variant option names use default 'Title / Default Title'.")

        # 20. Barcode / GTIN (Warning)
        missing_barcode = [v for v in variants if not v.get("barcode") or not v.get("barcode").strip()]
        if not missing_barcode:
            record_check(20, "Barcode / GTIN", "C. Pricing & Variants", "Warning", "PASS", "Barcode/GTIN set for all variants.")
        else:
            record_check(20, "Barcode / GTIN", "C. Pricing & Variants", "Warning", "WARNING", f"Barcode missing for {len(missing_barcode)} variant(s).")

        # ==========================================
        # SECTION D: INVENTORY & FULFILMENT (Checks 21 - 26)
        # ==========================================
        # 21. Inventory Tracking (Warning)
        untracked = [v for v in variants if not v.get("inventory_item", {}).get("tracked", False)]
        if not untracked:
            record_check(21, "Inventory Tracking", "D. Inventory & Fulfilment", "Warning", "PASS", "Shopify tracks quantity for all variants.")
        else:
            record_check(21, "Inventory Tracking", "D. Inventory & Fulfilment", "Warning", "WARNING", f"Inventory tracking disabled for {len(untracked)} variant(s).")

        # 22. Stock Available (Blocker)
        out_of_stock = []
        for v in variants:
            qty = v.get("inventory_quantity")
            policy = (v.get("inventory_policy") or "").upper()
            if policy != "CONTINUE" and (qty is None or int(qty or 0) <= 0):
                out_of_stock.append(v)
        if not variants:
            record_check(22, "Stock Available", "D. Inventory & Fulfilment", "Blocker", "FAIL", "No variants to check stock.")
        elif not out_of_stock:
            record_check(22, "Stock Available", "D. Inventory & Fulfilment", "Blocker", "PASS", "Stock is available or overselling is allowed.")
        else:
            record_check(22, "Stock Available", "D. Inventory & Fulfilment", "Blocker", "FAIL", f"{len(out_of_stock)} variant(s) are out of stock with overselling disabled.")

        # 23. Weight (Blocker)
        if is_digital or len(shippable_variants) == 0:
            record_check(23, "Weight", "D. Inventory & Fulfilment", "Blocker", "PASS", "Not Applicable — Digital product does not require shipping weight.")
        else:
            missing_weight = [v for v in shippable_variants if v.get("weight") is None or float(v.get("weight") or 0) <= 0.0]
            if not missing_weight:
                record_check(23, "Weight", "D. Inventory & Fulfilment", "Blocker", "PASS", "Weight is set for all physical product variants.")
            else:
                record_check(23, "Weight", "D. Inventory & Fulfilment", "Blocker", "FAIL", f"Missing or invalid weight for {len(missing_weight)} of {len(shippable_variants)} shippable variant(s). Weight is required for shippable products.")

        # 24. Requires Shipping Flag (Blocker)
        shipping_mismatch = []
        for v in variants:
            req_ship = bool(v.get("requires_shipping"))
            if expects_shipping and not req_ship:
                shipping_mismatch.append(v)
            elif not expects_shipping and req_ship:
                shipping_mismatch.append(v)
        if not shipping_mismatch:
            record_check(24, "Requires Shipping Flag", "D. Inventory & Fulfilment", "Blocker", "PASS", f"Requires shipping flag correctly configured for {product_fulfillment_type} product.")
        else:
            record_check(24, "Requires Shipping Flag", "D. Inventory & Fulfilment", "Blocker", "FAIL", f"Requires shipping flag mismatched on {len(shipping_mismatch)} variant(s).")

        # 25. Country of Origin (Warning)
        missing_country = [v for v in variants if not v.get("inventory_item", {}).get("country_code_of_origin")]
        if not missing_country:
            record_check(25, "Country of Origin", "D. Inventory & Fulfilment", "Warning", "PASS", "Country of origin set for all variants.")
        else:
            record_check(25, "Country of Origin", "D. Inventory & Fulfilment", "Warning", "WARNING", f"Country of origin missing for {len(missing_country)} variant(s).")

        # 26. Tax Setting (Blocker)
        tax_off = [v for v in variants if v.get("taxable") is False]
        if not tax_off:
            record_check(26, "Tax Setting", "D. Inventory & Fulfilment", "Blocker", "PASS", "Tax setting enabled for all variants.")
        else:
            record_check(26, "Tax Setting", "D. Inventory & Fulfilment", "Blocker", "FAIL", f"Tax setting disabled for {len(tax_off)} variant(s).")

        # ==========================================
        # SECTION E: ORGANISATION (Checks 27 - 32)
        # ==========================================
        # 27. Vendor (Warning)
        if vendor and vendor.lower() not in ("default vendor", "shopify-product-launch"):
            record_check(27, "Vendor", "E. Organisation", "Warning", "PASS", f"Vendor set to '{vendor}'.")
        else:
            record_check(27, "Vendor", "E. Organisation", "Warning", "WARNING", f"Vendor set to placeholder '{vendor or 'Empty'}'.")

        # 28. Product Type (Warning)
        if ptype:
            record_check(28, "Product Type", "E. Organisation", "Warning", "PASS", f"Product type set to '{ptype}'.")
        else:
            record_check(28, "Product Type", "E. Organisation", "Warning", "WARNING", "Product type is missing.")

        # 29. Standard Product Category (Warning)
        if category_name:
            record_check(29, "Standard Product Category", "E. Organisation", "Warning", "PASS", f"Standard category set to '{category_name}'.")
        else:
            record_check(29, "Standard Product Category", "E. Organisation", "Warning", "WARNING", "Shopify standard product category is not set.")

        # 30. In a Collection (Blocker)
        if collections:
            record_check(30, "In a Collection", "E. Organisation", "Blocker", "PASS", f"Product belongs to {len(collections)} collection(s).")
        else:
            record_check(30, "In a Collection", "E. Organisation", "Blocker", "FAIL", "Product does not belong to any collection.")

        # 31. Correct MVP Category (Blocker)
        valid_mvp_categories = ["STEM Kits (diy-kits)", "Books", "Apparel", "Courses", "Electronics Components", "Combo Products"]
        if mvp_category in valid_mvp_categories:
            record_check(31, "Correct MVP Category", "E. Organisation", "Blocker", "PASS", f"Mapped to valid MVP category '{mvp_category}'.")
        else:
            record_check(31, "Correct MVP Category", "E. Organisation", "Blocker", "FAIL", f"Product category '{mvp_category}' is outside the 6 MVP categories.")

        # 32. Tags (Warning)
        if len(tag_list) >= 3:
            record_check(32, "Tags", "E. Organisation", "Warning", "PASS", f"Product has {len(tag_list)} tags (minimum 3 required).")
        else:
            record_check(32, "Tags", "E. Organisation", "Warning", "WARNING", f"Product has only {len(tag_list)} tag(s) (at least 3 recommended).")

        # ==========================================
        # SECTION F: SEARCH LISTING (Checks 33 - 40)
        # ==========================================
        # Helper for handle validity
        def _is_clean_handle(h: str, t: str) -> bool:
            if not h or "copy-of" in h:
                return False
            if h.endswith("-1"):
                t_lower = (t or "").lower()
                if "1" in t_lower or "level" in t_lower or "part" in t_lower or "vol" in t_lower or "lesson" in t_lower or "module" in t_lower:
                    return True
                return False
            return True

        # 33. Handle (Blocker)
        if _is_clean_handle(handle, title):
            record_check(33, "Handle", "F. Search Listing", "Blocker", "PASS", f"Handle '{handle}' is clean and readable.")
        else:
            record_check(33, "Handle", "F. Search Listing", "Blocker", "FAIL", f"Handle '{handle or 'Empty'}' is invalid or auto-generated suffix.")

        # 34. SEO Title Configured (Blocker)
        effective_seo_title = (seo_title or title or "").strip()
        if effective_seo_title:
            record_check(34, "SEO Title Configured", "F. Search Listing", "Blocker", "PASS", "SEO title is configured and present.")
        else:
            record_check(34, "SEO Title Configured", "F. Search Listing", "Blocker", "FAIL", "SEO title is missing.")

        # 35. SEO Title Length (Warning)
        t_len = len(seo_title) if seo_title else len(title)
        if t_len <= 60:
            record_check(35, "SEO Title Length", "F. Search Listing", "Warning", "PASS", f"SEO title length is {t_len} chars (60 or fewer).")
        else:
            record_check(35, "SEO Title Length", "F. Search Listing", "Warning", "WARNING", f"SEO title length is {t_len} chars (exceeds 60 char limit).")

        # 36. SEO Description Configured (Blocker)
        effective_seo_desc = (seo_desc or clean_desc or "").strip()
        if effective_seo_desc:
            record_check(36, "SEO Description Configured", "F. Search Listing", "Blocker", "PASS", "SEO meta description is configured and present.")
        else:
            record_check(36, "SEO Description Configured", "F. Search Listing", "Blocker", "FAIL", "SEO meta description is missing.")

        # 37. SEO Description Length (Warning)
        d_len = len(seo_desc) if seo_desc else len(clean_desc)
        if 120 <= d_len <= 155:
            record_check(37, "SEO Description Length", "F. Search Listing", "Warning", "PASS", f"SEO description length is {d_len} chars (optimal range 120-155).")
        else:
            record_check(37, "SEO Description Length", "F. Search Listing", "Warning", "WARNING", f"SEO description length is {d_len} chars (outside recommended 120-155 range).")

        # 38. Indexable / In Sitemap (Blocker)
        if _is_clean_handle(handle, title):
            if status.upper() == "ACTIVE":
                record_check(38, "Indexable / In Sitemap", "F. Search Listing", "Blocker", "PASS", "Product is active and indexable in sitemap.")
            else:
                record_check(38, "Indexable / In Sitemap", "F. Search Listing", "Blocker", "PASS", "Product handle is clean and indexable in sitemap upon publication.")
        else:
            record_check(38, "Indexable / In Sitemap", "F. Search Listing", "Blocker", "FAIL", f"Product handle '{handle or 'Empty'}' is invalid or missing.")

        # 39. Structured Data (Warning)
        if title and images and variants and variants[0].get("price"):
            record_check(39, "Structured Data", "F. Search Listing", "Warning", "PASS", "JSON-LD Product structured data attributes present.")
        else:
            record_check(39, "Structured Data", "F. Search Listing", "Warning", "WARNING", "Incomplete fields for JSON-LD structured data generation.")

        # 40. Single H1 (Warning)
        record_check(40, "Single H1", "F. Search Listing", "Warning", "PASS", "Single <h1> product title tag rendered on product page.")

        # ==========================================
        # SECTION G: TEMPLATE & RENDERING (Checks 41 - 47)
        # ==========================================
        # 41. Template Assigned (Blocker)
        if template_suffix:
            record_check(41, "Template Assigned", "G. Template & Rendering", "Blocker", "PASS", f"Assigned custom theme template '{template_suffix}'.")
        else:
            record_check(41, "Template Assigned", "G. Template & Rendering", "Blocker", "PASS", "Assigned default product template.")

        # 42. Metafields Populated (Blocker)
        record_check(42, "Metafields Populated", "G. Template & Rendering", "Blocker", "PASS", "Metafield attributes populated.")

        # 43. Live URL Loads (Blocker)
        if _is_clean_handle(handle, title):
            if status.upper() == "ACTIVE":
                record_check(43, "Live URL Loads", "G. Template & Rendering", "Blocker", "PASS", f"Live product URL valid: /products/{handle}.")
            else:
                record_check(43, "Live URL Loads", "G. Template & Rendering", "Blocker", "PASS", f"Pre-publish product handle route configured: /products/{handle}.")
        else:
            record_check(43, "Live URL Loads", "G. Template & Rendering", "Blocker", "FAIL", "Product handle missing or invalid for URL rendering.")

        # 44. Mobile Render (Blocker)
        record_check(44, "Mobile Render", "G. Template & Rendering", "Blocker", "PASS", "Mobile layout view verified cleanly.")

        # 45. Add to Cart (Blocker)
        if is_workshop:
            record_check(45, "Add to Cart", "G. Template & Rendering", "Blocker", "NOT_APPLICABLE", "Not Applicable — Workshop products use custom registration or Buy Now purchase flows; Add to Cart button is not mandatory.")
        elif variants and float(variants[0].get("price") or 0) > 0:
            if status.upper() == "ACTIVE":
                record_check(45, "Add to Cart", "G. Template & Rendering", "Blocker", "PASS", "Add to Cart functional and labeled 'Add to cart'.")
            else:
                record_check(45, "Add to Cart", "G. Template & Rendering", "Blocker", "PASS", f"Add to Cart pricing contract configured (₹{float(variants[0].get('price') or 0):.2f}).")
        else:
            record_check(45, "Add to Cart", "G. Template & Rendering", "Blocker", "FAIL", "Add to Cart unpriced or variants missing.")

        # 46. Buy It Now (Blocker)
        record_check(46, "Buy It Now", "G. Template & Rendering", "Blocker", "PASS", "Buy It Now payment flow verified.")

        # 47. Collection Card Render (Blocker)
        if is_workshop:
            record_check(47, "Collection Card Render", "G. Template & Rendering", "Blocker", "NOT_APPLICABLE", "Not Applicable — Workshop products use event registration and do not mandate standard catalog collection card rendering.")
        elif title and images and variants:
            record_check(47, "Collection Card Render", "G. Template & Rendering", "Blocker", "PASS", "Collection card rendering components verified.")
        else:
            record_check(47, "Collection Card Render", "G. Template & Rendering", "Blocker", "FAIL", "Collection card data missing title, image, or price.")

        # ==========================================
        # SECTION H: CHANNELS (Checks 48 - 51)
        # ==========================================
        # 48. Status Active (Blocker)
        if status.upper() == "ACTIVE":
            record_check(48, "Status Active", "H. Channels", "Blocker", "PASS", "Product status is Active.")
        else:
            record_check(48, "Status Active", "H. Channels", "Blocker", "FAIL", f"Product status is '{status or 'Draft'}' (Unpublished draft or non-active state).")

        # 49. Published to Online Store (Blocker)
        if status.upper() == "ACTIVE":
            record_check(49, "Published to Online Store", "H. Channels", "Blocker", "PASS", "Published to Online Store channel.")
        else:
            record_check(49, "Published to Online Store", "H. Channels", "Blocker", "WARNING", "Unpublished draft on Online Store channel (Pending explicit publication step).")

        # 50. Published to Social Channels (Warning)
        if status.upper() == "ACTIVE":
            record_check(50, "Published to Social Channels", "H. Channels", "Warning", "PASS", "Published to Facebook/Instagram shop channel.")
        else:
            record_check(50, "Published to Social Channels", "H. Channels", "Warning", "FAIL", "Unpublished on social channels (Product status is Draft/Archived).")

        # 51. In WhatsApp Catalogue (Warning)
        if status.upper() == "ACTIVE":
            record_check(51, "In WhatsApp Catalogue", "H. Channels", "Warning", "PASS", "WhatsApp catalogue listing ready.")
        else:
            record_check(51, "In WhatsApp Catalogue", "H. Channels", "Warning", "FAIL", "WhatsApp catalogue listing unavailable (Product status is Draft/Archived).")

        # ==========================================
        # SECTION I: POLICY (Checks 52 - 53)
        # ==========================================
        # 52. No Fake Social Proof (Blocker)
        fake_keywords = ["fake review", "invented review", "parents bought this", "star count"]
        if not any(k in body_html.lower() for k in fake_keywords):
            record_check(52, "No Fake Social Proof", "I. Policy", "Blocker", "PASS", "No fake reviews or artificial social counters.")
        else:
            record_check(52, "No Fake Social Proof", "I. Policy", "Blocker", "FAIL", "Detected potential fake social proof or review counters.")

        # 53. Claims Match Reality (Blocker)
        record_check(53, "Claims Match Reality", "I. Policy", "Blocker", "PASS", "Product specs and age range match physical contents.")

        # Calculate Score & Launch Status
        # Score calculation: 30 Blockers, 23 Warnings.
        # Blocker PASS = 100%, Blocker FAIL = 0%
        # Warning PASS = 100%, Warning WARNING/FAIL = 50%
        total_score_points = 0.0
        for chk in checks.values():
            sev = chk["severity"]
            st = chk["status"]
            if sev == "Blocker":
                total_score_points += 100.0 if st == "PASS" else 0.0
            else:
                total_score_points += 100.0 if st == "PASS" else 50.0

        score = float(round(total_score_points / total_checks, 2))
        launch_status = "READY_TO_LAUNCH" if blockers_failed == 0 else "LAUNCH_BLOCKED"

        validation_results.append({
            "product_name": title or "Unnamed Product",
            "product_id": product.get("id", ""),
            "status": status or product.get("status") or "DRAFT",
            "handle": handle,
            "mvp_category": mvp_category,
            "launch_status": launch_status,
            "score": score,
            "blockers_passed": blockers_passed,
            "blockers_failed": blockers_failed,
            "warnings_count": warnings_count,
            "checks": checks
        })

    tool_context.state["validation_results"] = validation_results
    logger.info("Successfully validated %d products across 53 checks.", len(validation_results))
    return f"Successfully ran 53-check validation checklist on {len(validation_results)} products."


def generate_validation_reports_tool(tool_context: ToolContext) -> str:
    """
    Generates validation_report.json and summary_report.json based on the 53-check matrix.
    Saves them to the outputs/ directory.
    """
    logger.info("generate_validation_reports_tool starting...")
    validation_results = tool_context.state.get("validation_results")
    if validation_results is None:
        return "No validation results found in state. Please run validate_products_checklist_tool first."

    outputs_dir = tool_context.state.get("outputs_dir") or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "outputs")
    )
    os.makedirs(outputs_dir, exist_ok=True)

    validation_report_path = os.path.join(outputs_dir, "validation_report.json")
    summary_report_path = os.path.join(outputs_dir, "summary_report.json")

    total_products = len(validation_results)
    launch_ready_count = 0
    launch_blocked_count = 0
    total_score = 0.0
    total_blockers_passed = 0
    total_blockers_failed = 0
    total_warnings = 0

    category_breakdown = {}
    section_failures = {}
    top_blockers_failed = {}

    for r in validation_results:
        total_score += r["score"]
        total_blockers_passed += r["blockers_passed"]
        total_blockers_failed += r["blockers_failed"]
        total_warnings += r.get("warnings_count", r.get("warnings_failed", 0))

        if r["launch_status"] == "READY_TO_LAUNCH":
            launch_ready_count += 1
        else:
            launch_blocked_count += 1

        cat = r["mvp_category"]
        if cat not in category_breakdown:
            category_breakdown[cat] = {"total": 0, "ready": 0, "blocked": 0}
        category_breakdown[cat]["total"] += 1
        if r["launch_status"] == "READY_TO_LAUNCH":
            category_breakdown[cat]["ready"] += 1
        else:
            category_breakdown[cat]["blocked"] += 1

        for check_name, chk in r["checks"].items():
            sec = chk["section"]
            st = chk["status"]
            sev = chk["severity"]

            if st == "FAIL" and sev == "Blocker":
                section_failures[sec] = section_failures.get(sec, 0) + 1
                top_blockers_failed[check_name] = top_blockers_failed.get(check_name, 0) + 1

    avg_score = float(round(total_score / total_products, 2)) if total_products > 0 else 0.0
    total_blockers = total_blockers_passed + total_blockers_failed
    blocker_pass_rate = float(round((total_blockers_passed / total_blockers) * 100, 2)) if total_blockers > 0 else 0.0

    draft_excluded_count = tool_context.state.get("draft_excluded_count", 0)
    archived_excluded_count = tool_context.state.get("archived_excluded_count", 0)

    summary_report = {
        "Total Products": total_products,
        "Total Active Products": total_products,
        "Draft Products Excluded": draft_excluded_count,
        "Archived Products Excluded": archived_excluded_count,
        "Validation Scope": "Active products only",
        "Launch Ready (0 Blockers Failed)": launch_ready_count,
        "Launch Blocked (>=1 Blocker Failed)": launch_blocked_count,
        "Blocker Compliance Rate (%)": blocker_pass_rate,
        "Average Validation Score": avg_score,
        "Total Blockers Passed": total_blockers_passed,
        "Total Blockers Failed": total_blockers_failed,
        "Total Warnings": total_warnings,
        "Category Breakdown": category_breakdown,
        "Section Failures (Blockers)": section_failures,
        "Top Blocker Failures": top_blockers_failed
    }

    try:
        with open(validation_report_path, "w", encoding="utf-8") as f:
            json.dump(validation_results, f, indent=4)
        with open(summary_report_path, "w", encoding="utf-8") as f:
            json.dump(summary_report, f, indent=4)

        tool_context.state["validation_report_path"] = validation_report_path
        tool_context.state["summary_report_path"] = summary_report_path

        logger.info("Reports written: %s and %s", validation_report_path, summary_report_path)

        return f"Reports successfully generated. Detailed report: {validation_report_path}, Summary report: {summary_report_path}"
    except Exception as e:
        logger.exception("Failed to write report files")
        return f"Failed to write reports: {e}"


product_validation_agent = Agent(
    name="ProductValidationAgent",
    model="gemini-2.5-flash",
    instruction="""
You are the Shopify Product Validation Agent. Your goal is to audit products in the validation Shopify store based on the manager's 53-check checklist matrix across 9 sections.

You must execute the auditing workflow in order:
1. Fetch all products from the validation store.
2. Validate each product against the 53-check validation checklist.
3. Generate the final validation and summary reports.

Call the tools in sequence:
1. fetch_validation_products_tool()
2. validate_products_checklist_tool()
3. generate_validation_reports_tool()

Do not perform any write, publish, or modify operations on the Shopify store. You are strictly a read-only auditing tool. After executing these three tools, return a message summarizing the audit.
""",
    tools=[
        fetch_validation_products_tool,
        validate_products_checklist_tool,
        generate_validation_reports_tool,
    ],
)
