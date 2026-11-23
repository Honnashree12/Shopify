"""
Unit Tests for PDF Export Service and API Endpoints.
"""

import os
import json
import unittest
from unittest.mock import MagicMock, patch

from services.pdf_export_service import generate_validation_pdf_report


class TestPdfExportService(unittest.TestCase):

    def setUp(self):
        self.sample_products = [
            {
                "product_name": "KiddyPi Micro:bit + Scratch Combo",
                "product_id": "gid://shopify/Product/15792040411296",
                "handle": "kiddypi-microbit-scratch-combo",
                "mvp_category": "Combo Products",
                "score": 91.5,
                "launch_status": "LAUNCH_BLOCKED",
                "blockers_passed": 30,
                "blockers_failed": 1,
                "warnings_count": 7,
                "checks": {
                    "24. Requires Shipping Flag": {
                        "check_id": 24,
                        "check_name": "24. Requires Shipping Flag",
                        "section": "D. Inventory & Fulfilment",
                        "severity": "Blocker",
                        "final_result": "FAIL",
                        "explanation": "Requires shipping flag mismatched on 1 variant(s)."
                    },
                    "02. Title Formula": {
                        "check_id": 2,
                        "check_name": "02. Title Formula",
                        "section": "A. Content",
                        "severity": "Warning",
                        "final_result": "WARNING",
                        "explanation": "Title does not match standard MVP formula."
                    }
                }
            },
            {
                "product_name": "KiddyPi Door Alarm Kit",
                "product_id": "gid://shopify/Product/15774294999200",
                "handle": "kiddypi-door-alarm-kit",
                "mvp_category": "STEM Kits (diy-kits)",
                "score": 100.0,
                "launch_status": "READY_TO_LAUNCH",
                "blockers_passed": 31,
                "blockers_failed": 0,
                "warnings_count": 0,
                "checks": {
                    "01. Product Title": {
                        "check_id": 1,
                        "check_name": "01. Product Title",
                        "section": "A. Content",
                        "severity": "Blocker",
                        "final_result": "PASS",
                        "explanation": "Product title is present."
                    }
                }
            }
        ]

    def test_01_pdf_generation_all_products(self):
        pdf_bytes = generate_validation_pdf_report(
            products=self.sample_products,
            assignee_name="Rachana"
        )
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_02_pdf_generation_selected_products_only(self):
        pdf_bytes = generate_validation_pdf_report(
            products=self.sample_products,
            selected_identifiers=["15792040411296"],
            assignee_name="Rachana"
        )
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_03_pdf_content_structure(self):
        # Generate file to check non-empty PDF structure
        out_file = "outputs/test_audit_report.pdf"
        os.makedirs("outputs", exist_ok=True)
        pdf_bytes = generate_validation_pdf_report(
            products=self.sample_products,
            selected_identifiers=["15792040411296"],
            assignee_name="Rachana",
            output_filename_or_stream=out_file
        )
        self.assertTrue(os.path.exists(out_file))
        self.assertGreater(os.path.getsize(out_file), 1000)

    def test_04_no_shopify_mutation_during_pdf_export(self):
        with patch("shopify_client.ShopifyClient") as mock_client:
            pdf_bytes = generate_validation_pdf_report(
                products=self.sample_products,
                assignee_name="Rachana"
            )
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))
            mock_client.return_value.update_product.assert_not_called()
            mock_client.return_value.create_product.assert_not_called()
            mock_client.return_value.delete_product.assert_not_called()


if __name__ == "__main__":
    unittest.main()
