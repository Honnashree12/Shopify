# Copywriter Agent (`copywriter_agent.py`)

## 📌 Overview
The **Copywriter Agent** (`copywriter_agent`) is an AI copywriting specialist responsible for producing structured, high-conversion HTML product descriptions adhering to KiddyPi brand guidelines and Shopify formatting standards.

---

## 🎯 Primary Purpose
- Reads product context (name, raw description, price, category).
- Generates clean, semantically structured HTML (`<h2>`, `<h3>`, `<p>`, `<ul>`, `<li>`).
- Saves the generated description to the shared workflow state (`generated_description`).

---

## 🛠️ Tools Exposed & Used
- **`get_product_context()`**: Retrieves existing product context from state (`product_name`, `product_description`, `product_price`, `product_category`).
- **`save_description(description, tool_context)`**: Validates and saves the HTML string into `tool_context.state["generated_description"]`.

---

## 📐 Required Output Template Structure

The agent strictly enforces this HTML layout:
```html
<h2>[Product Name]</h2>
<p>[Short engaging introduction paragraph]</p>

<h3>Key Benefits</h3>
<ul>
  <li>[Benefit 1]</li>
  <li>[Benefit 2]</li>
  <li>[Benefit 3]</li>
</ul>

<h3>Features</h3>
<ul>
  <li>[Feature 1]</li>
  <li>[Feature 2]</li>
  <li>[Feature 3]</li>
</ul>

<h3>Specifications</h3>
<p>[Factual specifications provided in input description]</p>

<h3>Why Choose This Product?</h3>
<p>[Persuasive closing narrative encouraging purchase]</p>

<p><strong>Order yours today!</strong></p>
```

---

## 🛡️ Strict Operational Constraints
- **Strict Context Usage**: Must call `get_product_context()` first.
- **No Hallucination**: Must not change product name, category, or invent unverified specs.
- **No Placeholders**: Never outputs "Product Name Missing" or dummy text.
