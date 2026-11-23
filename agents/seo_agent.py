import logging
from typing import Optional, List, Dict, Any
# pyrefly: ignore[missing-import]
from google.adk import Agent
# pyrefly: ignore[missing-import]
from google.adk.tools.tool_context import ToolContext

from tools.product_context import get_product_context
from services.seo_validator import validate_seo_metadata, normalize_and_validate_keywords, sanitize_handle

logger = logging.getLogger("seo_agent")


def save_enhanced_seo_metadata(
    seo_title: str,
    meta_description: str,
    primary_keyword: str,
    secondary_keywords: str,
    search_intent: str,
    url_slug: str,
    product_tags: str,
    product_description_recommendations: str,
    image_alt_text_recommendations: str,
    tool_context: ToolContext,
) -> str:
    """
    Save validated and enhanced SEO metadata into the shared workflow state.
    """
    state = tool_context.state
    prod_name = state.get("product_name")
    raw_desc = state.get("product_description") or state.get("raw_description")

    # Clean and parse keyword tags
    all_kw = f"{primary_keyword}, {secondary_keywords}, {product_tags}"
    tags_list, normalized_kw = normalize_and_validate_keywords(all_kw)

    raw_meta = {
        "title": seo_title.strip() if seo_title else "",
        "description": meta_description.strip() if meta_description else "",
        "primary_keyword": primary_keyword.strip() if primary_keyword else "",
        "secondary_keywords": secondary_keywords.strip() if secondary_keywords else "",
        "search_intent": search_intent.strip() if search_intent else "Commercial Intent",
        "slug": url_slug.strip() if url_slug else "",
        "handle": url_slug.strip() if url_slug else "",
        "keywords": normalized_kw,
        "tags": normalized_kw,
        "tags_list": tags_list,
        "product_description_recommendations": product_description_recommendations.strip() if product_description_recommendations else "",
        "image_alt_text_recommendations": image_alt_text_recommendations.strip() if image_alt_text_recommendations else "",
    }

    # Deterministic validation layer
    val_res = validate_seo_metadata(
        seo_metadata=raw_meta,
        product_name=prod_name,
        product_description=raw_desc,
        existing_handle=state.get("existing_handle") or state.get("handle")
    )

    final_meta = val_res.sanitized_metadata
    final_meta["validation_errors"] = val_res.errors
    final_meta["validation_warnings"] = val_res.warnings
    final_meta["is_valid"] = val_res.is_valid

    tool_context.state["seo_metadata"] = final_meta

    print("\n========== ENHANCED SEO AGENT ==========")
    print("Product Name       :", prod_name)
    print("SEO Title          :", final_meta.get("title"))
    print("Meta Description   :", final_meta.get("description"))
    print("Primary Keyword    :", final_meta.get("primary_keyword"))
    print("URL Handle / Slug  :", final_meta.get("slug"))
    print("Normalized Tags    :", final_meta.get("keywords"))
    print("Validation Valid?  :", val_res.is_valid)
    if val_res.warnings:
        print("Validation Warnings:", val_res.warnings)
    print("=========================================\n")

    return "Enhanced SEO metadata validated and saved successfully."


def save_seo_metadata(
    seo_title: str,
    meta_description: str,
    keywords: str,
    url_slug: str,
    tool_context: ToolContext,
) -> str:
    """
    Backwards-compatible wrapper that automatically enriches standard 4-arg calls
    with deterministic defaults and validation.
    """
    return save_enhanced_seo_metadata(
        seo_title=seo_title,
        meta_description=meta_description,
        primary_keyword=keywords.split(",")[0].strip() if keywords else "",
        secondary_keywords=keywords,
        search_intent="Commercial / Educational STEM Purchase",
        url_slug=url_slug,
        product_tags=keywords,
        product_description_recommendations="Include practical child-friendly benefits, clear STEM topics, and safety guidelines.",
        image_alt_text_recommendations=f"{seo_title} top view showing components",
        tool_context=tool_context
    )


seo_agent = Agent(
    name="SEOAgent",
    model="gemini-2.5-flash",
    instruction="""
You are a senior Shopify E-commerce SEO Expert.

IMPORTANT:
Your FIRST action MUST be calling:
get_product_context()

The tool returns:
- product_name
- product_description
- product_price
- product_category

Use ONLY the values returned by the tool.
- Never invent another product or speculative claims.
- Never invent unverified technical certifications, NASA/ISRO affiliations, or warranties.
- Avoid keyword stuffing and unnatural phrasing.
- Ensure natural customer search language used by parents, hobbyists, and teachers.

Requirements:
1. Primary Keyword: 1 high-intent targeted search phrase.
2. Secondary Keywords: 3 to 6 comma-separated related search queries.
3. Search Intent: Commercial, Informational, or Transactional purpose.
4. SEO Title:
   - Must be concise and under 60 characters.
   - Include exact product name naturally.
5. Meta Description:
   - Between 140 and 160 characters.
   - Persuasive, summarizing key features with a clear click-through incentive.
6. URL Slug / Handle:
   - Lowercase, hyphen-separated, based on product name, no special characters.
7. Relevant Product Tags:
   - 4-8 comma-separated category, topic, and age-group tags.
8. Product Description Recommendations:
   - 1-2 practical bullet points to enhance content relevance.
9. Image ALT Text Recommendations:
   - 1-2 descriptive alt text phrases for primary product photos.

Call save_enhanced_seo_metadata() with all generated fields:
save_enhanced_seo_metadata(
    seo_title,
    meta_description,
    primary_keyword,
    secondary_keywords,
    search_intent,
    url_slug,
    product_tags,
    product_description_recommendations,
    image_alt_text_recommendations
)

Return nothing except the tool call.
Your final action MUST be calling save_enhanced_seo_metadata().
""",
    tools=[
        get_product_context,
        save_enhanced_seo_metadata,
        save_seo_metadata,
    ],
)
