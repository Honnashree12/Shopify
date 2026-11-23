import type { PipelineStageId, ProductLaunchState } from "./types";

export interface StageDef {
  id: PipelineStageId;
  index: number; // 1-based, matches backend failed_stage semantics
  label: string;
  detail: string;
}

export const PIPELINE_STAGES: StageDef[] = [
  { id: "ingest", index: 1, label: "Ingest", detail: "extract" },
  { id: "validate", index: 2, label: "Validate", detail: "check structure" },
  { id: "create", index: 3, label: "Create", detail: "Shopify basic" },
  { id: "media", index: 4, label: "Media", detail: "staged upload" },
  { id: "verify", index: 5, label: "Verify", detail: "live check" },
  { id: "report", index: 6, label: "Report", detail: "md · json" },
];

export type StageStatus = "done" | "active" | "failed" | "pending" | "skipped";

// Mirrors the real completion signals main.py's own
// _derive_folder_failed_stage() reads from ProductLaunchState — see
// docs/AGENT_WORKFLOW.md. This does not invent new signals; it reads the
// same fields the backend already populates at each stage.
export function deriveStageStatuses(state: ProductLaunchState | undefined): Record<PipelineStageId, StageStatus> {
  const empty: Record<PipelineStageId, StageStatus> = {
    ingest: "pending",
    validate: "pending",
    create: "pending",
    media: "pending",
    verify: "pending",
    report: "pending",
  };
  if (!state) return empty;

  const ingestDone = Boolean(state.manifest);
  const validateDone = state.missing_fields_list !== null && state.missing_fields_list !== undefined
    ? true
    : state.conflicts_list !== null && state.conflicts_list !== undefined;
  const createDone = Boolean(state.shopify_product_id);
  const hasMedia = Boolean((state.detected_images?.length ?? 0) + (state.detected_videos?.length ?? 0));
  const mediaDone = !hasMedia || Boolean(state.shopify_media) || Boolean(state.media_upload_results?.length);
  const verifyDone = Boolean(state.verification_result);
  const reportDone = Boolean(state.markdown_report_path || state.json_report_path) || state.status === "completed";

  const doneMap: Record<PipelineStageId, boolean> = {
    ingest: ingestDone,
    validate: validateDone,
    create: createDone,
    media: mediaDone,
    verify: verifyDone,
    report: reportDone,
  };

  const order: PipelineStageId[] = ["ingest", "validate", "create", "media", "verify", "report"];
  const result = { ...empty };

  let firstNotDone: PipelineStageId | null = null;
  for (const id of order) {
    if (doneMap[id]) {
      result[id] = "done";
    } else {
      firstNotDone = id;
      break;
    }
  }

  if (state.status === "failed") {
    const failedId = state.failed_stage ?? firstNotDone ?? "ingest";
    for (const id of order) result[id] = doneMap[id] ? "done" : "pending";
    result[failedId] = "failed";
  } else if (state.status === "running") {
    // Prefer the backend's authoritative live stage (workflow/progress_tracker.py)
    // over inferring it from which fields happen to be populated -- this is
    // exact rather than a best-effort guess.
    const activeId = state.current_stage ?? firstNotDone;
    if (activeId) result[activeId] = "active";
  } else if (state.status === "awaiting_approval" && firstNotDone) {
    result[firstNotDone] = "active";
  }

  return result;
}

export function statusPillTone(status: ProductLaunchState["status"]): "success" | "warning" | "danger" | "info" | "pending" {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "danger";
    case "awaiting_approval":
      return "warning";
    case "running":
      return "info";
    default:
      return "pending";
  }
}

export function statusLabel(status: ProductLaunchState["status"]): string {
  switch (status) {
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "awaiting_approval":
      return "Awaiting your review";
    case "running":
      return "Agent working";
    default:
      return "Pending";
  }
}

export interface ActivityItem {
  label: string;
  status: "done" | "pending" | "error";
}

// Every line here is a direct read of a real ProductLaunchState field the
// backend already populates at that stage — nothing fabricated. Mirrors the
// "AI Agent" activity list from the previous static/index.html console.
export function deriveActivityFeed(state?: ProductLaunchState): ActivityItem[] {
  if (!state) return [];
  const items: ActivityItem[] = [];

  if (state.manifest) items.push({ label: "Read product folder and extracted fields", status: "done" });
  if (state.missing_fields_list !== null && state.missing_fields_list !== undefined) {
    items.push({
      label:
        state.missing_fields_list.length > 0
          ? `Validated data — ${state.missing_fields_list.length} field(s) missing`
          : "Validated required fields",
      status: state.missing_fields_list.length > 0 ? "error" : "done",
    });
  }
  if (state.duplicate_detected) {
    items.push({ label: `Duplicate detected: "${state.existing_product_title ?? "existing product"}"`, status: "error" });
  }
  if (state.shopify_product_id) {
    items.push({ label: `Created Shopify product #${state.shopify_product_id}`, status: "done" });
  }
  const mediaCount = (state.detected_images?.length ?? 0) + (state.detected_videos?.length ?? 0);
  if (mediaCount > 0) {
    if (state.media_upload_results?.length || state.shopify_media) {
      const failedUploads = (state.media_upload_results ?? []).filter((r) => r.success === false).length;
      items.push({
        label:
          failedUploads > 0
            ? `Uploaded media — ${failedUploads} of ${mediaCount} file(s) failed`
            : `Uploaded ${mediaCount} media file(s)`,
        status: failedUploads > 0 ? "error" : "done",
      });
    }
  }
  if (state.verification_result) {
    const purchasable = (state.verification_result as { purchasable?: boolean }).purchasable;
    items.push({ label: purchasable ? "Verified live Shopify listing" : "Verification found issues with the listing", status: purchasable ? "done" : "error" });
  }
  if (state.markdown_report_path || state.json_report_path) {
    items.push({ label: "Generated launch report", status: "done" });
  }

  if (state.status === "awaiting_approval") {
    items.push({ label: "Waiting for your approval", status: "pending" });
  } else if (state.status === "running") {
    items.push({ label: "Working…", status: "pending" });
  }

  return items;
}
