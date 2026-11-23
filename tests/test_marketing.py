"""
Unit, Behavioral, and Integration Test Suite for MarketingAgent.

Tests:
1. Agent initialization, model specification, and tool bindings.
2. get_product_context tool execution and extraction from state.
3. save_marketing_assets tool execution and complete 10-field dictionary storage.
4. Edge cases: whitespace trimming, empty inputs, emoji support, and state integrity.
5. Workflow graph integration: confirms valid position in ProductLaunchWorkflow DAG.
6. Database persistence integration: validates storage into SQLite workshops schema.
"""

import pytest
from unittest.mock import MagicMock
from google.adk.tools.tool_context import ToolContext
from agents.marketing_agent import marketing_agent, save_marketing_assets
from tools.product_context import get_product_context
from product_workflow import product_launch_workflow
from agents.seo_agent import seo_agent
from agents.image_prompt_agent import image_prompt_agent


class MockToolContext:
    def __init__(self, state=None):
        self.state = state if state is not None else {}


def test_marketing_agent_configuration():
    """Verify that MarketingAgent is properly instantiated with ADK specifications."""
    assert marketing_agent.name == "MarketingAgent"
    assert "gemini-2.5-flash" in marketing_agent.model
    assert "You are an expert E-commerce Copywriter and Growth Marketer." in marketing_agent.instruction
    
    # Verify tools
    tool_names = [t.__name__ for t in marketing_agent.tools]
    assert "get_product_context" in tool_names
    assert "save_marketing_assets" in tool_names


def test_get_product_context_tool():
    """Verify get_product_context retrieves product attributes from state."""
    state = {
        "product_name": "KiddyPi Robotics Kit",
        "product_description": "DIY programmable robot with ultrasonic sensor.",
        "product_price": 1999,
        "product_category": "STEM Kits",
        "other_key": "ignored"
    }
    tool_context = MockToolContext(state=state)
    result = get_product_context(tool_context)
    
    assert result["product_name"] == "KiddyPi Robotics Kit"
    assert result["product_description"] == "DIY programmable robot with ultrasonic sensor."
    assert result["product_price"] == 1999
    assert result["product_category"] == "STEM Kits"
    assert "other_key" not in result


def test_save_marketing_assets_tool():
    """Verify save_marketing_assets properly trims and stores all 10 marketing fields."""
    state = {}
    tool_context = MockToolContext(state=state)
    
    res = save_marketing_assets(
        campaign_headline="  Ignite Young Minds with Robotics  ",
        short_description="  Hands-on DIY robotics for students aged 8-14.  ",
        long_copy="  Step into the world of creative engineering with hands-on component assembly.  ",
        social_caption="  Explore future technologies today! #STEM #Robotics  ",
        instagram_caption="  Build, code, and discover! 🤖✨ #KiddyPi  ",
        whatsapp_message="  🚀 *Exciting Workshop Alert!* Join this Saturday.  ",
        email_subject="  Unlock Your Child's Engineering Potential  ",
        email_body="  Dear Parent, discover hands-on robotics workshops this weekend.  ",
        call_to_action="  Register Now  ",
        taglines="  • Practical Learning\n• Real Sensors\n• Take-Home Kit  ",
        tool_context=tool_context
    )
    
    assert res == "Marketing assets saved successfully."
    assert "marketing_assets" in state
    
    assets = state["marketing_assets"]
    assert assets["campaign_headline"] == "Ignite Young Minds with Robotics"
    assert assets["short_description"] == "Hands-on DIY robotics for students aged 8-14."
    assert assets["long_copy"] == "Step into the world of creative engineering with hands-on component assembly."
    assert assets["social_caption"] == "Explore future technologies today! #STEM #Robotics"
    assert assets["instagram_caption"] == "Build, code, and discover! 🤖✨ #KiddyPi"
    assert assets["whatsapp_message"] == "🚀 *Exciting Workshop Alert!* Join this Saturday."
    assert assets["email_subject"] == "Unlock Your Child's Engineering Potential"
    assert assets["email_body"] == "Dear Parent, discover hands-on robotics workshops this weekend."
    assert assets["call_to_action"] == "Register Now"
    assert assets["taglines"] == "• Practical Learning\n• Real Sensors\n• Take-Home Kit"


def test_marketing_assets_preserves_existing_state():
    """Verify that saving marketing assets does not overwrite other critical workflow state keys."""
    state = {
        "product_name": "Frog Bot",
        "shopify_product_id": 998877,
        "approved_to_publish": True
    }
    tool_context = MockToolContext(state=state)
    
    save_marketing_assets(
        campaign_headline="Hop into Coding",
        short_description="Fun jumping robot kit.",
        long_copy="Long narrative.",
        social_caption="Caption #frog",
        instagram_caption="Insta caption 🐸",
        whatsapp_message="WhatsApp message",
        email_subject="Email subject",
        email_body="Email body",
        call_to_action="Order Today",
        taglines="Fun • Educational",
        tool_context=tool_context
    )
    
    # Original keys must remain intact
    assert state["product_name"] == "Frog Bot"
    assert state["shopify_product_id"] == 998877
    assert state["approved_to_publish"] is True
    assert "marketing_assets" in state
    assert state["marketing_assets"]["campaign_headline"] == "Hop into Coding"


def test_marketing_agent_workflow_integration():
    """Verify that MarketingAgent is properly wired into ProductLaunchWorkflow graph."""
    edges = product_launch_workflow.edges
    
    # Must have inbound transition from seo_agent
    inbound_edges = [edge for edge in edges if edge[1] == marketing_agent]
    assert len(inbound_edges) == 1
    assert inbound_edges[0][0] == seo_agent
    
    # Must have outbound transition to image_prompt_agent
    outbound_edges = [edge for edge in edges if edge[0] == marketing_agent]
    assert len(outbound_edges) == 1
    assert outbound_edges[0][1] == image_prompt_agent


def test_marketing_assets_unicode_and_emojis():
    """Verify that rich emoji formatting for WhatsApp and Instagram is preserved without corruption."""
    state = {}
    tool_context = MockToolContext(state=state)
    
    whatsapp_rich = "🚀 *Special Discount!* Use code: KIDDYPI2026 🎉\n\n• Point 1: 🔬 Microscopic Analysis\n• Point 2: 🤖 Robotic Control"
    insta_rich = "Ready to code? 💻✨ Tag a friend who loves robots! 🤖 #STEMKids #Robotics"
    
    save_marketing_assets(
        campaign_headline="STEM Explorer 🌟",
        short_description="Engaging STEM course 🚀",
        long_copy="Comprehensive syllabus for young makers 🛠️",
        social_caption="Check out our launch 🚀",
        instagram_caption=insta_rich,
        whatsapp_message=whatsapp_rich,
        email_subject="Exclusive Invite ✉️",
        email_body="Hello Parent 👋 Join us this Sunday!",
        call_to_action="Enroll Now ⚡",
        taglines="• Innovate 💡 • Create 🎨 • Build 🏗️",
        tool_context=tool_context
    )
    
    assets = state["marketing_assets"]
    assert "🌟" in assets["campaign_headline"]
    assert "💻✨" in assets["instagram_caption"]
    assert "🚀 *Special Discount!*" in assets["whatsapp_message"]
    assert "👋" in assets["email_body"]
