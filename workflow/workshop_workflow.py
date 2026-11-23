"""
Workshop Setup Workflow Definition & Execution Runner.

Provides Google ADK Workflow graph definition for Workshop Setup Agent
and asynchronous runner functions.
"""

import logging
from typing import Dict, Any, Optional
from google.adk import Workflow
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.workshop_setup_agent import workshop_setup_agent, ingest_workshop_input_tool, execute_approved_launch_tool
from services.workshop_service import WorkshopService, WorkshopInput, WorkshopWorkflowState

logger = logging.getLogger("workshop_workflow")

# ADK Workflow definition
workshop_setup_workflow = Workflow(
    name="WorkshopSetupWorkflow",
    edges=[
        ("START", workshop_setup_agent),
    ],
)


async def run_workshop_workflow_session(
    session_id: str,
    initial_state: Dict[str, Any],
    session_service: Optional[InMemorySessionService] = None
) -> Dict[str, Any]:
    """
    Asynchronously executes pre-approval workshop preparation pipeline.
    Transforms raw input -> structured metadata -> asset check -> search match -> draft payload -> PENDING_APPROVAL boundary.
    """
    input_data = WorkshopInput(
        name=initial_state.get("product_name") or initial_state.get("name") or "Untitled Workshop",
        description=initial_state.get("raw_description") or initial_state.get("description") or "",
        date=initial_state.get("date", ""),
        time=initial_state.get("time", ""),
        duration=initial_state.get("duration", ""),
        venue=initial_state.get("venue", ""),
        age_group=initial_state.get("age_group", ""),
        price=float(initial_state.get("price") or 0.0),
        vendor=initial_state.get("vendor") or "Store Vendor",
        product_type=initial_state.get("product_type") or "Workshop",
        topics=initial_state.get("topics") or [],
        poster_path=initial_state.get("poster_path"),
        video_url=initial_state.get("video_url"),
        sales_team_email=initial_state.get("sales_team_email") or "",
        input_folder_path=initial_state.get("product_folder_path"),
        custom_tags=initial_state.get("tags") or [],
        collection_name=initial_state.get("collection_name") or "Workshops",
        sku=initial_state.get("sku")
    )

    workshop_id = initial_state.get("workshop_id")
    state = WorkshopService.process_workshop_input(input_data, workshop_id=workshop_id)
    state = WorkshopService.understand_workshop_information(state)
    state = WorkshopService.check_assets(state)
    state = WorkshopService.search_existing_shopify_product(state)
    state = WorkshopService.prepare_website_content(state)
    state = WorkshopService.prepare_shopify_payload(state)
    state = WorkshopService.prepare_registration_config(state)

    # Persist state variables back to dictionary
    initial_state["workshop_id"] = state.workshop_id
    initial_state["current_stage"] = state.current_state
    initial_state["status"] = state.current_state
    initial_state["approved_to_publish"] = (state.approval_status == "APPROVED")
    initial_state["duplicate_detected"] = (state.matched_candidate_id is not None)
    if state.matched_candidate_id:
        initial_state["existing_product_id"] = state.matched_candidate_id
        initial_state["existing_product_title"] = state.matched_candidate_title
    if state.conflicts_list:
        initial_state["conflicts_list"] = state.conflicts_list
        initial_state["duplicate_action"] = "ASK"
    if state.proposed_shopify_payload:
        initial_state["shopify_product"] = state.proposed_shopify_payload.dict()
    if state.website_content:
        initial_state["generated_description"] = state.website_content.formatted_description_html

    logger.info("Workshop workflow session %s completed pre-approval stage (%s)", session_id, state.current_state)
    return initial_state
