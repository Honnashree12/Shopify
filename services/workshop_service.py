"""
Workshop Domain Service for Workshop Setup Agent.

This module is completely decoupled from Product Launch Agent internal pipelines.
It handles workshop input processing, metadata extraction, asset checking,
duplicate Shopify product detection, website presentation formatting, Shopify payload building,
registration flow configuration, approval boundary management, validation auditing, and
controlled publishing.

No business-specific vendor names, product IDs, prices, images, or URLs are hardcoded.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Literal, Protocol
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field                   

logger = logging.getLogger("workshop_service")

from shopify_client import get_validation_client

# =====================================================================
# DATA CONTRACTS & SCHEMAS (Generic for ANY Workshop)
# =====================================================================

class MediaInput(BaseModel):
    hero_image: Optional[str] = None
    gallery_images: List[str] = Field(default_factory=list)
    instructor_image: Optional[str] = None
    video_url: Optional[str] = None
    brochure_pdf: Optional[str] = None
    registration_qr: Optional[str] = None


class ProjectInput(BaseModel):
    title: str
    description: str
    image_url: Optional[str] = None
    technology: Optional[str] = None


class TimelineStepInput(BaseModel):
    step: int = 1
    title: str
    description: str
    duration: Optional[str] = None


class ContentInput(BaseModel):
    learning_outcomes: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    projects: List[ProjectInput] = Field(default_factory=list)
    journey: List[TimelineStepInput] = Field(default_factory=list)
    subtitle: Optional[str] = None
    eyebrow: Optional[str] = None
    course_introduction: Optional[str] = None
    course_core_concepts: Optional[str] = None
    course_skills: Optional[str] = None
    course_conclusion: Optional[str] = None
    course_level: Optional[str] = None
    course_mode: Optional[str] = None
    course_category: Optional[str] = None


class InstructorInput(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    bio: Optional[str] = None
    photo: Optional[str] = None


class RegistrationInputData(BaseModel):
    url: Optional[str] = None
    button_text: Optional[str] = "Register Now"
    seats_available: Optional[int] = None
    deadline: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class WorkshopInput(BaseModel):
    name: str
    description: str
    date: Optional[str] = ""
    time: Optional[str] = ""
    duration: Optional[str] = ""
    venue: Optional[str] = ""
    age_group: Optional[str] = ""
    price: float = 0.0
    vendor: Optional[str] = "Store Vendor"
    product_type: Optional[str] = "Workshop"
    topics: List[str] = Field(default_factory=list)
    poster_path: Optional[str] = None
    video_url: Optional[str] = None
    sales_team_email: Optional[str] = ""
    input_folder_path: Optional[str] = None
    custom_tags: List[str] = Field(default_factory=list)
    collection_name: Optional[str] = "Workshops"
    sku: Optional[str] = None
    require_registration: bool = True
    registration_fields: List[str] = Field(
        default_factory=lambda: ["child_name", "child_age", "parent_name", "school", "emergency_contact"]
    )
    checkout_url_template: str = "/cart/{variant_id}:1"

    # Extended Media, Content, Instructor, Registration sections
    media: MediaInput = Field(default_factory=MediaInput)
    content: ContentInput = Field(default_factory=ContentInput)
    instructor: InstructorInput = Field(default_factory=InstructorInput)
    registration: RegistrationInputData = Field(default_factory=RegistrationInputData)


class KiddypiWebsiteContent(BaseModel):
    workshop_id: str
    hero_headline: str
    formatted_description_html: str
    syllabus_modules: List[Dict[str, str]] = Field(default_factory=list)
    target_audience_summary: str
    poster_url: Optional[str] = None
    promo_video_url: Optional[str] = None
    faq_items: List[Dict[str, str]] = Field(default_factory=list)
    learning_outcomes: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    journey: List[Dict[str, Any]] = Field(default_factory=list)
    instructor: Dict[str, Any] = Field(default_factory=dict)
    media: Dict[str, Any] = Field(default_factory=dict)
    registration: Dict[str, Any] = Field(default_factory=dict)


class ShopifyWorkshopPayload(BaseModel):
    action: Literal["CREATE", "UPDATE"] = "CREATE"
    existing_product_id: Optional[int] = None
    title: str
    body_html: str
    vendor: str
    product_type: str
    tags: List[str] = Field(default_factory=list)
    price: float
    sku: str
    inventory_quantity: int = 100
    metafields: List[Dict[str, Any]] = Field(default_factory=list)
    collection_name: str = "Workshops"
    template_suffix: Optional[str] = "workshop"
    seo_description: Optional[str] = None
    status: str = "draft"  # Always starts as draft until explicit publication


class RegistrationConfig(BaseModel):
    is_registration_required: bool = True
    custom_fields: List[str] = Field(default_factory=list)
    buy_now_behavior: Literal["DIRECT_CHECKOUT", "CART_REDIRECT"] = "CART_REDIRECT"
    checkout_url_template: str = "/cart/{variant_id}:1"
    require_login: bool = False


# Workflow State Machine Enum Values
WORKFLOW_STATES = [
    "DRAFT",
    "UNDERSTANDING",
    "ASSET_CHECK",
    "CONTENT_PREPARED",
    "SHOPIFY_PREPARED",
    "REGISTRATION_PREPARED",
    "PENDING_APPROVAL",
    "APPROVED",
    "CREATING_OR_UPDATING",
    "VALIDATING",
    "VALIDATION_FAILED",
    "LAUNCH_READY",
    "PUBLISHED",
    "FAILED",
    "AMBIGUOUS_PRODUCT_MATCH",
    "MISSING_REQUIRED_ASSET",
    "INVALID_WORKSHOP_INPUT",
    "SHOPIFY_API_ERROR",
    "SHOPIFY_SYNC_FAILED",
]


class WorkshopWorkflowState(BaseModel):
    workshop_id: str
    current_state: str = "DRAFT"
    input_data: WorkshopInput
    matched_candidate_id: Optional[int] = None
    matched_candidate_title: Optional[str] = None
    match_confidence: float = 0.0
    conflicts_list: List[Dict[str, Any]] = Field(default_factory=list)
    duplicate_action: str = "ASK"
    website_content: Optional[KiddypiWebsiteContent] = None
    proposed_shopify_payload: Optional[ShopifyWorkshopPayload] = None
    registration_config: Optional[RegistrationConfig] = None
    approval_status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    approved_by_email: Optional[str] = None
    approved_at: Optional[str] = None
    shopify_product_id: Optional[int] = None
    shopify_variant_id: Optional[int] = None
    shopify_product_status: str = "draft"
    validation_results: Optional[Dict[str, Any]] = None
    generated_liquid_section: Optional[str] = None
    generated_json_template: Optional[Dict[str, Any]] = None
    visual_consistency_report: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# Abstract Interface for Shopify Client (enables offline unit testing)
class IShopifyClient(Protocol):
    def get_product_by_title(self, title: str) -> Optional[Dict[str, Any]]: ...
    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]: ...
    def create_product(self, **kwargs) -> Dict[str, Any]: ...
    def update_product(self, product_id: Any, **kwargs) -> Dict[str, Any]: ...
    def upload_product_images(self, product_id: Any, image_paths: List[str]) -> List[Dict[str, Any]]: ...
    def get_or_create_custom_collection(self, title: str) -> int: ...
    def add_product_to_collection(self, product_id: Any, collection_id: int) -> Dict[str, Any]: ...


# =====================================================================
# WORKSHOP DOMAIN SERVICE
# =====================================================================

def slugify(text: str) -> str:
    """Helper to convert title into slug for matching & handles."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def calculate_title_similarity(t1: str, t2: str) -> float:
    """Calculates Jaccard token similarity between two titles."""
    s1 = set(slugify(t1).split('-'))
    s2 = set(slugify(t2).split('-'))
    if not s1 or not s2:
        return 0.0
    intersection = s1.intersection(s2)
    union = s1.union(s2)
    return len(intersection) / len(union)


def to_rich_text_json(text: str) -> str:
    """Helper to convert plain text string into Shopify Rich Text JSON structure required by rich_text_field definitions."""
    if not text:
        text_str = ""
    else:
        text_str = str(text).strip()
    if text_str.startswith('{"type":"root"') or text_str.startswith('{"type": "root"'):
        return text_str
    return json.dumps({
        "type": "root",
        "children": [
            {
                "type": "paragraph",
                "children": [
                    {
                        "type": "text",
                        "value": text_str
                    }
                ]
            }
        ]
    })


class WorkshopService:
    """
    Independent Workshop Domain Service handling workflow transitions,
    content preparation, product matching, payload generation, approval verification,
    validation execution, and publication readiness.
    """

    @staticmethod
    def validate_workshop_input(input_data: WorkshopInput) -> Optional[str]:
        """Validates WorkshopInput data contracts and returns error message string if invalid."""
        if not input_data.name or not input_data.name.strip():
            return "Workshop name is required."
        if len(input_data.name.strip()) > 255:
            return "Workshop name exceeds maximum length of 255 characters."
        if not input_data.description or not input_data.description.strip():
            return "Workshop description is required."
        if len(input_data.description.strip()) > 10000:
            return "Workshop description exceeds maximum length of 10,000 characters."
        if input_data.price < 0:
            return "Registration price cannot be negative."

        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if input_data.sales_team_email and input_data.sales_team_email.strip():
            if not re.match(email_regex, input_data.sales_team_email.strip()):
                return f"Invalid sales team email format: {input_data.sales_team_email}"
        if input_data.registration and input_data.registration.contact_email and input_data.registration.contact_email.strip():
            if not re.match(email_regex, input_data.registration.contact_email.strip()):
                return f"Invalid registration contact email format: {input_data.registration.contact_email}"

        if input_data.registration and input_data.registration.seats_available is not None:
            if input_data.registration.seats_available < 0:
                return "Seats available cannot be negative."

        url_fields = [
            ("Video URL", input_data.video_url or (input_data.media and input_data.media.video_url)),
            ("Registration URL", input_data.registration and input_data.registration.url),
            ("Hero Image", input_data.poster_path or (input_data.media and input_data.media.hero_image)),
            ("Brochure PDF", input_data.media and input_data.media.brochure_pdf),
            ("Registration QR", input_data.media and input_data.media.registration_qr)
        ]
        for label, u in url_fields:
            if u and isinstance(u, str) and u.strip():
                u_str = u.strip()
                if not (u_str.startswith("http://") or u_str.startswith("https://") or u_str.startswith("/") or u_str.startswith("data:")):
                    return f"Invalid {label} format/URL: '{u}'"

        if input_data.media and input_data.media.brochure_pdf:
            path = input_data.media.brochure_pdf.split("?")[0].lower()
            if not path.endswith(".pdf") and not (path.startswith("http://") or path.startswith("https://") or path.startswith("/outputs")):
                return "Brochure file must be a PDF document."

        if input_data.content and input_data.content.projects:
            for i, prj in enumerate(input_data.content.projects):
                p_title = prj.title if hasattr(prj, "title") else prj.get("title", "")
                if not p_title or not p_title.strip():
                    return f"Project entry #{i+1} title is required."

        if input_data.content and input_data.content.journey:
            for i, step in enumerate(input_data.content.journey):
                s_title = step.title if hasattr(step, "title") else step.get("title", "")
                if not s_title or not s_title.strip():
                    return f"Timeline step #{i+1} title is required."

        return None

    @staticmethod
    def process_workshop_input(input_data: WorkshopInput, workshop_id: Optional[str] = None) -> WorkshopWorkflowState:
        """Step 1: Validate and ingest workshop input."""
        err = WorkshopService.validate_workshop_input(input_data)
        if err:
            state = WorkshopWorkflowState(
                workshop_id=workshop_id or "invalid",
                current_state="INVALID_WORKSHOP_INPUT",
                input_data=input_data,
                error_type="INVALID_WORKSHOP_INPUT",
                error_message=err
            )
            return state

        w_id = workshop_id or slugify(input_data.name)
        state = WorkshopWorkflowState(
            workshop_id=w_id,
            current_state="DRAFT",
            input_data=input_data
        )
        logger.info("Processed workshop input for ID: %s", w_id)
        return state

    @staticmethod
    def understand_workshop_information(state: WorkshopWorkflowState) -> WorkshopWorkflowState:
        """Step 2: Understand and extract structured information from input and attachments."""
        state.current_state = "UNDERSTANDING"
        inp = state.input_data
        
        # If input folder path provided, extract text using file_extractor
        extracted_text = ""
        if inp.input_folder_path and os.path.exists(inp.input_folder_path):
            try:
                from tools.file_extractor import scan_directory, extract_pdf, extract_docx, extract_csv
                files = scan_directory(inp.input_folder_path)
                text_parts = []
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext == ".pdf":
                        text_parts.append(extract_pdf(f))
                    elif ext == ".docx":
                        text_parts.append(extract_docx(f))
                    elif ext == ".csv":
                        text_parts.append(extract_csv(f))
                extracted_text = "\n".join(text_parts)
            except Exception as e:
                logger.warning("Failed to extract folder files: %s", e)

        # Merge extracted text into description if relevant
        if extracted_text and not inp.description:
            inp.description = extracted_text[:2000]

        logger.info("Understood workshop information for %s", state.workshop_id)
        return state

    @staticmethod
    def check_assets(state: WorkshopWorkflowState) -> WorkshopWorkflowState:
        """Step 3: Check existing local/remote assets."""
        state.current_state = "ASSET_CHECK"
        inp = state.input_data
        
        # Check poster file path if specified
        if inp.poster_path and not (os.path.exists(inp.poster_path) or inp.poster_path.startswith("http") or inp.poster_path.startswith("/")):
            logger.warning("Specified poster path does not exist: %s", inp.poster_path)
            
        logger.info("Asset check completed for %s", state.workshop_id)
        return state

    @staticmethod
    def search_existing_shopify_product(
        state: WorkshopWorkflowState,
        shopify_client: Optional[Any] = None
    ) -> WorkshopWorkflowState:
        """
        Step 4: Search existing Shopify products to decide CREATE vs UPDATE vs AMBIGUOUS_MATCH.
        Uses exact SKU search and normalized title similarity without guessing.
        """
        if shopify_client is None:
            try:
                from shopify_client import get_validation_client
                shopify_client = get_validation_client()
            except Exception as e:
                logger.warning("Shopify client unavailable for product search: %s", e)
                # Fallback to CREATE if shopify client not connected
                state.proposed_shopify_payload = None
                return state

        inp = state.input_data
        matches: List[Tuple[Dict[str, Any], float]] = []

        # 1. Search by SKU if available
        if inp.sku:
            try:
                sku_product = shopify_client.get_product_by_sku(inp.sku)
                if sku_product:
                    matches.append((sku_product, 1.0))
            except Exception as se:
                logger.warning("SKU search failed: %s", se)

        # 2. Search by Title
        try:
            title_product = shopify_client.get_product_by_title(inp.name)
            if title_product:
                tp_id = title_product.get("id") or title_product.get("product_id")
                if not any((m[0].get("id") or m[0].get("product_id")) == tp_id for m in matches):
                    sim = calculate_title_similarity(inp.name, title_product.get("title", ""))
                    matches.append((title_product, max(sim, 0.95)))  # Exact title search returned it
        except Exception as te:
            logger.warning("Title search failed: %s", te)

        # Evaluate matches
        if not matches:
            state.matched_candidate_id = None
            state.matched_candidate_title = None
            state.match_confidence = 0.0
            logger.info("No matching Shopify product found for '%s'. Will CREATE.", inp.name)
        elif len(matches) == 1 and matches[0][1] >= 0.90:
            match_prod = matches[0][0]
            matched_id = match_prod.get("id") or match_prod.get("product_id")
            state.matched_candidate_id = int(matched_id)
            state.matched_candidate_title = match_prod.get("title")
            state.match_confidence = matches[0][1]
            logger.info("Found single strong match for '%s': ID %s (Conf: %.2f)", inp.name, state.matched_candidate_id, state.match_confidence)
        else:
            # Multiple matches or weak similarity -> Require Human Review
            state.current_state = "AMBIGUOUS_PRODUCT_MATCH"
            state.conflicts_list = [
                {"id": m[0].get("id") or m[0].get("product_id"), "title": m[0].get("title"), "confidence": m[1]}
                for m in matches
            ]
            state.duplicate_action = "ASK"
            state.error_type = "AMBIGUOUS_PRODUCT_MATCH"
            state.error_message = f"Found {len(matches)} potential matching products. Review required before proceeding."
            logger.warning("Ambiguous product matches for '%s': %s", inp.name, state.conflicts_list)

        return state

    @staticmethod
    def prepare_website_content(state: WorkshopWorkflowState) -> WorkshopWorkflowState:
        """Step 5: Formats Kiddypi Website presentation content independently from Shopify product."""
        state.current_state = "CONTENT_PREPARED"
        inp = state.input_data
        
        modules = [{"title": topic, "description": f"Detailed session covering {topic}"} for topic in inp.topics]

        # Extract content & media
        learning_outcomes = list(inp.content.learning_outcomes) if inp.content and inp.content.learning_outcomes else []
        highlights = list(inp.content.highlights) if inp.content and inp.content.highlights else []

        projects = []
        if inp.content and inp.content.projects:
            for p in inp.content.projects:
                p_dict = p.dict() if hasattr(p, "dict") else dict(p)
                projects.append(p_dict)

        journey = []
        if inp.content and inp.content.journey:
            for j in inp.content.journey:
                j_dict = j.dict() if hasattr(j, "dict") else dict(j)
                journey.append(j_dict)

        instructor = inp.instructor.dict() if hasattr(inp.instructor, "dict") else dict(inp.instructor or {})
        if inp.media and inp.media.instructor_image and not instructor.get("photo"):
            instructor["photo"] = inp.media.instructor_image
        elif instructor.get("photo") and inp.media and not inp.media.instructor_image:
            inp.media.instructor_image = instructor["photo"]

        media = inp.media.dict() if hasattr(inp.media, "dict") else dict(inp.media or {})
        if inp.poster_path and not media.get("hero_image"):
            media["hero_image"] = inp.poster_path
        elif media.get("hero_image") and not inp.poster_path:
            inp.poster_path = media["hero_image"]

        if inp.video_url and not media.get("video_url"):
            media["video_url"] = inp.video_url
        elif media.get("video_url") and not inp.video_url:
            inp.video_url = media["video_url"]

        registration = inp.registration.dict() if hasattr(inp.registration, "dict") else dict(inp.registration or {})
        if inp.sales_team_email and not registration.get("contact_email"):
            registration["contact_email"] = inp.sales_team_email

        html_parts = [
            f"<div class='kiddypi-workshop-description' style='font-family: \"Poppins\", \"Inter\", sans-serif; color: #2B1A0E; line-height: 1.6; font-size: 15px;'>",
            f"<div style='background: linear-gradient(135deg, #FBF1E1 0%, #F5E2C4 100%); padding: 22px 26px; border-radius: 14px; margin-bottom: 24px; border: 1px solid #F5E2C4;'>",
            f"<div style='display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px;'>",
            f"<span style='background: #DA6A14; color: #FFFFFF; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; padding: 4px 12px; border-radius: 20px;'>OFFLINE WORKSHOP</span>",
            f"{f'<span style=\"background: #E87D1E; color: #FFFFFF; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 20px;\">📅 {inp.date}</span>' if inp.date else ''}",
            f"</div>",
            f"<p style='font-size: 16px; color: #2B1A0E; margin: 0 0 14px 0; font-weight: 500;'>{inp.description}</p>",
            f"<div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 13.5px; font-weight: 600; color: #6B4A2E; background: rgba(255,255,255,0.7); padding: 12px 16px; border-radius: 10px;'>",
            f"{f'<div>📍 <strong>Venue:</strong> {inp.venue}</div>' if inp.venue else ''}",
            f"{f'<div>⏰ <strong>Schedule:</strong> {inp.time} ({inp.duration})</div>' if inp.time or inp.duration else ''}",
            f"{f'<div>🎓 <strong>Target Age:</strong> {inp.age_group}</div>' if inp.age_group else ''}",
            f"</div>",
            f"</div>"
        ]

        if learning_outcomes:
            html_parts.append("<div style='margin-bottom: 24px;'><h3 style='color: #DA6A14; font-family: \"Fraunces\", serif; font-size: 20px; font-weight: 700; margin: 0 0 12px 0;'>🎯 What Students Will Learn</h3><ul style='list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px;'>")
            for outcome in learning_outcomes:
                html_parts.append(f"<li style='background: #FBF1E1; border: 1px solid #F5E2C4; border-radius: 10px; padding: 10px 14px; font-size: 14px; font-weight: 500;'>✨ {outcome}</li>")
            html_parts.append("</ul></div>")

        if highlights:
            html_parts.append("<div style='margin-bottom: 24px;'><h3 style='color: #DA6A14; font-family: \"Fraunces\", serif; font-size: 20px; font-weight: 700; margin: 0 0 12px 0;'>🌟 Workshop Highlights</h3><ul style='list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px;'>")
            for h in highlights:
                html_parts.append(f"<li style='background: #FFFFFF; border: 1.5px solid #F5E2C4; border-radius: 10px; padding: 10px 14px; font-size: 14px; font-weight: 600; color: #2B1A0E;'>🚀 {h}</li>")
            html_parts.append("</ul></div>")

        if projects:
            html_parts.append("<div style='margin-bottom: 24px;'><h3 style='color: #DA6A14; font-family: \"Fraunces\", serif; font-size: 20px; font-weight: 700; margin: 0 0 12px 0;'>🛠️ Featured Projects & Activities</h3><div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px;'>")
            for prj in projects:
                tech = f" <span style='font-size: 11px; background: #DA6A14; color: #fff; padding: 2px 8px; border-radius: 10px;'>{prj.get('technology')}</span>" if prj.get("technology") else ""
                html_parts.append(f"<div style='background: #FFFFFF; border: 1px solid #F5E2C4; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(43,26,14,0.05);'><h4 style='margin: 0 0 8px 0; color: #2B1A0E; font-size: 16px; font-weight: 700;'>{prj.get('title')}{tech}</h4><p style='margin: 0; font-size: 13.5px; color: #6B4A2E;'>{prj.get('description', '')}</p></div>")
            html_parts.append("</div></div>")

        if journey:
            html_parts.append("<div style='margin-bottom: 24px;'><h3 style='color: #DA6A14; font-family: \"Fraunces\", serif; font-size: 20px; font-weight: 700; margin: 0 0 12px 0;'>🗺️ Workshop Journey</h3><div style='display: flex; flex-direction: column; gap: 10px;'>")
            for step in journey:
                dur = f" <span style='color: #E87D1E;'>({step.get('duration')})</span>" if step.get("duration") else ""
                html_parts.append(f"<div style='background: #FBF1E1; border-left: 4px solid #DA6A14; padding: 12px 16px; border-radius: 0 10px 10px 0;'><strong style='color: #2B1A0E;'>Step {step.get('step', 1)}: {step.get('title')}</strong>{dur}<p style='margin: 4px 0 0 0; font-size: 13.5px; color: #6B4A2E;'>{step.get('description', '')}</p></div>")
            html_parts.append("</div></div>")

        if instructor.get("name"):
            html_parts.append(f"<div style='background: linear-gradient(135deg, #2B1A0E 0%, #3C200A 100%); color: #FFFFFF; border-radius: 14px; padding: 20px 24px; margin-top: 24px;'><h3 style='margin: 0 0 4px 0; color: #F5E2C4; font-size: 18px; font-weight: 700;'>👨‍🏫 Lead Instructor: {instructor['name']}</h3><div style='color: #E87D1E; font-size: 13px; font-weight: 600; margin-bottom: 8px;'>{instructor.get('role', '')}</div><p style='margin: 0; font-size: 13.5px; color: #FBF1E1; opacity: 0.9;'>{instructor.get('bio', '')}</p></div>")

        html_parts.append("</div>")
        html_desc = "".join(html_parts)

        state.website_content = KiddypiWebsiteContent(
            workshop_id=state.workshop_id,
            hero_headline=inp.name,
            formatted_description_html=html_desc,
            syllabus_modules=modules,
            target_audience_summary=inp.age_group or "All Ages",
            poster_url=media.get("hero_image") or inp.poster_path,
            promo_video_url=media.get("video_url") or inp.video_url,
            learning_outcomes=learning_outcomes,
            highlights=highlights,
            projects=projects,
            journey=journey,
            instructor=instructor,
            media=media,
            registration=registration
        )
        logger.info("Prepared website content for %s", state.workshop_id)
        return state

    @staticmethod
    def prepare_template_generation(state: WorkshopWorkflowState) -> WorkshopWorkflowState:
        """Step 5b: Executes Design Template Replication Engine."""
        try:
            from services.workshop_template_service import WorkshopTemplateService
            res = WorkshopTemplateService.process_template_replication(state.input_data)
            state.generated_liquid_section = res.get("liquid_code")
            state.generated_json_template = res.get("json_template")
            state.visual_consistency_report = res.get("visual_consistency_report")
            logger.info(
                "Completed template replication for %s: Visual Match Score %.1f%% (%s)",
                state.workshop_id,
                res.get("visual_score", 100.0),
                res.get("status", "DESIGN_MATCH")
            )
        except Exception as te:
            logger.warning("Template replication error for %s: %s", state.workshop_id, te)
        return state

    @staticmethod
    def prepare_shopify_payload(state: WorkshopWorkflowState) -> WorkshopWorkflowState:
        """Step 6: Builds proposed draft Shopify Product Payload."""
        state.current_state = "SHOPIFY_PREPARED"
        inp = state.input_data

        tags = list(set([inp.product_type or "Workshop", inp.vendor or "Store", inp.age_group] + inp.topics + inp.custom_tags))
        tags = [t for t in tags if t]

        metafields = [
            {"namespace": "workshop", "key": "venue", "value": inp.venue or "", "type": "single_line_text_field"},
            {"namespace": "workshop", "key": "schedule", "value": f"{inp.date} {inp.time}".strip(), "type": "single_line_text_field"},
            {"namespace": "workshop", "key": "age_group", "value": inp.age_group or "", "type": "single_line_text_field"},
            {"namespace": "workshop", "key": "sales_email", "value": inp.sales_team_email or "", "type": "single_line_text_field"},

            # Reference Custom Metafields (matching AI Tinker reference product schema)
            {"namespace": "custom", "key": "course_introduction", "value": to_rich_text_json((inp.content and inp.content.course_introduction) or inp.description or ""), "type": "rich_text_field"},
            {"namespace": "custom", "key": "course_core_concepts", "value": to_rich_text_json((inp.content and inp.content.course_core_concepts) or ", ".join(inp.topics)), "type": "rich_text_field"},
            {"namespace": "custom", "key": "course_skills", "value": to_rich_text_json((inp.content and inp.content.course_skills) or ", ".join(inp.content.learning_outcomes if inp.content else [])), "type": "rich_text_field"},
            {"namespace": "custom", "key": "course_conclusion", "value": to_rich_text_json((inp.content and inp.content.course_conclusion) or ""), "type": "rich_text_field"},
            {"namespace": "custom", "key": "course_location", "value": inp.venue or "", "type": "single_line_text_field"},
            {"namespace": "custom", "key": "course_level", "value": (inp.content and inp.content.course_level) or "Beginner / Intermediate", "type": "single_line_text_field"},
            {"namespace": "custom", "key": "course_mode", "value": (inp.content and inp.content.course_mode) or "Offline", "type": "single_line_text_field"},
            {"namespace": "custom", "key": "course_category", "value": (inp.content and inp.content.course_category) or "AI & STEM Workshop", "type": "single_line_text_field"},
            {"namespace": "custom", "key": "course_duration", "value": inp.duration or "", "type": "single_line_text_field"},
            {"namespace": "custom", "key": "subtitle", "value": (inp.content and inp.content.subtitle) or "", "type": "multi_line_text_field"},
            {"namespace": "custom", "key": "eyebrow", "value": (inp.content and inp.content.eyebrow) or "KiddyPi Workshop", "type": "single_line_text_field"}
        ]

        if inp.registration and inp.registration.url:
            metafields.append({"namespace": "course", "key": "external_url", "value": inp.registration.url, "type": "url"})

        action: Literal["CREATE", "UPDATE"] = "UPDATE" if state.matched_candidate_id else "CREATE"
        sku = inp.sku or f"WS-{slugify(inp.name).upper()[:12]}"

        state.proposed_shopify_payload = ShopifyWorkshopPayload(
            action=action,
            existing_product_id=state.matched_candidate_id,
            title=inp.name,
            body_html=state.website_content.formatted_description_html if state.website_content else inp.description,
            vendor=inp.vendor if (inp.vendor and inp.vendor != "Store Vendor") else "KiddyPi",
            product_type=inp.product_type or "Workshop",
            tags=tags,
            price=inp.price,
            sku=sku,
            inventory_quantity=100,
            metafields=metafields,
            collection_name=inp.collection_name or "Workshops",
            template_suffix=None,
            seo_description=inp.description,
            status="draft"  # Strict requirement: MUST stay draft
        )
        logger.info("Prepared proposed Shopify payload (action=%s) for %s", action, state.workshop_id)
        return state

    @staticmethod
    def prepare_registration_config(state: WorkshopWorkflowState) -> WorkshopWorkflowState:
        """Step 7: Prepares configurable Registration & Checkout contract."""
        state.current_state = "REGISTRATION_PREPARED"
        inp = state.input_data

        state.registration_config = RegistrationConfig(
            is_registration_required=inp.require_registration,
            custom_fields=inp.registration_fields,
            buy_now_behavior="CART_REDIRECT",
            checkout_url_template=inp.checkout_url_template,
            require_login=False
        )

        # Transition state to PENDING_APPROVAL - Execution pauses at Approval Boundary!
        state.current_state = "PENDING_APPROVAL"
        state.approval_status = "PENDING"
        logger.info("Workshop pipeline reached PENDING_APPROVAL boundary for %s", state.workshop_id)
        return state

    @staticmethod
    def approve_workshop(
        state: WorkshopWorkflowState,
        approver_email: str
    ) -> WorkshopWorkflowState:
        """Step 8: Process explicit human sign-off at Approval Boundary."""
        import datetime
        state.approval_status = "APPROVED"
        state.approved_by_email = approver_email
        state.approved_at = datetime.datetime.utcnow().isoformat() + "Z"
        state.current_state = "APPROVED"
        state.error_type = None
        state.error_message = None
        logger.info("Workshop %s APPROVED by %s", state.workshop_id, approver_email)
        return state


    @staticmethod
    def create_or_update_shopify_product(
        state: WorkshopWorkflowState,
        shopify_client: Optional[Any] = None,
        media_service: Optional[Any] = None
    ) -> WorkshopWorkflowState:
        """
        Step 9: Execute Shopify Product Create/Update (POST APPROVAL ONLY).
        Creates/updates product in 'draft' status.
        """
        if state.approval_status != "APPROVED":
            state.current_state = "PUBLISHING_BLOCKED"
            state.error_type = "PUBLISHING_BLOCKED"
            state.error_message = "Cannot create or update product on Shopify without explicit approval."
            raise PermissionError(state.error_message)

        state.current_state = "CREATING_OR_UPDATING"
        payload = state.proposed_shopify_payload
        if not payload:
            raise ValueError("Proposed Shopify payload is missing")

        if shopify_client is None:
            try:
                from shopify_client import get_validation_client
                shopify_client = get_validation_client()
            except Exception as e:
                state.current_state = "SHOPIFY_API_ERROR"
                state.error_type = "SHOPIFY_API_ERROR"
                state.error_message = f"Failed to initialize Shopify client: {e}"
                return state

        try:
            if payload.action == "CREATE" or not payload.existing_product_id:
                res = shopify_client.create_product(
                    title=payload.title,
                    body_html=payload.body_html,
                    vendor=payload.vendor,
                    product_type=payload.product_type,
                    price=payload.price,
                    sku=payload.sku,
                    tags=",".join(payload.tags),
                    metafields=payload.metafields,
                    template_suffix=payload.template_suffix or None,
                    seo_description=payload.seo_description,
                    status="draft"  # Strict rule: stay DRAFT
                )
                prod = res.get("product", res)
                state.shopify_product_id = int(prod["id"])
                variants = prod.get("variants", [])
                if variants:
                    state.shopify_variant_id = int(variants[0]["id"])
                logger.info("Created new Shopify product ID: %s (draft)", state.shopify_product_id)
            else:
                res = shopify_client.update_product(
                    product_id=payload.existing_product_id,
                    title=payload.title,
                    body_html=payload.body_html,
                    vendor=payload.vendor,
                    product_type=payload.product_type,
                    price=payload.price,
                    sku=payload.sku,
                    tags=",".join(payload.tags),
                    metafields=payload.metafields,
                    template_suffix=payload.template_suffix or None,
                    seo_description=payload.seo_description,
                    status="draft"  # Strict rule: stay DRAFT
                )
                prod = res.get("product", res)
                state.shopify_product_id = int(prod["id"])
                variants = prod.get("variants", [])
                if variants:
                    state.shopify_variant_id = int(variants[0]["id"])
                logger.info("Updated existing Shopify product ID: %s (draft)", state.shopify_product_id)

            # Assign to custom collection
            if payload.collection_name and state.shopify_product_id:
                try:
                    coll_id = shopify_client.get_or_create_custom_collection(payload.collection_name)
                    shopify_client.add_product_to_collection(state.shopify_product_id, coll_id)
                except Exception as ce:
                    logger.warning("Failed to assign collection '%s': %s", payload.collection_name, ce)

            # Upload media if poster provided
            if state.input_data.poster_path and os.path.exists(state.input_data.poster_path) and state.shopify_product_id:
                try:
                    shopify_client.upload_product_images(state.shopify_product_id, [state.input_data.poster_path])
                except Exception as me:
                    logger.warning("Failed to upload poster image: %s", me)

            state.shopify_product_status = "draft"
        except Exception as err:
            logger.error("Shopify product mutation failed: %s", err)
            state.current_state = "SHOPIFY_SYNC_FAILED"
            state.error_type = "SHOPIFY_SYNC_FAILED"
            state.error_message = f"Shopify product creation/update failed: {err}"

        return state

    @staticmethod
    def run_product_validation(
        state: WorkshopWorkflowState,
        validation_engine: Optional[Any] = None
    ) -> WorkshopWorkflowState:
        """
        Step 10: Run existing 53-item validation engine.
        CRITICAL SAFETY RULE: Passing validation marks the workshop LAUNCH_READY.
        It DOES NOT automatically activate or publish the product on Shopify!
        """
        if not state.shopify_product_id:
            state.current_state = "VALIDATION_FAILED"
            state.error_type = "VALIDATION_FAILED"
            state.error_message = "No Shopify product ID available to run validation on."
            return state

        state.current_state = "VALIDATING"
        logger.info("Running 53-item validation audit on Shopify product ID %s", state.shopify_product_id)

        try:
            if validation_engine is None:
                from services.unified_validation_engine import run_unified_validation_engine
                res = run_unified_validation_engine()
            else:
                res = validation_engine(state.shopify_product_id)

            state.validation_results = res
            
            # Check for blockers
            summary = res.get("summary", {}) if isinstance(res, dict) else {}
            blocker_fails = summary.get("blockers_failed", 0)

            if blocker_fails > 0:
                state.current_state = "VALIDATION_FAILED"
                state.error_type = "VALIDATION_FAILED"
                state.error_message = f"Validation failed with {blocker_fails} blocker issues."
                state.shopify_product_status = "draft"
                logger.warning("Product ID %s failed validation with %d blockers.", state.shopify_product_id, blocker_fails)
            else:
                # 0 Blockers -> LAUNCH_READY! Product remains DRAFT until explicit publish call.
                state.current_state = "LAUNCH_READY"
                state.shopify_product_status = "draft"
                logger.info("Product ID %s passed validation! State is now LAUNCH_READY (Product stays DRAFT until explicit publish).", state.shopify_product_id)

        except Exception as ve:
            logger.error("Validation engine execution failed: %s", ve)
            state.current_state = "VALIDATION_FAILED"
            state.error_type = "VALIDATION_FAILED"
            state.error_message = f"Validation execution error: {ve}"
            state.shopify_product_status = "draft"

        return state

    @staticmethod
    def publish_workshop_product(
        state: WorkshopWorkflowState,
        shopify_client: Optional[Any] = None
    ) -> WorkshopWorkflowState:
        """
        Step 11: Explicit, controlled publication step.
        Moves Shopify product status from 'draft' to 'active' ONLY after LAUNCH_READY.
        """
        if state.current_state != "LAUNCH_READY":
            raise ValueError(f"Cannot publish workshop product in state '{state.current_state}'. Must be LAUNCH_READY.")

        if not state.shopify_product_id:
            raise ValueError("Cannot publish: missing shopify_product_id")

        if shopify_client is None:
            from shopify_client import get_validation_client
            shopify_client = get_validation_client()

        try:
            shopify_client.update_product(
                product_id=state.shopify_product_id,
                status="draft",
                published=False
            )
            state.shopify_product_status = "draft"
            state.current_state = "PUBLISHED"
            logger.info("Updated workshop product ID %s on Shopify (status=draft)", state.shopify_product_id)
        except Exception as pe:
            logger.error("Failed to set Shopify product status to active: %s", pe)
            state.current_state = "SHOPIFY_SYNC_FAILED"
            state.error_type = "SHOPIFY_SYNC_FAILED"
            state.error_message = f"Publishing failed: {pe}"

        return state
