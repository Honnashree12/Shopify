# Shopify Product Launch System — Agents Architecture & Reference Index

This directory contains the 17 AI Agents powering the **Shopify Product Launch Agent** platform. Built on the **Google Agent Development Kit (ADK)** using `gemini-2.5-flash`, these agents collaborate across the end-to-end e-commerce product lifecycle—from raw folder ingestion and copy generation to catalog validation, Shopify publishing, and automated storefront verification.

---

## 📋 Complete Agent Roster (17 Agents Across 12 Modules)

| # | Agent Name | File | Primary Function | Model |
|---|---|---|---|---|
| 1 | **Product Validation Agent** | `product_validation_agent.py` | Runs 53-point catalog integrity matrix across 9 sections | `gemini-2.5-flash` |
| 2 | **Copywriter Agent** | `copywriter_agent.py` | Formats structured HTML product descriptions | `gemini-2.5-flash` |
| 3 | **SEO Agent** | `seo_agent.py` | Generates SEO titles, meta descriptions, keywords, & slugs | `gemini-2.5-flash` |
| 4 | **Strategist Agent** | `strategist_agent.py` | Formulates high-level campaign marketing strategy | `gemini-2.5-flash` |
| 5 | **Image Prompt Agent** | `image_prompt_agent.py` | Engineers 8 commercial 1:1 ratio image prompts | `gemini-2.5-flash` |
| 6 | **Image Generator Agent** | `image_generator_agent.py` | Orchestrates image generation & quality checks | `gemini-2.5-flash` |
| 7 | **Publisher Agent** | `publisher_agent.py` | Pushes payload, variants, & collections to Shopify API | `gemini-2.5-flash` |
| 8 | **Verification Agent** | `verification_agent.py` | Verifies post-publish price, status, & purchasability | `gemini-2.5-flash` |
| 9 | **Report Generator Agent** | `report_generator_agent.py` | Generates Markdown & JSON launch audit reports | `gemini-2.5-flash` |
| 10 | **Marketing Agent** | `marketing_agent.py` | Creates multi-channel promotional copy (Social, Email, WA) | `gemini-2.5-flash` |
| 11 | **Workshop Setup Agent** | `workshop_setup_agent.py` | Orchestrates workshop setup & design replication | `gemini-2.5-flash` |
| 12-17 | **Folder Pipeline Sub-Agents** | `folder_agents.py` | Automated batch folder ingestion to launch pipeline (6 agents) | `gemini-2.5-flash` |

---

## 📑 Agent Context Documentation Files

Detailed architecture, tool contracts, inputs, outputs, and usage guidelines for each agent are documented in their respective markdown context files:

- 🔍 [`product_validation_agent.md`](product_validation_agent.md) — 53-Check Validation Matrix Agent
- 📝 [`copywriter_agent.md`](copywriter_agent.md) — Copywriter Agent
- 🎯 [`seo_agent.md`](seo_agent.md) — SEO Agent
- 📊 [`strategist_agent.md`](strategist_agent.md) — Marketing Strategist Agent
- 🎨 [`image_prompt_agent.md`](image_prompt_agent.md) — Image Prompt Agent
- 🖼️ [`image_generator_agent.md`](image_generator_agent.md) — Image Generator Agent
- 🚀 [`publisher_agent.md`](publisher_agent.md) — Publisher Agent
- ✅ [`verification_agent.md`](verification_agent.md) — Verification Agent
- 📈 [`report_generator_agent.md`](report_generator_agent.md) — Report Generator Agent
- 📣 [`marketing_agent.md`](marketing_agent.md) — Multi-Channel Copywriting Agent
- 🎓 [`workshop_setup_agent.md`](workshop_setup_agent.md) — Workshop Setup Agent
- 📁 [`folder_agents.md`](folder_agents.md) — Batch Folder Sub-Agents Pipeline (Ingestion, Validation, Creation, Media, Verification, Report)

