# Product Launch Workflow — Requirements

**Purpose of this document:** this captures our understanding of the product publishing workflow
we discussed — who does what, how a product moves from an idea to a live Shopify listing, and
where the AI agent fits in. Please read through and confirm the six items flagged at the end under
**"Please Confirm."** Everything else reflects what we already agreed on; happy to adjust anything
that doesn't match your intent.

## 1. What We're Building

A single system where:
- **Lakshmi** prepares product listings (details, pricing, images, video).
- **You (Sandeep)** review and approve every listing before it goes live — nothing reaches the
  real Shopify store without your sign-off.
- The **AI agent** handles the technical work of actually publishing to Shopify once you've
  approved — creating the product, uploading media, and verifying it went live correctly.

No product is published without your approval. That's the core rule the whole system is built around.

## 2. Roles

**Sandeep — Reviewer / Approver**
- Decides which products should go into the store.
- Reviews everything Lakshmi submits: product info, pricing, images/video, and how it will look
  on the site.
- Approves it (→ agent publishes it) or sends it back with feedback (→ Lakshmi fixes and resubmits).
- Does not need to touch the technical Shopify publishing steps.

**Lakshmi — Catalogue / Shopify Admin**
- Adds and maintains product listings — details, catalogue data, images, videos.
- Sends listings to Sandeep for review once ready.
- Fixes anything Sandeep sends back and resubmits.
- Cannot publish a product directly — every listing goes through Sandeep first.

**AI Agent — technical execution only**
- Does not make any business decision.
- Only starts working after Sandeep approves a listing.
- Handles: validating the data, creating/updating the product on Shopify, uploading images and
  video, verifying the listing went live correctly, and producing a report.

## 3. The Workflow

```text
Product idea / decision (Sandeep)
       ↓
Lakshmi adds the product (details, images, video)
       ↓
Saved as Draft
       ↓
Agent checks the data automatically (nothing sent to Sandeep until this passes)
       ↓
Submitted for Sandeep's review
       ↓
Sandeep reviews
       ↓
   ┌─────────────┴─────────────┐
   ▼                           ▼
REQUEST CHANGES              APPROVE
   │                           │
   ▼                           ▼
Back to Lakshmi          AI Agent publishes to Shopify
with feedback                  │
   │                           ▼
   │                     Agent verifies it went live
   │                           │
   │                           ▼
   └──────────► Resubmit    Published
```

## 4. What the Agent Does Automatically vs. What Needs Your Decision

| Step | Decided by | Automated? |
|---|---|---|
| Which product should exist in the store | You | No — your call, always |
| Writing the description / SEO / tags | Lakshmi (can use AI help, but she reviews and edits it) | Assisted, not automatic |
| Is this listing good enough to go live | **You** | No — this is never automated |
| Creating the product on Shopify, uploading media, verifying it's live | Agent, only after your approval | Yes, fully automatic |
| What happens if something technically fails during publishing | Lakshmi (fix the data) or a technical admin (fix infrastructure issues) | Agent reports it, doesn't retry on its own |

## 5. If Something Goes Wrong

If a listing gets rejected, or a technical error happens during publishing, you and Lakshmi will
always see:
- Exactly which step it failed at (data entry, Shopify creation, media upload, or verification)
- A plain-language reason — not a raw error code or technical message

## 6. Please Confirm

Six open points before we start building — quick answers are all we need:

1. **Can you create or edit a product listing yourself**, or should every listing always go
   through Lakshmi first, even when the idea is yours?
2. If yes to the above — **can you approve a listing you created yourself**, or should someone
   else always approve it (to keep a clean record of who checked what)?
3. **Who should be able to manage user access and see technical error details** if something
   breaks — you, Lakshmi, or someone else on the technical side?
4. **Does every edit to an already-live product** need to go through this same review process, or
   only brand-new products?
5. **How should you be notified** when something needs your review — in the app only, or by email
   as well?
6. **If a rejected listing gets fixed and resubmitted**, does it need a full review again, or is a
   lighter check okay if only the specific issues you flagged were changed?

---

Once these are confirmed, we'll move ahead with building the review and approval screens around
the existing product-publishing pipeline that already works today.
