import logging
import os
import json
from datetime import datetime

from google.adk import Agent
from google.adk.tools.tool_context import ToolContext
from tools.product_context import get_product_context
from tools.image_generator import generate_product_image
from shopify_client import (
    create_product,
    upload_product_image,
    upload_product_images,
    get_or_create_custom_collection,
    add_product_to_collection,
    ShopifyConfigError,
    ShopifyAPIError,
)
import image_config
from services.image_generation_service import ImageGenerationService
from services.shopify_media_service import ShopifyMediaService

logger = logging.getLogger("publisher_agent")


def publish_to_shopify(tool_context: ToolContext) -> str:
    """
    Publish the finalized product to the real Shopify Admin API.
    Uses ONLY the original workflow state.
    """

    state = tool_context.state

    # Stop execution if admin approval is required and not yet given
    if not state.get("approved_to_publish", False):
        logger.info("Publishing is awaiting admin approval. Skipping Shopify creation.")
        return "Publishing skipped: Awaiting admin approval."

    print("\n========== WORKFLOW STATE ==========")
    print(state)
    print("====================================\n")

    product_name = state.get("product_name")
    product_description = state.get("product_description")
    product_price = state.get("product_price")
    product_category = state.get("product_category")

    generated_description = state.get("generated_description")
    seo_metadata = state.get("seo_metadata", {})

    missing = []

    if not product_name:
        missing.append("product_name")

    if not product_description:
        missing.append("product_description")

    if product_price is None:
        missing.append("product_price")

    if not product_category:
        missing.append("product_category")

    if not generated_description:
        missing.append("generated_description")

    if missing:
        return (
            "Publishing failed.\n"
            "Missing workflow state:\n"
            + "\n".join(f"- {item}" for item in missing)
        )

    # Handle missing or invalid SEO metadata safely
    if not seo_metadata or not isinstance(seo_metadata, dict):
        logger.warning("seo_metadata missing or invalid in state; synthesizing safe defaults from product details.")
        seo_metadata = {}

    # Extract and normalize SEO metadata
    from services.seo_validator import validate_seo_metadata
    val_res = validate_seo_metadata(
        seo_metadata=seo_metadata,
        product_name=product_name,
        product_description=generated_description or product_description
    )
    sanitized_seo = val_res.sanitized_metadata
    seo_title = sanitized_seo.get("title")
    seo_description = sanitized_seo.get("description")
    handle = sanitized_seo.get("slug") or sanitized_seo.get("handle")
    
    # Validated and normalized tags
    tags = sanitized_seo.get("keywords") or None

    try:

        product = create_product(
            title=product_name,
            body_html=generated_description,
            price=float(product_price),  # ensure numeric
            product_type=product_category,
            status="draft",
            tags=tags,
            seo_title=seo_title,
            seo_description=seo_description,
            handle=handle,
        )

        # Verify created product actually contains saved SEO fields
        from shopify_client import get_product
        try:
            created_check = get_product(product["id"])
            saved_seo_title = created_check.get("seo_title") or ""
            saved_seo_desc = created_check.get("seo_description") or ""
            saved_handle = created_check.get("handle") or ""

            seo_mismatches = []
            if seo_title and saved_seo_title != seo_title:
                msg = f"SEO Title verification mismatch: expected '{seo_title}', got '{saved_seo_title}'"
                logger.warning(msg)
                seo_mismatches.append(msg)
            if seo_description and saved_seo_desc != seo_description:
                msg = f"SEO Description verification mismatch: expected '{seo_description}', got '{saved_seo_desc}'"
                logger.warning(msg)
                seo_mismatches.append(msg)
            if handle and saved_handle != handle:
                msg = f"SEO Handle verification mismatch: expected '{handle}', got '{saved_handle}'"
                logger.warning(msg)
                seo_mismatches.append(msg)

            seo_verification = {
                "verified": len(seo_mismatches) == 0,
                "saved_seo_title": saved_seo_title,
                "saved_seo_description": saved_seo_desc,
                "saved_handle": saved_handle,
                "mismatches": seo_mismatches,
            }
        except Exception as ve:
            logger.warning("Failed to fetch product for SEO verification: %s", ve)
            seo_verification = {
                "verified": False,
                "saved_seo_title": None,
                "saved_seo_description": None,
                "saved_handle": None,
                "mismatches": [f"Verification fetch error: {ve}"],
            }
            created_check = {}

        product["seo_title"] = seo_verification.get("saved_seo_title") or seo_title
        product["seo_description"] = seo_verification.get("saved_seo_description") or seo_description
        product["handle"] = seo_verification.get("saved_handle") or handle
        product["seo_verification"] = seo_verification
        if created_check.get("url"):
            product["url"] = created_check["url"]

        state["shopify_product"] = product
        state["shopify_product_id"] = product["id"]
        state["shopify_url"] = product["url"]
        state["seo_verification"] = seo_verification

        variant_id = None
        if product.get("variants"):
            variant_id = product["variants"][0].get("id")
        state["shopify_variant_id"] = variant_id

        # Assign to custom collection 'Workshops' if category matches
        if product_category and str(product_category).lower() in ("workshop", "workshops"):
            try:
                coll_id = get_or_create_custom_collection("Workshops")
                add_product_to_collection(product["id"], coll_id)
                logger.info("Successfully assigned product %s to collection 'Workshops'", product["id"])
            except Exception as e:
                logger.warning("Could not assign product to Workshops collection (non-fatal): %s", e)

        # --- Automated Image Generation, Verification & Attachment Workflow ---
        upload_error_msg = ""
        image_prompts = state.get("image_prompts") or {}
        
        # 1. Generate Realistic Product Images (Hero, Lifestyle, Banner, Packaging, Closeup)
        logger.info("Starting automated post-creation image generation using %s...", image_config.PROVIDER)
        gen_result = ImageGenerationService.generate_and_verify_all(product_name, image_prompts)
        generated_paths = gen_result.get("image_paths", [])
        
        # 2. Resiliently Upload and Attach Images to Shopify Product
        logger.info("Uploading %d verified images to Shopify...", len(generated_paths))
        upload_results = ShopifyMediaService.upload_and_attach_all(product["id"], generated_paths)
        
        # 3. Verify Product Media Exists
        logger.info("Verifying media presence on Shopify product ID: %s", product["id"])
        verified_media = ShopifyMediaService.verify_media(product["id"])
        
        # 4. Save Image/Media details to the workflow state for down-stream processes & database
        state["image_paths"] = generated_paths
        state["shopify_media"] = verified_media

        # 5. Generate JSON Reports
        outputs_dir = "outputs"
        os.makedirs(outputs_dir, exist_ok=True)
        
        # Report A: image_generation_report.json
        gen_report = {
            "product_id": product["id"],
            "product_name": product_name,
            "generation_time": datetime.utcnow().isoformat(),
            "provider_used": image_config.PROVIDER,
            "prompts": image_prompts,
            "images": gen_result.get("details", [])
        }
        with open(os.path.join(outputs_dir, "image_generation_report.json"), "w", encoding="utf-8") as f:
            json.dump(gen_report, f, indent=4)
            
        # Report B: shopify_media_report.json
        media_report = {
            "product_id": product["id"],
            "shopify_media": verified_media,
            "verification_status": "verified" if len(verified_media) > 0 else "failed"
        }
        with open(os.path.join(outputs_dir, "shopify_media_report.json"), "w", encoding="utf-8") as f:
            json.dump(media_report, f, indent=4)
            
        # Report C: media_upload_log.json
        upload_log = {
            "product_id": product["id"],
            "logs": [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "upload",
                    "category": item.get("image_path", "").split("_")[-1].split(".")[0] if "_" in item.get("image_path", "") else "unknown",
                    "file": item.get("image_path"),
                    "status": "success" if item.get("success", False) else "failed",
                    "media_id": item.get("media_id"),
                    "attempts": item.get("attempts", 0),
                    "error": item.get("error")
                }
                for item in upload_results
            ]
        }
        with open(os.path.join(outputs_dir, "media_upload_log.json"), "w", encoding="utf-8") as f:
            json.dump(upload_log, f, indent=4)

        print("\n========== PRODUCT PUBLISHED WITH MEDIA ==========")
        print(product)
        print(f"Attached {len(verified_media)} images to Shopify product.")
        print("==================================================\n")

        verification_status_note = ""
        if not seo_verification.get("verified", False):
            mismatches = seo_verification.get("mismatches", [])
            verification_status_note = (
                f"\nWARNING: Shopify SEO field verification failed:\n"
                + "\n".join(f"- {item}" for item in mismatches)
            )

        return (
            f"Product published successfully.\n"
            f"Product ID: {product['id']}\n"
            f"URL: {product['url']}\n"
            f"Attached {len(verified_media)} media assets."
            f"{verification_status_note}"
        )


    except (ShopifyConfigError, ShopifyAPIError) as e:
        logger.error("Shopify publish failed: %s", e)
        return f"Publishing failed: {e}"
    except Exception as e:
        logger.exception("Unexpected error while publishing to Shopify")
        return f"Publishing failed: {e}"


publisher_agent = Agent(
    name="PublisherAgent",
    model="gemini-2.5-flash",
    instruction="""
You are the Shopify Publisher Agent.

You publish products to a real, live Shopify store. After publishing, you should also attach any available generated images via the same publish_to_shopify() call.

The workflow already contains:

- product_name
- product_description
- product_price
- product_category
- generated_description
- seo_metadata
- marketing
- image_prompts
- image_paths

Do NOT generate content.
Do NOT modify workflow values.
Use ONLY the existing workflow state.

Call:

publish_to_shopify()

Return nothing except the tool call.

Your final action MUST be calling publish_to_shopify().
""",
    tools=[
        get_product_context,
        publish_to_shopify,
    ],
)
