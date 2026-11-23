# Strategist Agent (`strategist_agent.py`)

## 📌 Overview
The **Strategist Agent** (`strategist_agent`) acts as a Senior E-Commerce Marketing Director. It evaluates existing product copy, category positioning, and target demographics to synthesize a high-level marketing strategy and campaign framework.

---

## 🎯 Primary Purpose
- Analyzes workflow product state (`product_name`, `product_category`, `product_price`, `seo_metadata`).
- Formulates a campaign name, target audience definition, and core messaging framework.
- Drafts initial social captions, email subject lines, body copy, and call-to-action (CTA).

---

## 🛠️ Tools Exposed & Used
- **`get_product_context()`**: Reads product data from workflow state.
- **`save_marketing_strategy(campaign_name, target_audience, marketing_strategy, social_caption, email_subject, email_body, call_to_action, tool_context)`**: Saves marketing dictionary into `tool_context.state["marketing"]`.

---

## 📥 Output State Schema

```json
{
  "marketing": {
    "campaign_name": "Young Innovators Robotics Series",
    "target_audience": "Parents of kids aged 8-14, STEM educators, robotics enthusiasts",
    "marketing_strategy": "Highlight hands-on problem solving, creativity, and screen-free learning.",
    "social_caption": "Unleash your child's inner engineer! 🤖 Spark curiosity with the KiddyPi Frog Bot DIY Kit.",
    "email_subject": "Build your first moving robot at home with KiddyPi!",
    "email_body": "Dear Parent, give your child the ultimate hands-on STEM experience...",
    "call_to_action": "Order your kit now and get instant access to guided tutorials!"
  }
}
```
