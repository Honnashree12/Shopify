"""
SEO Optimizer Agent for Existing Shopify Products.

Generates:
- Structured Before & After optimization proposals
- Optimized SEO Title (< 60 chars)
- Optimized Meta Description (140 - 160 chars)
- Clean URL handle recommendation (flagged to preserve existing handle by default to avoid breaking URLs)
- Normalized Tags
- Image ALT text recommendations

Strictly preserves:
- Price
- Inventory
- Variants
- Product Status
- Images (binaries/order)
- Collections
"""

import logging
import re
from typing import Dict, Any, List, Optional
from services.seo_validator import validate_seo_metadata, sanitize_handle, normalize_and_validate_keywords
from agents.seo_audit_agent import clean_html

logger = logging.getLogger("seo_optimizer_agent")


class SEOOptimizerAgent:
    """Generates high-quality, verified SEO improvements for existing Shopify products."""

    @staticmethod
    def generate_recommendations(
        product: Dict[str, Any],
        brand_name: str = "KiddyPi",
        preserve_handle: bool = True
    ) -> Dict[str, Any]:
        """
        Creates deterministic, brand-aligned, verified SEO proposals without unverified claims.
        """
        prod_id = str(product.get("id"))
        raw_title = product.get("title") or "Educational STEM Kit"
        body_html = product.get("body_html") or ""
        clean_desc = clean_html(body_html)
        product_type = product.get("product_type") or "STEM Kits"
        existing_handle = product.get("handle") or sanitize_handle(raw_title)

        existing_seo_title = product.get("seo_title") or product.get("metafields_global_title_tag") or ""
        existing_seo_desc = product.get("seo_description") or product.get("metafields_global_description_tag") or ""
        existing_tags = product.get("tags") or []
        if isinstance(existing_tags, str):
            existing_tags_list = [t.strip() for t in existing_tags.split(",") if t.strip()]
        else:
            existing_tags_list = list(existing_tags)

        # 1. Generate Optimized SEO Title (< 60 characters)
        # Format: "{Product Title} | {Brand/Category}"
        base_title = raw_title.strip()
        brand_suffix = f" | {brand_name}"
        max_title_len = 60 - len(brand_suffix)
        
        if len(base_title) <= max_title_len:
            opt_title = f"{base_title}{brand_suffix}"
        else:
            # Cleanly truncate on word boundary
            truncated = base_title[:max_title_len].rsplit(" ", 1)[0]
            opt_title = f"{truncated}{brand_suffix}"

        # 2. Generate Optimized Meta Description (140 - 160 characters)
        if clean_desc and len(clean_desc) >= 80:
            first_sentence = clean_desc.split(".")[0].strip()
            # Construct a compelling 140-160 char snippet
            target_lead = f"Discover the {base_title}. "
            lead_len = len(target_lead)
            remaining_chars = 150 - lead_len - len(f" Order your {product_type} today from {brand_name}!")
            
            if remaining_chars > 20 and len(first_sentence) > 10:
                short_snippet = first_sentence[:remaining_chars].rsplit(" ", 1)[0]
                opt_desc = f"{target_lead}{short_snippet}. Shop online at {brand_name} today!"
            else:
                opt_desc = f"Explore the {base_title}. Hands-on learning for young innovators. Shop high-quality {product_type} online at {brand_name}!"
        else:
            opt_desc = f"Shop the {base_title} online at {brand_name}. High quality hands-on {product_type} designed to inspire young minds. Buy yours today!"

        # Ensure description length strictly 130-160 chars
        if len(opt_desc) > 160:
            opt_desc = opt_desc[:157].rsplit(" ", 1)[0] + "..."
        elif len(opt_desc) < 130:
            opt_desc = opt_desc.rstrip(".") + f" Fast delivery across India from {brand_name}."

        # 3. URL Handle Recommendation
        recommended_handle = sanitize_handle(base_title)
        # If preserving existing handle (default safety rule to avoid breaking URLs)
        final_handle = existing_handle if preserve_handle and existing_handle else recommended_handle

        # 4. Tags / Keywords Enrichment
        clean_type = normalize_and_validate_keywords(product_type)[0]
        seed_keywords = [raw_title.lower(), product_type.lower(), brand_name.lower(), "kids stem", "educational kit"]
        all_tags = existing_tags_list + seed_keywords + clean_type
        clean_tags_list, tags_str = normalize_and_validate_keywords(all_tags)
        # Keep top 8 tags
        clean_tags_list = clean_tags_list[:8]
        tags_str = ", ".join(clean_tags_list)

        # 5. Image ALT Text Recommendations
        images = product.get("images") or []
        image_alt_recommendations = []
        for idx, img in enumerate(images):
            img_id = img.get("id")
            existing_alt = img.get("alt") or ""
            if idx == 0:
                rec_alt = f"{base_title} - Featured product view ({brand_name})"
            elif idx == 1:
                rec_alt = f"{base_title} - Box packaging and components"
            elif idx == 2:
                rec_alt = f"{base_title} - Project assembly and details"
            else:
                rec_alt = f"{base_title} - Detail view {idx+1}"
            
            image_alt_recommendations.append({
                "image_id": img_id,
                "current_alt": existing_alt,
                "recommended_alt": rec_alt
            })

        # Run through deterministic validator
        val_res = validate_seo_metadata(
            seo_metadata={
                "title": opt_title,
                "description": opt_desc,
                "slug": final_handle,
                "handle": final_handle,
                "keywords": tags_str,
                "tags": tags_str,
                "primary_keyword": clean_tags_list[0] if clean_tags_list else base_title.lower(),
                "search_intent": "Commercial / Transactional purchase"
            },
            product_name=base_title,
            product_description=clean_desc,
            existing_handle=existing_handle if preserve_handle else None
        )

        sanitized = val_res.sanitized_metadata

        return {
            "product_id": prod_id,
            "product_title": raw_title,
            "before": {
                "seo_title": existing_seo_title or "(Default Title)",
                "seo_description": existing_seo_desc or "(No meta description set)",
                "handle": existing_handle,
                "tags": existing_tags_list,
                "images": [{"id": img.get("id"), "alt": img.get("alt") or "(None)"} for img in images]
            },
            "after": {
                "seo_title": sanitized.get("title"),
                "seo_description": sanitized.get("description"),
                "handle": sanitized.get("handle"),
                "handle_changed": sanitized.get("handle") != existing_handle,
                "tags": sanitized.get("tags_list"),
                "image_alts": image_alt_recommendations
            },
            "validation": {
                "is_valid": val_res.is_valid,
                "errors": val_res.errors,
                "warnings": val_res.warnings
            },
            "changes_summary": [
                f"Updated SEO title from '{existing_seo_title or '(Default)'}' to '{sanitized.get('title')}'",
                f"Updated Meta description ({len(sanitized.get('description'))} chars)",
                f"Normalized tags ({len(sanitized.get('tags_list'))} tags)",
                f"Generated ALT text recommendations for {len(image_alt_recommendations)} images"
            ]
        }

