import React from "react";

interface FailureBreakdownProps {
  sectionFailures: Record<string, number>;
  selectedSection: string;
  onSelectSection: (section: string) => void;
}

export const FailureBreakdown: React.FC<FailureBreakdownProps> = ({
  sectionFailures,
  selectedSection,
  onSelectSection,
}) => {
  const maxCount = Math.max(...Object.values(sectionFailures), 1);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {Object.entries(sectionFailures)
        .sort((a, b) => b[1] - a[1])
        .map(([sec, count]) => {
          const percentage = Math.round((count / maxCount) * 100);
          const isSelected = selectedSection === sec;

          return (
            <div
              key={sec}
              onClick={() => onSelectSection(isSelected ? "All" : sec)}
              title={`${count} failed checks in ${sec}. Click to filter.`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                cursor: "pointer",
                padding: "5px 8px",
                borderRadius: 6,
                background: isSelected ? "#eff6ff" : "transparent",
                border: isSelected ? "1px solid #bfdbfe" : "1px solid transparent",
                transition: "all 0.15s ease"
              }}
            >
              <div style={{
                width: 170,
                fontSize: 12,
                fontWeight: 600,
                color: isSelected ? "#2563eb" : "#334155",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis"
              }}>
                {sec}
              </div>

              <div style={{ flex: 1, height: 6, background: "#f1f5f9", borderRadius: 3, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${percentage}%`,
                    background: count > 50 ? "#dc2626" : count > 20 ? "#d97706" : count > 0 ? "#2563eb" : "#16a34a",
                    borderRadius: 3,
                    transition: "width 0.4s ease"
                  }}
                />
              </div>

              <div style={{
                width: 32,
                textAlign: "right",
                fontSize: 12,
                fontWeight: 700,
                color: count > 0 ? "#dc2626" : "#16a34a"
              }}>
                {count}
              </div>
            </div>
          );
        })}
    </div>
  );
};
