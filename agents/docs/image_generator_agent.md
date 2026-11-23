# Image Generator Agent (`image_generator_agent.py`)

## 📌 Overview
The **Image Generator Agent** (`image_generator_agent`) coordinates image generation, aspect ratio verification (1:1 square padding), resolution checking, and file storage for product assets.

---

## 🎯 Primary Purpose
- Coordinates pre-generation checks and defers image rendering to the execution pipeline (`services/image_generation_service.py` & `services/shopify_media_service.py`).
- Ensures generated images adhere to resolution specs (min `1000x1000`, recommended `1350x1350`).
- Provides filename sanitization (`sanitize_filename`) for clean disk saving.

---

## 🛠️ Tools Exposed & Used
- **`get_product_context()`**: Reads product metadata.
- **`generate_images(tool_context)`**: Signals image pre-generation readiness and hands off rendering execution to the publishing pipeline.

---

## 🔄 Execution Hand-Off Architecture
Actual image generation executes via `services/image_generation_service.py` using Imagen 3 API:
1. Generates raw image bytes from `image_prompts`.
2. Verifies aspect ratio (`w == h`).
3. If non-square, automatically applies white/transparent canvas padding via `transform_image_to_square_padded` without cropping original pixels.
4. Uploads final media assets directly to Shopify product via REST/GraphQL API.
