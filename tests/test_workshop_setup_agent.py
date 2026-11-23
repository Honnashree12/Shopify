"""
Unit and Integration Tests for Workshop Setup Agent and WorkshopService.
"""

import unittest
from unittest.mock import MagicMock
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.workshop_service import (
    WorkshopService,
    WorkshopInput,
    WorkshopWorkflowState,
    calculate_title_similarity,
    slugify
)


class TestWorkshopService(unittest.TestCase):

    def setUp(self):
        self.sample_input = WorkshopInput(
            name="Robotics STEM Workshop",
            description="Hands-on robotics building session for young innovators.",
            date="20 August 2026",
            time="10:00 AM",
            duration="2 Hours",
            venue="Tech Center",
            age_group="8-14",
            price=999.0,
            vendor="Custom Maker Brand",
            product_type="Workshop",
            topics=["Robotics", "Sensors", "Coding"],
            sales_team_email="sales@example.com",
            collection_name="Workshops"
        )

    def test_slugify_and_similarity(self):
        self.assertEqual(slugify("Robotics STEM Workshop!"), "robotics-stem-workshop")
        sim = calculate_title_similarity("Robotics STEM Workshop", "Robotics STEM Workshop")
        self.assertAlmostEqual(sim, 1.0)
        sim_diff = calculate_title_similarity("Robotics STEM Workshop", "T-Shirt Cotton Tee")
        self.assertLess(sim_diff, 0.3)

    def test_process_workshop_input(self):
        state = WorkshopService.process_workshop_input(self.sample_input)
        self.assertEqual(state.workshop_id, "robotics-stem-workshop")
        self.assertEqual(state.current_state, "DRAFT")

        invalid_input = WorkshopInput(name="", description="Test")
        invalid_state = WorkshopService.process_workshop_input(invalid_input)
        self.assertEqual(invalid_state.current_state, "INVALID_WORKSHOP_INPUT")

    def test_search_existing_shopify_product_zero_matches(self):
        state = WorkshopService.process_workshop_input(self.sample_input)
        mock_client = MagicMock()
        mock_client.get_product_by_sku.return_value = None
        mock_client.get_product_by_title.return_value = None

        state = WorkshopService.search_existing_shopify_product(state, mock_client)
        self.assertIsNone(state.matched_candidate_id)
        self.assertEqual(state.match_confidence, 0.0)

    def test_search_existing_shopify_product_single_strong_match(self):
        state = WorkshopService.process_workshop_input(self.sample_input)
        mock_client = MagicMock()
        mock_client.get_product_by_sku.return_value = None
        mock_client.get_product_by_title.return_value = {
            "id": 123456,
            "title": "Robotics STEM Workshop"
        }

        state = WorkshopService.search_existing_shopify_product(state, mock_client)
        self.assertEqual(state.matched_candidate_id, 123456)
        self.assertGreaterEqual(state.match_confidence, 0.90)

    def test_prepare_content_and_shopify_payload(self):
        state = WorkshopService.process_workshop_input(self.sample_input)
        state = WorkshopService.prepare_website_content(state)
        self.assertIsNotNone(state.website_content)
        self.assertIn("Robotics STEM Workshop", state.website_content.hero_headline)

        state = WorkshopService.prepare_shopify_payload(state)
        self.assertIsNotNone(state.proposed_shopify_payload)
        self.assertEqual(state.proposed_shopify_payload.status, "draft")  # Strict check
        self.assertEqual(state.proposed_shopify_payload.vendor, "Custom Maker Brand")

    def test_approval_boundary_enforcement(self):
        state = WorkshopService.process_workshop_input(self.sample_input)
        state = WorkshopService.prepare_website_content(state)
        state = WorkshopService.prepare_shopify_payload(state)

        # Attempting create_or_update before approval MUST raise PermissionError
        with self.assertRaises(PermissionError):
            WorkshopService.create_or_update_shopify_product(state)

        # Approve state
        state = WorkshopService.approve_workshop(state, "approver@example.com")
        self.assertEqual(state.approval_status, "APPROVED")
        self.assertEqual(state.current_state, "APPROVED")

    def test_post_approval_draft_creation_and_validation(self):
        state = WorkshopService.process_workshop_input(self.sample_input)
        state = WorkshopService.approve_workshop(state, "approver@example.com")
        state = WorkshopService.prepare_website_content(state)
        state = WorkshopService.prepare_shopify_payload(state)

        mock_client = MagicMock()
        mock_client.create_product.return_value = {
            "product": {
                "id": 998877,
                "title": "Robotics STEM Workshop",
                "variants": [{"id": 112233}]
            }
        }
        mock_client.get_or_create_custom_collection.return_value = 5544
        mock_client.add_product_to_collection.return_value = {}

        state = WorkshopService.create_or_update_shopify_product(state, mock_client)
        self.assertEqual(state.shopify_product_id, 998877)
        self.assertEqual(state.shopify_variant_id, 112233)
        self.assertEqual(state.shopify_product_status, "draft")  # Must be draft

        # Run validation with mock engine passing 0 blockers
        mock_validation_engine = MagicMock()
        mock_validation_engine.return_value = {
            "summary": {"blockers_failed": 0, "warnings_failed": 2}
        }

        state = WorkshopService.run_product_validation(state, mock_validation_engine)
        self.assertEqual(state.current_state, "LAUNCH_READY")
        self.assertEqual(state.shopify_product_status, "draft")  # MUST stay draft!

    def test_explicit_controlled_publishing(self):
        state = WorkshopWorkflowState(
            workshop_id="test-ws",
            current_state="LAUNCH_READY",
            input_data=self.sample_input,
            shopify_product_id=998877,
            shopify_variant_id=112233,
            approval_status="APPROVED"
        )

        mock_client = MagicMock()
        mock_client.update_product.return_value = {"product": {"id": 998877, "status": "draft"}}

        state = WorkshopService.publish_workshop_product(state, mock_client)
        self.assertEqual(state.current_state, "PUBLISHED")
        self.assertEqual(state.shopify_product_status, "draft")
        mock_client.update_product.assert_called_once_with(product_id=998877, status="draft", published=False)

    def test_complete_workshop_creation_with_all_extended_fields(self):
        from services.workshop_service import (
            MediaInput, ContentInput, ProjectInput, TimelineStepInput, InstructorInput, RegistrationInputData
        )
        complete_input = WorkshopInput(
            name="Advanced AI & Robotics Masterclass",
            description="Deep dive into AI vision, MicroPython, and obstacle avoiding rovers.",
            price=2999.0,
            sales_team_email="sales@kiddypi.com",
            media=MediaInput(
                hero_image="https://example.com/hero.png",
                gallery_images=["https://example.com/g1.png", "https://example.com/g2.png"],
                instructor_image="https://example.com/instructor.png",
                video_url="https://example.com/demo.mp4",
                brochure_pdf="https://example.com/brochure.pdf",
                registration_qr="https://example.com/qr.png"
            ),
            content=ContentInput(
                learning_outcomes=["Build IR sensors", "Program autonomous motors"],
                highlights=["Take home kit included", "Certificate of completion"],
                projects=[
                    ProjectInput(title="Obstacle Rover", description="Autonomous rover using IR sensors", technology="MicroPython")
                ],
                journey=[
                    TimelineStepInput(step=1, title="Assembly", description="Build rover frame", duration="30 mins"),
                    TimelineStepInput(step=2, title="Coding", description="Program sensor loop", duration="45 mins")
                ]
            ),
            instructor=InstructorInput(
                name="Dr. Sarah Connor",
                role="Lead AI Researcher",
                bio="10+ years experience in robotics education.",
                photo="https://example.com/instructor.png"
            ),
            registration=RegistrationInputData(
                url="https://example.com/register",
                button_text="Reserve Spot",
                seats_available=20,
                deadline="24 August 2026",
                contact_email="support@kiddypi.com",
                contact_phone="+91 98765 43210"
            )
        )

        state = WorkshopService.process_workshop_input(complete_input)
        self.assertEqual(state.current_state, "DRAFT")
        
        state = WorkshopService.prepare_website_content(state)
        self.assertIsNotNone(state.website_content)
        self.assertEqual(len(state.website_content.learning_outcomes), 2)
        self.assertEqual(len(state.website_content.projects), 1)
        self.assertEqual(len(state.website_content.journey), 2)
        self.assertEqual(state.website_content.instructor["name"], "Dr. Sarah Connor")
        self.assertEqual(state.website_content.media["hero_image"], "https://example.com/hero.png")

    def test_validation_rules(self):
        # 1. Missing name
        invalid_name = WorkshopInput(name="", description="Valid desc", price=100.0)
        self.assertIsNotNone(WorkshopService.validate_workshop_input(invalid_name))

        # 2. Missing description
        invalid_desc = WorkshopInput(name="Valid Name", description="", price=100.0)
        self.assertIsNotNone(WorkshopService.validate_workshop_input(invalid_desc))

        # 3. Negative price
        invalid_price = WorkshopInput(name="Valid Name", description="Valid desc", price=-50.0)
        self.assertIsNotNone(WorkshopService.validate_workshop_input(invalid_price))

        # 4. Invalid email format
        invalid_email = WorkshopInput(name="Valid Name", description="Valid desc", sales_team_email="not-an-email")
        self.assertIsNotNone(WorkshopService.validate_workshop_input(invalid_email))

        # 5. Invalid URL format
        from services.workshop_service import MediaInput
        invalid_url = WorkshopInput(
            name="Valid Name",
            description="Valid desc",
            media=MediaInput(hero_image="ftp://invalid-scheme.com/img.png")
        )
        self.assertIsNotNone(WorkshopService.validate_workshop_input(invalid_url))

        # 6. Invalid brochure file type
        invalid_pdf = WorkshopInput(
            name="Valid Name",
            description="Valid desc",
            media=MediaInput(brochure_pdf="file.exe")
        )
        self.assertIsNotNone(WorkshopService.validate_workshop_input(invalid_pdf))

    def test_special_characters_and_omitted_optional_fields(self):
        minimal_input = WorkshopInput(
            name="🤖 STEM Workshop: C++ & Python (2026 Ed.)",
            description="Hands-on session with special chars: <>&\"'!"
        )
        state = WorkshopService.process_workshop_input(minimal_input)
        self.assertEqual(state.current_state, "DRAFT")
        state = WorkshopService.prepare_website_content(state)
        self.assertIsNotNone(state.website_content)
        self.assertIn("🤖 STEM Workshop", state.website_content.hero_headline)

    def test_metafield_types_match_store_schema(self):
        from services.workshop_service import ContentInput, RegistrationInputData
        input_data = WorkshopInput(
            name="Metafield Type Test",
            description="Test description",
            content=ContentInput(
                subtitle="A multi line subtitle",
                course_introduction="Intro",
                course_core_concepts="Concepts"
            ),
            registration=RegistrationInputData(url="https://kiddypi.com/register")
        )
        state = WorkshopService.process_workshop_input(input_data)
        state = WorkshopService.prepare_shopify_payload(state)
        mf_dict = {f"{m['namespace']}.{m['key']}": m for m in state.proposed_shopify_payload.metafields}

        # Check subtitle type is multi_line_text_field
        self.assertEqual(mf_dict["custom.subtitle"]["type"], "multi_line_text_field")
        # Check course_introduction type is rich_text_field
        self.assertEqual(mf_dict["custom.course_introduction"]["type"], "rich_text_field")
        # Check course.external_url type is url
        self.assertEqual(mf_dict["course.external_url"]["type"], "url")


if __name__ == "__main__":
    unittest.main()

