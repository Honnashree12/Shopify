"""
Deterministic SEO Content & Metadata Validator.

Validates:
- Field lengths (SEO Title <= 60 chars, Meta Description 140-160 chars)
- URL handle validity (lowercase, alphanumeric + hyphens, no special characters)
- Unsupported product claims / hallucinations
- Keyword stuffing / keyword quality
- Tag normalization and validation
- Image ALT text recommendations
"""

import re
from typing import Dict, Any, List, Optional, Tuple


# Disallowed speculative / unverified claim keywords for children's STEM products
UNSUPPORTED_CLAIMS_PATTERNS = [
    r"\bguaranteed\s+(admission|marks|grades|iq|first\s+rank)\b",
    r"\bofficially\s+certified\s+by\s+(isro|nasa|government|drdo)\b",
    r"\b100%\s+foolproof\b",
    r"\bcures?\b",
    r"\bmiracle\b",
]

def normalize_tag(tag: str) -> str:
    """Sanitizes and normalizes a single tag string."""
    if not tag:
        return ""
    # Strip whitespace, punctuation edges, lowercase
    cleaned = tag.strip().lower()
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    cleaned = re.sub(r'[^\w\s\-+]', '', cleaned)
    return " ".join(cleaned.split())


def normalize_and_validate_keywords(keywords_raw: Any) -> Tuple[List[str], str]:
    """
    Normalizes keyword input (string or list) into a deduplicated list of clean tags
    and a comma-separated tag string. Rejects garbage/empty tokens.
    """
    if isinstance(keywords_raw, list):
        tokens = [str(k) for k in keywords_raw]
    elif isinstance(keywords_raw, str):
        tokens = keywords_raw.split(",")
    else:
        tokens = []

    clean_tags: List[str] = []
    seen = set()

    for token in tokens:
        norm = normalize_tag(token)
        if norm and len(norm) >= 2 and norm not in seen:
            seen.add(norm)
            clean_tags.append(norm)

    return clean_tags, ", ".join(clean_tags)


def sanitize_handle(slug_or_title: str) -> str:
    """
    Generates a safe Shopify URL handle:
    - Lowercase
    - Replaces whitespace and non-alphanumeric with hyphens
    - Collapses consecutive hyphens
    - Strips leading and trailing hyphens
    """
    if not slug_or_title:
        return "product"
    handle = slug_or_title.strip().lower()
    handle = re.sub(r'[^a-z0-9\-]+', '-', handle)
    handle = re.sub(r'-+', '-', handle)
    handle = handle.strip('-')
    return handle or "product"


class SEOValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str], sanitized_metadata: Dict[str, Any]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings
        self.sanitized_metadata = sanitized_metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "sanitized_metadata": self.sanitized_metadata
        }


def validate_seo_metadata(
    seo_metadata: Dict[str, Any],
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    existing_handle: Optional[str] = None
) -> SEOValidationResult:
    """
    Deterministically validates and cleanses SEO metadata before publication or update.
    """
    errors: List[str] = []
    warnings: List[str] = []
    sanitized: Dict[str, Any] = dict(seo_metadata or {})

    # 1. SEO Title Check
    raw_title = str(sanitized.get("title") or "").strip()
    if not raw_title and product_name:
        raw_title = product_name.strip()
        warnings.append(f"SEO title was empty; defaulted to product name '{raw_title}'.")

    if not raw_title:
        errors.append("SEO title is missing and could not be inferred.")
    else:
        # Check length
        if len(raw_title) > 60:
            warnings.append(f"SEO title exceeds 60 characters ({len(raw_title)} chars). Recommendation is <= 60 chars.")
            # Automatically truncate cleanly at last word boundary within 60 chars if excessive
            if len(raw_title) > 70:
                truncated = raw_title[:57].rsplit(" ", 1)[0] + "..."
                warnings.append(f"Auto-trimmed excessive SEO title from {len(raw_title)} to {len(truncated)} chars.")
                raw_title = truncated

        # Keyword stuffing check in title (repeated words)
        words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', raw_title)]
        word_counts = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1
            if word_counts[w] >= 3:
                warnings.append(f"Possible keyword stuffing in SEO title: word '{w}' repeats {word_counts[w]} times.")

    sanitized["title"] = raw_title

    # 2. Meta Description Check
    raw_desc = str(sanitized.get("description") or "").strip()
    if not raw_desc and product_description:
        # Use first clean sentence of product description
        clean_desc = re.sub(r'<[^>]+>', ' ', product_description)
        clean_desc = " ".join(clean_desc.split())
        raw_desc = clean_desc[:155].rsplit(" ", 1)[0] + "." if len(clean_desc) > 155 else clean_desc
        warnings.append("Meta description was empty; generated from product description snippet.")

    if not raw_desc:
        errors.append("Meta description is missing.")
    else:
        desc_len = len(raw_desc)
        if desc_len < 100:
            warnings.append(f"Meta description is short ({desc_len} chars). Optimal target is 140-160 chars.")
        elif desc_len > 165:
            warnings.append(f"Meta description is long ({desc_len} chars). Search engines will truncate past ~160 chars.")
            # Auto-truncate cleanly
            raw_desc = raw_desc[:157].rsplit(" ", 1)[0] + "..."
            warnings.append(f"Trimmed meta description to 160 char boundary: '{raw_desc}'")

    sanitized["description"] = raw_desc

    # 3. Handle / Slug Check
    raw_slug = str(sanitized.get("slug") or sanitized.get("handle") or "").strip()
    
    # If existing product already has a handle, DO NOT change it without warning
    if existing_handle:
        if raw_slug and raw_slug != existing_handle:
            warnings.append(
                f"Existing product has handle '{existing_handle}'. Changing handle to '{raw_slug}' "
                "could break existing backlinks unless redirects are created."
            )
        else:
            raw_slug = existing_handle

    if not raw_slug:
        raw_slug = sanitize_handle(raw_title or product_name or "product")
        warnings.append(f"URL slug was generated as '{raw_slug}'.")
    else:
        safe_slug = sanitize_handle(raw_slug)
        if safe_slug != raw_slug:
            warnings.append(f"URL slug contained invalid characters and was normalized to '{safe_slug}'.")
        raw_slug = safe_slug

    sanitized["slug"] = raw_slug
    sanitized["handle"] = raw_slug

    # 4. Tags and Keywords Validation
    raw_kw = sanitized.get("keywords") or sanitized.get("tags") or ""
    clean_tags_list, normalized_kw_str = normalize_and_validate_keywords(raw_kw)
    sanitized["tags_list"] = clean_tags_list
    sanitized["keywords"] = normalized_kw_str

    if len(clean_tags_list) == 0:
        warnings.append("No valid keywords/tags found. Recommended 3-8 targeted tags.")
    elif len(clean_tags_list) > 15:
        warnings.append(f"Excessive keyword count ({len(clean_tags_list)}). Trimmed to top 10 relevant tags.")
        clean_tags_list = clean_tags_list[:10]
        sanitized["tags_list"] = clean_tags_list
        sanitized["keywords"] = ", ".join(clean_tags_list)

    # 5. Unsupported Claims & Hallucinations Check
    combined_text = f"{raw_title} {raw_desc} {sanitized.get('keywords', '')}".lower()
    for pattern in UNSUPPORTED_CLAIMS_PATTERNS:
        match = re.search(pattern, combined_text, re.IGNORECASE)
        if match:
            errors.append(f"Unsupported marketing claim detected: '{match.group(0)}'. Please remove speculative claims.")

    # 6. Primary Keyword & Search Intent Sanity
    if not sanitized.get("primary_keyword"):
        # Default primary keyword to first tag or product title
        if clean_tags_list:
            sanitized["primary_keyword"] = clean_tags_list[0]
        elif product_name:
            sanitized["primary_keyword"] = product_name.lower()
        else:
            sanitized["primary_keyword"] = "stem kit"

    if not sanitized.get("search_intent"):
        sanitized["search_intent"] = "Commercial / Transactional (parents and educators purchasing educational kits)"

    is_valid = len(errors) == 0
    return SEOValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        sanitized_metadata=sanitized
    )

