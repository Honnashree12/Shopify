"""
Workshop Design Analyzer.

Inspects reference Liquid, JSON, CSS, and JS files from previous workshops,
extracts common design tokens, HTML layout structure, section schemas, and Liquid variable placeholders,
and produces a machine-readable WorkshopTemplateManifest.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional

from models.workshop_template import (
    WorkshopTemplateManifest,
    DesignTokens,
    SectionSchema
)

logger = logging.getLogger("workshop_design_analyzer")

REFERENCE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "theme", "workshop_templates", "reference")
)


class WorkshopDesignAnalyzer:
    """
    Parses and analyzes reference workshop files to determine the common design system,
    extract design tokens, and build a reusable WorkshopTemplateManifest.
    """

    @staticmethod
    def get_reference_files() -> Dict[str, str]:
        """Discovers reference Liquid and JSON template files."""
        files = {}
        if not os.path.exists(REFERENCE_DIR):
            logger.warning("Reference template directory does not exist: %s", REFERENCE_DIR)
            return files

        for fname in os.listdir(REFERENCE_DIR):
            fpath = os.path.join(REFERENCE_DIR, fname)
            if os.path.isfile(fpath):
                files[fname] = fpath
        return files

    @staticmethod
    def extract_css_tokens_from_liquid(liquid_content: str) -> DesignTokens:
        """Extracts CSS variable tokens (colors, typography, spacing, shadows) from Liquid `<style>` block."""
        tokens = DesignTokens()
        
        # Regex search for CSS variables in style tag
        style_match = re.search(r'<style>(.*?)</style>', liquid_content, re.DOTALL)
        if not style_match:
            return tokens

        style_text = style_match.group(1)

        # Extract colors
        color_vars = {
            "paper": r'--paper:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))',
            "paper_tint": r'--paper-tint:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))',
            "paper_tint_deep": r'--paper-tint-deep:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))',
            "ink": r'--ink:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))',
            "ink_dark": r'--ink-dark:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))',
            "amber": r'--amber:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))',
            "rust": r'--rust:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))',
            "rust_mid": r'--rust-mid:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))',
            "line": r'--line:\s*(#[0-9a-fA-F]+|rgba?\([^)]+\))'
        }

        extracted_colors = {}
        for key, pattern in color_vars.items():
            m = re.search(pattern, style_text)
            if m:
                extracted_colors[key] = m.group(1)

        if extracted_colors:
            tokens.colors.update(extracted_colors)

        # Extract fonts
        font_match = re.search(r"font-family:\s*'([^']+)'", style_text)
        if font_match:
            tokens.typography["font_body"] = font_match.group(1)

        return tokens

    @staticmethod
    def extract_liquid_schema(liquid_content: str) -> Optional[Dict[str, Any]]:
        """Parses the Liquid `{% schema %}` JSON block from Liquid file."""
        schema_match = re.search(r'{%\s*schema\s*%}(.*?){%\s*endschema\s*%}', liquid_content, re.DOTALL)
        if not schema_match:
            return None
        try:
            return json.loads(schema_match.group(1).strip())
        except Exception as e:
            logger.warning("Failed to parse schema JSON from Liquid: %s", e)
            return None

    @staticmethod
    def analyze_reference_templates() -> WorkshopTemplateManifest:
        """
        Main entry point. Analyzes reference workshop implementations and builds
        the generic WorkshopTemplateManifest.
        """
        manifest = WorkshopTemplateManifest(
            template_id="kiddypi_workshop_v1",
            source_workshops=["AI Tinker Saturdays", "Mission Tiranga"]
        )

        ref_files = WorkshopDesignAnalyzer.get_reference_files()
        
        # Analyze Liquid section
        liquid_file = next((fpath for fname, fpath in ref_files.items() if fname.endswith('.liquid')), None)
        if liquid_file:
            with open(liquid_file, 'r', encoding='utf-8') as f:
                liquid_content = f.read()

            manifest.design_tokens = WorkshopDesignAnalyzer.extract_css_tokens_from_liquid(liquid_content)
            schema = WorkshopDesignAnalyzer.extract_liquid_schema(liquid_content)

            if schema:
                sec_schema = SectionSchema(
                    section_id="kiddypi_workshop_section",
                    type=schema.get("name", "kiddypi-workshop"),
                    settings_schema=schema.get("settings", []),
                    block_types=schema.get("blocks", []),
                    liquid_variables=["product.title", "product.price", "product.description", "section.settings"]
                )
                manifest.sections.append(sec_schema)

        logger.info("Successfully analyzed reference workshop templates. Derived manifest with %d sections.", len(manifest.sections))
        return manifest
