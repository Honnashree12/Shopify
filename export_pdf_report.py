"""
CLI Script to Generate Shopify Product Validation PDF Audit Reports.

Usage:
  python export_pdf_report.py [--output OUTPUT_PATH] [--assignee NAME] [--products ID1,ID2,...]

Examples:
  python export_pdf_report.py
  python export_pdf_report.py --assignee "Rachana" --output outputs/Rachana_Product_Audit_Report.pdf
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from services.pdf_export_service import generate_validation_pdf_report


def main():
    parser = argparse.ArgumentParser(description="Export Shopify Product Validation Audit Report PDF")
    parser.add_argument("--output", default="outputs/Shopify_Product_Validation_Audit_Report.pdf", help="Output PDF filepath")
    parser.add_argument("--assignee", default="Rachana", help="Assignee name to display on report header")
    parser.add_argument("--products", default=None, help="Comma-separated product IDs or names to filter")
    args = parser.parse_args()

    outputs_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "outputs")
    )
    os.makedirs(outputs_dir, exist_ok=True)

    report_path = os.path.join(outputs_dir, "unified_validation_report.json")
    if not os.path.exists(report_path):
        report_path = os.path.join(outputs_dir, "validation_report.json")

    if not os.path.exists(report_path):
        print(f"Error: No validation report found at {report_path}. Please run 'python run_unified_validation.py' first.")
        sys.exit(1)

    with open(report_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    selected_ids = [p.strip() for p in args.products.split(",") if p.strip()] if args.products else None

    out_path = os.path.abspath(args.output)
    
    print("Generating PDF audit report...")
    pdf_bytes = generate_validation_pdf_report(
        products=products,
        selected_identifiers=selected_ids,
        assignee_name=args.assignee,
        output_filename_or_stream=out_path
    )

    print(f"✅ PDF Audit Report successfully generated at: {out_path}")
    print(f"   Size: {len(pdf_bytes)} bytes")
    if selected_ids:
        print(f"   Filtered Products ({len(selected_ids)}): {', '.join(selected_ids)}")
    else:
        print(f"   Total Active Products Included: {len(products)}")


if __name__ == "__main__":
    main()
