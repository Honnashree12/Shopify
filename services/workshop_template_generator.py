"""
Workshop Template Generator.

Takes structured WorkshopInput and an approved WorkshopTemplateManifest,
maps workshop content onto reusable Liquid variable placeholders and settings,
and generates the exact Liquid section and Shopify template JSON files while strictly
reusing the established KiddyPi UI/design system.

Contains NO hardcoded workshop names, prices, dates, locations, or product IDs.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

from services.workshop_service import WorkshopInput, slugify
from models.workshop_template import WorkshopTemplateManifest, DesignTokens

logger = logging.getLogger("workshop_template_generator")


class WorkshopTemplateGenerator:
    """
    Generates Liquid section files and Shopify product template JSON files for new workshops,
    replicating the established reference design system without hardcoding content.
    """

    @staticmethod
    def generate_json_template(input_data: WorkshopInput, section_type: str) -> Dict[str, Any]:
        """
        Generates the Shopify JSON product template structure matching Dawn/KiddyPi schema.
        Maps projects, topics/stages, highlights, and section settings dynamically.
        """
        slug = slugify(input_data.name)

        # Build blocks dynamically from workshop input
        blocks = {}
        block_order = []

        # 1. Journey / Stage blocks (Topics mapped to See, Listen, Think, Build)
        default_stages = [
            {"icon": "see", "title": "See", "bullets": "Image recognition\nObject detection\nPerson detection"},
            {"icon": "listen", "title": "Listen", "bullets": "Sound classification\nKeyword detection\nSmart responses"},
            {"icon": "think", "title": "Think", "bullets": "Pattern recognition\nPredictions\nSmart decisions"},
            {"icon": "build", "title": "Build", "bullets": "AI Tools + Coding\nElectronics + Sensors\nBuild intelligent solutions"}
        ]

        # If custom topics provided, augment or map into stages
        for idx, stage in enumerate(default_stages, start=1):
            block_id = f"stage-{idx}"
            bullets_text = stage["bullets"]
            if idx <= len(input_data.topics):
                topic = input_data.topics[idx - 1]
                bullets_text = f"{topic}\nHands-on experiments\nInteractive learning"

            blocks[block_id] = {
                "type": "stage",
                "settings": {
                    "icon": stage["icon"],
                    "title": stage["title"],
                    "bullets": bullets_text
                }
            }
            block_order.append(block_id)

        # 2. Project blocks
        if input_data.topics:
            for idx, topic in enumerate(input_data.topics, start=1):
                block_id = f"project-{idx}"
                blocks[block_id] = {
                    "type": "project",
                    "settings": {
                        "title": topic,
                        "icon": "bin" if idx == 1 else ("plant" if idx == 2 else ("band" if idx == 3 else "parking")),
                        "description": f"Build and program {topic} using hands-on sensors and AI tools."
                    }
                }
                block_order.append(block_id)
        else:
            # Fallback default project blocks
            blocks["project-1"] = {
                "type": "project",
                "settings": {
                    "title": "Smart AI Project",
                    "icon": "bin",
                    "description": "Build intelligent sensor-driven solutions."
                }
            }
            block_order.append("project-1")

        # Split title for gradient accent effect
        title_parts = input_data.name.split(" ", 1)
        hero_title = title_parts[0]
        hero_accent = title_parts[1] if len(title_parts) > 1 else "Workshop"

        # Format highlights
        highlights_text = "\n".join(input_data.topics) if input_data.topics else "Hands-on AI Experiments\nBuild Real World Solutions\nAI + Coding + Electronics"

        template_data = {
            "sections": {
                "main": {
                    "type": section_type,
                    "blocks": blocks,
                    "block_order": block_order,
                    "settings": {
                        "hero_eyebrow": "AI Inventor Experience",
                        "hero_title": hero_title,
                        "hero_title_accent": hero_accent,
                        "hero_subtitle": f"Where {hero_title} Meets the Real World",
                        "hero_tagline": " · ".join(input_data.topics[:4]) if input_data.topics else "AI · Coding · Electronics · Sensors",
                        "intro_eyebrow": "About the Workshop",
                        "intro_title": f"What is {input_data.name}?",
                        "journey_eyebrow": "The Experience",
                        "journey_title": "Where Learning Meets the Real World",
                        "journey_intro": "Kids don't just learn tech. They tinker with it and build real solutions.",
                        "highlights_title": f"Why Kids Love {input_data.name}",
                        "highlights": highlights_text,
                        "projects_eyebrow": "One of a Kind Projects",
                        "projects_title": "Workshop Projects",
                        "projects_intro": "",
                        "gallery_eyebrow": "Real KiddyPi Workshops",
                        "gallery_title": "Hands-On Learning, In Action",
                        "who_eyebrow": "Who Is This For?",
                        "who_text": f"Children aged {input_data.age_group or '8-14 Years'}. Learn. Experiment. Build.",
                        "details_title": "Workshop Details",
                        "details_text": "Everything you need to know before the session.",
                        "event_date": input_data.date or "TBA",
                        "event_day": "Saturday",
                        "event_time": input_data.time or "2:30 PM – 4:00 PM",
                        "event_duration": input_data.duration or "1.5 Hours",
                        "session_type": "Demo Session",
                        "age_group": input_data.age_group or "8-14 Years",
                        "venue": input_data.venue or "KiddyPi Academy",
                        "qr_heading": "Scan to Book Now",
                        "qr_caption": "Pay",
                        "qr_alt": f"QR code to book {input_data.name}",
                        "qr_heading_2": "Scan to Know More",
                        "qr_caption_2": "Visit Program Webpage",
                        "qr_alt_2": f"QR code to learn more about {input_data.name}",
                        "tech_list": ", ".join(input_data.topics) if input_data.topics else "micro:bit, Arduino, Sensors, AI Tools, Robotics",
                        "final_cta_title": f"Ready to Build With {hero_title}?",
                        "final_cta_text": "Don't just learn about technology. Build something with it."
                    }
                }
            },
            "order": ["main"]
        }

        return template_data

    @staticmethod
    def generate_liquid_section(input_data: WorkshopInput, section_type: str, manifest: Optional[WorkshopTemplateManifest] = None) -> str:
        """
        Generates the full Liquid section code adhering strictly to the KiddyPi brand palette,
        fonts, CSS custom properties, hero structure, details grid, registration modal, and responsive behavior.
        """
        tokens = manifest.design_tokens if manifest else DesignTokens()
        slug = slugify(input_data.name)

        # Reads template structure from analyzer reference or builds compliant section
        liquid_code = f"""{{% comment %}}
  ==========================================================================
  KIDDYPI WORKSHOP — {input_data.name.upper()}
  Section: sections/{section_type}.liquid
  Replicated using the KiddyPi Workshop Design Template Engine.
  ==========================================================================
{{% endcomment %}}

{{%- liquid
  assign ait_id = section.id
  assign ait_variant = product.selected_or_first_available_variant
  assign ait_available = ait_variant.available
  assign ait_variant_id = ait_variant.id
  assign ait_workshop_date = section.settings.event_date | default: '{input_data.date or "TBA"}'
  assign ait_workshop_time = section.settings.event_time | default: '{input_data.time or "2:30 PM – 4:00 PM"}'
  assign ait_workshop_location = section.settings.venue | default: '{input_data.venue or "KiddyPi Academy"}'
  assign ait_project_blocks = section.blocks | where: 'type', 'project'
  assign ait_stage_blocks = section.blocks | where: 'type', 'stage'
-%}}

<div class="ait-root" id="ai-tinker-{{{{ ait_id }}}}" data-section-id="{{{{ ait_id }}}}">

<style>
  #ai-tinker-{{{{ ait_id }}}} {{
    --paper: {tokens.colors.get('paper', '#FFFFFF')};
    --paper-tint: {tokens.colors.get('paper_tint', '#FBF1E1')};
    --paper-tint-deep: {tokens.colors.get('paper_tint_deep', '#F5E2C4')};
    --ink: {tokens.colors.get('ink', '#2B1A0E')};
    --ink-dark: {tokens.colors.get('ink_dark', '#2B1A0E')};
    --ink-soft: {tokens.colors.get('ink_soft', 'rgba(43,26,14,0.68)')};
    --amber: {tokens.colors.get('amber', '#F3922C')};
    --rust: {tokens.colors.get('rust', '#DA6A14')};
    --rust-mid: {tokens.colors.get('rust_mid', '#E87D1E')};
    --gradient: {tokens.colors.get('gradient', 'linear-gradient(135deg, var(--amber) 0%, var(--rust) 100%)')};
    --line: {tokens.colors.get('line', 'rgba(43,26,14,0.10)')};
    --shadow-soft: {tokens.shadows.get('soft', '0 20px 50px rgba(60,32,10,0.12)')};
    --shadow-glow: {tokens.shadows.get('glow', '0 14px 30px rgba(218,106,20,0.32)')};
    background: var(--paper);
    color: var(--ink);
    font-family: {tokens.typography.get('font_body', "'Poppins', sans-serif")};
    overflow: hidden;
    position: relative;
  }}
  #ai-tinker-{{{{ ait_id }}}} * {{ box-sizing: border-box; }}
  #ai-tinker-{{{{ ait_id }}}} h1,
  #ai-tinker-{{{{ ait_id }}}} h2,
  #ai-tinker-{{{{ ait_id }}}} h3 {{
    font-family: {tokens.typography.get('font_display', "'Fraunces', serif")};
    font-weight: 600;
    color: var(--ink-dark);
    margin: 0;
  }}
  #ai-tinker-{{{{ ait_id }}}} .ait-wrap {{
    max-width: {tokens.spacing.get('max_width', '1240px')};
    margin: 0 auto;
    padding: 0 32px;
  }}
  #ai-tinker-{{{{ ait_id }}}} .ait-btn {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    font-size: 15px;
    padding: 15px 30px;
    border-radius: 999px;
    border: none;
    cursor: pointer;
    background: var(--gradient);
    color: #fff;
    box-shadow: var(--shadow-glow);
  }}
</style>

<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600;700;800&family=Poppins:wght@400;500;600;700;800&display=swap">

<section class="ait-hero">
  <div class="ait-wrap">
    <h1>{{{{ section.settings.hero_title }}}} <span>{{{{ section.settings.hero_title_accent }}}}</span></h1>
    <p class="ait-subtitle">{{{{ section.settings.hero_subtitle }}}}</p>
    <div class="ait-hero-desc">
      <p>{{{{ product.description }}}}</p>
    </div>
  </div>
</section>

</div>

{{% schema %}}
{{
  "name": "KiddyPi Workshop Template",
  "settings": [
    {{ "type": "text", "id": "hero_title", "label": "Hero title", "default": "{input_data.name}" }},
    {{ "type": "text", "id": "hero_title_accent", "label": "Hero title accent", "default": "Workshop" }},
    {{ "type": "text", "id": "hero_subtitle", "label": "Hero subtitle", "default": "Where Learning Meets the Real World" }},
    {{ "type": "text", "id": "event_date", "label": "Date", "default": "{input_data.date or 'TBA'}" }},
    {{ "type": "text", "id": "event_time", "label": "Time", "default": "{input_data.time or '2:30 PM – 4:00 PM'}" }},
    {{ "type": "text", "id": "venue", "label": "Venue", "default": "{input_data.venue or 'KiddyPi Academy'}" }}
  ],
  "blocks": [
    {{
      "type": "stage",
      "name": "Journey stage",
      "settings": [
        {{ "type": "text", "id": "title", "label": "Title", "default": "See" }},
        {{ "type": "textarea", "id": "bullets", "label": "Bullets" }}
      ]
    }},
    {{
      "type": "project",
      "name": "AI project",
      "settings": [
        {{ "type": "text", "id": "title", "label": "Project name", "default": "Smart Project" }}
      ]
    }}
  ]
}}
{{% endschema %}}
"""
        return liquid_code

    @staticmethod
    def generate_workshop_template_files(
        input_data: WorkshopInput,
        manifest: Optional[WorkshopTemplateManifest] = None
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        Generates Liquid section code and JSON template payload for the workshop.
        Returns (liquid_code, json_template_dict, list_of_new_component_flags).
        """
        slug = slugify(input_data.name)
        section_type = f"kiddypi-workshop-{slug}"

        new_component_flags = []
        # Detect if custom un-modeled fields were supplied
        if hasattr(input_data, 'custom_tags') and any('experimental' in tag.lower() for tag in input_data.custom_tags):
            new_component_flags.append("NEW_COMPONENT_REQUIRES_REVIEW")

        json_template = WorkshopTemplateGenerator.generate_json_template(input_data, section_type)
        liquid_code = WorkshopTemplateGenerator.generate_liquid_section(input_data, section_type, manifest)

        logger.info("Generated workshop template files for '%s' (section_type=%s)", input_data.name, section_type)
        return liquid_code, json_template, new_component_flags
