"""
Phase 1 Focused Tests -- SEO Metadata Integration, Validation & Shopify Publishing.
All tests use deterministic mocks with ZERO dependencies on live Vertex AI billing
or external Shopify network endpoints.
"""

from unittest.mock import MagicMock, patch
import pytest

from agents.seo_agent import save_enhanced_seo_metadata, save_seo_metadata
from agents.publisher_agent import publish_to_shopify
from services.seo_validator import (
    validate_seo_metadata,
    normalize_and_validate_keywords,
    sanitize_handle,
)
from shopify_client import ShopifyAPIError


def _mock_tool_context(state_dict):
    """Minimal ADK ToolContext stand-in exposing only `.state` as a dict."""
    ctx = MagicMock()
    ctx.state = state_dict
    return ctx


# ==============================================================================
# 1. Deterministic Validation & Keyword Normalization Tests
# ==============================================================================

def test_sanitize_handle():
    """Verify handle sanitization collapses special chars, spaces, and hyphens."""
    assert sanitize_handle("Wireless Earbuds - ANC 2026!") == "wireless-earbuds-anc-2026"
    assert sanitize_handle("  STEM Robot Kit @#$ v2.0  ") == "stem-robot-kit-v2-0"
    assert sanitize_handle("---Leading & Trailing---") == "leading-trailing"
    assert sanitize_handle("") == "product"


def test_normalize_and_validate_keywords():
    """Verify keywords normalization removes duplicates and strips punctuation."""
    raw = "stem toy, robotics, STEM toy,  coding kit , robot! , a"
    tags_list, tags_str = normalize_and_validate_keywords(raw)
    assert "stem toy" in tags_list
    assert "robotics" in tags_list
    assert "coding kit" in tags_list
    assert "robot" in tags_list
    assert len(tags_list) == 4  # 'a' filtered out (<2 chars), duplicate 'stem toy' deduplicated
    assert tags_str == "stem toy, robotics, coding kit, robot"


def test_validate_seo_metadata_lengths_and_claims():
    """Verify field length rules and detection of unsupported speculative claims."""
    seo_meta = {
        "title": "Super Advanced Guaranteed Admission Robot Kit for Young Engineers",  # 65 chars
        "description": "Short desc",  # < 100 chars
        "slug": "robot-kit",
        "keywords": "robot, coding",
    }
    res = validate_seo_metadata(seo_meta, product_name="Robot Kit")
    
    # Title length check warning
    assert any("exceeds 60 characters" in w for w in res.warnings)
    # Short description check warning
    assert any("Meta description is short" in w for w in res.warnings)
    # Unsupported claim error
    assert any("guaranteed admission" in err.lower() for err in res.errors)
    assert res.is_valid is False


# ==============================================================================
# 2. SEO Agent State Integration Tests
# ==============================================================================

def test_seo_agent_save_enhanced_metadata():
    """Verify SEOAgent tool stores validated metadata in shared state."""
    ctx = _mock_tool_context({
        "product_name": "Arduino Starter Kit",
        "product_description": "Comprehensive microcontroller learning kit with sensors.",
    })

    result = save_enhanced_seo_metadata(
        seo_title="Arduino Starter Kit for Beginners",
        meta_description="Learn electronics and robotics with the Arduino Starter Kit. Includes 30+ components and sensors.",
        primary_keyword="arduino starter kit",
        secondary_keywords="arduino kit, robotics kit, beginner electronics",
        search_intent="Commercial STEM Education",
        url_slug="arduino-starter-kit-beginners",
        product_tags="arduino, robotics, stem kit",
        product_description_recommendations="Highlight hands-on sensor projects.",
        image_alt_text_recommendations="Arduino starter kit components and breadboard",
        tool_context=ctx,
    )

    assert "validated and saved successfully" in result
    saved = ctx.state.get("seo_metadata")
    assert saved is not None
    assert saved["title"] == "Arduino Starter Kit for Beginners"
    assert saved["slug"] == "arduino-starter-kit-beginners"
    assert "arduino starter kit" in saved["keywords"]
    assert saved["is_valid"] is True


def test_seo_agent_save_seo_metadata_backwards_compatible():
    """Verify legacy 4-argument save_seo_metadata works seamlessly."""
    ctx = _mock_tool_context({
        "product_name": "Solar Rover Kit",
        "product_description": "Build a solar-powered rover.",
    })

    result = save_seo_metadata(
        seo_title="Solar Rover Kit for Kids",
        meta_description="Eco-friendly solar rover engineering kit designed for young builders.",
        keywords="solar rover, stem toy, solar car",
        url_slug="solar-rover-kit",
        tool_context=ctx,
    )

    assert "validated and saved successfully" in result
    saved = ctx.state.get("seo_metadata")
    assert saved["title"] == "Solar Rover Kit for Kids"
    assert saved["slug"] == "solar-rover-kit"


# ==============================================================================
# 3. Publisher Agent Integration & Mapping Tests
# ==============================================================================

@patch("agents.publisher_agent.create_product")
@patch("shopify_client.get_product")
@patch("services.image_generation_service.ImageGenerationService.generate_and_verify_all")
@patch("services.shopify_media_service.ShopifyMediaService.upload_and_attach_all")
@patch("services.shopify_media_service.ShopifyMediaService.verify_media")
def test_publisher_passes_seo_fields_to_shopify(
    mock_verify_media,
    mock_upload_media,
    mock_generate_images,
    mock_get_product,
    mock_create_product,
):
    """Verify publisher extracts SEO metadata and passes seo_title, seo_description, and handle."""
    mock_create_product.return_value = {
        "id": 88001,
        "title": "STEM Coding Robot",
        "url": "https://test-shop.myshopify.com/products/stem-coding-robot",
        "variants": [{"id": 99001}],
    }
    mock_get_product.return_value = {
        "id": 88001,
        "title": "STEM Coding Robot",
        "seo_title": "STEM Coding Robot for Kids 8-12",
        "seo_description": "Hands-on programmable robot kit designed for children to learn Python and scratch coding.",
        "handle": "stem-coding-robot",
        "url": "https://test-shop.myshopify.com/products/stem-coding-robot",
    }
    mock_generate_images.return_value = {"image_paths": [], "details": []}
    mock_upload_media.return_value = []
    mock_verify_media.return_value = []

    ctx = _mock_tool_context({
        "approved_to_publish": True,
        "product_name": "STEM Coding Robot",
        "product_description": "Programmable educational robot.",
        "product_price": 3499.0,
        "product_category": "Robotics",
        "generated_description": "<h2>Learn Python with Fun Robotics</h2>",
        "seo_metadata": {
            "title": "STEM Coding Robot for Kids 8-12",
            "description": "Hands-on programmable robot kit designed for children to learn Python and scratch coding.",
            "slug": "stem-coding-robot",
            "keywords": "stem robot, coding for kids, educational robot",
        },
    })

    result = publish_to_shopify(ctx)
    assert "Product published successfully" in result
    assert "WARNING: Shopify SEO field verification failed" not in result

    # Assert create_product arguments
    mock_create_product.assert_called_once()
    kwargs = mock_create_product.call_args.kwargs
    assert kwargs["title"] == "STEM Coding Robot"
    assert kwargs["body_html"] == "<h2>Learn Python with Fun Robotics</h2>"
    assert kwargs["price"] == 3499.0
    assert kwargs["status"] == "draft"
    assert kwargs["seo_title"] == "STEM Coding Robot for Kids 8-12"
    assert kwargs["seo_description"] == "Hands-on programmable robot kit designed for children to learn Python and scratch coding."
    assert kwargs["handle"] == "stem-coding-robot"
    assert "stem robot" in kwargs["tags"]

    # Assert verification in session state
    verification = ctx.state.get("seo_verification")
    assert verification is not None
    assert verification["verified"] is True
    assert verification["mismatches"] == []


@patch("agents.publisher_agent.create_product")
@patch("shopify_client.get_product")
@patch("services.image_generation_service.ImageGenerationService.generate_and_verify_all")
@patch("services.shopify_media_service.ShopifyMediaService.upload_and_attach_all")
@patch("services.shopify_media_service.ShopifyMediaService.verify_media")
def test_publisher_detects_seo_verification_mismatch(
    mock_verify_media,
    mock_upload_media,
    mock_generate_images,
    mock_get_product,
    mock_create_product,
):
    """Verify publisher warns when Shopify fails to save expected SEO fields."""
    mock_create_product.return_value = {
        "id": 88002,
        "title": "Sensor Kit",
        "url": "https://test-shop.myshopify.com/products/sensor-kit",
        "variants": [{"id": 99002}],
    }
    # Simulate Shopify dropping or truncating the meta description and modifying handle
    mock_get_product.return_value = {
        "id": 88002,
        "title": "Sensor Kit",
        "seo_title": "Sensor Kit",
        "seo_description": "",  # Disappeared!
        "handle": "sensor-kit-1",  # Changed!
        "url": "https://test-shop.myshopify.com/products/sensor-kit-1",
    }
    mock_generate_images.return_value = {"image_paths": [], "details": []}
    mock_upload_media.return_value = []
    mock_verify_media.return_value = []

    ctx = _mock_tool_context({
        "approved_to_publish": True,
        "product_name": "Sensor Kit",
        "product_description": "Electronics sensor module set.",
        "product_price": 1499.0,
        "product_category": "Electronics",
        "generated_description": "<h2>Complete Sensor Kit</h2>",
        "seo_metadata": {
            "title": "Sensor Kit",
            "description": "Essential sensor kit for beginner electronic projects.",
            "slug": "sensor-kit",
        },
    })

    result = publish_to_shopify(ctx)
    assert "WARNING: Shopify SEO field verification failed" in result

    verification = ctx.state.get("seo_verification")
    assert verification["verified"] is False
    assert len(verification["mismatches"]) >= 1


@patch("agents.publisher_agent.create_product")
@patch("shopify_client.get_product")
@patch("services.image_generation_service.ImageGenerationService.generate_and_verify_all")
@patch("services.shopify_media_service.ShopifyMediaService.upload_and_attach_all")
@patch("services.shopify_media_service.ShopifyMediaService.verify_media")
def test_publisher_missing_seo_metadata_safe_fallback(
    mock_verify_media,
    mock_upload_media,
    mock_generate_images,
    mock_get_product,
    mock_create_product,
):
    """Verify missing seo_metadata safely falls back to product details without crashing."""
    mock_create_product.return_value = {
        "id": 88003,
        "title": "Solar Toy",
        "url": "https://test-shop.myshopify.com/products/solar-toy",
        "variants": [{"id": 99003}],
    }
    mock_get_product.return_value = {
        "id": 88003,
        "title": "Solar Toy",
        "seo_title": "Solar Toy",
        "seo_description": "Solar toy snippet.",
        "handle": "solar-toy",
    }
    mock_generate_images.return_value = {"image_paths": [], "details": []}
    mock_upload_media.return_value = []
    mock_verify_media.return_value = []

    # Note: seo_metadata is completely missing
    ctx = _mock_tool_context({
        "approved_to_publish": True,
        "product_name": "Solar Toy",
        "product_description": "Solar powered engineering toy for young children.",
        "product_price": 999.0,
        "product_category": "Toys",
        "generated_description": "<h2>Eco-Friendly Solar Toy</h2>",
    })

    result = publish_to_shopify(ctx)
    assert "Product published successfully" in result
    mock_create_product.assert_called_once()
    kwargs = mock_create_product.call_args.kwargs
    # Title defaulted safely from product_name
    assert kwargs["seo_title"] == "Solar Toy"
    assert kwargs["handle"] == "solar-toy"


@patch("agents.publisher_agent.create_product")
def test_publisher_handles_shopify_api_failure(mock_create_product):
    """Verify ShopifyAPIError is caught and surfaced cleanly without uncaught exception."""
    mock_create_product.side_effect = ShopifyAPIError("Shopify API error (422): Handle already in use")

    ctx = _mock_tool_context({
        "approved_to_publish": True,
        "product_name": "Drone Kit",
        "product_description": "Quadcopter build kit.",
        "product_price": 4999.0,
        "product_category": "Robotics",
        "generated_description": "<h2>Build Your Own Drone</h2>",
        "seo_metadata": {"title": "Drone Kit", "slug": "drone-kit"},
    })

    result = publish_to_shopify(ctx)
    assert "Publishing failed: Shopify API error (422): Handle already in use" in result


def test_publisher_approval_gate_enforced():
    """Verify publishing is strictly skipped if approved_to_publish is False."""
    ctx = _mock_tool_context({
        "approved_to_publish": False,
        "product_name": "Unapproved Drone",
        "product_description": "Unapproved description.",
        "product_price": 4999.0,
        "product_category": "Robotics",
        "generated_description": "<h2>Build Your Own Drone</h2>",
    })

    result = publish_to_shopify(ctx)
    assert result == "Publishing skipped: Awaiting admin approval."

