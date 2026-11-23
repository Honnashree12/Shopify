// Mirrors state.py's ProductLaunchState. Kept intentionally close to the real
// Pydantic model returned by GET /status/{id} — do not add fields here that
// the backend doesn't actually return.
export interface ProductLaunchState {
  product_name: string;
  raw_description: string;
  price?: number | null;
  category?: string | null;

  generated_description?: string | null;
  seo_metadata?: Record<string, unknown> | null;
  marketing?: Record<string, unknown> | null;
  marketing_assets?: Record<string, unknown> | null;

  image_prompts?: Record<string, string> | null;
  image_paths?: string[] | null;
  shopify_media?: Array<Record<string, unknown>> | null;

  shopify_product?: Record<string, unknown> | null;
  shopify_product_id?: number | null;
  shopify_variant_id?: number | null;
  shopify_url?: string | null;

  verification_result?: Record<string, unknown> | null;

  markdown_report_path?: string | null;
  json_report_path?: string | null;

  status: LaunchStatus;
  approved_to_publish: boolean;
  workshop_id?: string | null;
  product_folder_path?: string | null;
  sku?: string | null;
  inventory_quantity?: number | null;
  product_status?: string | null;
  vendor?: string | null;
  tags?: string[] | null;

  detected_images?: string[] | null;
  detected_videos?: string[] | null;
  media_upload_results?: Array<Record<string, unknown>> | null;
  folder_report?: string | null;
  preview_mode: boolean;
  manifest?: Record<string, unknown> | null;
  conversions?: string[] | null;
  unsupported_media?: Array<Record<string, unknown>> | null;
  missing_fields_list?: string[] | null;
  conflicts_list?: Array<Record<string, unknown>> | null;

  duplicate_detected: boolean;
  existing_product_id?: number | null;
  existing_product_title?: string | null;
  existing_product_url?: string | null;
  duplicate_action: string;
  duplicate_action_resolved?: string | null;

  firebase_product_id?: string | null;
  firebase_sync_status?: string | null;
  firebase_media_paths?: string[] | null;
  design_system_version?: number | null;
  selected_shopify_template?: string | null;

  failed_stage?: PipelineStageId | null;
  // Live, backend-authoritative "which stage is executing right now" while
  // status === "running" -- see workflow/progress_tracker.py. Populated on
  // every GET /status/{id} read, not persisted. Prefer this over inferring
  // the active stage from field presence when it's available.
  current_stage?: PipelineStageId | null;
  product_version: number;
  approved_at_version?: number | null;
  errors: Record<string, string>;
  source?: "folder" | "campaign" | null;
}

export type LaunchStatus =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed";

export type PipelineStageId =
  | "ingest"
  | "validate"
  | "create"
  | "media"
  | "verify"
  | "report";

// GET /api/launches list item — see docs/API_CONTRACT.md for the additive
// endpoint this shape comes from.
export interface LaunchSummary {
  session_id: string;
  product_name: string;
  status: LaunchStatus;
  failed_stage?: PipelineStageId | null;
  preview_mode: boolean;
  created_at?: string | null;
  source: "folder" | "campaign";
}
