import React, { useEffect } from "react";

interface EvidenceModalProps {
  title: string;
  checkName: string;
  authority: string;
  result: string;
  explanation: string;
  imageUrl: string | null;
  viewport?: string;
  onClose: () => void;
}

export const EvidenceModal: React.FC<EvidenceModalProps> = ({
  title,
  checkName,
  authority,
  result,
  explanation,
  imageUrl,
  viewport = "390 × 844",
  onClose,
}) => {
  const [imageError, setImageError] = React.useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(15, 23, 42, 0.75)",
        backdropFilter: "blur(4px)",
        zIndex: 10000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#ffffff",
          borderRadius: 8,
          padding: 24,
          maxWidth: 760,
          width: "100%",
          maxHeight: "90vh",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid #e2e8f0", paddingBottom: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: "#9333ea", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                BROWSER VERIFIED EVIDENCE
              </span>
              <span style={{ fontSize: 11, color: "#64748b" }}>· Viewport: {viewport}</span>
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: "4px 0 0", color: "#0f172a" }}>
              {checkName}
            </h3>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{title}</div>
          </div>

          <button
            onClick={onClose}
            aria-label="Close modal"
            style={{ background: "none", border: "none", fontSize: 22, cursor: "pointer", color: "#64748b" }}
          >
            ×
          </button>
        </div>

        <div style={{ fontSize: 12, color: "#475569", background: "#f8fafc", padding: 12, borderRadius: 6, border: "1px solid #e2e8f0" }}>
          <strong>Result:</strong>{" "}
          <span style={{ color: result === "PASS" ? "#16a34a" : "#dc2626", fontWeight: 700 }}>
            {result}
          </span>{" "}
          ({authority}) — {explanation}
        </div>

        {/* Screenshot Container */}
        <div style={{ background: "#0f172a", borderRadius: 6, overflow: "hidden", minHeight: 240, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {imageError || !imageUrl ? (
            <div style={{ color: "#94a3b8", textAlign: "center", padding: 40 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#e2e8f0" }}>Browser evidence unavailable</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>Screenshot evidence image not found or failed to load</div>
            </div>
          ) : (
            <img
              src={imageUrl}
              alt={`Browser verification screenshot for ${checkName}`}
              onError={() => setImageError(true)}
              style={{ width: "100%", height: "auto", maxHeight: 480, objectFit: "contain" }}
            />
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 11, color: "#94a3b8" }}>
            Press <kbd style={{ background: "#f1f5f9", padding: "1px 4px", borderRadius: 3, border: "1px solid #cbd5e1" }}>ESC</kbd> to close
          </div>
          <button
            onClick={onClose}
            style={{ background: "#ffffff", border: "1px solid #cbd5e1", padding: "6px 16px", fontSize: 12, borderRadius: 4, cursor: "pointer", color: "#334155", fontWeight: 600 }}
          >
            Close Evidence
          </button>
        </div>
      </div>
    </div>
  );
};
