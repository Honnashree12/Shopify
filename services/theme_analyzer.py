import os
import json
import logging
import httpx
from typing import Optional, Dict, Any
from shopify_client import _get_config

logger = logging.getLogger(__name__)

# Preset design system to fall back on if API requests fail
DEFAULT_DESIGN_SYSTEM = {
    "colors": {
        "primary": "#121212",
        "secondary": "#ffffff",
        "accent": "#3d85c6",
        "background": "#ffffff",
        "surface": "#f9f9f9",
        "text": "#212121",
        "muted_text": "#757575",
        "border": "#e0e0e0",
        "hover": "#f0f0f0",
        "gradients": ["linear-gradient(180deg, #3d85c6 0%, #0b5394 100%)"]
    },
    "typography": {
        "font_header": "Inter, sans-serif",
        "font_body": "Inter, sans-serif",
        "heading_size": "2.25rem",
        "body_size": "1rem",
        "font_weight_bold": 700,
        "line_height": 1.5,
        "letter_spacing": "normal"
    },
    "layout": {
        "max_width": "1200px",
        "section_spacing": "4rem",
        "card_spacing": "1.5rem",
        "padding": "1.5rem",
        "border_radius": "8px",
        "shadows": "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    },
    "components": {
        "buttons": {
            "border_radius": "4px",
            "padding": "0.75rem 1.5rem",
            "font_weight": 600
        },
        "product_gallery": "grid",
        "product_info_layout": "stacked"
    },
    "responsive": {
        "mobile_breakpoint": "768px",
        "tablet_breakpoint": "990px"
    },
    "theme_source": {
        "theme_id": None,
        "theme_name": "Default Theme Preset"
    },
    "version": 1
}

THEME_REGISTRY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "theme"))
os.makedirs(THEME_REGISTRY_DIR, exist_ok=True)
THEME_REGISTRY_PATH = os.path.join(THEME_REGISTRY_DIR, "template_registry.json")


def get_active_theme_id(base_url: str, headers: dict) -> tuple[Optional[int], str]:
    """Fetches the active theme (role='main') from Shopify."""
    try:
        res = httpx.get(f"{base_url}/themes.json", headers=headers, timeout=15)
        res.raise_for_status()
        themes = res.json().get("themes", [])
        for theme in themes:
            if theme.get("role") == "main":
                return theme["id"], theme["name"]
        if themes:
            return themes[0]["id"], themes[0]["name"]
    except Exception as e:
        logger.error("Failed to fetch Shopify themes list: %s", e)
    return None, "Default Preset Theme"


def get_theme_asset(base_url: str, headers: dict, theme_id: int, asset_key: str) -> Optional[str]:
    """Downloads a specific asset value from the theme."""
    try:
        url = f"{base_url}/themes/{theme_id}/assets.json?asset[key]={asset_key}"
        res = httpx.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json().get("asset", {}).get("value")
    except Exception as e:
        logger.error("Failed to download theme asset %s: %s", asset_key, e)
    return None


def extract_and_sync_design_system(store_id: str) -> Dict[str, Any]:
    """
    Main entry point. Resolves active theme, extracts design parameters,
    creates local registry file, and stores the configuration in Firestore.
    """
    design_system = DEFAULT_DESIGN_SYSTEM.copy()
    registry = {
        "product_template": "templates/product.json",
        "collection_template": "templates/collection.json",
        "header": "sections/header.json",
        "footer": "sections/footer.json",
        "product_card": "snippets/product-card.liquid",
        "global_css": "assets/base.css",
        "sections": [],
        "snippets": []
    }
    
    try:
        base_url, store_url, headers = _get_config()
        theme_id, theme_name = get_active_theme_id(base_url, headers)
        
        if theme_id:
            logger.info("Found active Shopify theme: %s (ID: %s)", theme_name, theme_id)
            design_system["theme_source"] = {
                "theme_id": theme_id,
                "theme_name": theme_name
            }
            
            # Fetch config/settings_data.json to extract merchant settings
            settings_json = get_theme_asset(base_url, headers, theme_id, "config/settings_data.json")
            if settings_json:
                try:
                    settings = json.loads(settings_json)
                    current_settings = settings.get("current", {})
                    # If Dawn or similar theme setting layout:
                    if "colors_background_1" in current_settings:
                        design_system["colors"]["background"] = current_settings["colors_background_1"]
                    if "colors_text" in current_settings:
                        design_system["colors"]["text"] = current_settings["colors_text"]
                    if "colors_accent_1" in current_settings:
                        design_system["colors"]["accent"] = current_settings["colors_accent_1"]
                    if "colors_solid_button_labels" in current_settings:
                        design_system["colors"]["secondary"] = current_settings["colors_solid_button_labels"]
                    
                    # Resolve fonts
                    if "type_header_font_family" in current_settings:
                        design_system["typography"]["font_header"] = current_settings["type_header_font_family"]
                    if "type_body_font_family" in current_settings:
                        design_system["typography"]["font_body"] = current_settings["type_body_font_family"]
                        
                    # Resolve layout
                    if "page_width" in current_settings:
                        design_system["layout"]["max_width"] = f"{current_settings['page_width']}px"
                except Exception as e:
                    logger.error("Failed to parse settings_data.json: %s", e)
            
            # Query if custom templates exist to check availability
            for key in ["templates/product.json", "templates/product.liquid"]:
                if get_theme_asset(base_url, headers, theme_id, key):
                    registry["product_template"] = key
                    break
            for key in ["templates/collection.json", "templates/collection.liquid"]:
                if get_theme_asset(base_url, headers, theme_id, key):
                    registry["collection_template"] = key
                    break
            for key in ["assets/base.css", "assets/theme.css", "assets/global.css"]:
                if get_theme_asset(base_url, headers, theme_id, key):
                    registry["global_css"] = key
                    break
    except Exception as e:
        logger.warning("Could not connect to real Shopify API for theme analysis, using presets: %s", e)

    # Save Registry locally
    try:
        with open(THEME_REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
        logger.info("Saved local template registry to %s", THEME_REGISTRY_PATH)
    except Exception as e:
        logger.error("Failed to write theme registry locally: %s", e)
        
    # Sync with Firebase Firestore
    from services.firebase_service import save_design_system, get_design_system
    
    try:
        existing = get_design_system(store_id)
        if existing:
            # Only increment if source theme changed or parameters differ
            if existing.get("colors") != design_system["colors"] or existing.get("typography") != design_system["typography"]:
                design_system["version"] = existing.get("version", 1) + 1
            else:
                design_system["version"] = existing.get("version", 1)
    except Exception:
        pass
        
    save_design_system(store_id, design_system)
    return design_system
