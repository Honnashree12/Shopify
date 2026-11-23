"""
Phase 2 Focused Tests -- Existing Shopify Products SEO Audit & Optimization.
Tests audit detection, recommendation engine, dry-run mode, approval gating,
and preservation of non-SEO fields using deterministic mocks with ZERO dependencies
on live Vertex AI billing or real Shopify network endpoints.
"""

from unittest.mock import MagicMock, patch
import pytest

from agents.seo_audit_agent import ProductSEOAudit, audit_catalogue_seo, calculate_text_similarity
from agents.seo_optimizer_agent import SEOOptimizerAgent
from workflow.seo_optimization_workflow import SEOOptimizationWorkflow
from shopify_client import ShopifyAPIError


# ==============================================================================
# 1. Product SEO Audit Tests
# ==============================================================================

def test_audit_identifies_missing_and_invalid_fields():
    """Verify audit flags missing title, missing description, missing tags, and invalid handle."""
    product = {
        "id": 101,
        "title": "Robotics Sensor Board",
        "body_html": "<p>Quick sensor.</p>",  # Weak description (<25 words)
        "handle": "Sensor Board 101!",  # Invalid handle with spaces and special chars
        "tags": [],  # Missing tags
        "seo_title": "",  # Missing SEO title
        "seo_description": "",  # Missing meta description
        "images": [{"id": 501, "alt": ""}],  # Missing image ALT
    }

    audit = ProductSEOAudit.audit_product(product)

    issue_codes = [i["code"] for i in audit["issues"]]
    assert "MISSING_SEO_TITLE" in issue_codes
    assert "MISSING_META_DESCRIPTION" in issue_codes
    assert "WEAK_PRODUCT_DESCRIPTION" in issue_codes
    assert "MISSING_PRODUCT_TAGS" in issue_codes
    assert "MISSING_IMAGE_ALT_TEXT" in issue_codes
    assert "INVALID_URL_HANDLE" in issue_codes

    assert audit["status"] == "NEEDS_OPTIMIZATION"
    assert audit["seo_score"] < 50
    assert "internal technical checklist" in audit["disclaimer"].lower()


def test_audit_flags_excessive_lengths():
    """Verify audit warns when SEO title exceeds 60 chars and meta description exceeds 165 chars."""
    product = {
        "id": 102,
        "title": "Arduino Mega Microcontroller Board for Advanced Engineering Students",
        "body_html": "<p>" + ("Comprehensive microcontroller details with specifications. " * 15) + "</p>",
        "handle": "arduino-mega-board",
        "tags": ["arduino", "robotics", "stem", "coding"],
        "seo_title": "Arduino Mega Microcontroller Board for Advanced Engineering Students and Makers",  # 79 chars
        "seo_description": (
            "Learn microcontrollers with the ultimate Arduino Mega board featuring 54 digital I/O pins, "
            "16 analog inputs, 4 UARTs, and full USB connectivity for extensive robotics and automation projects worldwide."
        ),  # 214 chars
        "images": [{"id": 502, "alt": "Arduino Mega microcontroller board"}],
    }

    audit = ProductSEOAudit.audit_product(product)
    issue_codes = [i["code"] for i in audit["issues"]]
    assert "EXCESSIVE_SEO_TITLE_LENGTH" in issue_codes
    assert "EXCESSIVE_META_DESCRIPTION_LENGTH" in issue_codes
    assert audit["status"] == "CAN_IMPROVE"


def test_audit_detects_duplicate_seo_across_catalogue():
    """Verify audit flags near-identical SEO titles and descriptions across different products."""
    prod_a = {
        "id": 201,
        "title": "Solar Car Kit v1",
        "handle": "solar-car-kit-v1",
        "seo_title": "Solar Powered Car Engineering Kit | KiddyPi",
        "seo_description": "Build an eco-friendly solar car kit with solar panel and DC motor for kids.",
        "tags": ["solar", "car", "stem"],
        "images": [{"id": 601, "alt": "Solar car kit"}],
    }
    prod_b = {
        "id": 202,
        "title": "Solar Car Kit v2",
        "handle": "solar-car-kit-v2",
        "seo_title": "Solar Powered Car Engineering Kit | KiddyPi",  # Identical title
        "seo_description": "Build an eco-friendly solar car kit with solar panel and DC motor for kids.",  # Identical desc
        "tags": ["solar", "car", "stem"],
        "images": [{"id": 602, "alt": "Solar car kit"}],
    }

    audit_b = ProductSEOAudit.audit_product(prod_b, all_products=[prod_a, prod_b])
    issue_codes = [i["code"] for i in audit_b["issues"]]
    assert "DUPLICATE_SEO_TITLE" in issue_codes
    assert "DUPLICATE_META_DESCRIPTION" in issue_codes


def test_audit_catalogue_seo_summary():
    """Verify catalogue-wide audit produces rollup metrics and issue breakdown."""
    catalogue = [
        {
            "id": 301,
            "title": "Product One",
            "body_html": "<p>" + ("Good content. " * 30) + "</p>",
            "handle": "product-one",
            "tags": ["stem", "kit", "robotics", "coding"],
            "seo_title": "Product One | KiddyPi",
            "seo_description": "A high-quality educational STEM product designed for hands-on learning and creativity.",
            "images": [{"id": 701, "alt": "Product one photo"}],
        },
        {
            "id": 302,
            "title": "Product Two",
            "body_html": "<p>Short.</p>",
            "handle": "product-two",
            "tags": [],
            "seo_title": "",
            "seo_description": "",
            "images": [],
        },
    ]

    report = audit_catalogue_seo(catalogue)
    assert report["total_audited"] == 2
    assert report["products_with_issues"] >= 1
    assert "average_seo_score" in report
    assert "issue_breakdown" in report
    assert "MISSING_SEO_TITLE" in report["issue_breakdown"]


# ==============================================================================
# 2. SEO Optimizer Agent Recommendation Tests
# ==============================================================================

def test_optimizer_generates_before_and_after_proposals():
    """Verify optimizer produces compliant before-and-after proposals with reasons."""
    product = {
        "id": 401,
        "title": "Robotics DIY Arm Kit",
        "body_html": "<p>Build a 4-axis robotic arm with servos, acrylic frame, and joystick controllers. Perfect for STEM students learning robotics.</p>",
        "handle": "robotics-diy-arm-kit",
        "product_type": "Robotics Kits",
        "seo_title": "",  # Missing
        "seo_description": "",  # Missing
        "tags": "robot, arm",
        "images": [
            {"id": 801, "alt": ""},
            {"id": 802, "alt": "Old packaging"},
        ],
    }

    proposal = SEOOptimizerAgent.generate_recommendations(product, brand_name="KiddyPi", preserve_handle=True)

    assert proposal["product_id"] == "401"
    assert proposal["product_title"] == "Robotics DIY Arm Kit"

    # Before snapshot
    assert proposal["before"]["seo_title"] == "(Default Title)"
    assert proposal["before"]["handle"] == "robotics-diy-arm-kit"

    # After snapshot
    after = proposal["after"]
    assert len(after["seo_title"]) <= 60
    assert "Robotics DIY Arm Kit" in after["seo_title"]
    assert "KiddyPi" in after["seo_title"]

    assert 130 <= len(after["seo_description"]) <= 165
    assert len(after["tags"]) >= 4

    # Image ALT text suggestions
    alts = after["image_alts"]
    assert len(alts) == 2
    assert alts[0]["recommended_alt"] != ""
    assert "Robotics DIY Arm Kit" in alts[0]["recommended_alt"]

    # Handle preservation rule
    assert after["handle"] == "robotics-diy-arm-kit"
    assert after["handle_changed"] is False

    # Reasons summary
    assert len(proposal["changes_summary"]) >= 3


def test_optimizer_preserves_handle_by_default():
    """Verify existing handle is preserved by default to protect live URLs and backlinks."""
    product = {
        "id": 402,
        "title": "Legacy Product Title Changed",
        "handle": "original-legacy-url-handle-2023",
        "body_html": "<p>Description</p>",
    }

    proposal = SEOOptimizerAgent.generate_recommendations(product, preserve_handle=True)
    assert proposal["after"]["handle"] == "original-legacy-url-handle-2023"
    assert proposal["after"]["handle_changed"] is False


# ==============================================================================
# 3. SEO Optimization Workflow Tests (Dry-Run & Approval Enforcement)
# ==============================================================================

def test_workflow_dry_run_never_mutates_shopify():
    """Verify dry_run=True simulates updates and produces a preview with ZERO API mutations."""
    approved_proposals = [
        {
            "product_id": 501,
            "after": {
                "seo_title": "Optimized STEM Drone Kit | KiddyPi",
                "seo_description": "Explore aerial robotics with the STEM Drone Kit. Build and code your own quadcopter with KiddyPi today!",
                "tags": ["drone", "stem", "robotics", "coding"],
                "handle": "drone-kit",
                "image_alts": [{"image_id": 901, "recommended_alt": "STEM Drone Kit flying"}],
            },
            "approve_handle_change": False,
        }
    ]

    summary = SEOOptimizationWorkflow.apply_approved_optimizations(
        approved_proposals=approved_proposals,
        dry_run=True,
    )

    assert summary["dry_run"] is True
    assert summary["successful_updates"] == 1
    assert summary["failed_updates"] == 0
    assert summary["details"][0]["status"] == "SIMULATED_SUCCESS"
    assert summary["details"][0]["fields_to_update"]["seo_title"] == "Optimized STEM Drone Kit | KiddyPi"


@patch("workflow.seo_optimization_workflow.get_product")
@patch("workflow.seo_optimization_workflow.update_product")
@patch("workflow.seo_optimization_workflow.update_product_image_alt")
def test_workflow_applies_approved_updates_and_preserves_unrelated_fields(
    mock_update_alt,
    mock_update_product,
    mock_get_product,
):
    """Verify live updates modify ONLY approved SEO fields and assert price/status preservation."""
    # Mock baseline product
    mock_get_product.side_effect = [
        # Call 1: Baseline fetch before update
        {
            "id": 601,
            "title": "AI Vision Kit",
            "price": 4999.0,
            "status": "draft",
            "handle": "ai-vision-kit",
            "seo_title": "",
            "seo_description": "",
            "tags": "ai, vision",
        },
        # Call 2: Independent verification re-fetch after update
        {
            "id": 601,
            "title": "AI Vision Kit",
            "price": 4999.0,  # Strict preservation
            "status": "draft",  # Strict preservation
            "handle": "ai-vision-kit",
            "seo_title": "AI Vision Sensor Kit | KiddyPi",
            "seo_description": "Build edge AI vision applications with the AI Vision Sensor Kit. Shop high-quality STEM kits at KiddyPi!",
            "tags": "ai vision kit, edge ai, stem, robotics",
        },
    ]

    mock_update_product.return_value = {"id": 601, "status": "draft"}
    mock_update_alt.return_value = True

    approved_proposals = [
        {
            "product_id": 601,
            "after": {
                "seo_title": "AI Vision Sensor Kit | KiddyPi",
                "seo_description": "Build edge AI vision applications with the AI Vision Sensor Kit. Shop high-quality STEM kits at KiddyPi!",
                "tags": ["ai vision kit", "edge ai", "stem", "robotics"],
                "handle": "ai-vision-kit",
                "image_alts": [{"image_id": 911, "recommended_alt": "AI Vision Kit camera sensor"}],
            },
            "approve_handle_change": False,
        }
    ]

    summary = SEOOptimizationWorkflow.apply_approved_optimizations(
        approved_proposals=approved_proposals,
        user_email="admin@kiddypi.com",
        dry_run=False,
    )

    assert summary["dry_run"] is False
    assert summary["successful_updates"] == 1
    assert summary["failed_updates"] == 0

    detail = summary["details"][0]
    assert detail["status"] == "SUCCESS"
    assert detail["seo_title_verified"] is True
    assert detail["seo_desc_verified"] is True
    assert detail["unrelated_fields_preserved"] is True

    # Assert update_product was called with ONLY SEO fields
    mock_update_product.assert_called_once_with(
        601,
        seo_title="AI Vision Sensor Kit | KiddyPi",
        seo_description="Build edge AI vision applications with the AI Vision Sensor Kit. Shop high-quality STEM kits at KiddyPi!",
        tags="ai vision kit, edge ai, stem, robotics",
    )
    # Assert price, inventory, status were NOT passed to update_product
    call_kwargs = mock_update_product.call_args.kwargs
    assert "price" not in call_kwargs
    assert "status" not in call_kwargs
    assert "variants" not in call_kwargs

    # Assert image ALT text was updated
    mock_update_alt.assert_called_once_with(601, 911, "AI Vision Kit camera sensor")


@patch("workflow.seo_optimization_workflow.get_product")
@patch("workflow.seo_optimization_workflow.update_product")
def test_workflow_handles_partial_api_failure_gracefully(
    mock_update_product,
    mock_get_product,
):
    """Verify workflow handles individual product failures cleanly without crashing entire run."""
    mock_get_product.return_value = {
        "id": 701,
        "title": "Faulty Product",
        "price": 1000.0,
        "status": "draft",
    }
    mock_update_product.side_effect = ShopifyAPIError("Shopify API 500: Server temporary error")

    approved_proposals = [
        {
            "product_id": 701,
            "after": {
                "seo_title": "Faulty Product | KiddyPi",
                "seo_description": "Valid meta description for faulty product test.",
                "tags": ["test"],
                "image_alts": [],
            },
            "approve_handle_change": False,
        }
    ]

    summary = SEOOptimizationWorkflow.apply_approved_optimizations(
        approved_proposals=approved_proposals,
        dry_run=False,
    )

    assert summary["successful_updates"] == 0
    assert summary["failed_updates"] == 1
    assert summary["details"][0]["status"] == "FAILED"
    assert "Shopify API 500" in summary["details"][0]["error"]

