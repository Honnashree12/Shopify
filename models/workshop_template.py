"""
Workshop Design Template Models.

Defines Pydantic data contracts for template manifests, design tokens,
content mappings, and visual consistency audit reports.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class DesignTokens(BaseModel):
    colors: Dict[str, str] = Field(default_factory=lambda: {
        "paper": "#FFFFFF",
        "paper_tint": "#FBF1E1",
        "paper_tint_deep": "#F5E2C4",
        "ink": "#2B1A0E",
        "ink_dark": "#2B1A0E",
        "ink_soft": "rgba(43,26,14,0.68)",
        "amber": "#F3922C",
        "rust": "#DA6A14",
        "rust_mid": "#E87D1E",
        "gradient": "linear-gradient(135deg, #F3922C 0%, #DA6A14 100%)",
        "line": "rgba(43,26,14,0.10)"
    })
    typography: Dict[str, str] = Field(default_factory=lambda: {
        "font_display": "'Fraunces', 'Poppins', serif",
        "font_body": "'Poppins', 'Inter', sans-serif",
        "display_weight": "600",
        "body_weight": "400"
    })
    spacing: Dict[str, str] = Field(default_factory=lambda: {
        "max_width": "1240px",
        "section_padding": "64px 0",
        "grid_gap": "24px"
    })
    border_radius: Dict[str, str] = Field(default_factory=lambda: {
        "pill": "999px",
        "card": "18px",
        "hero": "32px",
        "modal": "28px"
    })
    shadows: Dict[str, str] = Field(default_factory=lambda: {
        "soft": "0 20px 50px rgba(60,32,10,0.12)",
        "glow": "0 14px 30px rgba(218,106,20,0.32)"
    })
    breakpoints: Dict[str, str] = Field(default_factory=lambda: {
        "desktop": "1240px",
        "tablet": "900px",
        "mobile": "600px"
    })


class SectionSchema(BaseModel):
    section_id: str
    type: str
    title: Optional[str] = None
    settings_schema: List[Dict[str, Any]] = Field(default_factory=list)
    block_types: List[Dict[str, Any]] = Field(default_factory=list)
    css_selectors: List[str] = Field(default_factory=list)
    liquid_variables: List[str] = Field(default_factory=list)


class WorkshopTemplateManifest(BaseModel):
    template_id: str = "kiddypi_workshop_v1"
    template_family: str = "kids_ai_workshop"
    source_workshops: List[str] = Field(default_factory=lambda: ["AI Tinker Saturdays", "Mission Tiranga"])
    design_tokens: DesignTokens = Field(default_factory=DesignTokens)
    sections: List[SectionSchema] = Field(default_factory=list)
    components: List[str] = Field(default_factory=lambda: [
        "hero_centered_2col",
        "about_2col",
        "journey_4stage_track",
        "program_highlights_grid",
        "project_cards_grid",
        "workshop_details_grid",
        "scan_qr_section",
        "technologies_strip",
        "final_cta",
        "sticky_purchase_bar",
        "registration_modal"
    ])
    animations: List[str] = Field(default_factory=lambda: [
        "reveal-on-scroll",
        "hero-float",
        "glow-parallax",
        "pulse-seats-dot",
        "shine-sweep"
    ])
    responsive_rules: Dict[str, str] = Field(default_factory=lambda: {
        "desktop": "2-column hero, 4-grid projects, 4-grid journey",
        "tablet": "single-column stacked hero, 2-grid projects, 2-grid journey",
        "mobile": "reduced padding, drawer registration modal"
    })


class VisualConsistencyReport(BaseModel):
    template_id: str
    match_percentage: float = 100.0
    checks_passed: List[str] = Field(default_factory=list)
    differences: List[str] = Field(default_factory=list)
    new_components_requiring_review: List[str] = Field(default_factory=list)
    status: str = "DESIGN_MATCH"  # DESIGN_MATCH or DESIGN_DIFFERENCES
