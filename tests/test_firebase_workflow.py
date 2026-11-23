import os
import shutil
import json
import pytest
from unittest.mock import patch, MagicMock

from services.firebase_service import (
    save_design_system,
    get_design_system,
    save_product,
    get_product,
    update_workflow_status,
    MOCK_FIRESTORE_DIR
)
from services.firebase_storage_service import upload_file, MOCK_STORAGE_DIR
from services.theme_analyzer import extract_and_sync_design_system, THEME_REGISTRY_PATH


@pytest.fixture(autouse=True)
def clean_mocks():
    """Ensure mock firestore and storage folders are clean before each test."""
    if os.path.exists(MOCK_FIRESTORE_DIR):
        shutil.rmtree(MOCK_FIRESTORE_DIR)
    if os.path.exists(MOCK_STORAGE_DIR):
        shutil.rmtree(MOCK_STORAGE_DIR)
    yield
    if os.path.exists(MOCK_FIRESTORE_DIR):
        shutil.rmtree(MOCK_FIRESTORE_DIR)
    if os.path.exists(MOCK_STORAGE_DIR):
        shutil.rmtree(MOCK_STORAGE_DIR)


def test_firebase_firestore_fallback():
    # Test saving/retrieving design system
    design_data = {"colors": {"primary": "#ff0000"}, "version": 1}
    save_design_system("test-store", design_data)
    
    retrieved = get_design_system("test-store")
    assert retrieved is not None
    assert retrieved["colors"]["primary"] == "#ff0000"
    assert retrieved["version"] == 1
    
    # Test saving/retrieving product document
    prod_data = {"title": "Test Product", "price": 99.99}
    save_product("prod_test_001", prod_data)
    
    retrieved_prod = get_product("prod_test_001")
    assert retrieved_prod is not None
    assert retrieved_prod["title"] == "Test Product"
    assert float(retrieved_prod["price"]) == 99.99
    
    # Test updating workflow stage status
    update_workflow_status("prod_test_001", "shopify", "completed")
    updated_prod = get_product("prod_test_001")
    assert updated_prod["workflow"]["shopify"] == "completed"


def test_firebase_storage_fallback(tmp_path):
    # Create a dummy image file
    dummy_file = tmp_path / "hero.png"
    dummy_file.write_text("dummy-image-bytes")
    
    meta = upload_file("prod_test_001", "images", str(dummy_file))
    assert meta is not None
    assert meta["filename"] == "hero.png"
    assert meta["content_type"] == "image/png"
    assert "public_url" in meta
    
    # Verify local file copies exist
    copied_path = os.path.join(MOCK_STORAGE_DIR, "products", "prod_test_001", "images", "hero.png")
    assert os.path.exists(copied_path)


@patch("services.theme_analyzer._get_config")
@patch("services.theme_analyzer.get_active_theme_id")
@patch("services.theme_analyzer.get_theme_asset")
def test_theme_analyzer_success(mock_get_asset, mock_get_theme_id, mock_get_config):
    # Mock Shopify config and theme responses
    mock_get_config.return_value = ("https://mock-store.myshopify.com/admin/api/2025-07", "mock-store", {})
    mock_get_theme_id.return_value = (12345, "Dawn")
    mock_get_asset.side_effect = lambda base, headers, theme_id, key: {
        "config/settings_data.json": json.dumps({
            "current": {
                "colors_background_1": "#ffffff",
                "colors_text": "#000000",
                "page_width": 1200
            }
        })
    }.get(key, None)
    
    design_system = extract_and_sync_design_system("test-store")
    assert design_system is not None
    assert design_system["colors"]["background"] == "#ffffff"
    assert design_system["colors"]["text"] == "#000000"
    assert design_system["layout"]["max_width"] == "1200px"
    assert design_system["theme_source"]["theme_name"] == "Dawn"
    
    # Verify registry was created
    assert os.path.exists(THEME_REGISTRY_PATH)
    with open(THEME_REGISTRY_PATH, "r", encoding="utf-8") as f:
        reg = json.load(f)
        assert "product_template" in reg
