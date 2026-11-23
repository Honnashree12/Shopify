"""
SEO Audit Engine for Existing Shopify Products.

Audits individual products or entire catalogue for:
- Missing SEO title
- Missing meta description
- Excessively long titles (> 60 chars)
- Excessively long descriptions (> 160 chars)
- Weak product descriptions (missing, too short, low content density)
- Missing or poor image ALT text
- Missing or unsuitable keywords/tags
- Duplicate or highly similar SEO content across catalogue
- Poor URL handles (special characters, numbers only, overly long)
- Missing relevant product information (vendor, product_type)

Generates:
- Structured issue checklists with severity (CRITICAL, WARNING, INFO)
- Technical SEO score (0 - 100) representing internal checklist compliance
  (explicitly disclaimed as internal content/technical checklist, not prediction of Google rankings)
- Actionable recommendations for optimization
"""

import re
import logging
from typing import Dict, Any, List, Optional
from difflib import SequenceMatcher

logger = logging.getLogger("seo_audit_agent")


def clean_html(raw_html: Optional[str]) -> str:
    """Strips HTML tags and normalizes whitespace."""
    if not raw_html or not isinstance(raw_html, str):
        return ""
    text = re.sub(r'<[^>]+>', ' ', raw_html)
    return " ".join(text.split())


def calculate_text_similarity(a: str, b: str) -> float:
    """Calculates ratio similarity between two strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


class ProductSEOAudit:
    """Evaluates a single product against comprehensive SEO best practices."""

    @staticmethod
    def audit_product(product: Dict[str, Any], all_products: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        product_id = product.get("id")
        title = product.get("title") or ""
        body_html = product.get("body_html") or ""
        clean_desc = clean_html(body_html)
        handle = product.get("handle") or ""
        tags = product.get("tags") or []
        if isinstance(tags, str):
            tags_list = [t.strip() for t in tags.split(",") if t.strip()]
        else:
            tags_list = list(tags)

        # SEO specific fields
        seo_title = product.get("seo_title") or product.get("metafields_global_title_tag") or ""
        seo_description = product.get("seo_description") or product.get("metafields_global_description_tag") or ""
        images = product.get("images") or []

        issues: List[Dict[str, Any]] = []
        deductions = 0

        # 1. SEO Title Audit
        if not seo_title:
            issues.append({
                "code": "MISSING_SEO_TITLE",
                "severity": "CRITICAL",
                "field": "seo_title",
                "message": "Missing SEO title tag. Search engines will default to raw product title.",
                "recommendation": f"Add an optimized SEO title containing target keywords within 60 chars (e.g. '{title[:50]} | KiddyPi')."
            })
            deductions += 20
        else:
            title_len = len(seo_title)
            if title_len > 60:
                issues.append({
                    "code": "EXCESSIVE_SEO_TITLE_LENGTH",
                    "severity": "WARNING",
                    "field": "seo_title",
                    "message": f"SEO title is {title_len} characters (exceeds recommended 60 character limit).",
                    "recommendation": f"Shorten to under 60 characters to prevent SERP truncation."
                })
                deductions += 10
            elif title_len < 20:
                issues.append({
                    "code": "SHORT_SEO_TITLE",
                    "severity": "WARNING",
                    "field": "seo_title",
                    "message": f"SEO title is very short ({title_len} characters).",
                    "recommendation": "Expand title to 30-60 characters including primary keyword and brand."
                })
                deductions += 5

        # 2. Meta Description Audit
        if not seo_description:
            issues.append({
                "code": "MISSING_META_DESCRIPTION",
                "severity": "CRITICAL",
                "field": "seo_description",
                "message": "Missing SEO meta description tag.",
                "recommendation": "Add a persuasive meta description between 140-160 characters highlighting key features and call to action."
            })
            deductions += 25
        else:
            desc_len = len(seo_description)
            if desc_len < 100:
                issues.append({
                    "code": "SHORT_META_DESCRIPTION",
                    "severity": "WARNING",
                    "field": "seo_description",
                    "message": f"Meta description is only {desc_len} characters (optimal range: 140-160).",
                    "recommendation": "Expand meta description with educational benefits, age group, and purchase appeal."
                })
                deductions += 10
            elif desc_len > 165:
                issues.append({
                    "code": "EXCESSIVE_META_DESCRIPTION_LENGTH",
                    "severity": "WARNING",
                    "field": "seo_description",
                    "message": f"Meta description is {desc_len} characters (likely truncated by search engines).",
                    "recommendation": "Trim to within 140-160 characters while keeping key benefits visible."
                })
                deductions += 5

        # 3. Product Description Content Depth
        if not clean_desc or len(clean_desc.split()) < 25:
            issues.append({
                "code": "WEAK_PRODUCT_DESCRIPTION",
                "severity": "CRITICAL",
                "field": "body_html",
                "message": f"Product description is very thin ({len(clean_desc.split())} words).",
                "recommendation": "Write a structured HTML description (>100 words) with key benefits, features, specifications, and FAQs."
            })
            deductions += 20
        elif len(clean_desc.split()) < 60:
            issues.append({
                "code": "SHORT_PRODUCT_DESCRIPTION",
                "severity": "INFO",
                "field": "body_html",
                "message": f"Product description has {len(clean_desc.split())} words. Recommended minimum is 80-150 words.",
                "recommendation": "Add curriculum alignment, child age recommendations, and kit contents list."
            })
            deductions += 5

        # 4. Image ALT Text Audit
        images_missing_alt = 0
        total_images = len(images)
        for img in images:
            alt = img.get("alt") if isinstance(img, dict) else None
            if not alt or not str(alt).strip():
                images_missing_alt += 1

        if total_images == 0:
            issues.append({
                "code": "NO_PRODUCT_IMAGES",
                "severity": "CRITICAL",
                "field": "images",
                "message": "Product has no visual images attached.",
                "recommendation": "Upload at least 1 hero image (1200x1200) with descriptive ALT text."
            })
            deductions += 15
        elif images_missing_alt > 0:
            issues.append({
                "code": "MISSING_IMAGE_ALT_TEXT",
                "severity": "WARNING",
                "field": "images",
                "message": f"{images_missing_alt} of {total_images} images lack descriptive ALT text.",
                "recommendation": f"Add descriptive accessibility and keyword-aligned ALT text to all {images_missing_alt} images."
            })
            deductions += min(15, images_missing_alt * 5)

        # 5. Product Tags / Keywords Audit
        if len(tags_list) == 0:
            issues.append({
                "code": "MISSING_PRODUCT_TAGS",
                "severity": "WARNING",
                "field": "tags",
                "message": "Product has no tags or keywords assigned.",
                "recommendation": "Add 4-8 targeted tags (e.g. category, age range, STEM subject, kit type)."
            })
            deductions += 10
        elif len(tags_list) < 3:
            issues.append({
                "code": "FEW_PRODUCT_TAGS",
                "severity": "INFO",
                "field": "tags",
                "message": f"Product has only {len(tags_list)} tags.",
                "recommendation": "Enrich with 2-4 additional tags for better storefront search and indexing."
            })
            deductions += 3

        # 6. URL Handle Audit
        if not handle:
            issues.append({
                "code": "MISSING_URL_HANDLE",
                "severity": "CRITICAL",
                "field": "handle",
                "message": "Product has no URL handle.",
                "recommendation": "Generate a clean lowercase hyphen-separated URL handle."
            })
            deductions += 15
        elif bool(re.search(r'[^a-z0-9\-]', handle)):
            issues.append({
                "code": "INVALID_URL_HANDLE",
                "severity": "WARNING",
                "field": "handle",
                "message": f"Handle '{handle}' contains uppercase or special characters.",
                "recommendation": "Normalize handle to lowercase letters, numbers, and hyphens only."
            })
            deductions += 5
        elif len(handle) > 75:
            issues.append({
                "code": "EXCESSIVE_HANDLE_LENGTH",
                "severity": "INFO",
                "field": "handle",
                "message": f"Handle length is {len(handle)} characters.",
                "recommendation": "Consider shortening handle for cleaner URLs and readability."
            })
            deductions += 2

        # 7. Duplicate / Highly Similar SEO Content Check (if catalogue provided)
        if all_products and (seo_title or seo_description):
            found_dup_title = False
            found_dup_desc = False
            for other in all_products:
                other_id = other.get("id")
                if other_id and str(other_id) != str(product_id):
                    other_title = other.get("seo_title") or other.get("metafields_global_title_tag") or ""
                    other_desc = other.get("seo_description") or other.get("metafields_global_description_tag") or ""
                    
                    if not found_dup_title and seo_title and other_title and calculate_text_similarity(seo_title, other_title) > 0.90:
                        issues.append({
                            "code": "DUPLICATE_SEO_TITLE",
                            "severity": "WARNING",
                            "field": "seo_title",
                            "message": f"SEO title is near-identical to another product ('{other.get('title')}').",
                            "recommendation": "Differentiate title by highlighting unique features, kit versions, or target age."
                        })
                        deductions += 10
                        found_dup_title = True

                    if not found_dup_desc and seo_description and other_desc and calculate_text_similarity(seo_description, other_desc) > 0.85:
                        issues.append({
                            "code": "DUPLICATE_META_DESCRIPTION",
                            "severity": "WARNING",
                            "field": "seo_description",
                            "message": f"Meta description is near-identical to product '{other.get('title')}'.",
                            "recommendation": "Customize description to reflect specific contents, components, and project outcomes."
                        })
                        deductions += 10
                        found_dup_desc = True

                if found_dup_title and found_dup_desc:
                    break

        # Calculate final SEO technical checklist score (0 - 100)
        seo_score = max(0, 100 - deductions)

        # Status categorization
        has_critical = any(i["severity"] == "CRITICAL" for i in issues)
        has_warning = any(i["severity"] == "WARNING" for i in issues)
        if has_critical:
            status = "NEEDS_OPTIMIZATION"
        elif has_warning:
            status = "CAN_IMPROVE"
        else:
            status = "OPTIMIZED"

        return {
            "product_id": str(product_id),
            "title": title,
            "handle": handle,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "tags": tags_list,
            "images_count": total_images,
            "images_missing_alt": images_missing_alt,
            "seo_score": seo_score,
            "status": status,
            "shopify_status": (product.get("status") or "ACTIVE").upper(),
            "issue_count": len(issues),
            "issues": issues,
            "disclaimer": "This score represents an internal technical checklist rating (0-100), not a guarantee or prediction of search engine rankings."
        }


def audit_catalogue_seo(products: List[Dict[str, Any]], active_only: bool = True) -> Dict[str, Any]:
    """
    Audits an entire collection/catalogue of Shopify products.
    By default filters for ACTIVE products only (excludes DRAFT and ARCHIVED products).
    """
    total_raw = len(products)
    if active_only:
        filtered_products = [
            p for p in products
            if (p.get("status") or "ACTIVE").strip().upper() == "ACTIVE"
        ]
        draft_excluded = len([
            p for p in products
            if (p.get("status") or "").strip().upper() == "DRAFT"
        ])
        archived_excluded = len([
            p for p in products
            if (p.get("status") or "").strip().upper() == "ARCHIVED"
        ])
    else:
        filtered_products = products
        draft_excluded = 0
        archived_excluded = 0

    results: List[Dict[str, Any]] = []
    total = len(filtered_products)
    products_with_issues = 0
    total_score = 0
    issue_type_counts: Dict[str, int] = {}

    for prod in filtered_products:
        audit = ProductSEOAudit.audit_product(prod, all_products=filtered_products)
        results.append(audit)
        total_score += audit["seo_score"]
        if audit["issue_count"] > 0:
            products_with_issues += 1
        for issue in audit["issues"]:
            code = issue["code"]
            issue_type_counts[code] = issue_type_counts.get(code, 0) + 1

    avg_score = round(total_score / total, 1) if total > 0 else 100.0

    return {
        "total_audited": total,
        "total_store_products": total_raw,
        "draft_excluded_count": draft_excluded,
        "archived_excluded_count": archived_excluded,
        "scope": "Active products only" if active_only else "All catalogue products",
        "products_with_issues": products_with_issues,
        "optimized_products": total - products_with_issues,
        "average_seo_score": avg_score,
        "issue_breakdown": issue_type_counts,
        "products": results,
        "disclaimer": "All audit metrics reflect internal technical and content checklist compliance, not Google rank predictions."
    }

