# SEO Agent (`seo_agent.py`)

## 📌 Overview
The **SEO Agent** (`seo_agent`) is a specialized search engine optimization agent designed to generate high-ranking, compliant meta tags, keywords, and URL handles for Shopify products.

---

## 🎯 Primary Purpose
- Generates optimized **SEO Title** tag (< 60 characters).
- Formulates compelling **Meta Description** (120 to 160 characters).
- Extracts 5–10 relevant **SEO Keywords**.
- Builds a clean, lowercase, hyphen-separated **URL Slug / Handle**.

---

## 🛠️ Tools Exposed & Used
- **`get_product_context()`**: Fetches `product_name`, `product_description`, `product_price`, and `product_category`.
- **`save_seo_metadata(seo_title, meta_description, keywords, url_slug, tool_context)`**: Saves metadata dictionary into `tool_context.state["seo_metadata"]`.

---

## 📥 Output State Schema

```json
{
  "seo_metadata": {
    "title": "KiddyPi Frog Bot DIY Kit | Build Your First Robot",
    "description": "Build your own working robotics kit with KiddyPi Frog Bot. Hands-on STEM learning kit for kids with easy assembly and full instructions.",
    "keywords": "kiddypi, frog bot, robotics kit, stem kit for kids, diy robot",
    "slug": "kiddypi-frog-bot-diy-robotics-kit"
  }
}
```

---

## ⚡ Strict Rules
- **SEO Title**: Must be under 60 characters and explicitly include the exact product name.
- **Meta Description**: Must be between 120 and 160 characters.
- **URL Slug**: Lowercase, hyphen-separated, alphanumeric only.
