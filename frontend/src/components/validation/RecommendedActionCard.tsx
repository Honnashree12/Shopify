import React from "react";

interface RecommendedActionProps {
  rank: number;
  checkName: string;
  affectedCount: number;
  isSelected: boolean;
  onSelect: () => void;
}

export const RecommendedActionCard: React.FC<RecommendedActionProps> = ({
  rank,
  checkName,
  affectedCount,
  isSelected,
  onSelect,
}) => {
  const rankStr = rank < 10 ? `0${rank}` : `${rank}`;

  return (
    <div
      onClick={onSelect}
      style={{
        background: isSelected ? "#fef2f2" : "#ffffff",
        border: isSelected ? "1px solid #fecaca" : "1px solid #e2e8f0",
        borderRadius: 8,
        padding: "14px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        cursor: "pointer",
        transition: "all 0.15s ease",
        boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)"
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{
          fontSize: 13,
          fontWeight: 800,
          color: "#94a3b8",
          fontFamily: "monospace",
          width: 24,
          flexShrink: 0
        }}>
          {rankStr}
        </div>

        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
              {checkName}
            </span>
            <span style={{
              background: "#fef2f2",
              color: "#dc2626",
              fontSize: 10,
              fontWeight: 700,
              padding: "1px 6px",
              borderRadius: 4,
              textTransform: "uppercase"
            }}>
              Critical
            </span>
          </div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
            <strong style={{ color: "#dc2626" }}>{affectedCount}</strong> products affected in store catalog
          </div>
        </div>
      </div>

      <button
        style={{
          background: isSelected ? "#dc2626" : "#f1f5f9",
          color: isSelected ? "#ffffff" : "#2563eb",
          border: "none",
          padding: "6px 12px",
          borderRadius: 6,
          fontSize: 11.5,
          fontWeight: 600,
          cursor: "pointer",
          whiteSpace: "nowrap"
        }}
      >
        {isSelected ? "Active Filter ✓" : "View affected products →"}
      </button>
    </div>
  );
};
