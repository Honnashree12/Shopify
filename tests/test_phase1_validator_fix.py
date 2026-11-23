import unittest
from agents.product_validation_agent import validate_products_checklist_tool

class MockToolContext:
    def __init__(self, state):
        self.state = state

class TestPhase1ValidatorFix(unittest.TestCase):

    def _create_sample_product(self, status="ACTIVE", title="Test Sample Product"):
        return {
            "id": "gid://shopify/Product/99999",
            "title": title,
            "body_html": "<p>Sample product description with detailed specs.</p>",
            "vendor": "KiddyPi",
            "product_type": "STEM Kit",
            "status": status,
            "handle": "test-sample-product",
            "tags": ["STEM", "Kits"],
            "seo_title": "Test Sample Product | STEM Kit",
            "seo_description": "Sample SEO description that is between 120 and 155 characters long for optimal search listing performance.",
            "collections": ["STEM Kits"],
            "images": [
                {"id": "gid://shopify/ProductImage/1", "url": "https://cdn.shopify.com/img.jpg", "altText": "Sample Alt Text", "width": 1000, "height": 1000}
            ],
            "variants": [
                {
                    "id": "gid://shopify/ProductVariant/1",
                    "title": "Default Title",
                    "sku": "KP-TEST-001",
                    "price": "999.00",
                    "compareAtPrice": "1299.00",
                    "inventoryQuantity": 25,
                    "weight": 0.5,
                    "weightUnit": "KILOGRAMS",
                    "requiresShipping": True,
                    "taxable": True,
                    "barcode": "1234567890123",
                    "countryCode": "IN",
                    "inventoryItem": {"tracked": True}
                }
            ]
        }

    # ----------------------------------------------------
    # TEST GROUP 1 — DRAFT PRODUCTS
    # ----------------------------------------------------
    def test_draft_product_check_50_fails(self):
        """Test 1: DRAFT product must FAIL Check 50 (Published to Social Channels)."""
        draft_product = self._create_sample_product(status="DRAFT", title="Draft STEM Kit")
        ctx = MockToolContext({"validation_products": [draft_product]})
        validate_products_checklist_tool(ctx)

        results = ctx.state.get("validation_results", [])
        self.assertEqual(len(results), 1)
        chk_50 = results[0]["checks"].get("50. Published to Social Channels")
        self.assertIsNotNone(chk_50)
        self.assertEqual(chk_50["status"], "FAIL")

    def test_draft_product_check_51_fails(self):
        """Test 2: DRAFT product must FAIL Check 51 (In WhatsApp Catalogue)."""
        draft_product = self._create_sample_product(status="DRAFT", title="Draft STEM Kit")
        ctx = MockToolContext({"validation_products": [draft_product]})
        validate_products_checklist_tool(ctx)

        results = ctx.state.get("validation_results", [])
        self.assertEqual(len(results), 1)
        chk_51 = results[0]["checks"].get("51. In WhatsApp Catalogue")
        self.assertIsNotNone(chk_51)
        self.assertEqual(chk_51["status"], "FAIL")

    def test_draft_product_both_checks_50_and_51_fail(self):
        """Test 3: DRAFT product must FAIL both Check 50 and Check 51."""
        draft_product = self._create_sample_product(status="DRAFT", title="Draft STEM Kit")
        ctx = MockToolContext({"validation_products": [draft_product]})
        validate_products_checklist_tool(ctx)

        results = ctx.state.get("validation_results", [])
        self.assertEqual(len(results), 1)
        chk_50 = results[0]["checks"].get("50. Published to Social Channels")
        chk_51 = results[0]["checks"].get("51. In WhatsApp Catalogue")
        self.assertEqual(chk_50["status"], "FAIL")
        self.assertEqual(chk_51["status"], "FAIL")

    # ----------------------------------------------------
    # TEST GROUP 2 — ACTIVE PRODUCTS
    # ----------------------------------------------------
    def test_active_product_check_50_passes(self):
        """Test 4: ACTIVE product must PASS Check 50."""
        active_product = self._create_sample_product(status="ACTIVE", title="Active STEM Kit")
        ctx = MockToolContext({"validation_products": [active_product]})
        validate_products_checklist_tool(ctx)

        results = ctx.state.get("validation_results", [])
        chk_50 = results[0]["checks"].get("50. Published to Social Channels")
        self.assertEqual(chk_50["status"], "PASS")

    def test_inactive_product_check_50_fails(self):
        """Test 5: Non-ACTIVE status must FAIL Check 50."""
        archived_product = self._create_sample_product(status="ARCHIVED", title="Archived Kit")
        ctx = MockToolContext({"validation_products": [archived_product]})
        validate_products_checklist_tool(ctx)

        results = ctx.state.get("validation_results", [])
        chk_50 = results[0]["checks"].get("50. Published to Social Channels")
        self.assertEqual(chk_50["status"], "FAIL")

    def test_active_product_check_51_passes(self):
        """Test 6: ACTIVE product must PASS Check 51."""
        active_product = self._create_sample_product(status="ACTIVE", title="Active STEM Kit")
        ctx = MockToolContext({"validation_products": [active_product]})
        validate_products_checklist_tool(ctx)

        results = ctx.state.get("validation_results", [])
        chk_51 = results[0]["checks"].get("51. In WhatsApp Catalogue")
        self.assertEqual(chk_51["status"], "PASS")

    def test_inactive_product_check_51_fails(self):
        """Test 7: Non-ACTIVE status must FAIL Check 51."""
        archived_product = self._create_sample_product(status="ARCHIVED", title="Archived Kit")
        ctx = MockToolContext({"validation_products": [archived_product]})
        validate_products_checklist_tool(ctx)

        results = ctx.state.get("validation_results", [])
        chk_51 = results[0]["checks"].get("51. In WhatsApp Catalogue")
        self.assertEqual(chk_51["status"], "FAIL")

    # ----------------------------------------------------
    # TEST GROUP 3 — VALIDATOR STRUCTURE REGRESSION
    # ----------------------------------------------------
    def test_validator_53_check_matrix_integrity(self):
        """Test 8: Verify 53 checks, 31 blockers, 22 warnings structure integrity."""
        product = self._create_sample_product(status="ACTIVE")
        ctx = MockToolContext({"validation_products": [product]})
        validate_products_checklist_tool(ctx)

        results = ctx.state.get("validation_results", [])
        checks = results[0]["checks"]
        
        self.assertEqual(len(checks), 53)
        blockers = [c for c in checks.values() if c["severity"] == "Blocker"]
        warnings = [c for c in checks.values() if c["severity"] == "Warning"]
        
        self.assertEqual(len(blockers), 31)
        self.assertEqual(len(warnings), 22)


if __name__ == "__main__":
    unittest.main()
