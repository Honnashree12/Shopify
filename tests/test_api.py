# pyrefly: ignore [missing-import]
import pytest
import sys
import os

os.environ["TESTING"] = "True"
os.environ["ALLOW_AUTH_FALLBACK"] = "True"

# Adjust path to import main and state
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
import main

app = main.app
client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_all_background_tasks():
    import sys
    from unittest.mock import MagicMock
    
    main_modules = [m for n, m in sys.modules.items() if n == "main" or n.endswith(".main")]
    orig_adk = {}
    orig_folder = {}
    
    for m in main_modules:
        if hasattr(m, "run_adk_workflow_background"):
            orig_adk[m] = m.run_adk_workflow_background
            m.run_adk_workflow_background = MagicMock()
        if hasattr(m, "run_folder_workflow_background"):
            orig_folder[m] = m.run_folder_workflow_background
            m.run_folder_workflow_background = MagicMock()
            
    yield
    
    for m, orig in orig_adk.items():
        m.run_adk_workflow_background = orig
    for m, orig in orig_folder.items():
        m.run_folder_workflow_background = orig

def test_health_check():
    """Verify that the health check endpoint returns 200 and ADK is ready.

    Phase 5 made /health's top-level "status" reflect real sub-component
    connectivity instead of always returning "healthy" (see main.py's
    health() -- a broken Shopify connection now correctly degrades overall
    status instead of masking it). This sandbox has no real Shopify
    credentials, so "degraded" is the CORRECT result here, not a failure;
    the previous unconditional "healthy" assertion was testing the old,
    intentionally-inaccurate behavior.
    """
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("healthy", "degraded")
    assert body["adk_ready"] is True

def test_initiate_launch():
    """Verify that the product launch endpoint accepts payload and starts session."""
    payload = {
        "product_name": "Eco-friendly Water Bottle",
        "raw_description": "Stainless steel, double-walled insulation, 500ml.",
        "price": 24.99,
        "category": "Home & Kitchen"
    }
    response = client.post("/launch", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["product_name"] == "Eco-friendly Water Bottle"
    assert data["status"] == "pending"
    assert data["raw_description"] == "Stainless steel, double-walled insulation, 500ml."

@pytest.mark.skip(
    reason="The mock Shopify API router was removed from this app; "
    "publisher/verification agents now call the real Shopify Admin API "
    "via shopify_client.py (see note in main.py)."
)
def test_shopify_mock_endpoints():
    """Verify the mock Shopify creation and retrieval endpoints using SQLite."""
    headers = {"X-Shopify-Access-Token": "test-token"}
    payload = {
        "product": {
            "title": "Test Insulated Flask",
            "body_html": "<p>Vacuum insulated flask</p>",
            "vendor": "Hydrate Co",
            "product_type": "Flask",
            "status": "draft",
            "price": 19.99
        }
    }
    
    # 1. Test POST /products
    post_response = client.post("/products", json=payload, headers=headers)
    assert post_response.status_code == 200
    post_data = post_response.json()
    assert "product" in post_data
    assert post_data["product"]["title"] == "Test Insulated Flask"
    assert post_data["product"]["price"] == 19.99
    assert post_data["product"]["status"] == "draft"
    assert "id" in post_data["product"]
    assert "handle" in post_data["product"]
    assert "url" in post_data["product"]
    
    product_id = post_data["product"]["id"]
    
    # 2. Test GET /products/{id}
    get_response = client.get(f"/products/{product_id}", headers=headers)
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["product"]["id"] == product_id
    assert get_data["product"]["title"] == "Test Insulated Flask"
    assert get_data["product"]["price"] == 19.99
    assert get_data["product"]["url"] == post_data["product"]["url"]
