"""
Comprehensive Automated Test Suite for MediaCompletenessValidationSkill.

Validates all 29 requirements and scenarios defined in the spec.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from services.media_completeness_validator import (
    MediaCompletenessValidationSkill,
    classify_product,
    is_combo_or_bundle_book,
)
from shopify_client import ShopifyAPIError


class TestMediaCompletenessValidationSkill(unittest.TestCase):

    def setUp(self):
        self.skill = MediaCompletenessValidationSkill()

    # 1. Complete STEM Kit
    def test_01_complete_stem_kit(self):
        product = {
            "id": 101, "title": "Robotics Explorer Kit", "status": "ACTIVE", "product_type": "STEM Kit",
            "collections": [{"title": "STEM Kits"}],
            "images": [
                {"id": 1, "alt": "hero main front", "url": "https://cdn.shopify.com/hero.jpg", "width": 1200, "height": 1200},
                {"id": 2, "alt": "kit box packaging", "url": "https://cdn.shopify.com/box.jpg", "width": 1200, "height": 1200},
                {"id": 3, "alt": "kit contents components laid out", "url": "https://cdn.shopify.com/contents.jpg", "width": 1200, "height": 1200},
                {"id": 4, "alt": "completed working project", "url": "https://cdn.shopify.com/completed.jpg", "width": 1200, "height": 1200},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "COMPLETE")
        self.assertEqual(res["summary"]["missing_media"], 0)

    # 2. STEM Kit missing Completed Project
    def test_02_stem_kit_missing_completed_project(self):
        product = {
            "id": 102, "title": "Bristle Bot Kit", "status": "ACTIVE", "product_type": "STEM Kit",
            "collections": [{"title": "STEM Kits"}],
            "images": [
                {"id": 1, "alt": "hero main front", "url": "https://cdn.shopify.com/hero.jpg", "width": 1200, "height": 1200},
                {"id": 2, "alt": "kit box packaging", "url": "https://cdn.shopify.com/box.jpg", "width": 1200, "height": 1200},
                {"id": 3, "alt": "kit contents components laid out", "url": "https://cdn.shopify.com/contents.jpg", "width": 1200, "height": 1200},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "INCOMPLETE")
        self.assertIn("Completed Project", res["missing_media_list"][0])

    # 3. STEM Kit wrong dimensions
    def test_03_stem_kit_wrong_dimensions(self):
        product = {
            "id": 103, "title": "Arduino Robotics Kit", "status": "ACTIVE", "product_type": "STEM Kit",
            "collections": [{"title": "STEM Kits"}],
            "images": [
                {"id": 1, "alt": "hero main front", "url": "https://cdn.shopify.com/hero.jpg", "width": 800, "height": 800},
                {"id": 2, "alt": "kit box packaging", "url": "https://cdn.shopify.com/box.jpg", "width": 1200, "height": 1200},
                {"id": 3, "alt": "kit contents components laid out", "url": "https://cdn.shopify.com/contents.jpg", "width": 1200, "height": 1200},
                {"id": 4, "alt": "completed working project", "url": "https://cdn.shopify.com/completed.jpg", "width": 1200, "height": 1200},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "INCOMPLETE")
        self.assertEqual(res["summary"]["invalid_media"], 1)

    # 4. Course with only Hero -> COMPLETE
    def test_04_course_with_only_hero(self):
        product = {
            "id": 104, "title": "Python Programming Course", "status": "ACTIVE", "product_type": "Course",
            "collections": [{"title": "Courses"}],
            "images": [{"id": 1, "alt": "course cover hero", "url": "https://cdn.shopify.com/cover.jpg", "width": 1200, "height": 800}]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "COMPLETE")

    # 5. Book with all required media -> COMPLETE
    def test_05_book_all_media_complete(self):
        product = {
            "id": 105, "title": "AI for Kids Book Vol 1", "status": "ACTIVE", "product_type": "Book",
            "collections": [{"title": "Books"}],
            "images": [
                {"id": 1, "alt": "book front cover", "url": "https://cdn.shopify.com/front.jpg", "width": 800, "height": 1200},
                {"id": 2, "alt": "book back cover", "url": "https://cdn.shopify.com/back.jpg", "width": 800, "height": 1200},
                {"id": 3, "alt": "sample interior page 1", "url": "https://cdn.shopify.com/page1.jpg", "width": 1200, "height": 900},
                {"id": 4, "alt": "sample interior page 2", "url": "https://cdn.shopify.com/page2.jpg", "width": 1200, "height": 900},
                {"id": 5, "alt": "book spine", "url": "https://cdn.shopify.com/spine.jpg", "width": 200, "height": 1200},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "COMPLETE")

    # 6. Book missing one interior page -> INCOMPLETE
    def test_06_book_missing_one_interior_page(self):
        product = {
            "id": 106, "title": "Computing Workbook 2", "status": "ACTIVE", "product_type": "Book",
            "collections": [{"title": "Books"}],
            "images": [
                {"id": 1, "alt": "book front cover", "url": "https://cdn.shopify.com/front.jpg", "width": 800, "height": 1200},
                {"id": 2, "alt": "book back cover", "url": "https://cdn.shopify.com/back.jpg", "width": 800, "height": 1200},
                {"id": 3, "alt": "sample interior page 1", "url": "https://cdn.shopify.com/page1.jpg", "width": 1200, "height": 900},
                {"id": 5, "alt": "book spine", "url": "https://cdn.shopify.com/spine.jpg", "width": 200, "height": 1200},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "INCOMPLETE")

    # 7. Book bundle requiring Bundle/Series Shot
    def test_07_book_bundle_requiring_bundle_shot(self):
        product = {
            "id": 107, "title": "STEM Book Series Bundle", "status": "ACTIVE", "product_type": "Book", "tags": "bundle",
            "collections": [{"title": "Books"}],
            "images": [
                {"id": 1, "alt": "book front cover", "url": "https://cdn.shopify.com/front.jpg", "width": 800, "height": 1200},
                {"id": 2, "alt": "book back cover", "url": "https://cdn.shopify.com/back.jpg", "width": 800, "height": 1200},
                {"id": 3, "alt": "sample interior page 1", "url": "https://cdn.shopify.com/page1.jpg", "width": 1200, "height": 900},
                {"id": 4, "alt": "sample interior page 2", "url": "https://cdn.shopify.com/page2.jpg", "width": 1200, "height": 900},
                {"id": 5, "alt": "book spine", "url": "https://cdn.shopify.com/spine.jpg", "width": 200, "height": 1200},
                {"id": 6, "alt": "bundle series shot", "url": "https://cdn.shopify.com/bundle.jpg", "width": 1200, "height": 900},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "COMPLETE")
        self.assertEqual(res["summary"]["total_required"], 5)

    # 8. Individual book without Bundle/Series Shot -> COMPLETE
    def test_08_individual_book_without_bundle_shot(self):
        product = {
            "id": 108, "title": "AI for Kids Vol 2", "status": "ACTIVE", "product_type": "Book",
            "collections": [{"title": "Books"}],
            "images": [
                {"id": 1, "alt": "book front cover", "url": "https://cdn.shopify.com/front.jpg", "width": 800, "height": 1200},
                {"id": 2, "alt": "book back cover", "url": "https://cdn.shopify.com/back.jpg", "width": 800, "height": 1200},
                {"id": 3, "alt": "sample interior page 1", "url": "https://cdn.shopify.com/page1.jpg", "width": 1200, "height": 900},
                {"id": 4, "alt": "sample interior page 2", "url": "https://cdn.shopify.com/page2.jpg", "width": 1200, "height": 900},
                {"id": 5, "alt": "book spine", "url": "https://cdn.shopify.com/spine.jpg", "width": 200, "height": 1200},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "COMPLETE")
        self.assertEqual(res["summary"]["total_required"], 4)

    # 9. Apparel complete
    def test_09_apparel_complete(self):
        product = {
            "id": 109, "title": "Engineer T-Shirt", "status": "ACTIVE", "product_type": "Apparel",
            "collections": [{"title": "Apparel"}],
            "images": [
                {"id": 1, "alt": "front-flat shirt", "url": "https://cdn.shopify.com/front-flat.jpg", "width": 1200, "height": 1200},
                {"id": 2, "alt": "back-flat shirt", "url": "https://cdn.shopify.com/back-flat.jpg", "width": 1200, "height": 1200},
                {"id": 3, "alt": "front-model model", "url": "https://cdn.shopify.com/front-model.jpg", "width": 1200, "height": 1500},
                {"id": 4, "alt": "back-model model", "url": "https://cdn.shopify.com/back-model.jpg", "width": 1200, "height": 1500},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "COMPLETE")

    # 10. Apparel missing Back On Model
    def test_10_apparel_missing_back_model(self):
        product = {
            "id": 110, "title": "Coder Hoodie", "status": "ACTIVE", "product_type": "Apparel",
            "collections": [{"title": "Apparel"}],
            "images": [
                {"id": 1, "alt": "front-flat shirt", "url": "https://cdn.shopify.com/front-flat.jpg", "width": 1200, "height": 1200},
                {"id": 2, "alt": "back-flat shirt", "url": "https://cdn.shopify.com/back-flat.jpg", "width": 1200, "height": 1200},
                {"id": 3, "alt": "front-model model", "url": "https://cdn.shopify.com/front-model.jpg", "width": 1200, "height": 1500},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "INCOMPLETE")
        self.assertIn("Back On Model", res["missing_media_list"][0])

    # 11. Electronics complete
    def test_11_electronics_complete(self):
        product = {
            "id": 111, "title": "DC Motor Module", "status": "ACTIVE", "product_type": "Electronics",
            "collections": [{"title": "Electronics"}],
            "images": [
                {"id": 1, "alt": "top-down view", "url": "https://cdn.shopify.com/top.jpg", "width": 1200, "height": 1200},
                {"id": 2, "alt": "45 angle view", "url": "https://cdn.shopify.com/angle.jpg", "width": 1200, "height": 1200},
                {"id": 3, "alt": "back additional view", "url": "https://cdn.shopify.com/back.jpg", "width": 1200, "height": 1200},
            ]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "COMPLETE")

    # 12. Workshop with only Hero/Banner -> COMPLETE
    def test_12_workshop_complete(self):
        product = {
            "id": 112, "title": "Robotics Explorer Workshop", "status": "ACTIVE", "product_type": "Workshop",
            "collections": [{"title": "Workshops"}],
            "images": [{"id": 1, "alt": "workshop hero banner", "url": "https://cdn.shopify.com/banner.jpg", "width": 1920, "height": 600}]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "COMPLETE")

    # 13. Unclassified product
    def test_13_unclassified_product(self):
        product = {"id": 113, "title": "Custom Unlabeled Gadget", "status": "DRAFT", "product_type": "", "collections": []}
        res = self.skill.audit_product(product)
        self.assertEqual(res["overall_status"], "UNCLASSIFIED")

    # 14. Shopify media API failure -> VALIDATION_ERROR
    @patch("shopify_client.get_validation_client")
    def test_14_shopify_api_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.fetch_all_products.side_effect = ShopifyAPIError("Shopify API 503 Service Unavailable")
        mock_get_client.return_value = mock_client
        res = self.skill.audit_store()
        self.assertEqual(res["overall_status"], "VALIDATION_ERROR")
        self.assertEqual(res["store_summary"]["validation_errors"], 1)

    # 15. Quantity validation
    def test_15_quantity_validation(self):
        product = {
            "id": 115, "title": "Sample Book", "status": "ACTIVE", "product_type": "Book",
            "images": [{"id": 1, "alt": "sample interior page 1", "url": "https://cdn.shopify.com/page1.jpg", "width": 1200, "height": 900}]
        }
        res = self.skill.audit_product(product)
        interior = next(item for item in res["checklist"] if item["key"] == "sample_interior")
        self.assertEqual(interior["found_quantity"], 1)
        self.assertEqual(interior["required_quantity"], 2)

    # 16. Dimension validation
    def test_16_dimension_validation(self):
        product = {
            "id": 116, "title": "Course Test", "status": "ACTIVE", "product_type": "Course",
            "images": [{"id": 1, "alt": "course cover hero", "url": "https://cdn.shopify.com/cover.jpg", "width": 500, "height": 500}]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["checklist"][0]["status"], "INVALID_DIMENSIONS")

    # 17. Format verification
    def test_17_format_verification(self):
        product = {
            "id": 117, "title": "Course Test", "status": "ACTIVE", "product_type": "Course",
            "images": [{"id": 1, "alt": "course cover hero", "url": "https://cdn.shopify.com/cover.jpg", "width": 1200, "height": 800}]
        }
        res = self.skill.audit_product(product)
        self.assertEqual(res["checklist"][0]["format_status"], "PASS")

    # 18. Image role matching
    def test_18_image_role_matching(self):
        product = {
            "id": 118, "title": "Microbit Maker Kit", "status": "ACTIVE", "product_type": "STEM Kit",
            "images": [{"id": 1, "alt": "kit box packaging", "url": "https://cdn.shopify.com/box.jpg", "width": 1200, "height": 1200}]
        }
        res = self.skill.audit_product(product)
        pkg = next(item for item in res["checklist"] if item["key"] == "packaging")
        self.assertEqual(pkg["status"], "PASS")

    # 19. Same image not incorrectly satisfying every role
    def test_19_same_image_not_satisfying_every_role(self):
        product = {
            "id": 119, "title": "Generic STEM Kit", "status": "ACTIVE", "product_type": "STEM Kit",
            "images": [{"id": 1, "alt": "generic kit image", "url": "https://cdn.shopify.com/generic.jpg", "width": 1200, "height": 1200}]
        }
        res = self.skill.audit_product(product)
        # Hero matched by position fallback, but packaging/contents/completed should be missing
        missing_count = sum(1 for item in res["checklist"] if item["status"] == "MISSING")
        self.assertGreaterEqual(missing_count, 3)

    # 20. Store-wide aggregation
    def test_20_storewide_aggregation(self):
        products = [
            {"id": 1, "title": "Course A", "status": "ACTIVE", "product_type": "Course", "images": [{"alt": "cover", "url": "a.jpg", "width": 1200, "height": 800}]},
            {"id": 2, "title": "Course B", "status": "ACTIVE", "product_type": "Course", "images": []}
        ]
        res = self.skill.audit_store(products)
        self.assertEqual(res["store_summary"]["total_products"], 2)
        self.assertEqual(res["store_summary"]["complete"], 1)
        self.assertEqual(res["store_summary"]["incomplete"], 1)

    # 21. Category summary
    def test_21_category_summary(self):
        products = [{"id": 1, "title": "Course A", "status": "ACTIVE", "product_type": "Course", "images": [{"alt": "cover", "url": "a.jpg", "width": 1200, "height": 800}]}]
        res = self.skill.audit_store(products)
        self.assertIn("Courses", res["categories"])
        self.assertEqual(res["categories"]["Courses"]["complete"], 1)

    # 22. Missing-media correction list
    def test_22_missing_media_correction_list(self):
        product = {"id": 122, "title": "Incomplete Course", "status": "ACTIVE", "product_type": "Course", "images": []}
        res = self.skill.audit_product(product)
        self.assertGreater(len(res["required_corrections"]), 0)

    # 23. Excel report generated (.xlsx)
    def test_23_excel_report_generated(self):
        products = [{"id": 1, "title": "Course A", "status": "ACTIVE", "product_type": "Course", "images": [{"alt": "cover", "url": "a.jpg", "width": 1200, "height": 800}]}]
        audit = self.skill.audit_store(products)
        reports = self.skill.generate_reports(audit, output_dir="scratch/test_reports")
        self.assertTrue(os.path.exists(reports["excel_path"]))
        self.assertTrue(reports["excel_path"].endswith(".xlsx"))

    # 24. CSV report generated (.csv)
    def test_24_csv_report_generated(self):
        products = [{"id": 1, "title": "Course A", "status": "ACTIVE", "product_type": "Course", "images": [{"alt": "cover", "url": "a.jpg", "width": 1200, "height": 800}]}]
        audit = self.skill.audit_store(products)
        reports = self.skill.generate_reports(audit, output_dir="scratch/test_reports")
        self.assertTrue(os.path.exists(reports["csv_path"]))

    # 25. PDF report generated (.pdf)
    def test_25_pdf_report_generated(self):
        products = [{"id": 1, "title": "Course A", "status": "ACTIVE", "product_type": "Course", "images": [{"alt": "cover", "url": "a.jpg", "width": 1200, "height": 800}]}]
        audit = self.skill.audit_store(products)
        reports = self.skill.generate_reports(audit, output_dir="scratch/test_reports")
        self.assertTrue(os.path.exists(reports["pdf_path"]))

    # 26. Report contains all audited ACTIVE products
    def test_26_report_contains_all_products(self):
        products = [
            {"id": 1, "title": "Item 1", "status": "ACTIVE", "product_type": "Course", "images": []},
            {"id": 2, "title": "Item 2", "status": "ACTIVE", "product_type": "Workshop", "images": []}
        ]
        audit = self.skill.audit_store(products)
        self.assertEqual(len(audit["products"]), 2)

    # 27. Report contains exact missing media
    def test_27_report_contains_exact_missing_media(self):
        product = {"id": 127, "title": "Missing Media Item", "status": "ACTIVE", "product_type": "Course", "images": []}
        res = self.skill.audit_product(product)
        self.assertEqual(res["missing_media_list"][0], "Course Cover / Hero (1 required)")

    # 28. Report contains invalid dimensions
    def test_28_report_contains_invalid_dimensions(self):
        product = {"id": 128, "title": "Invalid Dim Item", "status": "ACTIVE", "product_type": "Course", "images": [{"alt": "cover", "url": "a.jpg", "width": 100, "height": 100}]}
        res = self.skill.audit_product(product)
        self.assertIn("100 × 100", res["invalid_media_list"][0])

    # 29. Read-only behavior — zero Shopify mutations
    def test_29_readonly_behavior_zero_mutations(self):
        with patch("shopify_client.ShopifyClient.create_product") as mock_create, \
             patch("shopify_client.ShopifyClient.update_product") as mock_update:
            product = {"id": 129, "title": "Course A", "status": "ACTIVE", "product_type": "Course", "images": []}
            self.skill.audit_product(product)
            mock_create.assert_not_called()
            mock_update.assert_not_called()

    # 30. ACTIVE product scope filtering — DRAFT and ARCHIVED products excluded
    def test_30_active_products_only_filtering(self):
        products = [
            {"id": 1, "title": "Active Course", "status": "ACTIVE", "product_type": "Course", "images": []},
            {"id": 2, "title": "Draft Book", "status": "DRAFT", "product_type": "Book", "images": []},
            {"id": 3, "title": "Archived Kit", "status": "ARCHIVED", "product_type": "STEM Kit", "images": []},
        ]
        audit = self.skill.audit_store(products)
        self.assertEqual(audit["store_summary"]["total_fetched_products"], 3)
        self.assertEqual(audit["store_summary"]["active_products_audited"], 1)
        self.assertEqual(audit["store_summary"]["draft_products_excluded"], 1)
        self.assertEqual(audit["store_summary"]["archived_products_excluded"], 1)
        self.assertEqual(len(audit["products"]), 1)
        self.assertEqual(audit["products"][0]["product_title"], "Active Course")

    # 31. DRAFT and ARCHIVED products do not appear in Action Required
    def test_31_draft_and_archived_excluded_from_action_required(self):
        products = [
            {"id": 1, "title": "Incomplete Active Course", "status": "ACTIVE", "product_type": "Course", "images": []},
            {"id": 2, "title": "Incomplete Draft Book", "status": "DRAFT", "product_type": "Book", "images": []},
        ]
        audit = self.skill.audit_store(products)
        self.assertEqual(len(audit["action_required"]), 1)
        self.assertEqual(audit["action_required"][0]["product_title"], "Incomplete Active Course")

    # 32. Scope metrics sum validation
    def test_32_scope_metrics_sum_validation(self):
        products = [
            {"id": 1, "title": "Course 1", "status": "ACTIVE", "product_type": "Course", "images": [{"alt": "cover", "url": "a.jpg", "width": 1200, "height": 800}]},
            {"id": 2, "title": "Course 2", "status": "ACTIVE", "product_type": "Course", "images": []},
            {"id": 3, "title": "Draft 1", "status": "DRAFT", "product_type": "Course", "images": []},
        ]
        audit = self.skill.audit_store(products)
        summ = audit["store_summary"]
        self.assertEqual(summ["complete"] + summ["incomplete"] + summ["unclassified"] + summ["validation_errors"], summ["active_products_audited"])


if __name__ == "__main__":
    unittest.main()
