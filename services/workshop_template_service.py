"""
Workshop Template Service.

High-level coordinator connecting template analysis, generic template generation,
visual consistency auditing, and state object updates for Workshop Service.
"""

import logging
from typing import Dict, Any, Tuple, Optional

from services.workshop_service import WorkshopInput, slugify
from models.workshop_template import (
    WorkshopTemplateManifest,
    VisualConsistencyReport
)
from services.workshop_design_analyzer import WorkshopDesignAnalyzer
from services.workshop_template_generator import WorkshopTemplateGenerator
from services.workshop_visual_validator import WorkshopVisualValidator

logger = logging.getLogger("workshop_template_service")


class WorkshopTemplateService:
    """
    Service wrapper orchestrating the design replication engine.
    """

    @staticmethod
    def process_template_replication(input_data: WorkshopInput) -> Dict[str, Any]:
        """
        Executes end-to-end design template replication for a new workshop input:
        1. Analyzes reference templates to get manifest.
        2. Generates Liquid section & JSON product template.
        3. Audits visual consistency against reference design manifest.
        Returns a dictionary containing all generated assets and report.
        """
        # Step 1: Analyze reference templates
        manifest = WorkshopDesignAnalyzer.analyze_reference_templates()

        # Step 2: Generate workshop Liquid & JSON files
        liquid_code, json_template, new_flags = WorkshopTemplateGenerator.generate_workshop_template_files(
            input_data, manifest
        )

        # Step 3: Run visual consistency audit
        visual_report = WorkshopVisualValidator.audit_visual_consistency(
            liquid_code, json_template, manifest
        )

        if new_flags:
            visual_report.new_components_requiring_review.extend(new_flags)

        slug = slugify(input_data.name)
        section_name = f"kiddypi-workshop-{slug}.liquid"
        template_name = f"product.{slug}.json"

        return {
            "template_manifest": manifest.dict(),
            "liquid_filename": f"sections/{section_name}",
            "liquid_code": liquid_code,
            "json_filename": f"templates/{template_name}",
            "json_template": json_template,
            "visual_consistency_report": visual_report.dict(),
            "visual_score": visual_report.match_percentage,
            "status": visual_report.status
        }
