# Workshop Setup Agent (`workshop_setup_agent.py`)

## 📌 Overview
The **Workshop Setup Agent** (`workshop_setup_agent`) orchestrates workshop catalog entries, event registration configurations, and template replication workflows.

---

## 🎯 Primary Purpose
- Processes structured workshop inputs (`WorkshopInput`: name, date, venue, age group, price, topics, media).
- Executes duplicate product searches (`search_existing_shopify_product`) against existing store catalog.
- Generates landing page templates and registration attributes.
- Enforces the `PENDING_APPROVAL` boundary before publishing workshops to Shopify.

---

## 🛠️ Tools Exposed & Used
- **`ingest_workshop_input_tool(tool_context)`**: Converts state dictionary into `WorkshopInput` dataclass and triggers pipeline execution via `services/workshop_service.py`.

---

## ⚙️ Execution Steps
1. **Input Processing**: Ingests raw workshop form inputs and sanitizes dates/venues.
2. **Asset Inspection**: Validates posters, videos, and syllabus materials.
3. **Duplicate Detection**: Searches Shopify catalog for existing matching workshop titles or handles.
4. **Content Generation**: Formats workshop agenda, target age group callouts, and key takeaways.
5. **Template Replication**: Generates Liquid template suffix (`workshop-landing-page`).
6. **Payload Preparation**: Prepares draft product payload with custom metafields (date, venue, instructor).
