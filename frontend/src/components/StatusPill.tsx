import type { LaunchStatus } from "../api/types";
import { statusLabel, statusPillTone } from "../api/pipeline";

export function StatusPill({ status }: { status: LaunchStatus }) {
  const tone = statusPillTone(status);
  return (
    <span className={`pill pill-${tone}`}>
      <span className="pill-dot" aria-hidden="true" />
      {statusLabel(status)}
    </span>
  );
}
