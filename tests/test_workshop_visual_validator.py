"""
Unit tests for WorkshopVisualValidator.
"""

import pytest
from services.workshop_service import WorkshopInput
from services.workshop_template_generator import WorkshopTemplateGenerator
from services.workshop_visual_validator import WorkshopVisualValidator
from models.workshop_template import VisualConsistencyReport


def test_visual_consistency_audit():
    inp = WorkshopInput(
        name="Space Communication Workshop",
        description="Build satellite radio communication models.",
        date="20 November 2026",
        price=999.0,
        topics=["Satellites", "Radio", "Telemetry"]
    )

    liquid_code, json_template, _ = WorkshopTemplateGenerator.generate_workshop_template_files(inp)
    report = WorkshopVisualValidator.audit_visual_consistency(liquid_code, json_template)

    assert isinstance(report, VisualConsistencyReport)
    assert report.match_percentage >= 80.0
    assert report.status == "DESIGN_MATCH"
    assert len(report.checks_passed) > 0
