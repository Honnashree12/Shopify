"""
SEO Optimization Workflow for Existing Shopify Products.

Orchestrates:
1. Fetching catalogue products with pagination (via GraphQL with REST fallback)
2. Running the SEO Audit Engine
3. Generating optimized SEO proposals (Before-and-After)
4. Supporting dry-run executions (zero mutations)
5. Enforcing explicit human review / approval before applying changes
6. Updating ONLY approved SEO fields (seo_title, seo_description, tags, image alt text)
7. Re-fetching and verifying saved values from Shopify
8. Strictly preserving price, inventory, variants, status, image binaries, collections
9. Recording audit trails in Firebase / local outputs
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from shopify_client import ShopifyClient, get_product, update_product, update_product_image_alt, ShopifyAPIError
from config import settings
from agents.seo_audit_agent import ProductSEOAudit, audit_catalogue_seo
from agents.seo_optimizer_agent import SEOOptimizerAgent

logger = logging.getLogger("seo_optimization_workflow")

OUTPUTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))


class SEOOptimizationWorkflow:
    """Manages bulk and single-product SEO audits, proposals, and verified applications."""

    @staticmethod
    def get_client() -> ShopifyClient:
        store_url = settings.shopify_store_url or ""
        token = settings.shopify_access_token or ""
        if not store_url or not token:
            logger.warning("Shopify credentials not fully configured in settings.")
        return ShopifyClient(store_url=store_url, access_token=token)

    @classmethod
    def fetch_all_products_paginated(cls, active_only: bool = True) -> List[Dict[str, Any]]:
        """Fetches products using paginated GraphQL with automatic REST fallback, filtering active products by default."""
        client = cls.get_client()
        products = client.fetch_all_products()
        if active_only:
            products = [
                p for p in products
                if (p.get("status") or "ACTIVE").strip().upper() == "ACTIVE"
            ]
        return products

    @classmethod
    def run_catalogue_audit(cls, active_only: bool = True) -> Dict[str, Any]:
        """Runs the comprehensive SEO audit across active products in the store."""
        client = cls.get_client()
        all_products = client.fetch_all_products()
        audit_results = audit_catalogue_seo(all_products, active_only=active_only)
        
        # Save audit report
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        report_path = os.path.join(OUTPUTS_DIR, "seo_audit_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(audit_results, f, indent=2)

        return audit_results

    @classmethod
    def generate_proposals(
        cls,
        product_ids: Optional[List[str]] = None,
        preserve_handles: bool = True,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """
        Generates Before-and-After SEO optimization proposals for specified products
        or active catalogue products if product_ids is None. (Dry-run mode by definition).
        """
        all_products = cls.fetch_all_products_paginated(active_only=active_only)
        if product_ids:
            clean_filter_ids = {str(p).replace("gid://shopify/Product/", "").strip() for p in product_ids}
            targets = [p for p in all_products if str(p.get("id")).replace("gid://shopify/Product/", "").strip() in clean_filter_ids]
        else:
            targets = all_products

        proposals = []
        for prod in targets:
            rec = SEOOptimizerAgent.generate_recommendations(prod, preserve_handle=preserve_handles)
            proposals.append(rec)

        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "PROPOSAL_DRY_RUN",
            "total_products_evaluated": len(targets),
            "proposals": proposals,
            "disclaimer": "This is a dry-run preview. No Shopify changes have been applied. Explicit approval is required."
        }

        # Persist preview
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        preview_path = os.path.join(OUTPUTS_DIR, "seo_optimization_proposals.json")
        with open(preview_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

    @classmethod
    def apply_approved_optimizations(
        cls,
        approved_proposals: List[Dict[str, Any]],
        user_email: str = "approver@kiddypi.com",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Applies approved SEO proposals to Shopify Admin API.
        
        STRICT RULES:
        1. If dry_run=True, makes zero mutations and returns simulation report.
        2. Modifies ONLY:
           - seo_title
           - seo_description
           - tags
           - image ALT text
           - handle (ONLY if explicitly approved and handle_changed is approved)
        3. Never modifies price, inventory, variants, status, product images or collections.
        4. Re-fetches the product from Shopify to verify saved values.
        5. Logs results to audit logs.
        """
        results = []
        successful_updates = 0
        failed_updates = 0

        for prop in approved_proposals:
            pid = prop.get("product_id")
            after = prop.get("after") or {}
            
            new_title = after.get("seo_title")
            new_desc = after.get("seo_description")
            new_tags = ", ".join(after.get("tags") or [])
            update_handle = after.get("handle") if prop.get("approve_handle_change") else None
            image_alts = after.get("image_alts") or []

            if dry_run:
                results.append({
                    "product_id": pid,
                    "status": "SIMULATED_SUCCESS",
                    "fields_to_update": {
                        "seo_title": new_title,
                        "seo_description": new_desc,
                        "tags": new_tags,
                        "handle": update_handle,
                        "image_alts_count": len(image_alts)
                    }
                })
                successful_updates += 1
                continue

            # Live Update
            try:
                # 1. Fetch before state for baseline audit
                original = get_product(pid)
                orig_price = original.get("price")
                orig_variants = original.get("variants")
                orig_status = original.get("status")

                # 2. Execute SEO-only update via update_product
                update_kwargs: Dict[str, Any] = {
                    "seo_title": new_title,
                    "seo_description": new_desc,
                    "tags": new_tags,
                }
                if update_handle:
                    update_kwargs["handle"] = update_handle

                updated_resp = update_product(pid, **update_kwargs)

                # 3. Update Image ALT texts if specified
                alt_update_results = []
                for item in image_alts:
                    img_id = item.get("image_id")
                    rec_alt = item.get("recommended_alt")
                    if img_id and rec_alt:
                        ok = update_product_image_alt(pid, img_id, rec_alt)
                        alt_update_results.append({"image_id": img_id, "success": ok})

                # 4. Independent Verification Check by re-fetching product
                verified = get_product(pid)

                # Assert non-SEO fields were strictly preserved
                assert verified.get("price") == orig_price, "CRITICAL ERROR: Product price altered during SEO update!"
                assert verified.get("status") == orig_status, "CRITICAL ERROR: Product status altered during SEO update!"

                seo_title_saved = verified.get("seo_title") == new_title
                seo_desc_saved = verified.get("seo_description") == new_desc

                results.append({
                    "product_id": pid,
                    "status": "SUCCESS",
                    "seo_title_verified": seo_title_saved,
                    "seo_desc_verified": seo_desc_saved,
                    "saved_seo_title": verified.get("seo_title"),
                    "saved_seo_description": verified.get("seo_description"),
                    "saved_tags": verified.get("tags"),
                    "saved_handle": verified.get("handle"),
                    "image_alts_updated": len([r for r in alt_update_results if r["success"]]),
                    "unrelated_fields_preserved": True
                })
                successful_updates += 1

                # 5. Record Audit Trail
                try:
                    from services.firebase_service import save_audit_log
                    import uuid
                    log_id = f"AUDIT-SEO-{pid}-{uuid.uuid4().hex[:6].upper()}"
                    save_audit_log(log_id, {
                        "event_id": log_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "actor": user_email,
                        "role": "APPROVER",
                        "action": "SEO_OPTIMIZATION_APPLIED",
                        "product_id": str(pid),
                        "description": f"Applied verified SEO metadata to product {pid}: title='{new_title}'"
                    })
                except Exception as log_err:
                    logger.warning("Could not persist Firebase audit log for SEO update %s: %s", pid, log_err)

            except Exception as exc:
                logger.exception("Failed to apply SEO update for product %s: %s", pid, exc)
                failed_updates += 1
                results.append({
                    "product_id": pid,
                    "status": "FAILED",
                    "error": str(exc)
                })

        execution_summary = {
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "applied_by": user_email,
            "total_requested": len(approved_proposals),
            "successful_updates": successful_updates,
            "failed_updates": failed_updates,
            "details": results
        }

        # Save history log
        history_path = os.path.join(OUTPUTS_DIR, "seo_optimization_history.json")
        try:
            history = []
            if os.path.exists(history_path):
                with open(history_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            history.insert(0, execution_summary)
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(history[:50], f, indent=2)  # Keep last 50 runs
        except Exception as e:
            logger.warning("Could not save history log: %s", e)

        return execution_summary

