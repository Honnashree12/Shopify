# Report Generator Agent (`report_generator_agent.py`)

## 📌 Overview
The **Report Generator Agent** (`report_generator_agent`) summarizes complete workflow state data into audit reports formatted in Markdown, JSON, and PDF formats.

---

## 🎯 Primary Purpose
- Aggregates metadata across Product Copy, SEO, Marketing Strategy, Publishing, and Verification stages.
- Writes structured launch reports to `outputs/launch_report.md` and `outputs/launch_report.json`.
- Serves as data source for PDF export generation (`services/pdf_export_service.py`).

---

## 🛠️ Tools Exposed & Used
- **`save_launch_reports(tool_context)`**: Compiles workflow state and writes formatted report files into `outputs/`.

---

## 📄 Output Report Contents
- **Product Overview**: Title, Category, Price, Clean HTML Description.
- **Shopify Resource Identifiers**: Product ID, Live Storefront URL, Status.
- **SEO Metadata**: Title tag, Meta Description, Keywords, URL Handle.
- **Marketing Strategy**: Campaign Name, Target Audience, Social Caption, Promotional Email.
- **Verification Summary**: Product existence check, price matching pass/fail status.
