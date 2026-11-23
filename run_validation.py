import os
import asyncio
import logging
from dotenv import load_dotenv

import sys
# Ensure UTF-8 stdout encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Load env variables first
load_dotenv()

from config import settings, setup_logging
setup_logging(settings.log_level)

from agents.product_validation_agent import product_validation_agent
from google.adk import Workflow
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logger = logging.getLogger("run_validation")

# Define a single-node workflow to run the validation agent
validation_workflow = Workflow(
    name="ProductValidationWorkflow",
    edges=[
        ("START", product_validation_agent),
    ],
)

async def main():
    print("\n==============================================")
    print("SHOPIFY PRODUCT VALIDATION AUDIT")
    print("==============================================\n")
    
    # Check that validation store environment variables are set
    store = os.getenv("SHOPIFY_VALIDATION_STORE")
    token = os.getenv("SHOPIFY_VALIDATION_TOKEN")
    
    if store and not token:
        # Fallback to database-stored OAuth token
        from services.firebase_service import get_shopify_token
        token = get_shopify_token(store)
        
    if token and ("your_" in token or not token.strip()):
        token = None
        
    if not store or not token:
        print("Error: SHOPIFY_VALIDATION_STORE is not configured, or validation token is missing.")
        print("Please configure SHOPIFY_VALIDATION_STORE in your .env, and ensure the store has completed the OAuth flow or set SHOPIFY_VALIDATION_TOKEN.")
        print("\nExample:")
        print("SHOPIFY_VALIDATION_STORE=your-validation-store.myshopify.com")
        print("SHOPIFY_VALIDATION_TOKEN=shpat_your_validation_token")
        return

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="shopify-product-validation",
        agent=validation_workflow,
        session_service=session_service,
    )
    
    # Pre-create the validation session in the session service
    await session_service.create_session(
        app_name="shopify-product-validation",
        user_id="cli-user",
        session_id="validation-session",
        state={},
    )
    
    message = types.Content(
        role="user",
        parts=[types.Part(text="Run validation audit on all products in the Shopify validation store.")],
    )
    
    print(f"Starting audit on store: {store}")
    print("Running workflow events...")
    
    try:
        async for event in runner.run_async(
            user_id="cli-user",
            session_id="validation-session",
            new_message=message,
        ):
            print(event)
            
        print("\n==============================================")
        print("AUDIT WORKFLOW COMPLETED")
        print("==============================================\n")
        
        # Check output files
        outputs_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "outputs")
        )
        summary_path = os.path.join(outputs_dir, "summary_report.json")
        validation_path = os.path.join(outputs_dir, "validation_report.json")
        
        if os.path.exists(summary_path):
            print(f"Summary Report generated: {summary_path}")
            with open(summary_path, "r", encoding="utf-8") as f:
                print(f.read())
        else:
            print("Warning: summary_report.json not found in outputs/ directory.")
            
        if os.path.exists(validation_path):
            print(f"Detailed Validation Report generated: {validation_path}")
            
    except Exception as e:
        logger.warning("Workflow runner failed (%s). Executing deterministic validation tools directly...", e)
        print(f"Workflow runner note: {e}\nExecuting direct validation tools...")
        from agents.product_validation_agent import (
            fetch_validation_products_tool,
            validate_products_checklist_tool,
            generate_validation_reports_tool,
        )
        class DirectToolContext:
            def __init__(self):
                self.state = {}
        tool_ctx = DirectToolContext()
        print(fetch_validation_products_tool(tool_ctx))
        print(validate_products_checklist_tool(tool_ctx))
        print(generate_validation_reports_tool(tool_ctx))

if __name__ == "__main__":
    asyncio.run(main())
