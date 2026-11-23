"""
Media Completeness Validation Skill / Agent for KiddyPi Shopify Store.

Provides an independently callable, read-only ADK-compatible tool and agent wrapper
for validating product media completeness. Reuses existing ShopifyClient infrastructure.
"""

import logging
from typing import Any, Dict, List, Optional
# pyrefly: ignore [missing-import]
from google.adk import Agent

from shopify_client import ShopifyClient, ShopifyAPIError, get_product
from services.media_completeness_validator import (
    validate_product_media_completeness,
    validate_collection_media_completeness,
    validate_store_media_completeness,
    format_single_product_report,
)

logger = logging.getLogger("media_completeness_agent")


def validate_product_media_completeness_tool(
    product_id: Optional[Any] = None,
    product_payload: Optional[Dict[str, Any]] = None,
    collection_name: Optional[str] = None,
    store_wide: bool = False,
) -> Dict[str, Any]:
    """
    Read-only validation tool to inspect Shopify product media completeness.

    Args:
        product_id: Shopify Product ID to fetch and validate via live Shopify API.
        product_payload: Optional pre-loaded Shopify product dictionary.
        collection_name: Optional collection name filter for batch audit.
        store_wide: If True, audits all products across the store.

    Returns:
        Structured audit report dict containing completeness status and checklist.
    """
    logger.info("Executing Media Completeness Validation Tool (read-only)...")

    # 1. Single pre-loaded product payload supplied
    if product_payload:
        try:
            res = validate_product_media_completeness(product_payload)
            res["formatted_report"] = format_single_product_report(res)
            return res
        except Exception as e:
            logger.exception("Error validating product payload")
            return {
                "overall_status": "VALIDATION_ERROR",
                "message": "Unable to retrieve or parse product media.",
                "reason": str(e),
            }

    # 2. Single product ID supplied — fetch via ShopifyClient
    if product_id:
        try:
            raw_product = get_product(product_id)
            res = validate_product_media_completeness(raw_product)
            res["formatted_report"] = format_single_product_report(res)
            return res
        except ShopifyAPIError as exc:
            logger.error("Shopify API Error fetching product %s: %s", product_id, exc)
            return {
                "overall_status": "VALIDATION_ERROR",
                "message": "Unable to retrieve Shopify media.",
                "reason": str(exc),
                "decision_made": False,
            }
        except Exception as exc:
            logger.exception("Unexpected error fetching product %s: %s", product_id, exc)
            return {
                "overall_status": "VALIDATION_ERROR",
                "message": "Unable to retrieve Shopify media.",
                "reason": str(exc),
                "decision_made": False,
            }

    # 3. Batch collection or storewide validation
    try:
        from config import settings
        store_url = settings.shopify_validation_store or settings.shopify_store_url or "validation-store.myshopify.com"
        token = settings.shopify_validation_token or settings.shopify_access_token or "shpat_placeholder"
        client = ShopifyClient(store_url=store_url, access_token=token)
        all_prods = client.fetch_all_products()

        if store_wide:
            return validate_store_media_completeness(all_prods)
        elif collection_name:
            filtered = [
                p for p in all_prods
                if collection_name.lower() in [c.get("title", "").lower() for c in (p.get("collections") or [])]
                or collection_name.lower() in str(p.get("product_type") or "").lower()
            ]
            return validate_collection_media_completeness(filtered, collection_name)
        else:
            return validate_store_media_completeness(all_prods)

    except ShopifyAPIError as exc:
        logger.error("Shopify API Error executing batch media audit: %s", exc)
        return {
            "overall_status": "VALIDATION_ERROR",
            "message": "Unable to retrieve Shopify media for store/collection audit.",
            "reason": str(exc),
            "decision_made": False,
        }
    except Exception as exc:
        logger.exception("Unexpected error executing batch media audit: %s", exc)
        return {
            "overall_status": "VALIDATION_ERROR",
            "message": "Unable to retrieve Shopify media for store/collection audit.",
            "reason": str(exc),
            "decision_made": False,
        }


# ============================================================================
# ADK AGENT WRAPPER
# ============================================================================

media_completeness_agent = Agent(
    name="MediaCompletenessValidationSkill",
    model="gemini-2.5-flash",
    description=(
        "Read-only validation agent that inspects product media against collection-specific "
        "requirements for STEM Kits, Courses, Books, Apparels, Electronics, and Workshops. "
        "Outputs exact missing or invalid image types without modifying any Shopify data."
    ),
    instruction=(
        "You are the Media Completeness Validation Agent. Your sole responsibility is to evaluate "
        "whether Shopify products have all required images for their collection type. You must NEVER "
        "upload, modify, delete, resize, or reorder any media. Always report exact missing images."
    ),
    tools=[validate_product_media_completeness_tool],
)
