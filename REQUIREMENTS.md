# Product Launch Platform – Requirements

## Overview & Architecture Context

### System Objective & Primary Goal
Build a secure, role-based Product Launch platform for managing the complete lifecycle of products from product submission to Shopify publication for **Subhanu Technologies Pvt Ltd** and its consumer STEM learning platform **KiddyPi** (based at the Bengaluru Learning Hub).

**Company & Brand Identity Context:**
- **Legal Entity:** Subhanu Technologies Pvt Ltd (*Repository-Confirmed Implementation Context*)
- **Consumer Brand:** KiddyPi (Default Vendor = `KiddyPi`) (*Repository-Confirmed Implementation Context*)
- **STEM Education Focus:** Hands-on experiential learning in AI, Robotics, IoT, Coding, and Electronics designed for students aged 6–18 (tiered for ages 6–8, 8–12, and 12–18). (*Repository-Confirmed Implementation Context*)
- **Target Audience:** Students (primary learners; ages 6–18), Parents (primary purchasers — *Requires Stakeholder Confirmation*), and Schools/STEM Labs (institutional buyers — *Requires Stakeholder Confirmation*).
- **Product & Service Portfolio:**
  1. *Physical STEM Kits:* micro:bit Beginner STEM Kit, Arduino Robotics Kit, Circuit Quest 5-in-1, Smart Dustbin, Smart Street Light, Bristle Bot. (*Repository-Confirmed Implementation Context*)
  2. *Experiential Workshops & Courses:* AI Tinker Saturdays, Mission Tiranga, AI Robotics Masterclass, Scratch Level 1, Web Programming Level 1. (*Repository-Confirmed Implementation Context*)
- **Shopify Environments:**
  - *Admin API Endpoint:* `kinq5t-q5.myshopify.com` (*Repository-Confirmed Implementation Context*)
  - *Public Customer Storefront:* `shop.kiddypi.com` (*Repository-Confirmed Implementation Context*)

The platform combines:
- Human approval and decision-making
- AI/agent-based product validation and preparation
- Shopify product creation and publishing
- Firebase/Firestore for application data and workflow state
- Firebase Storage for product media
- Role-based access and authorization
- Auditability and workflow tracking

**Primary Goal:** The final system provides a controlled product publishing workflow where:
**Lakshmi prepares the product → Agent validates it → Sandeep reviews and approves it → Agent publishes it to Shopify → Agent verifies the result → Firestore records the complete workflow.** No product should be published without the required human approval.

Existing Product Launch Agent functionality is retained and integrated into this workflow rather than rebuilt. See `docs/CURRENT_ARCHITECTURE.md` for what exists today.

### High-Level System Architecture & Component Flow
```text
                    ┌─────────────────────┐
                    │       USERS         │
                    │ Sandeep | Lakshmi   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Web Application   │
                    │ Dashboard / Review  │
                    └──────────┬──────────┘
                               │
                         Auth + RBAC
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Workflow Management │
                    │ Human-in-the-loop   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Product Launch      │
                    │ Agent               │
                    ├─────────────────────┤
                    │ Ingest              │
                    │ Validate            │
                    │ Create              │
                    │ Media               │
                    │ Verify              │
                    │ Report              │
                    └──────┬───────┬──────┘
                           │       │
                 ┌─────────┘       └──────────┐
                 ▼                            ▼
        ┌─────────────────┐          ┌─────────────────┐
        │    Firestore    │          │ Firebase        │
        │ Workflow/Data   │          │ Storage         │
        └─────────────────┘          └─────────────────┘
                           │
                           ▼
                    ┌─────────────────┐
                    │     Shopify     │
                    │ Product Store   │
                    └─────────────────┘
```

### Scope & Open Decisions
- **Out of Scope for This Phase**:
  - Public storefront changes (customer-facing Shopify theme/pages).
  - The separate Workshops Platform (`static/admin.html`, workshop registrations, SQLite-backed) — untouched by this effort unless Sandeep decides otherwise. It shares the same FastAPI backend, so changes here must not break it.
  - Multi-store / multi-tenant support — single Shopify store, as today.
- **Open Questions for Sandeep**:
  1. Can Sandeep create/edit listings directly, or does data entry always go through Lakshmi? (§2)
  2. Can Sandeep approve a listing he created himself, or is self-approval always blocked? (§2, §12)
  3. Who is the Platform Admin in practice? (§2)
  4. Does every edit to an already-live product need to go through this same review gate, or only new product creation? (Default assumption until answered: every create and edit goes through review for v1).
  5. Notification channel: in-app only for v1, or also email? (SMTP already configured for Workshops).
  6. Does a resubmitted/fixed listing need a fresh full review, or is a lighter re-check acceptable? (Default assumption until answered: full fresh review every time).

---

## Role: Catalog Admin (Lakshmi – Shopify Admin / Product Manager)

**Role Overview & Responsibilities:**
- Receive products selected for publishing.
- Add product information.
- Upload catalogue information, images, and videos.
- Correct products rejected by the reviewer.
- Resubmit products for review.

**Permissions:**
- Create, edit, and save products as drafts.
- Upload media.
- Submit products for review.
- View reviewer feedback.
- Modify rejected products.
- Resubmit products.
- Lakshmi must not be able to bypass the approval process and directly publish a product.

### Module: Catalog Management & Product Ingestion

#### Feature Set: Product Draft & Listing Management

##### Feature: Product Draft Creation & Editing

###### Feature ID & Title
FEAT-CAT-01: Product Draft Creation & Editing

###### Roles
Lakshmi (Catalog Admin)

###### Status
Active Specification

###### Workflow & Production Rules
1. Lakshmi receives product details, catalogue files, or folder data.
2. Lakshmi adds product name, description, SKU, price, inventory, category, tags, and vendor/brand info into the editor.
3. KiddyPi catalog constraints enforce Vendor default = `KiddyPi`, Currency = `INR` (`₹`), and category in (`Workshops`, `STEM Kits`, `Apparel`, `Courses`).
4. Lakshmi saves the product as a draft.
5. Product state transitions to `DRAFT`.
6. Product remains protected as `DRAFT` in Firestore and cannot be published to Shopify directly.

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Lakshmi (Creator/Editor with full draft modification access), Sandeep (Read-only during review), Agent (System read/validation access).
- **Access / Entry Point**: Catalog Admin Dashboard -> "Add Product" button / Listing Edit Form.

###### Pre-Conditions
- **User Preconditions**: Authenticated user with Lakshmi / Catalog Admin role privileges.
- **Data Preconditions**: Valid product metadata or ingested folder path.
- **System Preconditions**: Firestore database connection active.
- **Workflow Preconditions**: Product in `DRAFT` or `CHANGES_REQUESTED` state.
- **UI Preconditions**: Form fields rendered for name, description, SKU, price, inventory, category, tags, vendor.

###### Client-Side Acceptance
- **Valid Input Testing**: Form accepts standard text strings, decimal prices in INR (`₹`), SKUs, and supported STEM categories (`Workshops`, `STEM Kits`, `Apparel`, `Courses`).
- **Invalid Input Testing**: Negative prices or empty product titles trigger inline form validation errors.
- **Special-Character Testing**: Unicode characters, currency symbols (₹, $, &), and HTML formatting in description handled safely.
- **Boundary Testing**: Maximum text limits for title, SKU, and description enforced.
- **UI Behavior & Visual State**: "Save Draft" button updates document state to `DRAFT` without triggering validation or publishing.
- **Interaction & Stress Testing**: Unsaved changes prompt confirmation dialog before navigating away.
- **Client-Side Security**: Client checks auth token; editing controls disabled if user session is invalid.

###### Server-Side Acceptance
- **API Request Validation**: Express/FastAPI payload validator enforces input field schemas.
- **Authentication & Session Integrity**: Firebase Auth token verified; role check enforces `catalog_admin` role server-side.
- **Tenant Isolation & Scoping**: Single-store catalog scoping enforced.
- **Database Integrity & Constraints**: Document created/updated in Firestore `products/{productId}` with updated metadata.
- **API Response Codes & Payloads**: 200 OK on success with product document; 400 Bad Request on schema failure; 401/403 on auth error.
- **Concurrency & Idempotency**: Document edits use update timestamps to prevent race conditions.
- **Audit Logging & Telemetry**: Event `PRODUCT_CREATED` or `PRODUCT_EDITED` written to `audit_logs/{logId}` with user, timestamp, and product ID.

###### Business Logic
- **Actor Eligibility**: Only users holding the Lakshmi / Catalog Admin role can create or edit draft products.
- **Business Domain Rules**: Products created by Lakshmi default to Vendor `KiddyPi`, Currency `INR`, and must remain in `DRAFT` state until submitted and approved. Direct publication to Shopify is strictly forbidden.
- **State Machine Transitions**: `NEW` -> `DRAFT` or `CHANGES_REQUESTED` -> `DRAFT`.
- **Workflow Dependencies**: Saved drafts must pass Agent Validation before moving to Review queue.
- **Data Integrity Rules**: Product metadata stored in Firestore `products/{productId}` as the durable system of record.
- **Business Failure Handling**: Database write failure displays error message and preserves local input state for retry.

###### Post-Conditions
- **Successful Post-Conditions**: Product document updated in Firestore with status `DRAFT`.
- **Failure Post-Conditions**: Product remains in previous state; error notification displayed.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-CAT-01.1: Lakshmi can create and edit product draft information (name, description, SKU, price, inventory, category, tags, vendor).
  - AC-CAT-01.2: Product draft is saved to Firestore under `products/{productId}` with state `DRAFT`.
  - AC-CAT-01.3: Direct publish to Shopify from the draft screen is strictly blocked both in UI and backend.

###### Edge / Negative Test Matrix
- Attempting to submit an empty form blocks submission with field-level highlights.
- Unauthenticated POST request to `/api/products` returns 401 Unauthorized.

###### Completion List (Definition of Done)
- Draft creation/edit UI form built.
- Firestore persistence implemented.
- Server-side RBAC validation active.

---

##### Feature: Product Media Management

###### Feature ID & Title
FEAT-CAT-02: Product Media Upload & Management

###### Roles
Lakshmi (Catalog Admin)

###### Status
Active Specification

###### Workflow & Production Rules
1. Lakshmi selects or drag-and-drops product images and videos.
2. Media files are uploaded to Firebase Storage under product-specific paths.
3. Media paths are linked to the Firestore product document.
4. Processed images and videos are validated for supported formats.
5. If upload fails, the actual failed stage (`Media`) and real HTTP/network error must be surfaced (§16).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Lakshmi (Upload, reorder, remove media), Sandeep (View media during review), Agent (Process media during Shopify sync).
- **Access / Entry Point**: Product Editor UI -> Media Upload Gallery.

###### Pre-Conditions
- **User Preconditions**: Authenticated as Lakshmi (Catalog Admin).
- **Data Preconditions**: Valid image files (PNG, JPG, WEBP) or video files (MP4, MOV).
- **System Preconditions**: Firebase Storage service initialized and accessible.
- **Workflow Preconditions**: Product draft record exists in Firestore.
- **UI Preconditions**: Media uploader container rendered.

###### Client-Side Acceptance
- **Valid Input Testing**: Multiple images and videos upload cleanly and display preview thumbnails.
- **Invalid Input Testing**: Unsupported file types (e.g. `.exe`, `.pdf`) rejected with clear format warning.
- **Special-Character Testing**: Filenames with spaces and special characters sanitized safely.
- **Boundary Testing**: Max file size checks executed before upload initiation.
- **UI Behavior & Visual State**: Upload progress bar displayed per file; thumbnails render upon completion.
- **Interaction & Stress Testing**: Concurrent multi-file drag-and-drop handled cleanly.
- **Client-Side Security**: Signed upload URLs or Firebase Storage security rules enforced.

###### Server-Side Acceptance
- **API Request Validation**: Validates file MIME types and size parameters.
- **Authentication & Session Integrity**: Bearer token validated for Storage access.
- **Tenant Isolation & Scoping**: Files saved under `products/{productId}/media/` in Firebase Storage.
- **Database Integrity & Constraints**: Media metadata array stored in `products/{productId}.media_paths`.
- **API Response Codes & Payloads**: 200 OK with uploaded file metadata array.
- **Concurrency & Idempotency**: Re-uploading or updating media updates the array idempotently.
- **Audit Logging & Telemetry**: Event `MEDIA_UPLOADED` written to audit logs.

###### Business Logic
- **Actor Eligibility**: Lakshmi role authorized to manage draft media assets.
- **Business Domain Rules**: Media must be associated with the relevant Firestore product record. Upload failures must show real errors and NEVER degrade into generic errors like `'NoneType' object has no attribute 'state'` (§5, §16).
- **State Machine Transitions**: State remains `DRAFT` or `CHANGES_REQUESTED`.
- **Workflow Dependencies**: Media files required prior to Agent Validation step.
- **Data Integrity Rules**: Firebase Storage paths recorded in Firestore.
- **Business Failure Handling**: Real HTTP errors (e.g., HTTP 429, storage quota) preserved and displayed with stage indicator (`Stage: Media`).

###### Post-Conditions
- **Successful Post-Conditions**: Media uploaded to Firebase Storage; URLs saved in Firestore product document.
- **Failure Post-Conditions**: UI surfaces `Media Upload Failed` modal with stage and real error message (§16).

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-CAT-02.1: Lakshmi can upload product images and videos to Firebase Storage.
  - AC-CAT-02.2: Media files are linked to the Firestore product document.
  - AC-CAT-02.3: Real upload errors are displayed showing stage (`Media`) and message without suppression (§16).

###### Edge / Negative Test Matrix
- Network interruption during video upload shows "Upload failed at stage: Media" with a "Retry Upload" button.

###### Completion List (Definition of Done)
- Firebase Storage integration functional.
- Real error propagation verified (§16).
- Media gallery UI completed.

---

#### Feature Set: Review Submission & Resubmission

##### Feature: Submit Product for Review

###### Feature ID & Title
FEAT-CAT-03: Submit Product for Review

###### Roles
Lakshmi (Catalog Admin)

###### Status
Active Specification

###### Workflow & Production Rules
1. Lakshmi completes draft details and media, then clicks "Submit for Review".
2. System automatically triggers Agent Validation FIRST (§3).
3. If validation succeeds, product transitions `DRAFT` -> `VALIDATING` -> `READY_FOR_REVIEW`.
4. Product enters Sandeep's review queue.
5. If validation fails, state transitions to `VALIDATION_FAILED` and product remains in Lakshmi's queue with error details (§3).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Lakshmi (Initiator), Agent (Automated Validator), Sandeep (Target Approver).
- **Access / Entry Point**: Catalog Editor / Dashboard -> "Submit for Review" button.

###### Pre-Conditions
- **User Preconditions**: Authenticated as Lakshmi (Catalog Admin).
- **Data Preconditions**: Product draft exists in Firestore.
- **System Preconditions**: Agent Validation service active.
- **Workflow Preconditions**: Product state is `DRAFT` or `CHANGES_REQUESTED`.
- **UI Preconditions**: "Submit for Review" button enabled.

###### Client-Side Acceptance
- **Valid Input Testing**: Clicking submit starts validation spinner and updates status UI.
- **Invalid Input Testing**: Attempting to submit a product with missing required fields triggers validation failure UI.
- **Special-Character Testing**: Payload transmitted cleanly without character truncation.
- **Boundary Testing**: UI disables submit button during in-flight validation request to prevent double submissions.
- **UI Behavior & Visual State**: Status badge updates to `VALIDATING` then `READY_FOR_REVIEW` or `VALIDATION_FAILED`.
- **Interaction & Stress Testing**: Concurrent user activity handles status transition gracefully.
- **Client-Side Security**: Token sent in authorization header.

###### Server-Side Acceptance
- **API Request Validation**: Endpoint checks product payload completeness before triggering workflow state transition.
- **Authentication & Session Integrity**: Verifies Firebase Auth token and `catalog_admin` role.
- **Tenant Isolation & Scoping**: Single-store scope enforced.
- **Database Integrity & Constraints**: Updates `workflow_state` in `products/{productId}` and `workflow/{workflowId}` in Firestore.
- **API Response Codes & Payloads**: 200 OK with new state object.
- **Concurrency & Idempotency**: State machine enforces valid transition rules (`DRAFT` -> `VALIDATING` -> `READY_FOR_REVIEW`).
- **Audit Logging & Telemetry**: Event `SUBMITTED_FOR_REVIEW` written to `audit_logs/{logId}`.

###### Business Logic
- **Actor Eligibility**: Lakshmi role authorized to submit. Self-approval blocked (§2, §12).
- **Business Domain Rules**: Agent Validation MUST run before reaching Sandeep (§3). Sandeep should never see a listing that fails required-field/media/duplicate checks (§3).
- **State Machine Transitions**: `DRAFT` -> `VALIDATING` -> `READY_FOR_REVIEW` (if valid) or `VALIDATION_FAILED` (if invalid).
- **Workflow Dependencies**: Automatic handoff to Sandeep's queue upon successful validation.
- **Data Integrity Rules**: Workflow state stored in Firestore as durable source of truth (§6, §9).
- **Business Failure Handling**: If agent validation fails, state becomes `VALIDATION_FAILED` and itemized blocker list is displayed to Lakshmi.

###### Post-Conditions
- **Successful Post-Conditions**: State set to `READY_FOR_REVIEW`; product appears on Sandeep's review queue.
- **Failure Post-Conditions**: State set to `VALIDATION_FAILED`; product remains in Lakshmi's queue with error report.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-CAT-03.1: Agent Validation runs automatically before a listing reaches Sandeep's review queue (§3).
  - AC-CAT-03.2: Valid listings transition to `READY_FOR_REVIEW` in Firestore and appear on Sandeep's queue.
  - AC-CAT-03.3: Invalid listings transition to `VALIDATION_FAILED` and remain with Lakshmi.

###### Edge / Negative Test Matrix
- Submitting a listing with a duplicate SKU triggers `VALIDATION_FAILED` before Sandeep ever sees it.

###### Completion List (Definition of Done)
- Pre-review Agent Validation pipeline connected.
- Firestore workflow state updates verified.

---

##### Feature: Resubmit Rejected Product

###### Feature ID & Title
FEAT-CAT-04: Resubmit Rejected Product

###### Roles
Lakshmi (Catalog Admin)

###### Status
Active Specification

###### Workflow & Production Rules
1. Sandeep requests changes on a product, setting state to `CHANGES_REQUESTED`.
2. Product returns to Lakshmi's dashboard with reviewer comments (§4, §7).
3. Lakshmi reviews feedback, edits product information/media, and clicks "Resubmit".
4. Product runs through Agent Validation again.
5. If validation passes, product transitions to `READY_FOR_REVIEW` / `UNDER_REVIEW` on Sandeep's queue.

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Lakshmi (Editor/Resubmitter), Sandeep (Feedback Provider), Agent (Re-validator).
- **Access / Entry Point**: Catalog Dashboard -> "Products Requiring Changes" tab -> Edit & Resubmit form.

###### Pre-Conditions
- **User Preconditions**: Authenticated as Lakshmi (Catalog Admin).
- **Data Preconditions**: Product state is `CHANGES_REQUESTED` with reviewer comments in Firestore.
- **System Preconditions**: Workflow engine active.
- **Workflow Preconditions**: Product in `CHANGES_REQUESTED` state.
- **UI Preconditions**: Sandeep's comments displayed at top of editor UI.

###### Client-Side Acceptance
- **Valid Input Testing**: Edits made, resubmit clicked, status badge updates.
- **Invalid Input Testing**: Resubmitting without resolving flagged errors triggers validation stop.
- **Special-Character Testing**: Multiline reviewer comments displayed cleanly.
- **Boundary Testing**: Resubmission audit trail tracks iteration count.
- **UI Behavior & Visual State**: Status transitions from `CHANGES_REQUESTED` to `VALIDATING` then `READY_FOR_REVIEW`.
- **Interaction & Stress Testing**: Editing fields while reviewing comments operates smoothly.
- **Client-Side Security**: Lakshmi cannot edit reviewer comment history or alter approval records.

###### Server-Side Acceptance
- **API Request Validation**: Validates that product state is `CHANGES_REQUESTED`.
- **Authentication & Session Integrity**: Token and role verified.
- **Tenant Isolation & Scoping**: Store scoped.
- **Database Integrity & Constraints**: Updates Firestore document `products/{productId}` with updated payload and state.
- **API Response Codes & Payloads**: 200 OK.
- **Concurrency & Idempotency**: Atomic state updates prevent race conditions.
- **Audit Logging & Telemetry**: Event `PRODUCT_RESUBMITTED` logged to `audit_logs/{logId}`.

###### Business Logic
- **Actor Eligibility**: Lakshmi role authorized.
- **Business Domain Rules**: Resubmitted products undergo full fresh agent validation (§3, §4). Full fresh review required by default (§4).
- **State Machine Transitions**: `CHANGES_REQUESTED` -> `VALIDATING` -> `READY_FOR_REVIEW`.
- **Workflow Dependencies**: Requires existing `CHANGES_REQUESTED` state and reviewer feedback record.
- **Data Integrity Rules**: Reviewer feedback history preserved in Firestore audit trail (§13).
- **Business Failure Handling**: Validation failure during resubmit sets state to `VALIDATION_FAILED`.

###### Post-Conditions
- **Successful Post-Conditions**: Product updated, validated, and returned to Sandeep's review queue.
- **Failure Post-Conditions**: Product remains in `CHANGES_REQUESTED` or `VALIDATION_FAILED`.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-CAT-04.1: Rejected products return to Lakshmi's queue with reviewer feedback displayed (§4, §7).
  - AC-CAT-04.2: Lakshmi can modify rejected listings and resubmit them for fresh review (§4).

###### Edge / Negative Test Matrix
- Attempting to resubmit an already `APPROVED` product returns a 400 Bad Request error.

###### Completion List (Definition of Done)
- Rejection feedback display and resubmission loop verified.

---

#### Feature Set: Lakshmi Workspace & Monitoring

##### Feature: Lakshmi Catalog Dashboard

###### Feature ID & Title
FEAT-CAT-05: Lakshmi Catalog Dashboard

###### Roles
Lakshmi (Catalog Admin)

###### Status
Active Specification

###### Workflow & Production Rules
1. Lakshmi logs into the application.
2. System detects `catalog_admin` role and directs to Lakshmi Dashboard (§11, §14).
3. Dashboard displays categorized overview: Drafts, Products requiring changes, Products submitted for review, Recently updated products, Published products, and Agent status (§14).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Lakshmi (Primary User), System (Data Provider).
- **Access / Entry Point**: Login -> Role Detection -> Lakshmi Dashboard (`/dashboard/catalog`).

###### Pre-Conditions
- **User Preconditions**: Authenticated with `catalog_admin` role.
- **Data Preconditions**: Firestore catalog collections available.
- **System Preconditions**: Firestore query service operational.
- **Workflow Preconditions**: Successful authentication.
- **UI Preconditions**: Dashboard layout component loaded.

###### Client-Side Acceptance
- **Valid Input Testing**: Clicking dashboard tabs filters product cards by status.
- **Invalid Input Testing**: Search query with no matches displays clear empty state.
- **Special-Character Testing**: Product names with special characters rendered safely.
- **Boundary Testing**: Large catalog lists handled with pagination.
- **UI Behavior & Visual State**: Clear visual indicators for products needing attention (§14, §19), adhering to official KiddyPi brand palette tokens: Background Cream (`#FAF6F0`), Primary Text/Headers Ink (`#1C1917`), Brand/CTA Accent Orange (`#EA580C`), and Success Status Indicator Green (`#16A34A`).
- **Interaction & Stress Testing**: Switching tabs rapidly maintains accurate counts.
- **Client-Side Security**: Sandeep's review controls (`APPROVE` / `REQUEST CHANGES`) hidden from Lakshmi's UI (§12).

###### Server-Side Acceptance
- **API Request Validation**: Query filter parameters validated.
- **Authentication & Session Integrity**: Firebase Auth token verified; role check enforces `catalog_admin`.
- **Tenant Isolation & Scoping**: Store scoped.
- **Database Integrity & Constraints**: Firestore indexed queries on `workflow_state` and `updated_at`.
- **API Response Codes & Payloads**: 200 OK with categorized product summaries.
- **Concurrency & Idempotency**: Real-time subscriptions or REST reads.
- **Audit Logging & Telemetry**: User session login logged.

###### Business Logic
- **Actor Eligibility**: Lakshmi / Catalog Admin role.
- **Business Domain Rules**: Dashboard surfaces actionable categories for catalog management (§14).
- **State Machine Transitions**: N/A (Read-only overview).
- **Workflow Dependencies**: Data pulled from Firestore as durable source of truth (§6, §9).
- **Data Integrity Rules**: Real-time state reflects Firestore `products` collection.
- **Business Failure Handling**: Firestore query failure shows error banner without crashing app.

###### Post-Conditions
- **Successful Post-Conditions**: Dashboard rendered with current product counts and status lists.
- **Failure Post-Conditions**: Error alert displayed if data fetch fails.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-CAT-05.1: Lakshmi Dashboard displays Drafts, Products Requiring Changes, Submitted Products, Recently Updated, Published Products, and Agent Status (§14).
  - AC-CAT-05.2: Role detection routes Lakshmi to Catalog Dashboard upon login (§11).

###### Edge / Negative Test Matrix
- Logging in as Lakshmi hides all review approval controls.

###### Completion List (Definition of Done)
- Lakshmi Dashboard UI built and wired to Firestore queries.

---

## Role: Product Reviewer / Approver (Sandeep – Product Reviewer / Approver)

**Role Overview & Responsibilities:**
- Decide which products should be published.
- Review products submitted by Lakshmi.
- Check product information, images, videos, pricing, buttons, UI/content, and overall presentation (§2).
- Approve products for Shopify publication.
- Reject products when changes are required and provide feedback (§2).

**Permissions:**
- View products submitted for review.
- Review complete product information.
- Approve or request changes.
- View publishing status and history.
- View published products.
- Sandeep should not need to manually perform the technical Shopify publishing process (§2).
- Sandeep cannot approve a listing he created/submitted himself (No self-approval rule §2, §12).

### Module: Product Review & Approval

#### Feature Set: Listing Review & Presentation Inspection

##### Feature: Product Review Screen

###### Feature ID & Title
FEAT-REV-01: Product Review Screen

###### Roles
Sandeep (Product Reviewer / Approver)

###### Status
Active Specification

###### Workflow & Production Rules
1. Sandeep selects a listing from his review queue (`READY_FOR_REVIEW` or `UNDER_REVIEW`).
2. System displays Product Review Screen (§7).
3. Display includes: Product name, description, SKU, price, inventory, category, tags, vendor/brand, images, videos, Shopify template, status, product ID, agent validation results, missing information, conflicts, duplicates, and media validation (§7).
4. State transitions to `UNDER_REVIEW`.
5. Sandeep evaluates listing quality, presentation, pricing, and content (§2, §4).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Sandeep (Inspector/Reviewer), System (Data Provider).
- **Access / Entry Point**: Sandeep Review Dashboard -> Awaiting Review Queue -> Select Product.

###### Pre-Conditions
- **User Preconditions**: Authenticated with Sandeep / Approver role.
- **Data Preconditions**: Product state is `READY_FOR_REVIEW` or `UNDER_REVIEW`.
- **System Preconditions**: Product review detail service active.
- **Workflow Preconditions**: Agent Validation completed successfully (§3).
- **UI Preconditions**: Review screen modal / view loaded.

###### Client-Side Acceptance
- **Valid Input Testing**: Review screen loads text, price, SKU, tags, and media player cleanly.
- **Invalid Input Testing**: N/A (Read-only inspection).
- **Special-Character Testing**: Description HTML, special characters, and formatting render safely.
- **Boundary Testing**: Long multi-line descriptions and multiple media files render in scrollable containers.
- **UI Behavior & Visual State**: Action buttons (`APPROVE`, `REQUEST CHANGES`) clearly visible (§7). Displays storefront preview matching KiddyPi responsive layout blocks (Hero header with badge, glassmorphism event info cards for date/time/venue/age, tabbed syllabus breakdown, and sticky bottom CTA bar).
- **Interaction & Stress Testing**: Image gallery lightbox and video preview player control smoothly.
- **Client-Side Security**: Data fields are read-only for Sandeep; direct edit fields hidden (§12).

###### Server-Side Acceptance
- **API Request Validation**: Validates product ID parameter.
- **Authentication & Session Integrity**: Verifies Firebase Auth token and Sandeep role.
- **Tenant Isolation & Scoping**: Single-store scope.
- **Database Integrity & Constraints**: Updates product state to `UNDER_REVIEW` in Firestore `products/{productId}`.
- **API Response Codes & Payloads**: 200 OK with complete product details and agent validation report.
- **Concurrency & Idempotency**: Atomic state read/update.
- **Audit Logging & Telemetry**: Event `REVIEW_STARTED` written to `audit_logs/{logId}`.

###### Business Logic
- **Actor Eligibility**: Sandeep role authorized. Self-approval rule checked (§2, §12).
- **Business Domain Rules**: Sandeep reviews product presentation, media, pricing, and UI content (§2, §4). Technical validation is already verified by Agent (§3).
- **State Machine Transitions**: `READY_FOR_REVIEW` -> `UNDER_REVIEW`.
- **Workflow Dependencies**: Must have passed Agent Validation (§3).
- **Data Integrity Rules**: Product data loaded from Firestore `products/{productId}`.
- **Business Failure Handling**: Failed media loads display fallback placeholders with warning icons.

###### Post-Conditions
- **Successful Post-Conditions**: Review screen displayed; state set to `UNDER_REVIEW` in Firestore.
- **Failure Post-Conditions**: Error alert displayed if product review data fails to load.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-REV-01.1: Product Review Screen displays complete listing info, media gallery, validation audit, and decision buttons (`APPROVE`, `REQUEST CHANGES`) (§7).
  - AC-REV-01.2: Opening review updates product state to `UNDER_REVIEW` in Firestore (§6).

###### Edge / Negative Test Matrix
- Opening an already published product displays historical review record with action buttons disabled.

###### Completion List (Definition of Done)
- Review screen UI component built.
- Media viewer and validation report display integrated.

---

#### Feature Set: Approval Decisioning & Change Request

##### Feature: Approve Product Listing

###### Feature ID & Title
FEAT-REV-02: Approve Product Listing

###### Roles
Sandeep (Product Reviewer / Approver)

###### Status
Active Specification

###### Workflow & Production Rules
1. Sandeep reviews listing on Product Review Screen and clicks `APPROVE`.
2. System verifies Sandeep's authorization and checks self-approval rule (§2, §12).
3. System writes a traceable `Approve` event (user ID, timestamp, approval signature) to Firestore `products/{productId}` and `workflow/{workflowId}` (§12, §13).
4. State transitions `UNDER_REVIEW` -> `APPROVED`.
5. System automatically triggers Product Launch Agent to execute Shopify publishing pipeline (§4, §5).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Sandeep (Approver), Product Launch Agent (Automated Execution Trigger).
- **Access / Entry Point**: Product Review Screen -> `APPROVE` button.

###### Pre-Conditions
- **User Preconditions**: Authenticated as Sandeep. Submitter ID != Approver ID (no self-approval §2, §12).
- **Data Preconditions**: Product state is `UNDER_REVIEW` or `READY_FOR_REVIEW`.
- **System Preconditions**: Product Launch Agent trigger service active.
- **Workflow Preconditions**: Agent Validation passed.
- **UI Preconditions**: `APPROVE` button active.

###### Client-Side Acceptance
- **Valid Input Testing**: Clicking `APPROVE` displays confirmation dialog and triggers agent progress UI.
- **Invalid Input Testing**: Attempting approval on invalid state shows error toast.
- **Special-Character Testing**: Approval note supports standard unicode characters.
- **Boundary Testing**: Submit button locked during API request to prevent duplicate clicks.
- **UI Behavior & Visual State**: Status badge updates to `APPROVED` then `PUBLISHING`.
- **Interaction & Stress Testing**: UI seamlessly hands off view to agent execution tracker (§15).
- **Client-Side Security**: Auth token sent with API call.

###### Server-Side Acceptance
- **API Request Validation**: Validates product ID and current state.
- **Authentication & Session Integrity**: Verifies bearer token and Sandeep role server-side. Enforces **no self-approval rule** (§2, §12).
- **Tenant Isolation & Scoping**: Store scoped.
- **Database Integrity & Constraints**: Writes `approval_status: "APPROVED"`, `approved_by: userId`, `approved_at: timestamp` to Firestore `products/{productId}`.
- **API Response Codes & Payloads**: 200 OK with approval confirmation.
- **Concurrency & Idempotency**: Atomic state transaction prevents duplicate execution triggers.
- **Audit Logging & Telemetry**: Event `PRODUCT_APPROVED` written to `audit_logs/{logId}` with full context (§13).

###### Business Logic
- **Actor Eligibility**: Only Sandeep role can approve. Whoever submitted a listing CANNOT approve it (§2, §12).
- **Business Domain Rules**: Human approval is MANDATORY before Shopify publication (§4, §12). Launch Agent MUST NOT publish without a traceable Approve event in Firestore (§12, §13).
- **State Machine Transitions**: `UNDER_REVIEW` -> `APPROVED` -> `PUBLISHING`.
- **Workflow Dependencies**: Triggers Product Launch Agent execution pipeline (§5).
- **Data Integrity Rules**: Traceable approval record saved in Firestore before Shopify call is allowed (§12, §13).
- **Business Failure Handling**: Agent invocation failure sets state to `PUBLISH_FAILED` with error log.

###### Post-Conditions
- **Successful Post-Conditions**: Traceable approval recorded in Firestore; state set to `APPROVED`; Product Launch Agent triggered.
- **Failure Post-Conditions**: Approval blocked if self-approval detected or role unauthorized; state remains `UNDER_REVIEW`.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-REV-02.1: Sandeep can approve listings, creating a traceable `Approve` event in Firestore (§4, §12, §13).
  - AC-REV-02.2: Approved products automatically trigger Product Launch Agent execution (§4, §5).
  - AC-REV-02.3: Submitter cannot approve their own submission (§2, §12).

###### Edge / Negative Test Matrix
- User submitting a draft attempts to approve it via API: Server rejects with `403 Forbidden: Self-approval prohibited`.

###### Completion List (Definition of Done)
- Backend approval endpoint with RBAC & self-approval check built.
- Firestore traceable audit event logging verified.
- Agent pipeline execution trigger connected.

---

##### Feature: Reject Product & Request Changes

###### Feature ID & Title
FEAT-REV-03: Reject Product & Request Changes

###### Roles
Sandeep (Product Reviewer / Approver)

###### Status
Active Specification

###### Workflow & Production Rules
1. Sandeep reviews listing and clicks `REQUEST CHANGES`.
2. System opens feedback dialog requiring written comments explaining requested changes (§4, §7).
3. Sandeep enters feedback and submits.
4. Product state transitions `UNDER_REVIEW` -> `CHANGES_REQUESTED`.
5. Product returns to Lakshmi's queue with feedback attached (§4, §7).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Sandeep (Reviewer), Lakshmi (Recipient).
- **Access / Entry Point**: Product Review Screen -> `REQUEST CHANGES` button & modal.

###### Pre-Conditions
- **User Preconditions**: Authenticated as Sandeep (Approver).
- **Data Preconditions**: Product in `UNDER_REVIEW` / `READY_FOR_REVIEW` state.
- **System Preconditions**: Firestore messaging/comment service active.
- **Workflow Preconditions**: Product under review.
- **UI Preconditions**: Feedback text area rendered.

###### Client-Side Acceptance
- **Valid Input Testing**: Entering comments and submitting updates state cleanly.
- **Invalid Input Testing**: Submitting empty feedback shows validation error requiring comment text.
- **Special-Character Testing**: Multi-line feedback, quotes, and punctuation preserved.
- **Boundary Testing**: Max character limit enforced for comment field.
- **UI Behavior & Visual State**: Status badge updates to `CHANGES_REQUESTED`.
- **Interaction & Stress Testing**: Modal open/close actions responsive.
- **Client-Side Security**: Input sanitized to prevent XSS.

###### Server-Side Acceptance
- **API Request Validation**: Validates that feedback comment string is non-empty.
- **Authentication & Session Integrity**: Verifies token and Sandeep role.
- **Tenant Isolation & Scoping**: Store scoped.
- **Database Integrity & Constraints**: Updates `workflow_state: "CHANGES_REQUESTED"` and appends comment to `reviewer_comments` array in Firestore `products/{productId}`.
- **API Response Codes & Payloads**: 200 OK.
- **Concurrency & Idempotency**: Atomic state write.
- **Audit Logging & Telemetry**: Event `CHANGES_REQUESTED` written to `audit_logs/{logId}` with comments (§13).

###### Business Logic
- **Actor Eligibility**: Sandeep role authorized.
- **Business Domain Rules**: Written reviewer feedback mandatory when requesting changes (§4). Product returned to Lakshmi for edits (§4).
- **State Machine Transitions**: `UNDER_REVIEW` -> `CHANGES_REQUESTED`.
- **Workflow Dependencies**: Product returned to Lakshmi's "Products Requiring Changes" queue (§14).
- **Data Integrity Rules**: Comments persisted in Firestore document.
- **Business Failure Handling**: Database failure preserves comment text in modal for retry.

###### Post-Conditions
- **Successful Post-Conditions**: State set to `CHANGES_REQUESTED`; feedback saved; product visible in Lakshmi's queue.
- **Failure Post-Conditions**: State remains `UNDER_REVIEW` if save fails.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-REV-03.1: Sandeep can request changes with mandatory feedback comments (§4, §7).
  - AC-REV-03.2: Product state updates to `CHANGES_REQUESTED` and returns to Lakshmi (§4).

###### Edge / Negative Test Matrix
- Submitting change request without comments blocks submit with alert "Reviewer comment is required".

###### Completion List (Definition of Done)
- Change request modal and API endpoint functional.
- Comment persistence in Firestore verified.

---

#### Feature Set: Sandeep Workspace & Activity Monitoring

##### Feature: Sandeep Review Dashboard

###### Feature ID & Title
FEAT-REV-04: Sandeep Review Dashboard

###### Roles
Sandeep (Product Reviewer / Approver)

###### Status
Active Specification

###### Workflow & Production Rules
1. Sandeep logs into application.
2. System detects `approver` role and routes to Sandeep Review Dashboard (§11, §14).
3. Dashboard displays: Products awaiting review, Recently approved products, Products requiring changes, Published products, and Publishing activity (§14).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Sandeep (Primary User), System (Data Provider).
- **Access / Entry Point**: Login -> Role Detection -> Sandeep Dashboard (`/dashboard/review`).

###### Pre-Conditions
- **User Preconditions**: Authenticated with Sandeep / Approver role.
- **Data Preconditions**: Firestore catalog collections accessible.
- **System Preconditions**: Review queue query index ready.
- **Workflow Preconditions**: Successful authentication.
- **UI Preconditions**: Dashboard container loaded.

###### Client-Side Acceptance
- **Valid Input Testing**: Tabs filter queue by awaiting review, approved, and activity.
- **Invalid Input Testing**: Search query with no matches displays empty queue banner.
- **Special-Character Testing**: Handles special characters in product titles safely.
- **Boundary Testing**: High volume queue paginated cleanly.
- **UI Behavior & Visual State**: Review queue counts highlighted with badges (§14, §19).
- **Interaction & Stress Testing**: Switching tabs renders cached query lists rapidly.
- **Client-Side Security**: Edit buttons hidden; review buttons displayed (§12).

###### Server-Side Acceptance
- **API Request Validation**: Query parameters validated.
- **Authentication & Session Integrity**: Verifies Firebase Auth token and Sandeep role.
- **Tenant Isolation & Scoping**: Store scoped.
- **Database Integrity & Constraints**: Firestore indexed queries on `workflow_state == "READY_FOR_REVIEW"`.
- **API Response Codes & Payloads**: 200 OK with categorized product list.
- **Concurrency & Idempotency**: Read queries.
- **Audit Logging & Telemetry**: Dashboard access logged.

###### Business Logic
- **Actor Eligibility**: Sandeep / Approver role.
- **Business Domain Rules**: Surfaces review queue and publishing activity metrics relevant to approver (§14).
- **State Machine Transitions**: N/A (Read-only dashboard).
- **Workflow Dependencies**: Reads live states from Firestore (§6, §9).
- **Data Integrity Rules**: State pulled from Firestore as durable source of truth (§6, §9).
- **Business Failure Handling**: Query failure shows refresh button.

###### Post-Conditions
- **Successful Post-Conditions**: Sandeep Dashboard rendered with pending review queue.
- **Failure Post-Conditions**: Error alert displayed on read failure.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-REV-04.1: Sandeep Dashboard displays Awaiting Review, Recently Approved, Changes Requested, Published Products, and Publishing Activity (§14).
  - AC-REV-04.2: Role detection routes Sandeep to Review Dashboard upon login (§11).

###### Edge / Negative Test Matrix
- Logging in as Sandeep displays review queue and hides draft creation controls.

###### Completion List (Definition of Done)
- Sandeep Dashboard UI component built and wired to Firestore queries.

---

## Role: Product Launch Agent (Automated Pipeline)

**Role Overview & Responsibilities:**
- Automates technical operations after required human approval (§2):
  - Product validation and normalization (§5).
  - Required-field and media checks (§5).
  - Image/video processing (§5).
  - Shopify product creation/update (§5, §8).
  - Shopify media upload (§5, §8).
  - Duplicate and conflict detection (§5, §18).
  - Firebase/Firestore synchronization (§9).
  - Shopify listing verification (§5, §8).
  - Reporting and error handling (§5, §16).
- The agent must NOT independently approve products requiring human review, and MUST NEVER publish without a traceable Approve event (§2, §12).

### Module: Automated Product Publishing Pipeline

#### Feature Set: Technical Execution Pipeline

##### Feature: Automated Ingest & Validation

###### Feature ID & Title
FEAT-AGT-01: Automated Ingest & Validation

###### Roles
Product Launch Agent (Automated Pipeline)

###### Status
Active Specification

###### Workflow & Production Rules
1. Agent ingests product details, `product.json`, catalogue data, images, videos, pricing, SKU, inventory, metadata (§5, §18).
2. Agent executes the 53-rule automated validation engine (`services/unified_validation_engine.py`) checking KiddyPi catalog rules (Vendor == `KiddyPi`, Currency == `INR`, title length, SEO description, image resolution, pricing > 0, template suffix, duplicates, and conflicts) (§5, §18).
3. Validation runs automatically:
   - Before human review (triggered by Lakshmi submit) (§3).
   - Post-approval pre-publish verification (§5).
4. Validation failure stops publishing immediately, sets state to `VALIDATION_FAILED`, and logs exact blocker reasons (§5, §15, §16).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Product Launch Agent (Automated Worker), System (Executor).
- **Access / Entry Point**: System event call during submit or pre-publish pipeline.

###### Pre-Conditions
- **User Preconditions**: System service execution context.
- **Data Preconditions**: Product payload or folder ingestion path available.
- **System Preconditions**: `services/unified_validation_engine.py` initialized.
- **Workflow Preconditions**: State is `DRAFT` or `VALIDATING`.
- **UI Preconditions**: Agent status widget visible on UI (`✓ Ingest`, `⟳ Validate`) (§15).

###### Client-Side Acceptance
- **Valid Input Testing**: Agent status widget shows step progress (`✓ Ingest`, `✓ Validate`) (§15).
- **Invalid Input Testing**: Validation error displays red failed icon (`✗ Validate`) with error count (§15).
- **Special-Character Testing**: Error text sanitized for UI rendering.
- **Boundary Testing**: High volume validation rules execute without UI freeze.
- **UI Behavior & Visual State**: Live status updates show actual failed stage (§15, §16).
- **Interaction & Stress Testing**: Real-time progress updates stream via WebSocket/polling.
- **Client-Side Security**: Technical error logs sanitized for standard users (§16).

###### Server-Side Acceptance
- **API Request Validation**: Validates incoming product data schema.
- **Authentication & Session Integrity**: System service authentication.
- **Tenant Isolation & Scoping**: Store scoped.
- **Database Integrity & Constraints**: Saves validation audit report in Firestore `products/{productId}.validation_results`.
- **API Response Codes & Payloads**: Internal service result dictionary (`status`, `blockers`, `warnings`).
- **Concurrency & Idempotency**: Validation lock prevents concurrent duplicate runs.
- **Audit Logging & Telemetry**: Event `AGENT_VALIDATION_COMPLETED` logged to `audit_logs/{logId}`.

###### Business Logic
- **Actor Eligibility**: Product Launch Agent execution context.
- **Business Domain Rules**: Validation failure MUST stop publishing until resolved (§5). Real errors preserved without suppression (§16).
- **State Machine Transitions**: `DRAFT` -> `VALIDATING` -> `READY_FOR_REVIEW` or `VALIDATION_FAILED`.
- **Workflow Dependencies**: Ingest -> Validate -> Create -> Media -> Verify -> Report (§5, §15).
- **Data Integrity Rules**: Validation results stored in Firestore `products/{productId}` (§9).
- **Business Failure Handling**: Fails to `VALIDATION_FAILED` state; logs specific blocker list (§6, §16).

###### Post-Conditions
- **Successful Post-Conditions**: Validation passed; audit report saved in Firestore; state set to `READY_FOR_REVIEW`.
- **Failure Post-Conditions**: State set to `VALIDATION_FAILED`; blocker list saved in Firestore.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-AGT-01.1: Agent validates required fields, structure, pricing/SKU consistency, media formats, duplicates, and conflicts (§5, §18).
  - AC-AGT-01.2: Validation failure halts workflow and displays exact failed stage and error details (§5, §15, §16).

###### Edge / Negative Test Matrix
- Duplicate SKU detection halts validation and sets state to `VALIDATION_FAILED`.

###### Completion List (Definition of Done)
- Validation engine integrated into pipeline and UI stage display verified.

---

##### Feature: Shopify Product Creation & Media Sync

###### Feature ID & Title
FEAT-AGT-02: Shopify Product Creation & Media Sync

###### Roles
Product Launch Agent (Automated Pipeline)

###### Status
Active Specification

###### Workflow & Production Rules
1. Triggered ONLY after explicit human approval (`approval_status == "APPROVED"`) (§4, §12).
2. Agent prepares GraphQL/REST payload targeting Shopify Admin API (`kinq5t-q5.myshopify.com`), creating/updating Shopify product strictly with initial `status = "draft"` and `template_suffix = "workshop"` (§5, §8).
3. Agent uploads images and videos via Shopify 3-phase GraphQL staged uploads (`stagedUploadsCreate` -> HTTP upload -> `productCreate`/`productUpdate`) (`shopify_client.py`, `shopify_media_service.py`) (§5, §8).
4. Reuses theme templates (`templates/product.workshop.json`), preserves store conventions, and prevents duplicate creation (§8, §18).
5. Media failures MUST show real error (e.g. HTTP 429) and MUST NOT degrade into generic errors like `'NoneType' object has no attribute 'state'` (§5, §16).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Product Launch Agent (Executer), Shopify REST/GraphQL APIs (Target).
- **Access / Entry Point**: Triggered by Firestore state transition to `APPROVED`.

###### Pre-Conditions
- **User Preconditions**: System service context with valid Shopify API credentials. Traceable Approve event exists (§12).
- **Data Preconditions**: Approved product document in Firestore.
- **System Preconditions**: `shopify_client.py` and `services/shopify_media_service.py` active.
- **Workflow Preconditions**: State is `APPROVED` / `PUBLISHING`. `approval_status == "APPROVED"`.
- **UI Preconditions**: Agent status widget showing `✓ Create`, `⟳ Media` (§15).

###### Client-Side Acceptance
- **Valid Input Testing**: UI progress indicator displays stage progression (`✓ Create`, `✓ Media`) (§15).
- **Invalid Input Testing**: Media failure displays `✗ Media` with exact HTTP status message (§15, §16).
- **Special-Character Testing**: Body HTML, title, tags, and metafields transmitted with UTF-8 encoding.
- **Boundary Testing**: High resolution video upload handles timeout parameters cleanly.
- **UI Behavior & Visual State**: Real-time stage indicators reflect exact failed stage (§15).
- **Interaction & Stress Testing**: Resuming after media retry re-runs upload without creating duplicate Shopify products.
- **Client-Side Security**: Shopify access tokens kept secure server-side (§17).

###### Server-Side Acceptance
- **API Request Validation**: Validates Shopify REST/GraphQL payload schemas.
- **Authentication & Session Integrity**: Secure server-side Shopify token authorization (§17).
- **Tenant Isolation & Scoping**: Store scoped.
- **Database Integrity & Constraints**: Saves `shopify_product_id`, `shopify_variant_id`, and `shopify_url` to Firestore `products/{productId}`.
- **API Response Codes & Payloads**: 201 Created / 200 OK from Shopify APIs.
- **Concurrency & Idempotency**: Prevents duplicate creation using title/SKU search before creation (§8, §18).
- **Audit Logging & Telemetry**: Events `SHOPIFY_PRODUCT_CREATED` and `SHOPIFY_MEDIA_UPLOADED` logged to audit log.

###### Business Logic
- **Actor Eligibility**: Product Launch Agent. Execution BLOCKED if `approval_status != "APPROVED"` (§12).
- **Business Domain Rules**: Products remain protected as `DRAFT` until publishing conditions satisfied (§5). Media failure MUST preserve real error message and stage indicator (`Media`) without generic degradation (§5, §16).
- **State Machine Transitions**: `APPROVED` -> `PUBLISHING` -> `PUBLISHED` (or `PUBLISH_FAILED` / `MEDIA_FAILED`).
- **Workflow Dependencies**: Requires prior human approval (§4, §12).
- **Data Integrity Rules**: Shopify product ID and URL saved back to Firestore (§8, §9).
- **Business Failure Handling**: On media error, state becomes `MEDIA_FAILED`; logs real HTTP error (e.g. `Shopify staged upload failed: HTTP 429 – Resource Exhausted`) (§16).

###### Post-Conditions
- **Successful Post-Conditions**: Product created/updated on Shopify; media attached; IDs saved in Firestore.
- **Failure Post-Conditions**: State set to `PUBLISH_FAILED` or `MEDIA_FAILED`; real error saved in Firestore.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-AGT-02.1: Agent creates/updates Shopify product and uploads media ONLY after approval (§4, §5, §12).
  - AC-AGT-02.2: Media upload failures display real errors (`Stage: Media`) without `NoneType` crashes (§5, §16).
  - AC-AGT-02.3: Shopify product IDs, handles, and URLs synchronized with Firestore (§8, §9).

###### Edge / Negative Test Matrix
- Rate-limit HTTP 429 from Shopify API surfaces `Stage: Media, Error: HTTP 429` in UI without crashing backend loop.

###### Completion List (Definition of Done)
- Shopify product creation and media sync connected.
- Real error propagation verified (§16).

---

##### Feature: Listing Verification & Firestore Reporting

###### Feature ID & Title
FEAT-AGT-03: Listing Verification & Firestore Reporting

###### Roles
Product Launch Agent (Automated Pipeline)

###### Status
Active Specification

###### Workflow & Production Rules
1. After Shopify product creation and media upload, Agent verifies the draft listing (§5, §8).
2. Verification checks Shopify product information, media, status, product ID, and storefront URL (`shop.kiddypi.com`) (§5, §8).
3. Live publishing (`status = "active"`) requires a separate explicit human publish trigger; approval alone retains product as DRAFT until publish command is received.
4. Agent writes full status, Shopify ID/URL, media status, verification report, and workflow history into Firestore (`workflow/{workflowId}` and `audit_logs/{logId}`) (§5, §9, §13).
5. State transitions to `PUBLISHED` (or `VERIFICATION_FAILED`).
6. **External Integration Boundary:** Agentic BOSS orchestration is recognized strictly as a planned external integration boundary; local system code remains independent and isolated.

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Product Launch Agent (Verification worker), Firestore (Report storage).
- **Access / Entry Point**: Automatic pipeline trigger post media upload.

###### Pre-Conditions
- **User Preconditions**: System service context.
- **Data Preconditions**: `shopify_product_id` present.
- **System Preconditions**: Verification client and Firestore sync service active.
- **Workflow Preconditions**: Creation and media steps completed (`✓ Create`, `✓ Media`).
- **UI Preconditions**: Agent status widget showing `⟳ Verify` -> `✓ Report` (§15).

###### Client-Side Acceptance
- **Valid Input Testing**: UI shows all steps checked (`✓ Ingest`, `✓ Validate`, `✓ Create`, `✓ Media`, `✓ Verify`, `✓ Report`) and displays live Shopify product link (§15).
- **Invalid Input Testing**: Verification failure displays red `✗ Verify` step icon (§15).
- **Special-Character Testing**: Shopify URL formatted cleanly as clickable link.
- **Boundary Testing**: All variants and media verified against expected counts.
- **UI Behavior & Visual State**: Status updates to green `PUBLISHED` badge (§6).
- **Interaction & Stress Testing**: Viewing historical reports loads complete verification log from Firestore.
- **Client-Side Security**: Access tokens hidden from UI output.

###### Server-Side Acceptance
- **API Request Validation**: Verification rule check payload.
- **Authentication & Session Integrity**: System service authorization.
- **Tenant Isolation & Scoping**: Store scoped.
- **Database Integrity & Constraints**: Updates Firestore `products/{productId}` with `verification_status: "PASSED"`, `workflow_state: "PUBLISHED"`, `published_at: timestamp`.
- **API Response Codes & Payloads**: 200 OK.
- **Concurrency & Idempotency**: Atomic state write.
- **Audit Logging & Telemetry**: Event `PRODUCT_PUBLISHED` written to `audit_logs/{logId}` (§13).

###### Business Logic
- **Actor Eligibility**: Product Launch Agent.
- **Business Domain Rules**: Verifies live Shopify product data against requirement payload (§5, §8). State model MUST live in Firestore as durable system of record surviving server restarts (§6, §9).
- **State Machine Transitions**: `PUBLISHING` -> `PUBLISHED` (or `VERIFICATION_FAILED`).
- **Workflow Dependencies**: Requires completed creation and media upload steps.
- **Data Integrity Rules**: In-memory dict (`active_sessions`) is execution cache only; Firestore is system of record (§6, §9).
- **Business Failure Handling**: Mismatches mark state `VERIFICATION_FAILED` and generate report entry.

###### Post-Conditions
- **Successful Post-Conditions**: Listing verified; state set to `PUBLISHED` in Firestore; live store URL available.
- **Failure Post-Conditions**: State set to `VERIFICATION_FAILED`; error details saved in Firestore.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-AGT-03.1: Agent verifies live Shopify product details, media, status, ID, and URL (§5, §8).
  - AC-AGT-03.2: Workflow state and verification report persisted in Firestore surviving server restarts (§6, §9).

###### Edge / Negative Test Matrix
- Mismatch between expected variant price and live Shopify price flags verification alert in report.

###### Completion List (Definition of Done)
- Verification step implemented.
- Firestore durable state persistence verified.

---

## Role: Platform Admin (System Administration)

**Role Overview & Responsibilities:**
- Manage user accounts and role assignments (Approver, Catalog Admin) (§2).
- View full audit log across all products (§2).
- View full technical error details (stack traces, infrastructure errors) that Lakshmi and Sandeep should not have to see (§2, §16).

### Module: Platform Administration & Security

#### Feature Set: Access Control & Technical Observability

##### Feature: User & Role Administration

###### Feature ID & Title
FEAT-ADM-01: User & Role Administration

###### Roles
Platform Admin (System Administration)

###### Status
Active Specification

###### Workflow & Production Rules
1. Platform Admin logs into application.
2. Admin manages user assignments for Sandeep (Approver) and Lakshmi (Catalog Admin) roles in Firestore `users/{userId}` (§2, §9).
3. System enforces role-based access control (RBAC) across all frontend views and backend API endpoints (§11, §12).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Platform Admin (Manager), Lakshmi / Sandeep (Role Subjects).
- **Access / Entry Point**: Admin Portal -> User Management (`/admin/users`).

###### Pre-Conditions
- **User Preconditions**: Authenticated with `platform_admin` role.
- **Data Preconditions**: Firebase Auth users existing.
- **System Preconditions**: Firebase Admin SDK active.
- **Workflow Preconditions**: Admin session active.
- **UI Preconditions**: User management interface rendered.

###### Client-Side Acceptance
- **Valid Input Testing**: Role assignment toggle updates user role and refreshes permissions.
- **Invalid Input Testing**: Assigning invalid role string rejected.
- **Special-Character Testing**: User emails handled cleanly.
- **Boundary Testing**: Multi-user role edits.
- **UI Behavior & Visual State**: Role badges (`Catalog Admin`, `Approver`, `Platform Admin`) displayed.
- **Interaction & Stress Testing**: Role changes take effect on user's next API request.
- **Client-Side Security**: Admin controls hidden from non-admin users (§12).

###### Server-Side Acceptance
- **API Request Validation**: Payload validated against allowed role enum (`catalog_admin`, `approver`, `platform_admin`).
- **Authentication & Session Integrity**: Verifies caller has `platform_admin` claim.
- **Tenant Isolation & Scoping**: Single-tenant platform directory.
- **Database Integrity & Constraints**: Updates `users/{userId}` document in Firestore.
- **API Response Codes & Payloads**: 200 OK.
- **Concurrency & Idempotency**: Atomic user role write.
- **Audit Logging & Telemetry**: Event `USER_ROLE_UPDATED` written to `audit_logs/{logId}`.

###### Business Logic
- **Actor Eligibility**: Only Platform Admin role.
- **Business Domain Rules**: Server-side role checks MUST enforce permissions for every endpoint (§12).
- **State Machine Transitions**: N/A.
- **Workflow Dependencies**: User role dictates dashboard routing (§11) and permission checks (§12).
- **Data Integrity Rules**: User roles stored in Firestore `users/{userId}` (§9).
- **Business Failure Handling**: Unauthorized user receives 403 Forbidden.

###### Post-Conditions
- **Successful Post-Conditions**: User role updated in Firestore and custom claims.
- **Failure Post-Conditions**: Role remains unchanged; 403/500 error returned.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-ADM-01.1: Platform Admin can manage user role assignments for Lakshmi and Sandeep (§2).
  - AC-ADM-01.2: Server-side RBAC enforces permission boundaries on all API endpoints (§12).

###### Edge / Negative Test Matrix
- Lakshmi attempting to post to `/api/admin/roles` receives 403 Forbidden.

###### Completion List (Definition of Done)
- Role management UI and RBAC authorization middleware implemented.

---

##### Feature: Technical Audit Logging & System Error Visibility

###### Feature ID & Title
FEAT-ADM-02: Technical Audit Logging & System Error Visibility

###### Roles
Platform Admin (System Administration)

###### Status
Active Specification

###### Workflow & Production Rules
1. System records immutable audit logs for all important actions: created/edited, submitted, reviewed, changes requested, approved, agent started, Shopify product created, media uploaded, verified, published (§13).
2. Each log entry contains user/agent, action, timestamp, product, previous state, and new state (§13).
3. System shows human-readable messages and stage indicators to Sandeep/Lakshmi, and full technical detail (stack traces, infra errors) ONLY to Platform Admin (§2, §16).

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Platform Admin (Full log & stack trace viewer), Sandeep/Lakshmi (Sanitized error viewers), System (Audit logger).
- **Access / Entry Point**: Admin Portal -> System Audit Logs (`/admin/logs`) / Technical Error Modal.

###### Pre-Conditions
- **User Preconditions**: Authenticated user.
- **Data Preconditions**: Firestore `audit_logs` collection populated.
- **System Preconditions**: Centralized logging middleware active.
- **Workflow Preconditions**: Action triggered.
- **UI Preconditions**: Audit log viewer or error modal rendered.

###### Client-Side Acceptance
- **Valid Input Testing**: Filtering logs by user, action, timestamp, product ID, or state delta.
- **Invalid Input Testing**: N/A.
- **Special-Character Testing**: Stack traces and error text formatted cleanly in code block container.
- **Boundary Testing**: High-volume log listing paginated cleanly.
- **UI Behavior & Visual State**: Full technical stack trace toggle visible ONLY to Platform Admin (§2, §16).
- **Interaction & Stress Testing**: Real-time log streaming renders smoothly.
- **Client-Side Security**: Stack traces hidden from Lakshmi and Sandeep client UIs (§2, §16).

###### Server-Side Acceptance
- **API Request Validation**: Audit log filter parameters validated.
- **Authentication & Session Integrity**: Verifies token; filters stack trace data unless requester is `platform_admin`.
- **Tenant Isolation & Scoping**: Store scoped log query.
- **Database Integrity & Constraints**: Writes immutable log document to Firestore `audit_logs/{logId}`.
- **API Response Codes & Payloads**: 200 OK with log entries array.
- **Concurrency & Idempotency**: Async non-blocking log writes.
- **Audit Logging & Telemetry**: Self-documenting telemetry.

###### Business Logic
- **Actor Eligibility**: Platform Admin accesses technical stack traces; Lakshmi/Sandeep access sanitized messages (§2, §16).
- **Business Domain Rules**: Every state transition MUST be recorded (§6, §13). Errors MUST preserve real technical detail and NEVER suppress exceptions (§16).
- **State Machine Transitions**: N/A.
- **Workflow Dependencies**: Executed on every lifecycle state event (§13).
- **Data Integrity Rules**: Audit logs stored in Firestore `audit_logs/{logId}` as durable record (§9, §13).
- **Business Failure Handling**: Logging error falls back to standard console output without breaking primary transaction.

###### Post-Conditions
- **Successful Post-Conditions**: Audit log entry written to Firestore; displayed in Admin audit log viewer.
- **Failure Post-Conditions**: Fallback console log created if Firestore log write fails.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-ADM-02.1: Immutable audit log records user/agent, action, timestamp, product ID, previous state, and new state (§13).
  - AC-ADM-02.2: Full technical error details and stack traces shown ONLY to Platform Admin (§2, §16).
  - AC-ADM-02.3: Sandeep and Lakshmi view human-readable messages and stage indicators (§2, §16).

###### Edge / Negative Test Matrix
- Lakshmi viewing a media upload failure sees `Stage: Media, Error: Staged upload failed (HTTP 429)`, while Platform Admin sees full Python stack trace and request headers.

###### Completion List (Definition of Done)
- Audit log service, Firestore collection, and role-based error detail UI verified.

---

## Role: Workshop Creation / Setup Agent (Automated Workshop Pipeline)

**Role Overview & Responsibilities:**
- Ingest raw workshop specifications, date, time, duration, venue, age group, pricing, sales email, topics, media (hero, gallery, instructor photo, video, brochure PDF, registration QR), content (learning outcomes, highlights, projects/activities, journey timeline), instructor details (name, role, bio, photo), registration CTA parameters (URL, button text, seats, deadline, contact email, contact phone), and input assets.
- Validate and ingest workshop input cleanly into `WorkshopInput` and durable workflow state.
- Extract structured metadata, generate website presentation HTML, and generate reusable KiddyPi workshop Liquid sections and JSON templates (`templates/product.workshop.json`).
- Search existing Shopify products using exact SKU and normalized title similarity matching to prevent duplicate creation.
- Hold execution at the `PENDING_APPROVAL` human boundary until explicit human sign-off (Sandeep).
- Upon approval, create or update the Shopify product in `DRAFT` status with `template_suffix = "workshop"`.
- Trigger the 53-rule Product Validation Agent.
- Transition to `LAUNCH_READY` while preserving Shopify `DRAFT` status when all pre-publish blocker rules pass (`blockers_failed == 0`).
- Execute explicit, controlled publication to `ACTIVE` status ONLY upon explicit publication request.

### Module: Workshop Setup & Lifecycle Management

#### Feature Set: Workshop Setup & Presentation Preparation

##### Feature: Workshop Ingestion, Asset Check & Presentation Preparation

###### Feature ID & Title
FEAT-WS-01: Workshop Ingestion, Asset Check & Presentation Preparation

###### Roles
Workshop Creation / Setup Agent (Automated Pipeline), Catalog Admin (Lakshmi)

###### Status
Active Specification

###### Workflow & Production Rules
1. Workshop Creation Agent ingests raw input parameters (name, description, date, time, duration, venue, age_group, price, sales_email, topics, poster_path, video_url).
2. Input is validated; if name is missing, state transitions to `INVALID_WORKSHOP_INPUT`.
3. Agent extracts structured information from optional input folder attachments.
4. Agent verifies local/remote poster and video assets.
5. Agent formats website presentation content (`KiddypiWebsiteContent`) independently from Shopify product representation.
6. Agent executes Design Template Replication Engine generating `generated_liquid_section` and `generated_json_template` (`templates/product.workshop.json`).
7. Workflow transitions state to `CONTENT_PREPARED`.

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Catalog Admin (Input submitter), Workshop Setup Agent (Automated ingest/generator), System (State manager).
- **Access / Entry Point**: API Endpoint `/api/workshops/setup` / Workshop Workflow Runner (`run_workshop_workflow_session`).

###### Pre-Conditions
- **User Preconditions**: Authenticated request with Catalog Admin or API authority.
- **Data Preconditions**: Valid workshop input schema.
- **System Preconditions**: Workshop Service and ADK Workflow initialized.
- **Workflow Preconditions**: Workshop session started.
- **UI Preconditions**: Workshop creation form rendered.

###### Client-Side Acceptance
- **Valid Input Testing**: Accepts workshop title, date, time, duration, venue, age range (8-12), INR price (₹999), and topics list.
- **Invalid Input Testing**: Empty workshop title triggers validation rejection with `INVALID_WORKSHOP_INPUT`.
- **Special-Character Testing**: Unicode symbols (₹, –, :) and special venue addresses handled safely.
- **Boundary Testing**: Large description text and multiple topics handled without truncation.
- **UI Behavior & Visual State**: Progress indicator displays stage transitions: `DRAFT` -> `UNDERSTANDING` -> `ASSET_CHECK` -> `CONTENT_PREPARED`.
- **Interaction & Stress Testing**: Concurrent setup requests isolated by unique `workshop_id`.
- **Client-Side Security**: Input sanitized to prevent script injection.

###### Server-Side Acceptance
- **API Request Validation**: Pydantic `WorkshopInput` schema validation enforced.
- **Authentication & Session Integrity**: Bearer auth / API session token verified.
- **Tenant Isolation & Scoping**: Workshop state scoped by `workshop_id`.
- **Database Integrity & Constraints**: Durable state recorded in Firestore / local workflow state.
- **API Response Codes & Payloads**: 200 OK with `WorkshopWorkflowState`.
- **Concurrency & Idempotency**: `workshop_id` slugification ensures consistent state keying.
- **Audit Logging & Telemetry**: Event `WORKSHOP_SETUP_STARTED` written to audit logs.

###### Business Logic
- **Actor Eligibility**: Workshop Setup Agent execution context.
- **Business Domain Rules**: Workshop content must be formatted cleanly; liquid sections and json templates must reuse KiddyPi workshop design (`templates/product.workshop.json`).
- **State Machine Transitions**: `DRAFT` -> `UNDERSTANDING` -> `ASSET_CHECK` -> `CONTENT_PREPARED`.
- **Workflow Dependencies**: Must complete before Shopify payload preparation and approval boundary.
- **Data Integrity Rules**: Presentation content kept distinct from Shopify draft payload.
- **Business Failure Handling**: Missing optional assets log warnings without breaking pipeline.

###### Post-Conditions
- **Successful Post-Conditions**: Presentation content, Liquid section, and JSON template generated; state set to `CONTENT_PREPARED`.
- **Failure Post-Conditions**: State set to `INVALID_WORKSHOP_INPUT` or `MISSING_REQUIRED_ASSET`.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-WS-01.1: Workshop input ingested and validated cleanly.
  - AC-WS-01.2: Website presentation HTML, Liquid section, and JSON template generated reusing KiddyPi theme (`template_suffix = "workshop"`).

###### Edge / Negative Test Matrix
- Attempting setup without a workshop name returns 400 Bad Request with `INVALID_WORKSHOP_INPUT`.

###### Completion List (Definition of Done)
- Ingestion and content preparation logic implemented and verified via unit tests.

---

##### Feature: Product Search & Draft Shopify Payload Building

###### Feature ID & Title
FEAT-WS-02: Product Search & Draft Shopify Payload Building

###### Roles
Workshop Creation / Setup Agent (Automated Pipeline)

###### Status
Active Specification

###### Workflow & Production Rules
1. Agent queries Shopify store for existing product using exact SKU and normalized title Jaccard similarity.
2. If single match with confidence >= 0.90 found, action set to `UPDATE` with `existing_product_id`.
3. If multiple weak matches found, state transitions to `AMBIGUOUS_PRODUCT_MATCH` and requires human resolution.
4. If zero matches found, action set to `CREATE`.
5. Agent builds proposed Shopify payload strictly with `status = "draft"` and `template_suffix = "workshop"`.
6. Agent prepares registration configuration (`RegistrationConfig`).
7. Execution halts at `PENDING_APPROVAL` human boundary.

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Workshop Setup Agent (Worker), Shopify Admin API (Lookup target), Sandeep (Approver at boundary).
- **Access / Entry Point**: Workshop Workflow Runner -> `search_existing_shopify_product` & `prepare_shopify_payload`.

###### Pre-Conditions
- **User Preconditions**: System execution context.
- **Data Preconditions**: `CONTENT_PREPARED` state active.
- **System Preconditions**: Shopify API client initialized.
- **Workflow Preconditions**: Content preparation complete.
- **UI Preconditions**: N/A.

###### Client-Side Acceptance
- **Valid Input Testing**: Verified SKU and title search payloads.
- **Invalid Input Testing**: N/A.
- **Special-Character Testing**: Title slugification strips special characters safely for handle matching.
- **Boundary Testing**: Ambiguous matches stop execution safely.
- **UI Behavior & Visual State**: UI status displays `PENDING_APPROVAL`.
- **Interaction & Stress Testing**: Idempotent re-runs update existing draft payload without creating duplicate products.
- **Client-Side Security**: Shopify API credentials protected server-side.

###### Server-Side Acceptance
- **API Request Validation**: Payload fields match `ShopifyWorkshopPayload` model.
- **Authentication & Session Integrity**: Verified backend authentication.
- **Tenant Isolation & Scoping**: Single-store scoping.
- **Database Integrity & Constraints**: Proposed payload saved in state.
- **API Response Codes & Payloads**: 200 OK.
- **Concurrency & Idempotency**: Duplicate detection prevents duplicate product creation.
- **Audit Logging & Telemetry**: Event `SHOPIFY_PAYLOAD_PREPARED` written to audit log.

###### Business Logic
- **Actor Eligibility**: Workshop Setup Agent.
- **Business Domain Rules**: Proposed Shopify payload MUST specify `status = "draft"` and `template_suffix = "workshop"`. Direct publication at this stage is strictly FORBIDDEN.
- **State Machine Transitions**: `CONTENT_PREPARED` -> `SHOPIFY_PREPARED` -> `REGISTRATION_PREPARED` -> `PENDING_APPROVAL`.
- **Workflow Dependencies**: Halts at `PENDING_APPROVAL` until human sign-off.
- **Data Integrity Rules**: `status` MUST be `"draft"`.
- **Business Failure Handling**: Shopify lookup failure defaults safely to `CREATE` or flags error.

###### Post-Conditions
- **Successful Post-Conditions**: Proposed Shopify draft payload built; state set to `PENDING_APPROVAL`.
- **Failure Post-Conditions**: State set to `AMBIGUOUS_PRODUCT_MATCH` or `SHOPIFY_API_ERROR`.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-WS-02.1: Duplicate detection matches existing products by SKU and title.
  - AC-WS-02.2: Proposed payload enforces `status = "draft"` and `template_suffix = "workshop"`.
  - AC-WS-02.3: Pipeline pauses at `PENDING_APPROVAL` human boundary.

###### Edge / Negative Test Matrix
- Multiple matching products halt pipeline in `AMBIGUOUS_PRODUCT_MATCH` state.

###### Completion List (Definition of Done)
- Search, payload building, and approval boundary pausing verified.

---

##### Feature: Human Approval, Controlled Draft Creation, 53-Rule Validation & Explicit Publication

###### Feature ID & Title
FEAT-WS-03: Human Approval, Controlled Draft Creation, 53-Rule Validation & Explicit Publication

###### Roles
Product Decision Maker (Sandeep), Workshop Creation / Setup Agent (Automated Pipeline)

###### Status
Active Specification

###### Workflow & Production Rules
1. Sandeep reviews proposed workshop content, pricing, schedule, and metadata.
2. Sandeep submits explicit approval (`approve_workshop`). State transitions to `APPROVED`.
3. Unauthorized creation/publication attempts without approval are strictly rejected with `PermissionError`.
4. Workshop Agent executes `create_or_update_shopify_product`, creating/updating product on Shopify strictly with `status = "draft"`.
5. Agent triggers 53-rule Product Validation Agent.
6. Validation checks execute with lifecycle-aware pre-publish evaluation.
7. If 0 blockers fail, state transitions to `LAUNCH_READY` while Shopify status remains `draft`.
8. Explicit publish request (`publish_workshop_product`) updates Shopify product status `draft` -> `active` and state -> `PUBLISHED`.

###### Actors & Access
- **Actor Matrix (Actors & Usage)**: Sandeep (Mandatory Approver), Workshop Setup Agent (Executor), Product Validation Agent (Validator).
- **Access / Entry Point**: Review Dashboard -> Approve Button (`/api/workshops/{id}/approve`) / Publish Button (`/api/workshops/{id}/publish`).

###### Pre-Conditions
- **User Preconditions**: Authenticated as Sandeep / Product Decision Maker.
- **Data Preconditions**: Workshop in `PENDING_APPROVAL` or `LAUNCH_READY` state.
- **System Preconditions**: Shopify Client and Unified Validation Engine active.
- **Workflow Preconditions**: Approval record present in state for draft creation.
- **UI Preconditions**: Approve and Publish buttons rendered in reviewer UI.

###### Client-Side Acceptance
- **Valid Input Testing**: Approver email and timestamp passed in approval request.
- **Invalid Input Testing**: Non-approver attempting approval receives HTTP 403.
- **Special-Character Testing**: Approver comments and emails handled cleanly.
- **Boundary Testing**: Publish button disabled until state reaches `LAUNCH_READY`.
- **UI Behavior & Visual State**: Status transitions: `PENDING_APPROVAL` -> `APPROVED` -> `CREATING_OR_UPDATING` -> `VALIDATING` -> `LAUNCH_READY` -> `PUBLISHED`.
- **Interaction & Stress Testing**: Idempotent approval calls do not re-create duplicate Shopify products.
- **Client-Side Security**: RBAC checks enforce approver role.

###### Server-Side Acceptance
- **API Request Validation**: Validates approval payload and approver token.
- **Authentication & Session Integrity**: Verifies approver identity in Firestore / Auth session.
- **Tenant Isolation & Scoping**: Store scoped publishing.
- **Database Integrity & Constraints**: Writes audit log for approval, draft creation, validation, and publication.
- **API Response Codes & Payloads**: 200 OK on success; 403 Forbidden on unauthorized attempt; 400 Bad Request if publish attempted before `LAUNCH_READY`.
- **Concurrency & Idempotency**: Atomic state updates prevent double-publishing.
- **Audit Logging & Telemetry**: Events `WORKSHOP_APPROVED`, `SHOPIFY_DRAFT_CREATED`, `VALIDATION_COMPLETED`, `WORKSHOP_PUBLISHED` written to audit log.

###### Business Logic
- **Actor Eligibility**: Sandeep role required for approval.
- **Business Domain Rules**:
  - Approval MUST NOT automatically publish products.
  - Draft product creation MUST set `status = "draft"`.
  - Passing validation (`blockers_failed == 0`) MUST transition state to `LAUNCH_READY` while preserving `status = "draft"`.
  - Only explicit `publish_workshop_product` invocation moves status from `draft` to `active`.
- **State Machine Transitions**: `PENDING_APPROVAL` -> `APPROVED` -> `CREATING_OR_UPDATING` -> `VALIDATING` -> `LAUNCH_READY` -> `PUBLISHED`.
- **Workflow Dependencies**: Creation requires `APPROVED`; Validation requires Shopify Product ID; Publishing requires `LAUNCH_READY`.
- **Data Integrity Rules**: Shopify `status` remains `"draft"` until explicit publish.
- **Business Failure Handling**: Validation failure with blockers transitions state to `VALIDATION_FAILED` and blocks publication.

###### Post-Conditions
- **Successful Post-Conditions**: Product created as draft, validated as `LAUNCH_READY`, and explicitly published to `ACTIVE` status on Shopify.
- **Failure Post-Conditions**: State set to `PUBLISHING_BLOCKED`, `VALIDATION_FAILED`, or `SHOPIFY_SYNC_FAILED`.

###### Acceptance Matrix
- **Acceptance Criteria (Traceable AC Checklist)**:
  - AC-WS-03.1: Approval required before Shopify product draft creation.
  - AC-WS-03.2: Created product starts in `draft` status with `template_suffix = "workshop"`.
  - AC-WS-03.3: 53-rule validation passes pre-publish draft with 0 blockers, reaching `LAUNCH_READY` while remaining `draft`.
  - AC-WS-03.4: Explicit publish command transitions Shopify product from `draft` to `active`.

###### Edge / Negative Test Matrix
- Attempting to publish a workshop in `VALIDATION_FAILED` state throws `ValueError` and blocks publication.

###### Completion List (Definition of Done)
- Approval boundary, draft creation, 53-rule validation integration, and explicit publishing pipeline verified.
