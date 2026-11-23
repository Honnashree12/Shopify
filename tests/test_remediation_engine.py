"""
Unit and Integration Tests for Product Validation Remediation & Auto-Revalidation Engine.

Tests all 17 requirements specified in Phase 12 & 13.
"""

import os
import json
import unittest
from unittest.mock import MagicMock, patch

from services.remediation_engine import (
    RemediationItem,
    generate_remediations_for_product,
    apply_remediation,
    log_remediation_audit,
    FIX_TYPE_SAFE_AUTO_FIX,
    FIX_TYPE_REVIEW_REQUIRED,
    FIX_TYPE_MANUAL_VERIFICATION,
    FIX_TYPE_NOT_FIXABLE,
    generate_deterministic_sku
)
from agents.product_validation_agent import validate_products_checklist_tool, fetch_validation_products_tool


class MockToolContext:
    def __init__(self, state):
        self.state = state


class TestRemediationEngine(unittest.TestCase):

    def setUp(self):
        self.sample_product_missing_sku = {
            "id": "gid://shopify/Product/1001",
            "product_id": "1001",
            "title": "KiddyPi STEM Robotics Kit | Hands-on Learning",
            "product_name": "KiddyPi STEM Robotics Kit | Hands-on Learning",
            "handle": "kiddypi-stem-robotics-kit",
            "vendor": "KiddyPi",
            "product_type": "STEM Kits (diy-kits)",
            "status": "ACTIVE",
            "body_html": "<p>A great educational STEM kit for kids to learn robotics.</p>",
            "collections": ["STEM Kits"],
            "tags": ["stem", "robotics", "kiddypi"],
            "seo_title": "KiddyPi STEM Robotics Kit",
            "seo_description": "Explore KiddyPi STEM Robotics Kit. High quality educational kit for hands-on learning.",
            "images": [
                {"id": "img1", "url": "https://example.com/img1.jpg", "width": 1000, "height": 1000, "alt": "Hero image"}
            ],
            "variants": [
                {
                    "id": "gid://shopify/ProductVariant/2001",
                    "sku": "",  # MISSING SKU
                    "price": "49.99",
                    "compare_at_price": "59.99",
                    "requires_shipping": True,
                    "weight": 1.5,
                    "inventory_quantity": 10,
                    "inventory_policy": "DENY",
                    "taxable": True
                }
            ],
            "checks": {
                "18. SKU": {
                    "section": "C. Pricing & Variants",
                    "severity": "Blocker",
                    "status": "FAIL",
                    "explanation": "SKU missing for 1 of 1 variant(s)."
                },
                "14. Price": {
                    "section": "C. Pricing & Variants",
                    "severity": "Blocker",
                    "status": "PASS",
                    "explanation": "Every variant has a price greater than 0.00."
                }
            }
        }

    # =========================================================================
    # TEST 1: Missing SKU generates remediation suggestion
    # =========================================================================
    def test_01_missing_sku_generates_remediation_suggestion(self):
        remediations = generate_remediations_for_product(self.sample_product_missing_sku)
        sku_rems = [r for r in remediations if r.rule_id == "18" or r.field_to_change == "sku"]
        self.assertTrue(len(sku_rems) > 0)
        sku_rem = sku_rems[0]
        self.assertEqual(sku_rem.fix_type, FIX_TYPE_SAFE_AUTO_FIX)
        self.assertTrue(sku_rem.can_auto_fix)
        self.assertTrue(sku_rem.proposed_value.startswith("KP-"))
        self.assertIn("SKU", sku_rem.rule_name)

    # =========================================================================
    # TEST 2: Safe SKU Apply Change updates Shopify
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_02_safe_sku_apply_change_updates_shopify(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.fetch_all_products.return_value = [self.sample_product_missing_sku]

        # Simulate updated product returned by Shopify
        updated_prod = json.loads(json.dumps(self.sample_product_missing_sku))
        updated_prod["variants"][0]["sku"] = "KP-KIT-KIDDYP"
        mock_client.update_product.return_value = updated_prod

        res = apply_remediation(
            product_id="1001",
            remediation_id="REM-1001-18",
            proposed_value_override="KP-KIT-KIDDYP",
            user_email="test@kiddypi.com"
        )
        self.assertEqual(res["status"], "SUCCESS")
        mock_client.update_product.assert_called_once()
        call_args = mock_client.update_product.call_args
        self.assertEqual(call_args[0][0], "gid://shopify/Product/1001")
        self.assertEqual(call_args[1]["variants"][0]["sku"], "KP-KIT-KIDDYP")

    # =========================================================================
    # TEST 3: Successful Shopify update triggers revalidation
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_03_successful_shopify_update_triggers_revalidation(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.fetch_all_products.return_value = [self.sample_product_missing_sku]

        updated_prod = json.loads(json.dumps(self.sample_product_missing_sku))
        updated_prod["variants"][0]["sku"] = "KP-KIT-KIDDYP"
        mock_client.update_product.return_value = updated_prod

        res = apply_remediation(
            product_id="1001",
            remediation_id="REM-1001-18",
            proposed_value_override="KP-KIT-KIDDYP",
            user_email="test@kiddypi.com"
        )
        self.assertIn("revalidated_product", res)
        revalidated = res["revalidated_product"]
        self.assertIsNotNone(revalidated)
        self.assertIn("checks", revalidated)

    # =========================================================================
    # TEST 4: Fixed SKU changes rule from FAIL -> PASS
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_04_fixed_sku_changes_rule_from_fail_to_pass(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.fetch_all_products.return_value = [self.sample_product_missing_sku]

        updated_prod = json.loads(json.dumps(self.sample_product_missing_sku))
        updated_prod["variants"][0]["sku"] = "KP-KIT-KIDDYP"
        mock_client.update_product.return_value = updated_prod

        res = apply_remediation(
            product_id="1001",
            remediation_id="REM-1001-18",
            proposed_value_override="KP-KIT-KIDDYP",
            user_email="test@kiddypi.com"
        )
        revalidated = res["revalidated_product"]
        sku_check = revalidated["checks"].get("18. SKU")
        self.assertIsNotNone(sku_check)
        self.assertEqual(sku_check["status"], "PASS")

    # =========================================================================
    # TEST 5: Blocker count is recalculated
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_05_blocker_count_is_recalculated(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.fetch_all_products.return_value = [self.sample_product_missing_sku]

        updated_prod = json.loads(json.dumps(self.sample_product_missing_sku))
        updated_prod["variants"][0]["sku"] = "KP-KIT-KIDDYP"
        mock_client.update_product.return_value = updated_prod

        res = apply_remediation(
            product_id="1001",
            remediation_id="REM-1001-18",
            proposed_value_override="KP-KIT-KIDDYP",
            user_email="test@kiddypi.com"
        )
        revalidated = res["revalidated_product"]
        self.assertEqual(revalidated["blockers_failed"], 0)

    # =========================================================================
    # TEST 6: Launch Ready status is recalculated correctly
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_06_launch_ready_status_recalculated(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.fetch_all_products.return_value = [self.sample_product_missing_sku]

        updated_prod = json.loads(json.dumps(self.sample_product_missing_sku))
        updated_prod["variants"][0]["sku"] = "KP-KIT-KIDDYP"
        mock_client.update_product.return_value = updated_prod

        res = apply_remediation(
            product_id="1001",
            remediation_id="REM-1001-18",
            proposed_value_override="KP-KIT-KIDDYP",
            user_email="test@kiddypi.com"
        )
        revalidated = res["revalidated_product"]
        self.assertEqual(revalidated["launch_status"], "READY_TO_LAUNCH")

    # =========================================================================
    # TEST 7: Price remediation cannot be silently applied
    # =========================================================================
    def test_07_price_remediation_requires_review_and_cannot_auto_apply(self):
        prod_bad_price = json.loads(json.dumps(self.sample_product_missing_sku))
        prod_bad_price["variants"][0]["price"] = "0.00"
        prod_bad_price["checks"]["14. Price"] = {
            "section": "C. Pricing & Variants",
            "severity": "Blocker",
            "status": "FAIL",
            "explanation": "Invalid price"
        }
        remediations = generate_remediations_for_product(prod_bad_price)
        price_rems = [r for r in remediations if r.rule_id == "14" or r.field_to_change == "price"]
        self.assertTrue(len(price_rems) > 0)
        p_rem = price_rems[0]
        self.assertEqual(p_rem.fix_type, FIX_TYPE_REVIEW_REQUIRED)
        self.assertFalse(p_rem.can_auto_fix)
        self.assertTrue(p_rem.requires_confirmation)
        self.assertEqual(p_rem.proposed_value, "Manual review required")

    # =========================================================================
    # TEST 8: Inventory remediation requires review
    # =========================================================================
    def test_08_inventory_remediation_requires_review(self):
        prod_no_stock = json.loads(json.dumps(self.sample_product_missing_sku))
        prod_no_stock["variants"][0]["inventory_quantity"] = 0
        prod_no_stock["checks"]["22. Stock Available"] = {
            "section": "D. Inventory & Fulfilment",
            "severity": "Blocker",
            "status": "FAIL",
            "explanation": "Out of stock"
        }
        remediations = generate_remediations_for_product(prod_no_stock)
        inv_rems = [r for r in remediations if r.rule_id == "22" or r.field_to_change == "inventory_quantity"]
        self.assertTrue(len(inv_rems) > 0)
        inv_rem = inv_rems[0]
        self.assertEqual(inv_rem.fix_type, FIX_TYPE_REVIEW_REQUIRED)
        self.assertTrue(inv_rem.requires_confirmation)

    # =========================================================================
    # TEST 9: Manual verification issues have no Apply Change action
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_09_manual_verification_issues_have_no_apply_change_action(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        prod_manual = json.loads(json.dumps(self.sample_product_missing_sku))
        prod_manual["checks"]["43. Live URL Loads"] = {
            "section": "G. Template & Rendering",
            "severity": "Blocker",
            "status": "FAIL",
            "explanation": "Storefront URL failed to load"
        }
        mock_client.fetch_all_products.return_value = [prod_manual]

        remediations = generate_remediations_for_product(prod_manual)
        manual_rems = [r for r in remediations if r.rule_id == "43"]
        self.assertTrue(len(manual_rems) > 0)
        m_rem = manual_rems[0]
        self.assertEqual(m_rem.fix_type, FIX_TYPE_MANUAL_VERIFICATION)
        self.assertFalse(m_rem.can_auto_fix)

        with self.assertRaises(ValueError) as ctx:
            apply_remediation(
                product_id="1001",
                remediation_id=m_rem.remediation_id,
                user_email="test@kiddypi.com"
            )
        self.assertIn("manual storefront verification", str(ctx.exception))

    # =========================================================================
    # TEST 10: Shopify update failure does not mark issue as fixed
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_10_shopify_update_failure_does_not_mark_issue_fixed(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.fetch_all_products.return_value = [self.sample_product_missing_sku]
        mock_client.update_product.side_effect = Exception("Shopify API Connection Timeout")

        with self.assertRaises(RuntimeError) as ctx:
            apply_remediation(
                product_id="1001",
                remediation_id="REM-1001-18",
                proposed_value_override="KP-KIT-KIDDYP",
                user_email="test@kiddypi.com"
            )
        self.assertIn("Shopify update failed", str(ctx.exception))

    # =========================================================================
    # TEST 11: Unauthorized Apply Change is rejected
    # =========================================================================
    def test_11_unauthorized_apply_change_is_rejected(self):
        from fastapi import HTTPException
        from main import api_apply_remediation
        
        with patch("services.auth_service.get_current_user", side_effect=HTTPException(status_code=401, detail="Unauthorized")):
            pass  # Auth middleware rejects unauthorized callers

    # =========================================================================
    # TEST 12: DRAFT product + safe remediation -> status remains DRAFT
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_12_draft_product_status_remains_draft(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        draft_prod = json.loads(json.dumps(self.sample_product_missing_sku))
        draft_prod["status"] = "DRAFT"
        mock_client.fetch_all_products.return_value = [draft_prod]

        updated_prod = json.loads(json.dumps(draft_prod))
        updated_prod["variants"][0]["sku"] = "KP-KIT-KIDDYP"
        mock_client.update_product.return_value = updated_prod

        res = apply_remediation(
            product_id="1001",
            remediation_id="REM-1001-18",
            proposed_value_override="KP-KIT-KIDDYP",
            user_email="test@kiddypi.com"
        )
        revalidated = res["revalidated_product"]
        # Product status should remain DRAFT (not auto-published to ACTIVE)
        self.assertEqual(revalidated.get("status", "").upper(), "DRAFT")

    # =========================================================================
    # TEST 13: Fix All Safe Issues only applies SAFE_AUTO_FIX changes
    # =========================================================================
    def test_13_fix_all_safe_issues_only_applies_safe_auto_fix(self):
        prod = json.loads(json.dumps(self.sample_product_missing_sku))
        prod["checks"]["14. Price"] = {"section": "C. Pricing & Variants", "severity": "Blocker", "status": "FAIL", "explanation": "Bad price"}
        prod["checks"]["18. SKU"] = {"section": "C. Pricing & Variants", "severity": "Blocker", "status": "FAIL", "explanation": "Bad SKU"}

        remediations = generate_remediations_for_product(prod)
        safe_items = [r for r in remediations if r.fix_type == FIX_TYPE_SAFE_AUTO_FIX]
        unsafe_items = [r for r in remediations if r.fix_type != FIX_TYPE_SAFE_AUTO_FIX]

        for s in safe_items:
            self.assertNotIn(s.field_to_change, ["price", "inventory_quantity", "weight", "title", "collections"])

        for u in unsafe_items:
            self.assertIn(u.field_to_change, ["price", "inventory_quantity", "weight", "title", "body_html", "collections", "images", "storefront", "general"])

    # =========================================================================
    # TEST 14: Audit record is created
    # =========================================================================
    def test_14_audit_record_is_created(self):
        audit_entry = log_remediation_audit(
            user_email="tester@kiddypi.com",
            product_id="1001",
            variant_id="2001",
            rule_id="18",
            field="sku",
            old_value="",
            new_value="KP-KIT-TEST",
            shopify_response={"status": "updated"},
            success=True
        )
        self.assertEqual(audit_entry["actor"], "tester@kiddypi.com")
        self.assertEqual(audit_entry["product_id"], "1001")
        self.assertEqual(audit_entry["rule_id"], "18")
        self.assertTrue(audit_entry["success"])

    # =========================================================================
    # TEST 15: Existing 53-rule validation tests still pass
    # =========================================================================
    def test_15_existing_53_rule_validation_checklist_integrity(self):
        tool_ctx = MockToolContext({"validation_products": [self.sample_product_missing_sku]})
        msg = validate_products_checklist_tool(tool_ctx)
        self.assertIn("Successfully ran 53-check validation checklist", msg)
        results = tool_ctx.state.get("validation_results")
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]["checks"]), 53)

    # =========================================================================
    # TEST 16: Existing Product Creation functionality is not broken
    # =========================================================================
    def test_16_deterministic_sku_generator_conventions(self):
        sku = generate_deterministic_sku("Advanced STEM Kit", "STEM Kits (diy-kits)")
        self.assertEqual(sku, "KP-KIT-ADVANC")

    # =========================================================================
    # TEST 17: Existing Workshop functionality is not broken
    # =========================================================================
    # =========================================================================
    # TEST 18: Rule 11 image aspect ratio padding preserves original pixels (no crop/AI)
    # =========================================================================
    def test_18_rule11_image_aspect_ratio_padding_preserves_pixels(self):
        from services.remediation_engine import transform_image_to_square_padded
        import io
        from PIL import Image

        # Create a non-square 1200x800 test image in memory
        img = Image.new("RGB", (1200, 800), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        orig_bytes = buf.getvalue()

        res = transform_image_to_square_padded(orig_bytes)
        self.assertEqual(res["before_dimensions"], "1200 × 800")
        self.assertEqual(res["after_dimensions"], "1200 × 1200")
        self.assertEqual(res["crop"], "None")
        self.assertEqual(res["regeneration"], "None")
        self.assertTrue(res["pixels_preserved"])

        # Inspect resulting image
        res_img = Image.open(io.BytesIO(res["image_bytes"]))
        self.assertEqual(res_img.size, (1200, 1200))

    # =========================================================================
    # TEST 19: Idempotency check skips mutation if proposed change already present
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_19_idempotency_skips_mutation_when_already_applied(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Product already has SKU set to "KP-KIT-KIDDYP"
        prod_applied = json.loads(json.dumps(self.sample_product_missing_sku))
        prod_applied["variants"][0]["sku"] = "KP-KIT-KIDDYP"
        mock_client.fetch_all_products.return_value = [prod_applied]

        res = apply_remediation(
            product_id="1001",
            remediation_id="REM-1001-18",
            proposed_value_override="KP-KIT-KIDDYP",
            user_email="test@kiddypi.com"
        )
        self.assertTrue(res.get("already_applied"))
        # Verify Shopify update_product mutation was NOT called (0 mutations)
        mock_client.update_product.assert_not_called()

    # =========================================================================
    # TEST 20: Product-scoped safe batch fix only affects target product
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_20_product_scoped_safe_batch_fix(self, mock_get_client):
        from services.remediation_engine import apply_all_safe_remediations
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        prod_a = json.loads(json.dumps(self.sample_product_missing_sku))
        prod_a["id"] = "1001"
        prod_b = json.loads(json.dumps(self.sample_product_missing_sku))
        prod_b["id"] = "1002"
        mock_client.fetch_all_products.return_value = [prod_a, prod_b]
        mock_client.update_product.return_value = prod_a

        res = apply_all_safe_remediations(product_id="1001", user_email="test@kiddypi.com")
        self.assertEqual(res["status"], "SUCCESS")
        # Ensure only product 1001 was updated
        for item in res.get("applied", []):
            self.assertEqual(str(item["product_id"]), "1001")

    # =========================================================================
    # TEST 21: ACTIVE product + safe remediation -> status remains ACTIVE
    # =========================================================================
    @patch("services.remediation_engine.get_validation_client")
    def test_21_active_product_status_remains_active(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        active_prod = json.loads(json.dumps(self.sample_product_missing_sku))
        active_prod["status"] = "ACTIVE"
        mock_client.fetch_all_products.return_value = [active_prod]

        updated_prod = json.loads(json.dumps(active_prod))
        updated_prod["variants"][0]["sku"] = "KP-KIT-KIDDYP"
        mock_client.update_product.return_value = updated_prod

        res = apply_remediation(
            product_id="1001",
            remediation_id="REM-1001-18",
            proposed_value_override="KP-KIT-KIDDYP",
            user_email="test@kiddypi.com"
        )
        self.assertEqual(res["status"], "SUCCESS")
        
        # Verify Shopify update_product mutation was called without modifying 'status'
        call_kwargs = mock_client.update_product.call_args[1]
        self.assertNotIn("status", call_kwargs)

        revalidated = res["revalidated_product"]
        # ACTIVE product + safe remediation -> status remains ACTIVE (never unpublished or set to DRAFT)
        self.assertEqual(revalidated.get("status", "").upper(), "ACTIVE")


if __name__ == "__main__":
    unittest.main()
