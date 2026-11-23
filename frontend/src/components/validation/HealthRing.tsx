import React from "react";

interface HealthRingProps {
  rate: number;
  passed: number;
  total: number;
  failed: number;
}

export const HealthRing: React.FC<HealthRingProps> = ({ rate, passed, total, failed }) => {
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (circumference * Math.max(0, Math.min(100, rate))) / 100;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
      <div style={{ position: "relative", width: 100, height: 100, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <svg width="100" height="100" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={radius} fill="transparent" stroke="#f1f5f9" strokeWidth="8" />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="transparent"
            stroke="#2563eb"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
            style={{ transition: "stroke-dashoffset 0.8s ease" }}
          />
        </svg>
        <div style={{ position: "absolute", textAlign: "center" }}>
          <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", letterSpacing: "-0.02em" }}>
            {rate.toFixed(1)}%
          </div>
          <div style={{ fontSize: 9, color: "#64748b", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em" }}>Compliance</div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
          Blocker Compliance
        </div>
        <div style={{ fontSize: 12, color: "#64748b" }}>
          <strong style={{ color: "#16a34a" }}>{passed}</strong> passed / <strong style={{ color: "#0f172a" }}>{total}</strong> total evaluations
        </div>
        <div style={{ fontSize: 11, color: "#dc2626", fontWeight: 600 }}>
          {failed} blocker checks failing storewide
        </div>
      </div>
    </div>
  );
};
