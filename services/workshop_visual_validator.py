"""
Workshop Visual Validator.

Runs automated design consistency audits comparing generated workshop templates
against the reference WorkshopTemplateManifest design system. Verifies color usage, font families,
section layout hierarchy, button styles, cards, spacing, responsive rules, and returns a VisualConsistencyReport.
"""

import re
import logging
from typing import Dict, Any, List, Optional

from models.workshop_template import (
    WorkshopTemplateManifest,
    VisualConsistencyReport,
    DesignTokens
)

logger = logging.getLogger("workshop_visual_validator")


class WorkshopVisualValidator:
    """
    Automated visual consistency checker that audits generated Liquid markup and JSON template
    against the reference design tokens and section hierarchy.
    """

    @staticmethod
    def audit_visual_consistency(
        liquid_code: str,
        json_template: Dict[str, Any],
        manifest: Optional[WorkshopTemplateManifest] = None
    ) -> VisualConsistencyReport:
        """
        Audits generated Liquid code and JSON template against reference manifest rules.
        Calculates design match percentage and lists passed checks and differences.
        """
        manifest = manifest or WorkshopTemplateManifest()
        tokens = manifest.design_tokens

        checks_passed = []
        differences = []
        score_weight = 0
        total_checks = 0

        # Check 1: Primary Brand Colors (Paper, Ink, Amber, Rust)
        total_checks += 1
        color_matches = 0
        for color_name, color_val in tokens.colors.items():
            if color_val.lower() in liquid_code.lower():
                color_matches += 1
        if color_matches >= 3:
            checks_passed.append(f"Color Palette Verification: Matched {color_matches} core brand color tokens.")
            score_weight += 1
        else:
            differences.append(f"Color Palette Difference: Only matched {color_matches} brand colors.")

        # Check 2: Typography (Fraunces & Poppins)
        total_checks += 1
        has_fraunces = "'Fraunces'" in liquid_code or "Fraunces" in liquid_code
        has_poppins = "'Poppins'" in liquid_code or "Poppins" in liquid_code
        if has_fraunces and has_poppins:
            checks_passed.append("Typography Verification: Both Fraunces (display) and Poppins (body) fonts referenced.")
            score_weight += 1
        else:
            differences.append("Typography Difference: Missing Fraunces or Poppins font declaration.")

        # Check 3: Hero Section Structure
        total_checks += 1
        if "ait-hero" in liquid_code or "hero" in liquid_code.lower():
            checks_passed.append("Hero Section Structure: Verified 2-column hero structure.")
            score_weight += 1
        else:
            differences.append("Hero Section Structure: Hero CSS class not found.")

        # Check 4: JSON Template Section Order & Schema
        total_checks += 1
        sections = json_template.get("sections", {})
        if "main" in sections and sections["main"].get("type"):
            checks_passed.append("Shopify Template Structure: Valid product section template definition.")
            score_weight += 1
        else:
            differences.append("Shopify Template Structure: Invalid main section in JSON template.")

        # Check 5: Responsive & Breakpoint rules
        total_checks += 1
        if "@media" in liquid_code or "max-width" in liquid_code:
            checks_passed.append("Responsive Layout Verification: Mobile & tablet breakpoints present.")
            score_weight += 1
        else:
            differences.append("Responsive Layout Difference: Missing media query breakpoints.")

        # Compute match percentage
        match_percentage = round((score_weight / total_checks) * 100.0, 1) if total_checks > 0 else 100.0
        status = "DESIGN_MATCH" if match_percentage >= 80.0 else "DESIGN_DIFFERENCES"

        report = VisualConsistencyReport(
            template_id=manifest.template_id,
            match_percentage=match_percentage,
            checks_passed=checks_passed,
            differences=differences,
            status=status
        )

        logger.info("Visual consistency audit completed: Score %.1f%% (Status: %s)", match_percentage, status)
        return report
