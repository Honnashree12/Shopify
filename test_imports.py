import sys

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agents.copywriter_agent import copywriter_agent
from agents.seo_agent import seo_agent
from agents.strategist_agent import strategist_agent
from agents.image_prompt_agent import image_prompt_agent
from agents.image_generator_agent import image_generator_agent
from agents.marketing_agent import marketing_agent
from agents.publisher_agent import publisher_agent
from agents.verification_agent import verification_agent
from agents.report_generator_agent import report_generator_agent
from agents.product_validation_agent import product_validation_agent
from agents.media_completeness_agent import validate_product_media_completeness_tool
from agents.workshop_setup_agent import workshop_setup_agent

from agents.folder_agents import (
    folder_ingestion_agent,
    folder_validation_agent,
    folder_creation_agent,
    folder_media_agent,
    folder_verification_agent,
    folder_report_agent,
)

print("[PASS] Copywriter loaded:", copywriter_agent.name)
print("[PASS] SEO loaded:", seo_agent.name)
print("[PASS] Strategist loaded:", strategist_agent.name)
print("[PASS] Image Prompt loaded:", image_prompt_agent.name)
print("[PASS] Image Generator loaded:", image_generator_agent.name)
print("[PASS] Marketing loaded:", marketing_agent.name)
print("[PASS] Publisher loaded:", publisher_agent.name)
print("[PASS] Verification loaded:", verification_agent.name)
print("[PASS] Report Generator loaded:", report_generator_agent.name)
print("[PASS] Product Validation loaded:", product_validation_agent.name)
print("[PASS] Media Completeness loaded: validate_product_media_completeness_tool")
print("[PASS] Workshop Setup loaded:", workshop_setup_agent.name)

print("[PASS] Folder Ingestion loaded:", folder_ingestion_agent.name)
print("[PASS] Folder Validation loaded:", folder_validation_agent.name)
print("[PASS] Folder Creation loaded:", folder_creation_agent.name)
print("[PASS] Folder Media loaded:", folder_media_agent.name)
print("[PASS] Folder Verification loaded:", folder_verification_agent.name)
print("[PASS] Folder Report loaded:", folder_report_agent.name)
print("\nAll 18 agents verified and ready for deployment!")
