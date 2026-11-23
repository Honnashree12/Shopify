"""
Runner script for MediaCompletenessValidationSkill.

Executes a storewide media completeness audit and generates downloadable report files:
1. outputs/media_completeness_audit_<timestamp>.xlsx (Excel Report - 5 Sheets)
2. outputs/media_completeness_audit_<timestamp>.csv  (CSV Export)
3. outputs/media_completeness_audit_<timestamp>.pdf  (PDF Summary Report)
4. docs/audits/media-completeness-report.md         (Markdown Report)
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from config import settings
from shopify_client import get_validation_client
from services.media_completeness_validator import MediaCompletenessValidationSkill

logger = logging.getLogger("run_media_completeness_audit")


def main():
    print("\n==============================================")
    print("MEDIA COMPLETENESS VALIDATION SKILL — STORE AUDIT")
    print("==============================================\n")

    try:
        client = get_validation_client()
        store_url = client.store_url
        print(f"Connecting to Shopify store ({store_url}) via get_validation_client()...")
        products = client.fetch_all_products()
        print(f"Successfully fetched {len(products)} live products from Shopify.")
    except Exception as exc:
        print(f"\nERROR: Live Shopify API call failed: {exc}")
        print("Audit aborted: Unable to fetch live store catalog. VALIDATION_ERROR report generated.")
        store_url = settings.validation_store_url or settings.shopify_store_url or "kinq5t-q5.myshopify.com"
        skill = MediaCompletenessValidationSkill(store_url=store_url)
        audit_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "store_name": store_url,
            "overall_status": "VALIDATION_ERROR",
            "reason": f"Unable to retrieve Shopify media catalog: {exc}",
            "store_summary": {"total_products": 0, "complete": 0, "incomplete": 0, "unclassified": 0, "validation_errors": 1},
            "categories": {},
            "products": [],
            "action_required": []
        }
        report_paths = skill.generate_reports(audit_result)
        print(f"✓ Error Report XLSX: {report_paths['excel_path']}")
        return

    skill = MediaCompletenessValidationSkill(store_url=store_url, access_token=client.access_token)

    print("\nExecuting MediaCompletenessValidationSkill audit...")
    audit_result = skill.audit_store(products)

    print("\nGenerating downloadable reports...")
    report_paths = skill.generate_reports(audit_result)

    print(f"✓ Downloadable Excel Report (.xlsx): {report_paths['excel_path']}")
    print(f"✓ Downloadable CSV Report (.csv):   {report_paths['csv_path']}")
    print(f"✓ Downloadable PDF Report (.pdf):   {report_paths['pdf_path']}")
    print(f"✓ Markdown Audit Report (.md):      {report_paths['markdown_path']}")

    print("\n==============================================")
    print("AUDIT RESULTS SUMMARY")
    print("==============================================\n")
    summ = audit_result['store_summary']
    print(f"Store:                        {audit_result.get('store_name')}")
    print("Validation Scope:             ACTIVE PRODUCTS ONLY")
    print(f"Total Shopify Products Found: {summ.get('total_fetched_products', summ.get('total_products'))}")
    print(f"Active Products Audited:      {summ.get('active_products_audited', summ.get('total_products'))}")
    print(f"Draft Products Excluded:      {summ.get('draft_products_excluded', 0)}")
    print(f"Archived Products Excluded:   {summ.get('archived_products_excluded', 0)}")
    print(f"COMPLETE:                     {summ['complete']}")
    print(f"INCOMPLETE:                   {summ['incomplete']}")
    print(f"UNCLASSIFIED:                 {summ['unclassified']}")
    print(f"VALIDATION_ERROR:             {summ['validation_errors']}\n")

    if audit_result['action_required']:
        print("ACTIONABLE CORRECTION CHECKLIST:")
        for idx, act in enumerate(audit_result['action_required'], 1):
            print(f"{idx}. {act['product_title']} ({act['profile']}) [{act['shopify_status']}]")
            for c in act['corrections']:
                print(f"   - {c}")
    print("\n==============================================\n")


if __name__ == "__main__":
    main()
