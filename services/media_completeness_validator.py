"""
Media Completeness Validation Skill for KiddyPi Shopify Store.

This module implements the `MediaCompletenessValidationSkill` class — a reusable,
read-only storewide audit skill that inspects Shopify product media, checks quantity,
dimensions, and formats against collection profiles, and generates downloadable
Excel (.xlsx), CSV (.csv), PDF (.pdf), and Markdown (.md) reports.
"""

import os
import re
import csv
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from shopify_client import ShopifyClient, ShopifyAPIError, get_product
from config import settings

logger = logging.getLogger("media_completeness_validator")

# ============================================================================
# CENTRALIZED MEDIA REQUIREMENTS CONFIGURATION (SOURCE OF TRUTH)
# ============================================================================

MEDIA_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "stem_kits": {
        "profile_name": "STEM Kits",
        "description": "Required minimum media for STEM Kits",
        "requirements": [
            {
                "key": "hero",
                "name": "Hero / Featured Image",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["hero", "featured", "front", "main", "primary", "cover"],
                "position_fallback": 1,
                "required": True,
            },
            {
                "key": "packaging",
                "name": "Kit Box / Packaging",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["box", "packaging", "package", "box-shot", "unboxing"],
                "position_fallback": None,
                "required": True,
            },
            {
                "key": "contents",
                "name": "Contents Laid Out",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["contents", "components", "parts", "laid-out", "flatlay", "kit-contents"],
                "position_fallback": None,
                "required": True,
            },
            {
                "key": "completed_project",
                "name": "Completed Project",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["completed", "working-project", "assembled", "built", "final", "project-action", "demo"],
                "position_fallback": None,
                "required": True,
            },
        ],
    },
    "courses": {
        "profile_name": "Courses",
        "description": "Required minimum media for Online/Offline Courses",
        "requirements": [
            {
                "key": "course_hero",
                "name": "Course Cover / Hero",
                "quantity": 1,
                "width": 1200,
                "height": 800,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["cover", "hero", "banner", "thumbnail", "course-cover", "main"],
                "position_fallback": 1,
                "required": True,
            }
        ],
    },
    "books": {
        "profile_name": "Books",
        "description": "Required media for Books and Book Bundles",
        "requirements": [
            {
                "key": "front_cover",
                "name": "Book Front Cover",
                "quantity": 1,
                "width": 800,
                "height": 1200,
                "orientation": "portrait",
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["front", "front-cover", "cover", "main"],
                "position_fallback": 1,
                "required": True,
            },
            {
                "key": "back_cover",
                "name": "Back Cover",
                "quantity": 1,
                "width": 800,
                "height": 1200,
                "orientation": "portrait",
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["back", "back-cover", "rear"],
                "position_fallback": None,
                "required": True,
            },
            {
                "key": "sample_interior",
                "name": "Sample Interior Pages",
                "quantity": 2,
                "width": 1200,
                "height": 900,
                "orientation": "landscape",
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["interior", "sample", "page", "preview", "inside", "spread"],
                "position_fallback": None,
                "required": True,
            },
            {
                "key": "spine",
                "name": "Book Spine",
                "quantity": 1,
                "width": 200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["spine", "side-view", "side"],
                "position_fallback": None,
                "required": True,
            },
            {
                "key": "bundle_shot",
                "name": "Bundle / Series Shot",
                "quantity": 1,
                "width": 1200,
                "height": 900,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["bundle", "series", "combo", "collection", "set"],
                "position_fallback": None,
                "required": False,  # Conditionally required for combos/bundles
            },
        ],
    },
    "apparels": {
        "profile_name": "Apparel / T-Shirts",
        "description": "Required minimum media for Apparel products",
        "requirements": [
            {
                "key": "front_flat_lay",
                "name": "Front Flat Lay",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["front-flat", "flatlay-front", "front-flat-lay", "front-flatlay"],
                "position_fallback": 1,
                "required": True,
            },
            {
                "key": "back_flat_lay",
                "name": "Back Flat Lay",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["back-flat", "flatlay-back", "back-flat-lay", "back-flatlay"],
                "position_fallback": None,
                "required": True,
            },
            {
                "key": "front_on_model",
                "name": "Front On Model",
                "quantity": 1,
                "width": 1200,
                "height": 1500,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["front-model", "model-front", "on-model-front"],
                "position_fallback": None,
                "required": True,
            },
            {
                "key": "back_on_model",
                "name": "Back On Model",
                "quantity": 1,
                "width": 1200,
                "height": 1500,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["back-model", "model-back", "on-model-back"],
                "position_fallback": None,
                "required": True,
            },
        ],
    },
    "electronics": {
        "profile_name": "Electronics",
        "description": "Required minimum media for Electronic components/boards",
        "requirements": [
            {
                "key": "top_down",
                "name": "Product Top-Down View",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["top", "top-down", "flat", "overhead"],
                "position_fallback": 1,
                "required": True,
            },
            {
                "key": "angle_45",
                "name": "Product 45° Angle View",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["45", "angle", "perspective", "iso", "isometric", "side-angle"],
                "position_fallback": None,
                "required": True,
            },
            {
                "key": "back_additional_view",
                "name": "Back / Additional Product View",
                "quantity": 1,
                "width": 1200,
                "height": 1200,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["back", "rear", "bottom", "underside", "additional"],
                "position_fallback": None,
                "required": True,
            },
        ],
    },
    "workshops": {
        "profile_name": "Workshops",
        "description": "Required media for Educational Workshops",
        "requirements": [
            {
                "key": "workshop_hero",
                "name": "Workshop Hero / Banner",
                "quantity": 1,
                "width": 1920,
                "height": 600,
                "formats": ["jpg", "jpeg", "png"],
                "keywords": ["banner", "hero", "header", "workshop-hero", "cover"],
                "position_fallback": 1,
                "required": True,
            }
        ],
    },
}


# ============================================================================
# CLASSIFICATION & MATCHING HELPERS
# ============================================================================

def classify_product(product: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """
    Classifies a Shopify product into a requirement profile key.
    Order: Collections -> Product Type -> Tags -> Title keywords.
    """
    if not isinstance(product, dict):
        return None, "Unclassified"

    title = str(product.get("title") or "").strip().lower()
    product_type = str(product.get("product_type") or "").strip().lower()
    raw_tags = product.get("tags") or ""
    tags_str = " ".join(raw_tags).lower() if isinstance(raw_tags, list) else str(raw_tags).lower()

    collections = product.get("collections") or []
    coll_titles = []
    for c in collections:
        if isinstance(c, dict):
            coll_titles.append(str(c.get("title") or "").strip().lower())
        elif isinstance(c, str):
            coll_titles.append(c.strip().lower())

    text = f"{product_type} {' '.join(coll_titles)} {tags_str} {title}"

    if any(k in text for k in ["stem kit", "stem kits", "kit", "kits", "diy kit", "robotics kit", "starter kit"]):
        return "stem_kits", "STEM Kits"
    if any(k in text for k in ["course", "courses", "masterclass", "bootcamp", "training"]):
        return "courses", "Courses"
    if any(k in text for k in ["book", "books", "workbook", "workbooks", "guide", "manual"]):
        return "books", "Books"
    if any(k in text for k in ["apparel", "t-shirt", "tshirt", "t shirt", "hoodie", "wear"]):
        return "apparels", "Apparel / T-Shirts"
    if any(k in text for k in ["electronics", "electronic", "sensor", "module", "board", "motor", "microcontroller"]):
        return "electronics", "Electronics"
    if any(k in text for k in ["workshop", "workshops", "seminar", "event"]):
        return "workshops", "Workshops"

    return None, "Unclassified"


def is_combo_or_bundle_book(product: Dict[str, Any]) -> bool:
    """Checks if a book product is a bundle or series combo."""
    text = f"{product.get('title', '')} {product.get('tags', '')} {product.get('product_type', '')}".lower()
    return any(k in text for k in ["bundle", "combo", "series", "pack", "set", "collection"])


def extract_image_format(image_dict: Dict[str, Any]) -> Optional[str]:
    """Extracts format (extension) from image dictionary."""
    src = str(image_dict.get("url") or image_dict.get("src") or "").split("?")[0].lower()
    if src.endswith(".png"):
        return "png"
    if src.endswith(".jpg") or src.endswith(".jpeg"):
        return "jpg"
    if src.endswith(".webp"):
        return "webp"
    if src.endswith(".gif"):
        return "gif"
    return None


def extract_image_dimensions(image_dict: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    """Extracts width and height integers from image dictionary."""
    w, h = image_dict.get("width"), image_dict.get("height")
    try:
        w_val = int(w) if w is not None else None
    except Exception:
        w_val = None
    try:
        h_val = int(h) if h is not None else None
    except Exception:
        h_val = None
    return w_val, h_val


# ============================================================================
# MAIN REUSABLE SKILL CLASS
# ============================================================================

class MediaCompletenessValidationSkill:
    """
    Read-only Storewide Media Completeness Validation Skill for KiddyPi Shopify store.
    """

    def __init__(self, store_url: Optional[str] = None, access_token: Optional[str] = None):
        self.store_url = store_url or settings.shopify_validation_store or settings.shopify_store_url or "validation-store.myshopify.com"
        self.access_token = access_token or settings.shopify_validation_token or settings.shopify_access_token or "shpat_placeholder"

    def match_images_to_requirements(
        self, product: Dict[str, Any], profile_key: str
    ) -> Dict[str, Any]:
        """
        Matches product images against profile requirements.
        Enforces role matching, quantity, dimensions, and formats.
        """
        profile_data = MEDIA_REQUIREMENTS[profile_key]
        req_list = profile_data["requirements"]
        existing_images = product.get("images") or []
        
        is_book_bundle = False
        if profile_key == "books":
            is_book_bundle = is_combo_or_bundle_book(product)

        active_requirements = []
        for r in req_list:
            if r["key"] == "bundle_shot":
                if is_book_bundle:
                    r_copy = dict(r)
                    r_copy["required"] = True
                    active_requirements.append(r_copy)
            else:
                active_requirements.append(r)

        matched_per_req: Dict[str, List[Tuple[Dict[str, Any], int]]] = {r["key"]: [] for r in active_requirements}
        used_image_ids = set()

        # Pass 1: Match by Keyword in Alt Text or Filename across all requirements
        for req in active_requirements:
            req_key = req["key"]
            req_qty = req["quantity"]
            keywords = req.get("keywords", [])

            for idx, img in enumerate(existing_images):
                img_id = img.get("id") if img.get("id") is not None else f"idx_{idx}"
                if img_id in used_image_ids:
                    continue

                alt = str(img.get("alt") or "").strip().lower()
                src = str(img.get("url") or img.get("src") or "").split("?")[0].lower()
                filename = os.path.basename(src).lower()
                combined = f"{alt} {filename}"

                if any(kw in combined for kw in keywords):
                    matched_per_req[req_key].append((img, idx))
                    used_image_ids.add(img_id)
                    if len(matched_per_req[req_key]) == req_qty:
                        break

        # Pass 2: Match by Position Fallback if requirement is still unsatisfied
        for req in active_requirements:
            req_key = req["key"]
            req_qty = req["quantity"]
            pos_fallback = req.get("position_fallback")

            if not matched_per_req[req_key] and pos_fallback is not None:
                fallback_idx = pos_fallback - 1
                if 0 <= fallback_idx < len(existing_images):
                    img = existing_images[fallback_idx]
                    img_id = img.get("id") if img.get("id") is not None else f"idx_{fallback_idx}"
                    if img_id not in used_image_ids:
                        matched_per_req[req_key].append((img, fallback_idx))
                        used_image_ids.add(img_id)

        # Build Evaluation Checklist
        checklist = []
        total_required_roles = len(active_requirements)
        valid_roles_count = 0
        missing_roles_count = 0
        invalid_roles_count = 0

        for req in active_requirements:
            req_key = req["key"]
            req_name = req["name"]
            req_qty = req["quantity"]
            target_w = req["width"]
            target_h = req["height"]
            target_formats = req.get("formats", ["jpg", "jpeg", "png"])

            matched_images = matched_per_req[req_key]

            if not matched_images:
                missing_roles_count += 1
                checklist.append({
                    "key": req_key,
                    "name": req_name,
                    "required_quantity": req_qty,
                    "found_quantity": 0,
                    "status": "MISSING",
                    "required_dimensions": f"{target_w} × {target_h}",
                    "actual_dimensions": "None",
                    "format_status": "N/A",
                    "matched_file": None,
                    "action": f"Add {req_qty} × {target_w}×{target_h} image for '{req_name}'."
                })
            elif len(matched_images) < req_qty:
                missing_qty = req_qty - len(matched_images)
                missing_roles_count += 1
                first_img = matched_images[0][0]
                w, h = extract_image_dimensions(first_img)
                matched_filenames = [os.path.basename(str(m[0].get("url") or m[0].get("src") or "")).split("?")[0] for m in matched_images]

                checklist.append({
                    "key": req_key,
                    "name": req_name,
                    "required_quantity": req_qty,
                    "found_quantity": len(matched_images),
                    "status": "INCOMPLETE_QUANTITY",
                    "required_dimensions": f"{target_w} × {target_h}",
                    "actual_dimensions": f"{w} × {h}" if w and h else "Unknown",
                    "format_status": "PASS",
                    "matched_file": ", ".join(matched_filenames),
                    "action": f"Add {missing_qty} additional image for '{req_name}' ({req_qty} required, found {len(matched_images)})."
                })
            else:
                role_invalid = False
                first_img, first_idx = matched_images[0]
                w, h = extract_image_dimensions(first_img)
                fmt = extract_image_format(first_img)

                dim_status = "PASS"
                if w is None or h is None:
                    dim_status = "FORMAT_UNVERIFIED"
                elif w != target_w or h != target_h:
                    dim_status = "INVALID_DIMENSIONS"
                    role_invalid = True

                fmt_status = "PASS"
                if fmt is None:
                    fmt_status = "FORMAT_UNVERIFIED"
                elif fmt not in target_formats:
                    fmt_status = "INVALID_FORMAT"

                matched_filenames = [os.path.basename(str(m[0].get("url") or m[0].get("src") or "")).split("?")[0] for m in matched_images]

                if role_invalid:
                    invalid_roles_count += 1
                    checklist.append({
                        "key": req_key,
                        "name": req_name,
                        "required_quantity": req_qty,
                        "found_quantity": len(matched_images),
                        "status": "INVALID_DIMENSIONS",
                        "required_dimensions": f"{target_w} × {target_h}",
                        "actual_dimensions": f"{w} × {h}" if w and h else "Unknown",
                        "format_status": fmt_status,
                        "matched_file": ", ".join(matched_filenames),
                        "action": f"Replace {req_name} with a {target_w}×{target_h} image (Actual: {w}×{h})."
                    })
                else:
                    valid_roles_count += 1
                    checklist.append({
                        "key": req_key,
                        "name": req_name,
                        "required_quantity": req_qty,
                        "found_quantity": len(matched_images),
                        "status": "PASS",
                        "required_dimensions": f"{target_w} × {target_h}",
                        "actual_dimensions": f"{w} × {h}" if w and h else f"{target_w} × {target_h}",
                        "format_status": fmt_status,
                        "matched_file": ", ".join(matched_filenames),
                        "action": None
                    })

        overall = "COMPLETE" if (missing_roles_count == 0 and invalid_roles_count == 0) else "INCOMPLETE"

        return {
            "overall_status": overall,
            "total_required": total_required_roles,
            "valid_media": valid_roles_count,
            "missing_media": missing_roles_count,
            "invalid_media": invalid_roles_count,
            "checklist": checklist
        }

    def audit_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Audits a single product object and returns complete evaluation dict."""
        timestamp = datetime.now(timezone.utc).isoformat()
        product_id = product.get("id")
        product_title = product.get("title") or "Unknown Product"
        shopify_status = (product.get("status") or "").strip().upper() or "UNKNOWN"

        profile_key, profile_name = classify_product(product)

        if not profile_key:
            return {
                "timestamp": timestamp,
                "product_id": product_id,
                "product_title": product_title,
                "shopify_status": shopify_status,
                "product_type": product.get("product_type") or "N/A",
                "collections": [c.get("title") if isinstance(c, dict) else str(c) for c in (product.get("collections") or [])],
                "requirement_profile": "Unclassified",
                "overall_status": "UNCLASSIFIED",
                "summary": {"total_required": 0, "valid_media": 0, "missing_media": 0, "invalid_media": 0},
                "checklist": [],
                "missing_media_list": [],
                "invalid_media_list": [],
                "required_corrections": ["Classify product type or assign to a collection in Shopify before media audit."],
                "reason": "Collection / Product Type could not be determined confidently."
            }

        match_res = self.match_images_to_requirements(product, profile_key)

        missing_list = []
        invalid_list = []
        corrections = []

        for item in match_res["checklist"]:
            if item["status"] in ("MISSING", "INCOMPLETE_QUANTITY"):
                missing_list.append(f"{item['name']} ({item['required_quantity']} required)")
                corrections.append(item["action"])
            elif item["status"] == "INVALID_DIMENSIONS":
                invalid_list.append(f"{item['name']} (Actual: {item['actual_dimensions']}, Required: {item['required_dimensions']})")
                corrections.append(item["action"])

        return {
            "timestamp": timestamp,
            "product_id": product_id,
            "product_title": product_title,
            "shopify_status": shopify_status,
            "product_type": product.get("product_type") or "N/A",
            "collections": [c.get("title") if isinstance(c, dict) else str(c) for c in (product.get("collections") or [])],
            "requirement_profile": profile_name,
            "overall_status": match_res["overall_status"],
            "summary": {
                "total_required": match_res["total_required"],
                "valid_media": match_res["valid_media"],
                "missing_media": match_res["missing_media"],
                "invalid_media": match_res["invalid_media"],
            },
            "checklist": match_res["checklist"],
            "missing_media_list": missing_list,
            "invalid_media_list": invalid_list,
            "required_corrections": corrections
        }

    def audit_store(self, products: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Audits all products across the Shopify store in one single operation.
        Returns store-wide summary, category metrics, product list, and correction list.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        validation_error_count = 0

        if products is None:
            try:
                from shopify_client import get_validation_client
                client = get_validation_client()
                products = client.fetch_all_products()
            except Exception as exc:
                logger.error("Failed to retrieve products from Shopify: %s", exc)
                return {
                    "timestamp": timestamp,
                    "store_name": self.store_url,
                    "overall_status": "VALIDATION_ERROR",
                    "reason": f"Unable to retrieve Shopify media catalog: {exc}",
                    "store_summary": {"total_products": 0, "complete": 0, "incomplete": 0, "unclassified": 0, "validation_errors": 1},
                    "categories": {},
                    "products": [],
                    "action_required": []
                }

        raw_products = products or []
        total_fetched_products = len(raw_products)

        active_products = []
        draft_excluded_count = 0
        archived_excluded_count = 0
        other_excluded_count = 0

        for p in raw_products:
            st_raw = (p.get("status") or "").strip().upper()
            if st_raw == "ACTIVE":
                active_products.append(p)
            elif st_raw == "DRAFT":
                draft_excluded_count += 1
            elif st_raw == "ARCHIVED":
                archived_excluded_count += 1
            else:
                other_excluded_count += 1

        audited_products = []
        category_metrics: Dict[str, Dict[str, int]] = {}
        total_complete = 0
        total_incomplete = 0
        total_unclassified = 0
        action_required_list = []

        for p in active_products:
            res = self.audit_product(p)
            audited_products.append(res)
            
            st = res["overall_status"]
            cat = res["requirement_profile"]

            if cat not in category_metrics:
                category_metrics[cat] = {"total": 0, "complete": 0, "incomplete": 0, "unclassified": 0}

            category_metrics[cat]["total"] += 1

            if st == "COMPLETE":
                total_complete += 1
                category_metrics[cat]["complete"] += 1
            elif st == "UNCLASSIFIED":
                total_unclassified += 1
                category_metrics[cat]["unclassified"] += 1
            elif st == "VALIDATION_ERROR":
                validation_error_count += 1
            else:
                total_incomplete += 1
                category_metrics[cat]["incomplete"] += 1

            if st != "COMPLETE" and res["required_corrections"]:
                action_required_list.append({
                    "product_id": res["product_id"],
                    "product_title": res["product_title"],
                    "shopify_status": res["shopify_status"],
                    "profile": res["requirement_profile"],
                    "status": st,
                    "missing_media": res["missing_media_list"],
                    "invalid_media": res["invalid_media_list"],
                    "corrections": res["required_corrections"]
                })

        return {
            "timestamp": timestamp,
            "store_name": self.store_url,
            "scope": "ACTIVE_ONLY",
            "store_summary": {
                "total_fetched_products": total_fetched_products,
                "active_products_audited": len(active_products),
                "draft_products_excluded": draft_excluded_count,
                "archived_products_excluded": archived_excluded_count,
                "other_products_excluded": other_excluded_count,
                "total_products": len(active_products),
                "complete": total_complete,
                "incomplete": total_incomplete,
                "unclassified": total_unclassified,
                "validation_errors": validation_error_count,
            },
            "categories": category_metrics,
            "products": audited_products,
            "action_required": action_required_list
        }

    # =========================================================================
    # REPORT GENERATION METHOD (.xlsx, .csv, .pdf, .md)
    # =========================================================================

    def generate_reports(self, audit_result: Dict[str, Any], output_dir: str = "outputs") -> Dict[str, str]:
        """
        Generates 4 downloadable report formats:
        1. Excel (.xlsx) with 5 structured sheets
        2. CSV (.csv) product-level summary
        3. PDF (.pdf) executive report
        4. Markdown (.md) audit report
        """
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs("docs/audits", exist_ok=True)
        
        ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_path = os.path.abspath(os.path.join(output_dir, f"media_completeness_audit_{ts_slug}.xlsx"))
        csv_path = os.path.abspath(os.path.join(output_dir, f"media_completeness_audit_{ts_slug}.csv"))
        pdf_path = os.path.abspath(os.path.join(output_dir, f"media_completeness_audit_{ts_slug}.pdf"))
        md_path = os.path.abspath("docs/audits/media-completeness-report.md")

        # 1. EXCEL REPORT (5 SHEETS)
        self._export_excel_report(audit_result, excel_path)

        # 2. CSV REPORT
        self._export_csv_report(audit_result, csv_path)

        # 3. PDF REPORT
        self._export_pdf_report(audit_result, pdf_path)

        # 4. MARKDOWN REPORT
        self._export_markdown_report(audit_result, md_path)

        return {
            "excel_path": excel_path,
            "csv_path": csv_path,
            "pdf_path": pdf_path,
            "markdown_path": md_path,
        }

    # -------------------------------------------------------------------------
    # EXCEL GENERATOR (_export_excel_report)
    # -------------------------------------------------------------------------
    def _export_excel_report(self, data: Dict[str, Any], file_path: str):
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # remove default sheet

        # Styles
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=16, bold=True, color="1E293B")
        sub_font = Font(name="Calibri", size=11, italic=True, color="64748B")
        bold_font = Font(name="Calibri", size=11, bold=True)
        
        green_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        red_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        yellow_fill = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")

        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        # SHEET 1: SUMMARY
        ws1 = wb.create_sheet(title="Summary")
        ws1.append(["KiddyPi Shopify Store — Media Completeness Audit Summary"])
        ws1.append(["Validation Scope: ACTIVE PRODUCTS ONLY"])
        ws1.append([f"Generated At: {data.get('timestamp')}", f"Store: {data.get('store_name')}"])
        ws1.append([])
        
        ws1.append(["Store Catalog Scope Metrics", "Count"])
        summ = data.get("store_summary", {})
        ws1.append(["Total Shopify Products Found", summ.get("total_fetched_products", summ.get("total_products", 0))])
        ws1.append(["Active Products Audited", summ.get("active_products_audited", summ.get("total_products", 0))])
        ws1.append(["Draft Products Excluded", summ.get("draft_products_excluded", 0)])
        ws1.append(["Archived Products Excluded", summ.get("archived_products_excluded", 0)])
        ws1.append([])

        ws1.append(["Active Products Audit Metrics", "Count"])
        ws1.append(["COMPLETE Products", summ.get("complete", 0)])
        ws1.append(["INCOMPLETE Products", summ.get("incomplete", 0)])
        ws1.append(["UNCLASSIFIED Products", summ.get("unclassified", 0)])
        ws1.append(["Validation Errors", summ.get("validation_errors", 0)])
        ws1.append([])

        ws1.append(["Category Summary", "Total Products", "Complete", "Incomplete", "Unclassified"])
        for cat, metric in data.get("categories", {}).items():
            ws1.append([cat, metric["total"], metric["complete"], metric["incomplete"], metric["unclassified"]])

        # Format Sheet 1
        ws1.cell(row=1, column=1).font = title_font
        ws1.cell(row=2, column=1).font = sub_font

        # SHEET 2: PRODUCT AUDIT
        ws2 = wb.create_sheet(title="Product Audit")
        headers_ws2 = [
            "Product Name", "Product ID", "Shopify Status", "Product Type",
            "Requirement Profile", "Overall Status", "Required Count",
            "Valid Count", "Missing Count", "Invalid Count",
            "Missing Media", "Invalid Media", "Recommended Action"
        ]
        ws2.append(headers_ws2)
        for p in data.get("products", []):
            summ_p = p.get("summary", {})
            ws2.append([
                p.get("product_title"),
                p.get("product_id"),
                p.get("shopify_status"),
                p.get("product_type"),
                p.get("requirement_profile"),
                p.get("overall_status"),
                summ_p.get("total_required", 0),
                summ_p.get("valid_media", 0),
                summ_p.get("missing_media", 0),
                summ_p.get("invalid_media", 0),
                "; ".join(p.get("missing_media_list", [])),
                "; ".join(p.get("invalid_media_list", [])),
                "; ".join(p.get("required_corrections", []))
            ])

        # SHEET 3: MISSING & INVALID MEDIA
        ws3 = wb.create_sheet(title="Missing & Invalid Media")
        headers_ws3 = [
            "Product Name", "Product ID", "Shopify Status", "Requirement Profile",
            "Overall Status", "Missing Media Items", "Invalid Media Items", "Action Items"
        ]
        ws3.append(headers_ws3)
        for act in data.get("action_required", []):
            ws3.append([
                act.get("product_title"),
                act.get("product_id"),
                act.get("shopify_status"),
                act.get("profile"),
                act.get("status"),
                "; ".join(act.get("missing_media", [])),
                "; ".join(act.get("invalid_media", [])),
                "; ".join(act.get("corrections", []))
            ])

        # SHEET 4: MEDIA DETAIL
        ws4 = wb.create_sheet(title="Media Detail")
        headers_ws4 = [
            "Product Name", "Product ID", "Profile", "Media Name",
            "Required Qty", "Found Qty", "Required Dimensions",
            "Actual Dimensions", "Status", "Matched File", "Action Needed"
        ]
        ws4.append(headers_ws4)
        for p in data.get("products", []):
            for chk in p.get("checklist", []):
                ws4.append([
                    p.get("product_title"),
                    p.get("product_id"),
                    p.get("requirement_profile"),
                    chk.get("name"),
                    chk.get("required_quantity"),
                    chk.get("found_quantity"),
                    chk.get("required_dimensions"),
                    chk.get("actual_dimensions"),
                    chk.get("status"),
                    chk.get("matched_file") or "N/A",
                    chk.get("action") or "None"
                ])

        # SHEET 5: REQUIREMENT MATRIX
        ws5 = wb.create_sheet(title="Requirement Matrix")
        headers_ws5 = ["Profile Key", "Profile Name", "Media Key", "Media Name", "Required Qty", "Width", "Height", "Formats"]
        ws5.append(headers_ws5)
        for prof_key, prof in MEDIA_REQUIREMENTS.items():
            for req in prof["requirements"]:
                ws5.append([
                    prof_key,
                    prof["profile_name"],
                    req["key"],
                    req["name"],
                    req["quantity"],
                    req["width"],
                    req["height"],
                    ", ".join(req.get("formats", []))
                ])

        # Auto-fit columns and apply header styling across all sheets
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row, min_col=1, max_col=sheet.max_column):
                for cell in row:
                    cell.border = border_thin
            
            # Header styling for row 1 if headers exist
            if sheet.title in ["Product Audit", "Missing & Invalid Media", "Media Detail", "Requirement Matrix"]:
                for cell in sheet[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")

            for col in sheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

        wb.save(file_path)

    # -------------------------------------------------------------------------
    # CSV GENERATOR (_export_csv_report)
    # -------------------------------------------------------------------------
    def _export_csv_report(self, data: Dict[str, Any], file_path: str):
        headers = [
            "product_name", "product_id", "shopify_status", "product_type",
            "requirement_profile", "overall_status", "total_required",
            "valid_media", "missing_media_count", "invalid_media_count",
            "missing_media", "invalid_media", "required_actions"
        ]
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for p in data.get("products", []):
                summ = p.get("summary", {})
                writer.writerow([
                    p.get("product_title"),
                    p.get("product_id"),
                    p.get("shopify_status"),
                    p.get("product_type"),
                    p.get("requirement_profile"),
                    p.get("overall_status"),
                    summ.get("total_required", 0),
                    summ.get("valid_media", 0),
                    summ.get("missing_media", 0),
                    summ.get("invalid_media", 0),
                    "; ".join(p.get("missing_media_list", [])),
                    "; ".join(p.get("invalid_media_list", [])),
                    "; ".join(p.get("required_corrections", []))
                ])

    # -------------------------------------------------------------------------
    # PDF GENERATOR (_export_pdf_report)
    # -------------------------------------------------------------------------
    def _export_pdf_report(self, data: Dict[str, Any], file_path: str):
        doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#1E293B"))
        h2_style = ParagraphStyle("H2Style", parent=styles["Heading2"], fontSize=13, leading=16, textColor=colors.HexColor("#0F172A"))
        body_style = ParagraphStyle("BodyStyle", parent=styles["Normal"], fontSize=9, leading=12)

        elements = [
            Paragraph("KiddyPi Shopify Media Completeness Audit", title_style),
            Paragraph("<b>Validation Scope</b>: ACTIVE PRODUCTS ONLY", body_style),
            Paragraph(f"Generated At: {data.get('timestamp')} | Store: {data.get('store_name')}", body_style),
            Spacer(1, 10),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1")),
            Spacer(1, 10),
            Paragraph("Executive Store Summary", h2_style),
        ]

        summ = data.get("store_summary", {})
        summary_table_data = [
            ["Metric", "Value"],
            ["Total Shopify Products Found", str(summ.get("total_fetched_products", summ.get("total_products", 0)))],
            ["Active Products Audited", str(summ.get("active_products_audited", summ.get("total_products", 0)))],
            ["Draft Products Excluded", str(summ.get("draft_products_excluded", 0))],
            ["Archived Products Excluded", str(summ.get("archived_products_excluded", 0))],
            ["COMPLETE Products", str(summ.get("complete", 0))],
            ["INCOMPLETE Products", str(summ.get("incomplete", 0))],
            ["UNCLASSIFIED Products", str(summ.get("unclassified", 0))],
            ["Validation Errors", str(summ.get("validation_errors", 0))],
        ]
        t_summary = Table(summary_table_data, colWidths=[200, 100])
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        elements.append(t_summary)
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("Actionable Correction Checklist", h2_style))
        act_data = [["Product", "Profile", "Status", "Action Items Needed"]]
        for act in data.get("action_required", []):
            act_data.append([
                Paragraph(f"<b>{act['product_title']}</b><br/>ID: {act['product_id']}", body_style),
                act['profile'],
                act['status'],
                Paragraph("<br/>".join([f"• {c}" for c in act['corrections']]), body_style)
            ])

        if len(act_data) > 1:
            t_act = Table(act_data, colWidths=[140, 90, 80, 220])
            t_act.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ]))
            elements.append(t_act)
        else:
            elements.append(Paragraph("🎉 All products have complete, valid media!", body_style))

        doc.build(elements)

    # -------------------------------------------------------------------------
    # MARKDOWN GENERATOR (_export_markdown_report)
    # -------------------------------------------------------------------------
    def _export_markdown_report(self, data: Dict[str, Any], file_path: str):
        summ = data.get("store_summary", {})
        md = [
            "# KiddyPi Shopify Store — Media Completeness Audit Report\n",
            "**Validation Scope**: `ACTIVE PRODUCTS ONLY`\n",
            f"**Audit Timestamp**: `{data.get('timestamp')}`\n",
            f"**Target Store**: `{data.get('store_name')}`\n",
            "## Executive Store Summary\n",
            f"- **Total Shopify Products Found**: {summ.get('total_fetched_products', summ.get('total_products', 0))}",
            f"- **Active Products Audited**: {summ.get('active_products_audited', summ.get('total_products', 0))}",
            f"- **Draft Products Excluded**: {summ.get('draft_products_excluded', 0)}",
            f"- **Archived Products Excluded**: {summ.get('archived_products_excluded', 0)}",
            f"- **COMPLETE Products**: {summ.get('complete', 0)} (✓ All required media present)",
            f"- **INCOMPLETE Products**: {summ.get('incomplete', 0)} (✗ Missing or invalid dimensions)",
            f"- **UNCLASSIFIED Products**: {summ.get('unclassified', 0)} (⚠ Needs collection classification)",
            f"- **Validation Errors**: {summ.get('validation_errors', 0)}\n",
            "---\n",
            "## Category Metrics\n",
            "| Profile Category | Total Products | Complete | Incomplete | Unclassified |",
            "| :--- | :---: | :---: | :---: | :---: |"
        ]

        for cat, metric in data.get("categories", {}).items():
            md.append(f"| **{cat}** | {metric['total']} | {metric['complete']} | {metric['incomplete']} | {metric['unclassified']} |")

        md.append("\n---\n")
        md.append("## Store Product Audit Table\n")
        md.append("| Product Title | Product ID | Shopify Status | Profile | Overall Status | Required | Valid | Missing | Invalid |")
        md.append("| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |")

        for p in data.get("products", []):
            s = p.get("summary", {})
            md.append(f"| **{p.get('product_title')}** | `{p.get('product_id')}` | `{p.get('shopify_status')}` | {p.get('requirement_profile')} | `{p.get('overall_status')}` | {s.get('total_required')} | {s.get('valid_media')} | {s.get('missing_media')} | {s.get('invalid_media')} |")

        md.append("\n---\n")
        md.append("## Actionable Correction Checklist\n")

        actions = data.get("action_required", [])
        if not actions:
            md.append("🎉 **No media corrections required! All products have complete, valid media.**\n")
        else:
            for idx, act in enumerate(actions, 1):
                md.append(f"### {idx}. {act['product_title']} (`{act['profile']}`)")
                md.append(f"- **Product ID**: `{act['product_id']}`")
                md.append(f"- **Shopify Status**: `{act['shopify_status']}`")
                md.append(f"- **Overall Status**: `{act['status']}`")
                md.append("- **Required Actions**:")
                for corr in act.get("corrections", []):
                    md.append(f"  - {corr}")
                md.append("")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))


# ============================================================================
# CONVENIENCE TOP-LEVEL HELPER FUNCTIONS
# ============================================================================

def validate_product_media_completeness(
    product: Dict[str, Any],
    store_url: Optional[str] = None,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """Top-level helper function to audit a single product payload."""
    skill = MediaCompletenessValidationSkill(store_url=store_url, access_token=access_token)
    return skill.audit_product(product)


def validate_store_media_completeness(
    products: Optional[List[Dict[str, Any]]] = None,
    store_url: Optional[str] = None,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """Top-level helper function to audit an entire store catalog."""
    skill = MediaCompletenessValidationSkill(store_url=store_url, access_token=access_token)
    return skill.audit_store(products)


def validate_collection_media_completeness(
    products: List[Dict[str, Any]],
    collection_name: str,
    store_url: Optional[str] = None,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """Top-level helper function to audit a single collection subset of products."""
    skill = MediaCompletenessValidationSkill(store_url=store_url, access_token=access_token)
    filtered = [
        p for p in products
        if collection_name.lower() in [c.get("title", "").lower() for c in (p.get("collections") or [])]
        or collection_name.lower() in str(p.get("product_type") or "").lower()
    ]
    return skill.audit_store(filtered)


def format_single_product_report(audit_result: Dict[str, Any]) -> str:
    """Formats a single product audit result into human-readable text."""
    lines = [
        f"Product: {audit_result.get('product_title')} (ID: {audit_result.get('product_id')})",
        f"Shopify Status: {audit_result.get('shopify_status')}",
        f"Requirement Profile: {audit_result.get('requirement_profile')}",
        f"Overall Status: {audit_result.get('overall_status')}",
        "--- Checklist ---"
    ]
    for chk in audit_result.get("checklist", []):
        lines.append(f"  • {chk.get('name')}: {chk.get('status')} (Found: {chk.get('found_quantity')}/{chk.get('required_quantity')})")
    if audit_result.get("required_corrections"):
        lines.append("--- Actionable Corrections ---")
        for corr in audit_result.get("required_corrections", []):
            lines.append(f"  - {corr}")
    return "\n".join(lines)

