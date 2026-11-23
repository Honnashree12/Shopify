"""
Unit tests for WorkshopDesignAnalyzer.
"""

import pytest
from services.workshop_design_analyzer import WorkshopDesignAnalyzer
from models.workshop_template import WorkshopTemplateManifest, DesignTokens


def test_analyze_reference_templates():
    manifest = WorkshopDesignAnalyzer.analyze_reference_templates()
    assert isinstance(manifest, WorkshopTemplateManifest)
    assert manifest.template_id == "kiddypi_workshop_v1"
    assert "AI Tinker Saturdays" in manifest.source_workshops
    assert isinstance(manifest.design_tokens, DesignTokens)


def test_extract_css_tokens_from_liquid():
    sample_liquid = """
    <style>
      #ai-tinker-123 {
        --paper: #FFFFFF;
        --ink: #2B1A0E;
        --amber: #F3922C;
        --rust: #DA6A14;
        font-family: 'Poppins', sans-serif;
      }
    </style>
    """
    tokens = WorkshopDesignAnalyzer.extract_css_tokens_from_liquid(sample_liquid)
    assert tokens.colors["paper"] == "#FFFFFF"
    assert tokens.colors["amber"] == "#F3922C"
    assert tokens.colors["rust"] == "#DA6A14"
    assert tokens.typography["font_body"] == "Poppins"
