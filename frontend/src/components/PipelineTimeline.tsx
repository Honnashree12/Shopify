import type { ProductLaunchState } from "../api/types";
import { PIPELINE_STAGES, deriveStageStatuses, type StageStatus } from "../api/pipeline";

const ICONS: Record<StageStatus, string> = {
  done: "✓",
  active: "●",
  failed: "!",
  pending: "○",
  skipped: "—",
};

export function PipelineTimeline({ state }: { state?: ProductLaunchState }) {
  const statuses = deriveStageStatuses(state);

  return (
    <ol className="pipeline-timeline" aria-label="Launch pipeline progress">
      {PIPELINE_STAGES.map((stage) => {
        const st = statuses[stage.id];
        const isAwaiting = st === "active" && state?.status === "awaiting_approval";
        return (
          <li key={stage.id} className={`pipeline-stage pipeline-stage--${st}${isAwaiting ? " pipeline-stage--awaiting" : ""}`}>
            <span className="pipeline-stage__icon" aria-hidden="true">{isAwaiting ? "⚠" : ICONS[st]}</span>
            <span className="pipeline-stage__body">
              <span className="pipeline-stage__index">{String(stage.index).padStart(2, "0")}</span>
              <span className="pipeline-stage__label">{stage.label}</span>
              <span className="pipeline-stage__detail">{stage.detail}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
