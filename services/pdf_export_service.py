"""
PDF Export Service for Shopify Product Validation Audit Reports.

Generates professional PDF audit reports containing:
- Executive Summary & Audit Overview
- Per-Product Details: Name, Shopify ID, Category, Score, Launch Status
- Blocker Counts & Warning Counts
- Separate BLOCKER FAILURES Table (Rule ID, Rule Name, Why Failed, Current State, Suggested Fix)
- Separate WARNING FAILURES Table
- Supports filtering by selected product IDs or names (e.g., for team assignment).
"""

import os
import io
import json
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)

from services.remediation_engine import generate_remediations_for_product, RemediationItem

logger = logging.getLogger("pdf_export_service")


def generate_validation_pdf_report(
    products: List[Dict[str, Any]],
    selected_identifiers: Optional[List[str]] = None,
    assignee_name: Optional[str] = None,
    output_filename_or_stream: Optional[Any] = None
) -> bytes:
    """
    Generates PDF bytes for a given list of product validation results.
    
    :param products: List of product validation result dictionaries.
    :param selected_identifiers: Optional list of product IDs or product titles to include.
    :param assignee_name: Optional recipient name (e.g. "Rachana").
    :param output_filename_or_stream: Path to save file or BytesIO object.
    :return: Bytes of the generated PDF document.
    """
    # Filter products if specific identifiers were selected
    target_products = products
    if selected_identifiers:
        norm_ids = {str(i).strip().lower() for i in selected_identifiers if str(i).strip()}
        target_products = []
        for p in products:
            pid = str(p.get("product_id") or p.get("id") or "").strip().lower()
            pname = str(p.get("product_name") or p.get("title") or "").strip().lower()
            phandle = str(p.get("handle") or "").strip().lower()
            
            if any(nid in pid or pid in nid or nid in pname or nid in phandle for nid in norm_ids):
                target_products.append(p)
                
        if not target_products:
            # Fallback to all products if filter matches nothing
            target_products = products

    buffer = io.BytesIO()
    doc_target = output_filename_or_stream if output_filename_or_stream else buffer

    doc = SimpleDocTemplate(
        doc_target,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    PRIMARY = colors.HexColor("#1e293b")      # Dark Slate
    SECONDARY = colors.HexColor("#2563eb")    # Brand Blue
    TEXT_DARK = colors.HexColor("#0f172a")    # Body Text
    TEXT_MUTED = colors.HexColor("#64748b")   # Gray Muted
    BG_LIGHT = colors.HexColor("#f8fafc")     # Section BG
    BORDER_COLOR = colors.HexColor("#cbd5e1") # Border
    
    RED_FAIL = colors.HexColor("#dc2626")     # Blocker Red
    GREEN_PASS = colors.HexColor("#16a34a")   # Ready Green
    AMBER_WARN = colors.HexColor("#d97706")   # Warning Amber

    # Custom Typography Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=PRIMARY,
        fontName="Helvetica-Bold",
        alignment=0,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=TEXT_MUTED,
        fontName="Helvetica",
        spaceAfter=10
    )

    h2_style = ParagraphStyle(
        "H2Header",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        textColor=PRIMARY,
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11.5,
        textColor=TEXT_DARK,
        fontName="Helvetica"
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.white,
        fontName="Helvetica-Bold"
    )

    cell_style = ParagraphStyle(
        "TableCell",
        parent=body_style,
        fontSize=7.5,
        leading=10
    )

    cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=cell_style,
        fontName="Helvetica-Bold"
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("SHOPIFY PRODUCT AUDIT REPORT", title_style))
    meta_info = f"Generated: {datetime.now().strftime('%b %d, %Y · %I:%M %p')}"
    if assignee_name:
        meta_info += f"  |  Assigned To: <b>{assignee_name}</b>"
    meta_info += f"  |  Scope: Active Products Only ({len(target_products)} Products)"
    story.append(Paragraph(meta_info, subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=SECONDARY, spaceAfter=10))

    # 2. Executive Summary Metrics Box
    total_prods = len(target_products)
    ready_count = sum(1 for p in target_products if p.get("launch_status") == "READY_TO_LAUNCH" or p.get("blockers_failed", 0) == 0)
    blocked_count = total_prods - ready_count
    avg_score = round(sum(p.get("score", 0.0) for p in target_products) / total_prods, 1) if total_prods > 0 else 0.0
    tot_blockers = sum(p.get("blockers_failed", 0) for p in target_products)
    tot_warnings = sum(p.get("warnings_failed", p.get("warnings_count", 0)) for p in target_products)

    summary_data = [
        [
            Paragraph(f"<b>Products Included:</b> {total_prods}", body_style),
            Paragraph(f"<b>Average Score:</b> {avg_score} / 100", body_style),
            Paragraph(f"<b>Launch Ready:</b> <font color='#16a34a'><b>{ready_count}</b></font>", body_style),
            Paragraph(f"<b>Launch Blocked:</b> <font color='#dc2626'><b>{blocked_count}</b></font>", body_style),
        ],
        [
            Paragraph(f"<b>Total Failed Blockers:</b> <font color='#dc2626'><b>{tot_blockers}</b></font>", body_style),
            Paragraph(f"<b>Total Warnings:</b> <font color='#d97706'><b>{tot_warnings}</b></font>", body_style),
            Paragraph("<b>Checks per Product:</b> 53 Checks", body_style),
            Paragraph("<b>Engine:</b> Unified API + Browser", body_style),
        ]
    ]

    summary_table = Table(summary_data, colWidths=[135, 135, 135, 135])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 10))

    # 3. Iterate over Products
    for idx, product in enumerate(target_products):
        p_name = product.get("product_name") or product.get("title") or "Unnamed Product"
        p_id = str(product.get("product_id") or product.get("id") or "N/A")
        handle = product.get("handle") or ""
        cat = product.get("mvp_category") or "Unknown"
        score = product.get("score", 0.0)
        b_failed = product.get("blockers_failed", 0)
        w_count = product.get("warnings_failed", product.get("warnings_count", 0))
        is_ready = product.get("launch_status") == "READY_TO_LAUNCH" or b_failed == 0

        # Build Remediation Map for details
        rems = generate_remediations_for_product(product)
        rem_by_rule_id = {}
        for r in rems:
            rem_by_rule_id[r.rule_id] = r
            rem_by_rule_id[r.rule_name] = r

        # Product Header Card
        status_text = "<font color='#16a34a'><b>🟢 READY TO LAUNCH</b></font>" if is_ready else "<font color='#dc2626'><b>🔴 LAUNCH BLOCKED</b></font>"
        
        prod_meta_table_data = [
            [
                Paragraph(f"<b>{idx + 1}. {p_name}</b>", ParagraphStyle("PTitle", parent=body_style, fontSize=10.5, leading=13, fontName="Helvetica-Bold", textColor=PRIMARY)),
                Paragraph(status_text, ParagraphStyle("PStatus", parent=body_style, alignment=2))
            ],
            [
                Paragraph(f"<b>Shopify ID:</b> {p_id} &nbsp;|&nbsp; <b>Handle:</b> {handle} &nbsp;|&nbsp; <b>Category:</b> {cat}", subtitle_style),
                Paragraph(f"<b>Score: {score:.1f}/100</b> &nbsp;|&nbsp; Blockers: <font color='#dc2626'><b>{b_failed}</b></font> &nbsp;|&nbsp; Warnings: <font color='#d97706'><b>{w_count}</b></font>", ParagraphStyle("PStats", parent=body_style, alignment=2))
            ]
        ]

        prod_header_table = Table(prod_meta_table_data, colWidths=[360, 180])
        prod_header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))

        product_elements = [prod_header_table, Spacer(1, 4)]

        # Collect Blockers & Warnings
        checks = product.get("checks") or {}
        blocker_items = []
        warning_items = []

        for check_key, chk in checks.items():
            st = chk.get("final_result") or chk.get("status") or "FAIL"
            sev = chk.get("severity") or "Warning"
            
            if st in ("FAIL", "WARNING"):
                # Extract clean rule ID and name
                rule_num = str(chk.get("check_id") or "")
                rule_name = chk.get("check_name") or check_key
                match = re.match(r'^(\d+)\.\s*(.*)$', check_key)
                if match:
                    rule_num = match.group(1)
                    rule_name = match.group(2)

                explanation = chk.get("explanation") or chk.get("final_evidence", {}).get("explanation") or "Validation check failed."
                
                # Retrieve remediation details if available
                rem_item = rem_by_rule_id.get(rule_num) or rem_by_rule_id.get(rule_name)
                curr_val = rem_item.current_value if rem_item else "Not configured / invalid"
                suggested_fix = rem_item.proposed_value if rem_item else "Configure per checklist matrix"
                
                if isinstance(suggested_fix, list):
                    suggested_fix = ", ".join(map(str, suggested_fix))
                if isinstance(curr_val, list):
                    curr_val = ", ".join(map(str, curr_val))

                if rem_item and rem_item.manual_instructions:
                    suggested_fix = f"{suggested_fix} ({rem_item.manual_instructions})"

                item_tuple = (rule_num, rule_name, explanation, str(curr_val), str(suggested_fix))

                if sev == "Blocker":
                    blocker_items.append(item_tuple)
                else:
                    warning_items.append(item_tuple)

        # 4. BLOCKERS TABLE
        if blocker_items:
            product_elements.append(Paragraph("<font color='#dc2626'><b>❌ BLOCKER FAILURES (Must fix to Launch)</b></font>", h2_style))
            
            b_table_data = [
                [
                    Paragraph("Rule", table_header_style),
                    Paragraph("Rule Name", table_header_style),
                    Paragraph("Why It Failed", table_header_style),
                    Paragraph("Current State", table_header_style),
                    Paragraph("Suggested Fix / Action", table_header_style)
                ]
            ]

            for r_num, r_name, exp, curr, fix in blocker_items:
                b_table_data.append([
                    Paragraph(f"<b>Rule {r_num}</b>", cell_bold),
                    Paragraph(r_name, cell_bold),
                    Paragraph(exp, cell_style),
                    Paragraph(curr, cell_style),
                    Paragraph(f"<font color='#2563eb'><b>{fix}</b></font>", cell_style)
                ])

            b_table = Table(b_table_data, colWidths=[50, 110, 160, 90, 130])
            b_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#991b1b")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#fca5a5")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#fee2e2")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]))
            product_elements.append(b_table)
            product_elements.append(Spacer(1, 6))

        # 5. WARNINGS TABLE
        if warning_items:
            product_elements.append(Paragraph("<font color='#d97706'><b>⚠️ WARNING FAILURES (Quality / Best Practice)</b></font>", h2_style))
            
            w_table_data = [
                [
                    Paragraph("Rule", table_header_style),
                    Paragraph("Rule Name", table_header_style),
                    Paragraph("Issue Description", table_header_style),
                    Paragraph("Current State", table_header_style),
                    Paragraph("Suggested Recommendation", table_header_style)
                ]
            ]

            for r_num, r_name, exp, curr, fix in warning_items:
                w_table_data.append([
                    Paragraph(f"<b>Rule {r_num}</b>", cell_bold),
                    Paragraph(r_name, cell_bold),
                    Paragraph(exp, cell_style),
                    Paragraph(curr, cell_style),
                    Paragraph(f"<font color='#d97706'><b>{fix}</b></font>", cell_style)
                ])

            w_table = Table(w_table_data, colWidths=[50, 110, 160, 90, 130])
            w_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#92400e")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#fde68a")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#fef3c7")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]))
            product_elements.append(w_table)
            product_elements.append(Spacer(1, 6))

        if not blocker_items and not warning_items:
            product_elements.append(Paragraph("<font color='#16a34a'><b>✅ Perfect compliance — All 53 rules passed successfully!</b></font>", body_style))
            product_elements.append(Spacer(1, 6))

        product_elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=4, spaceAfter=8))
        story.append(KeepTogether(product_elements))

    # Build Document
    doc.build(story)
    
    if output_filename_or_stream and isinstance(output_filename_or_stream, str):
        with open(output_filename_or_stream, "rb") as f:
            return f.read()
            
    return buffer.getvalue()
