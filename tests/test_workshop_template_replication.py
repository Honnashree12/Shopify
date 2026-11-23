"""
End-to-End Integration tests for Workshop Design Template Replication Engine.
"""

import pytest
from services.workshop_service import WorkshopService, WorkshopInput
from services.workshop_template_service import WorkshopTemplateService


def test_template_replication_end_to_end():
    inp = WorkshopInput(
        name="Future AI Inventors Workshop",
        description="Learn neural network basics and vision models.",
        date="05 December 2026",
        time="3:00 PM – 5:00 PM",
        duration="2 Hours",
        venue="KiddyPi Jayanagar Lab",
        age_group="12-18 Years",
        price=650.0,
        topics=["Neural Networks", "Computer Vision", "Ethics in AI"]
    )

    # Test WorkshopTemplateService directly
    result = WorkshopTemplateService.process_template_replication(inp)
    assert result["visual_score"] >= 80.0
    assert result["status"] == "DESIGN_MATCH"
    assert "sections/kiddypi-workshop-future-ai-inventors-workshop.liquid" in result["liquid_filename"]
    assert "templates/product.future-ai-inventors-workshop.json" in result["json_filename"]

    # Test full WorkshopService pipeline integration
    state = WorkshopService.process_workshop_input(inp)
    state = WorkshopService.understand_workshop_information(state)
    state = WorkshopService.check_assets(state)
    state = WorkshopService.prepare_website_content(state)
    state = WorkshopService.prepare_template_generation(state)
    state = WorkshopService.prepare_shopify_payload(state)
    state = WorkshopService.prepare_registration_config(state)

    # Verify state hit PENDING_APPROVAL boundary safely
    assert state.current_state == "PENDING_APPROVAL"
    assert state.approval_status == "PENDING"
    assert state.generated_liquid_section is not None
    assert state.generated_json_template is not None
    assert state.visual_consistency_report is not None
    assert state.visual_consistency_report["match_percentage"] >= 80.0

    # Verify no hardcoded values in generated payload
    assert "Future AI Inventors Workshop" in state.proposed_shopify_payload.title
    assert state.proposed_shopify_payload.status == "draft"
