"""
Regression test suite for Workshop Approval workflow and Shopify integration.
Tests requirements A through H:
- Successful approval creates draft and updates database.
- Shopify failure returns HTTP error, prevents false approval in database.
- Shopify product remains DRAFT after approval.
- Publish remains blocked until LAUNCH_READY.
- Verifies no calls to ShopifyClient.from_env().
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import sqlite3
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from data.database import init_db, create_workshop, get_workshop
from services.workshop_service import WorkshopService, WorkshopWorkflowState

client = TestClient(app)

# Dummy authorization headers for APPROVER role
HEADERS = {
    "Authorization": "Bearer mock-approver-token"
}


class TestWorkshopApprovalRegression(unittest.TestCase):

    def setUp(self):
        init_db(clear=True)
        self.workshop_data = {
            "id": "regr-workshop-101",
            "name": "Robotics STEM Workshop",
            "description": "Hands-on robotics building session.",
            "date": "20 August 2026",
            "time": "10:00 AM",
            "duration": "2 Hours",
            "venue": "Tech Center",
            "age_group": "8-14",
            "price": 999.0,
            "topics": ["Robotics", "Coding"],
            "poster_path": None,
            "video_url": None,
            "sales_team_email": "sales@example.com",
            "status": "pending_approval"
        }
        create_workshop(self.workshop_data)

    def test_A_successful_approval_flow(self):
        """A. Successful approval: approval -> Shopify draft -> validation -> DB update."""
        mock_shopify = MagicMock()
        mock_shopify.create_product.return_value = {
            "product": {
                "id": 887766,
                "title": "Robotics STEM Workshop",
                "variants": [{"id": 554433}],
                "status": "draft"
            }
        }
        mock_shopify.get_or_create_custom_collection.return_value = 1111
        mock_shopify.add_product_to_collection.return_value = {}

        mock_validation = MagicMock()
        mock_validation.return_value = {
            "summary": {"blockers_failed": 0, "warnings_failed": 1}
        }

        with patch("shopify_client.get_validation_client", return_value=mock_shopify), \
             patch("services.workshop_service.get_validation_client", return_value=mock_shopify), \
             patch("services.workshop_service.WorkshopService.run_product_validation") as mock_val_step:

            # Setup run_product_validation behavior to return LAUNCH_READY
            def mock_val_side_effect(state):
                state.current_state = "LAUNCH_READY"
                state.shopify_product_status = "draft"
                return state
            mock_val_step.side_effect = mock_val_side_effect

            response = client.post("/api/workshops/regr-workshop-101/approve", headers=HEADERS)
            self.assertEqual(response.status_code, 200)
            res_json = response.json()
            self.assertEqual(res_json["status"], "success")
            self.assertEqual(res_json["shopify_product_id"], 887766)
            self.assertEqual(res_json["shopify_variant_id"], 554433)

            # DB check: should be updated to status="approved" and shopify_product_id=887766
            w = get_workshop("regr-workshop-101")
            self.assertEqual(w["status"], "approved")
            self.assertEqual(w["shopify_product_id"], 887766)

    def test_B_shopify_client_failure_returns_http_error(self):
        """B. Shopify client failure: approval -> Shopify error -> HTTP error -> DB not approved."""
        with patch("shopify_client.get_validation_client", side_effect=Exception("Shopify Auth Failed")), \
             patch("services.workshop_service.get_validation_client", side_effect=Exception("Shopify Auth Failed")):
            response = client.post("/api/workshops/regr-workshop-101/approve", headers=HEADERS)
            # Must return non-200 (e.g. 502 or 500)
            self.assertNotEqual(response.status_code, 200)
            self.assertIn("detail", response.json())

            # DB check: workshop status MUST NOT falsely become approved
            w = get_workshop("regr-workshop-101")
            self.assertNotEqual(w["status"], "approved")
            self.assertIsNone(w.get("shopify_product_id"))

    def test_C_shopify_product_remains_draft_after_approval(self):
        """C. Shopify product remains DRAFT after approval."""
        mock_shopify = MagicMock()
        mock_shopify.create_product.return_value = {
            "product": {
                "id": 887766,
                "title": "Robotics STEM Workshop",
                "variants": [{"id": 554433}],
                "status": "draft"
            }
        }
        with patch("shopify_client.get_validation_client", return_value=mock_shopify), \
             patch("services.workshop_service.get_validation_client", return_value=mock_shopify), \
             patch("services.unified_validation_engine.run_unified_validation_engine", return_value={"summary": {"blockers_failed": 0}}):
            response = client.post("/api/workshops/regr-workshop-101/approve", headers=HEADERS)
            self.assertEqual(response.status_code, 200)
            res_json = response.json()

            # Product status must be draft
            self.assertEqual(res_json["product_status"], "draft")
            # Verify update_product with 'active' was NOT called during approval
            for call in mock_shopify.update_product.call_args_list:
                self.assertNotEqual(call.kwargs.get("status"), "active")

    def test_D_publish_blocked_until_launch_ready(self):
        """D. Publish is still blocked until state is LAUNCH_READY."""
        from services.workshop_service import WorkshopInput
        sample_inp = WorkshopInput(name="Test", description="Test")
        state = WorkshopWorkflowState(
            workshop_id="regr-workshop-101",
            current_state="PENDING_APPROVAL",
            shopify_product_id=887766,
            input_data=sample_inp
        )
        mock_shopify = MagicMock()
        with self.assertRaises(ValueError) as ctx:
            WorkshopService.publish_workshop_product(state, mock_shopify)
        self.assertIn("Must be LAUNCH_READY", str(ctx.exception))

    def test_H_no_remaining_calls_to_from_env(self):
        """H. Verify there is no call to ShopifyClient.from_env() in the codebase."""
        import glob
        code_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        python_files = glob.glob(os.path.join(code_dir, "**", "*.py"), recursive=True)
        
        found_matches = []
        for pf in python_files:
            # Skip test runner or scratch files if any
            if "scratch" in pf or "test_workshop_approval_regression.py" in pf:
                continue
            with open(pf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "ShopifyClient.from_env" in content:
                    found_matches.append(pf)
        
        self.assertEqual(found_matches, [], f"Found unexpected calls to ShopifyClient.from_env() in: {found_matches}")


if __name__ == "__main__":
    unittest.main()
