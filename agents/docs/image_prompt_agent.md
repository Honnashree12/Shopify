# Image Prompt Agent (`image_prompt_agent.py`)

## 📌 Overview
The **Image Prompt Agent** (`image_prompt_agent`) acts as an AI Creative Director specializing in commercial product photography. It crafts 8 photorealistic, high-conversion image generation prompts tailored for Vertex AI / Imagen 3.

---

## 🎯 Primary Purpose
- Reads product context and category details.
- Formulates 8 specialized image prompts specifying studio lighting, DSLR camera settings, compositions, and background details.
- Guarantees outputs adhere to **1:1 square aspect ratio** catalog standards without text artifacts or plastic textures.

---

## 🛠️ Tools Exposed & Used
- **`get_product_context()`**: Fetches product context.
- **`save_image_prompts(...)`**: Saves 8 prompts into `tool_context.state["image_prompts"]`.

---

## 📸 The 8 Prompts Generated
1. **Hero Image Prompt**: Clean white studio background, product centered, soft shadows, 1:1 ratio.
2. **Lifestyle Image Prompt**: In-use context with natural lighting and realistic setting.
3. **Workshop Banner Prompt**: Wide/hero web banner layout with space for text overlay.
4. **Classroom Scene Prompt**: Students collaborating on STEM projects in a modern classroom.
5. **Product Thumbnail Prompt**: High-impact close-up optimized for small grid viewports.
6. **Certificate Preview Prompt**: Professional workshop certificate template preview.
7. **Gallery Image 1 Prompt**: Overhead/flat-lay shot of kit components, tools, and guidebooks.
8. **Gallery Image 2 Prompt**: Macro close-up shot highlighting assembly details and component textures.
