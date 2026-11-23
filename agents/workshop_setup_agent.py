"""
Workshop Setup Agent.

ADK Agent orchestration layer exposing tools for processing workshops,
matching Shopify products, managing approval boundaries, executing product creation/update,
running the 53-item validation engine, and handling controlled publishing.
"""

import logging
import json
from typing import Dict, Any, Optional

from google.adk import Agent
from google.adk.tools.tool_context import ToolContext

from services.workshop_service import (
    WorkshopService,
    WorkshopInput,
    WorkshopWorkflowState
)

logger = logging.getLogger("workshop_setup_agent")


def ingest_workshop_input_tool(tool_context: ToolContext) -> str:
    """ADK Tool to ingest workshop input and execute preliminary pre-approval preparation steps."""
    state_dict = tool_context.state
    
    # Reconstruct WorkshopInput from tool_context state
    input_data = WorkshopInput(
        name=state_dict.get("product_name") or state_dict.get("name") or "Untitled Workshop",
        description=state_dict.get("raw_description") or state_dict.get("description") or "",
        date=state_dict.get("date", ""),
        time=state_dict.get("time", ""),
        duration=state_dict.get("duration", ""),
        venue=state_dict.get("venue", ""),
        age_group=state_dict.get("age_group", ""),
        price=float(state_dict.get("price") or 0.0),
        vendor=state_dict.get("vendor") or "Store Vendor",
        product_type=state_dict.get("product_type") or "Workshop",
        topics=state_dict.get("topics") or [],
        poster_path=state_dict.get("poster_path"),
        video_url=state_dict.get("video_url"),
        sales_team_email=state_dict.get("sales_team_email") or "",
        input_folder_path=state_dict.get("product_folder_path"),
        custom_tags=state_dict.get("tags") or [],
        collection_name=state_dict.get("collection_name") or "Workshops",
        sku=state_dict.get("sku"),
        media=state_dict.get("media") or {},
        content=state_dict.get("content") or {},
        instructor=state_dict.get("instructor") or {},
        registration=state_dict.get("registration") or {}
    )

    workshop_id = state_dict.get("workshop_id")
    state = WorkshopService.process_workshop_input(input_data, workshop_id=workshop_id)
    
    # Step 2: Extract information
    state = WorkshopService.understand_workshop_information(state)
    
    # Step 3: Check assets
    state = WorkshopService.check_assets(state)

    # Step 4: Search existing products
    state = WorkshopService.search_existing_shopify_product(state)

    # Step 5: Prepare website content
    state = WorkshopService.prepare_website_content(state)

    # Step 5b: Design Template Replication Engine
    state = WorkshopService.prepare_template_generation(state)

    # Step 6: Prepare proposed Shopify payload
    state = WorkshopService.prepare_shopify_payload(state)

    # Step 7: Prepare registration config & hit PENDING_APPROVAL boundary
    state = WorkshopService.prepare_registration_config(state)

    # Update tool_context state
    state_dict["workshop_id"] = state.workshop_id
    state_dict["current_stage"] = state.current_state
    state_dict["status"] = state.current_state
    state_dict["approved_to_publish"] = (state.approval_status == "APPROVED")
    state_dict["duplicate_detected"] = (state.matched_candidate_id is not None)
    if state.matched_candidate_id:
        state_dict["existing_product_id"] = state.matched_candidate_id
        state_dict["existing_product_title"] = state.matched_candidate_title
    if state.conflicts_list:
        state_dict["conflicts_list"] = state.conflicts_list
        state_dict["duplicate_action"] = "ASK"

    if state.proposed_shopify_payload:
        state_dict["shopify_product"] = state.proposed_shopify_payload.dict()

    if state.website_content:
        state_dict["generated_description"] = state.website_content.formatted_description_html

    if state.visual_consistency_report:
        state_dict["visual_consistency_report"] = state.visual_consistency_report

    return json.dumps({
        "status": "success",
        "workshop_id": state.workshop_id,
        "current_state": state.current_state,
        "approval_status": state.approval_status,
        "matched_candidate_id": state.matched_candidate_id,
        "visual_consistency_score": state.visual_consistency_report.get("match_percentage") if state.visual_consistency_report else 100.0,
        "design_status": state.visual_consistency_report.get("status") if state.visual_consistency_report else "DESIGN_MATCH"
    })


def execute_approved_launch_tool(tool_context: ToolContext) -> str:
    """
    ADK Tool to execute Shopify product creation/update and run validation post approval.
    Does NOT automatically publish the product to 'active' status.
    """
    state_dict = tool_context.state

    if not state_dict.get("approved_to_publish", False):
        return json.dumps({
            "status": "error",
            "message": "Execution blocked: Workshop has not been approved."
        })

    w_id = state_dict.get("workshop_id", "unknown")

    # Reconstruct input & state object
    input_data = WorkshopInput(
        name=state_dict.get("product_name") or state_dict.get("name") or "Workshop",
        description=state_dict.get("raw_description") or "",
        price=float(state_dict.get("price") or 0.0),
        vendor=state_dict.get("vendor") or "Store Vendor",
        product_type=state_dict.get("product_type") or "Workshop"
    )

    state = WorkshopWorkflowState(
        workshop_id=w_id,
        current_state="APPROVED",
        input_data=input_data,
        approval_status="APPROVED",
        matched_candidate_id=state_dict.get("existing_product_id")
    )

    # Re-prepare payload if needed
    state = WorkshopService.prepare_website_content(state)
    state = WorkshopService.prepare_shopify_payload(state)

    # Step 9: Create or Update Shopify Product (as Draft)
    state = WorkshopService.create_or_update_shopify_product(state)
    if state.shopify_product_id:
        state_dict["shopify_product_id"] = state.shopify_product_id
        state_dict["shopify_variant_id"] = state.shopify_variant_id

    # Step 10: Run 53-item validation engine
    state = WorkshopService.run_product_validation(state)

    state_dict["current_stage"] = state.current_state
    state_dict["status"] = state.current_state
    state_dict["validation_results"] = state.validation_results

    return json.dumps({
        "status": "success",
        "workshop_id": state.workshop_id,
        "current_state": state.current_state,
        "shopify_product_id": state.shopify_product_id,
        "shopify_variant_id": state.shopify_variant_id,
        "validation_passed": (state.current_state == "LAUNCH_READY")
    })


# Instantiate Google ADK Agent
workshop_setup_agent = Agent(
    name="workshop_setup_agent",
    model="gemini-2.5-flash",
    description="Agent for managing modular Workshop setup, duplicate search, approval gating, validation, and publishing.",
    tools=[
        ingest_workshop_input_tool,
        execute_approved_launch_tool
    ]
)
