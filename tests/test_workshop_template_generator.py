"""
Unit tests for WorkshopTemplateGenerator.
"""

import pytest
from services.workshop_service import WorkshopInput
from services.workshop_template_generator import WorkshopTemplateGenerator


def test_generate_json_template_generic():
    inp = WorkshopInput(
        name="AI Robotics Challenge",
        description="Hands-on robotics workshop for young innovators.",
        date="15 October 2026",
        time="10:00 AM – 1:00 PM",
        duration="3 Hours",
        venue="KiddyPi Maker Space",
        age_group="10-16 Years",
        price=799.0,
        topics=["Robotics", "Sensors", "Python Coding"]
    )

    json_template = WorkshopTemplateGenerator.generate_json_template(inp, "kiddypi-workshop-ai-robotics-challenge")
    assert "sections" in json_template
    assert "main" in json_template["sections"]

    main_settings = json_template["sections"]["main"]["settings"]
    assert main_settings["hero_title"] == "AI"
    assert main_settings["hero_title_accent"] == "Robotics Challenge"
    assert main_settings["event_date"] == "15 October 2026"
    assert main_settings["venue"] == "KiddyPi Maker Space"

    # Verify no hardcoded template titles
    assert "AI Tinker Saturdays" not in json_template["sections"]["main"]["settings"]["hero_title"]


def test_generate_liquid_section_tokens():
    inp = WorkshopInput(
        name="Python Game Development",
        description="Learn Pygame and game logic.",
        price=499.0,
        topics=["Pygame", "Logic", "Graphics"]
    )

    liquid_code, json_template, flags = WorkshopTemplateGenerator.generate_workshop_template_files(inp)
    assert "--paper:" in liquid_code
    assert "--rust:" in liquid_code
    assert "Poppins" in liquid_code
    assert "{% schema %}" in liquid_code
    assert isinstance(json_template, dict)
