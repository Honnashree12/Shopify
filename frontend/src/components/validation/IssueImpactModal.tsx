import React, { useState, useMemo, useEffect } from "react";
import type { AuditedProduct } from "../../pages/Validation";

interface IssueImpactModalProps {
  checkName: string;
  products: AuditedProduct[];
  onClose: () => void;
  onSelectProduct: (product: AuditedProduct) => void;
}

export const IssueImpactModal: React.FC<IssueImpactModalProps> = ({
  checkName,
  products,
  onClose,
  onSelectProduct,
}) => {
  const [filter, setFilter] = useState<"ALL" | "READY" | "BLOCKED">("ALL");

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Clean title for display
  const cleanCheckName = useMemo(() => {
    return checkName.replace(/^\d+\.\s*/, "");
  }, [checkName]);

  // Dynamic analysis across all products for this check
  const analysis = useMemo(() => {
    const affectedList: Array<{
      product: AuditedProduct;
      currentBlockers: number;
      remainingAfterFix: number;
      willBecomeLaunchReady: boolean;
      isBlockerCheck: boolean;
    }> = [];

    products.forEach((p) => {
      const checksObj = p.checks || {};
      
      // Find matching check by key, check_name, or stripped check_name
      const matchedEntry = Object.entries(checksObj).find(([key, val]) => {
        const nameClean = (val.check_name || key).replace(/^\d+\.\s*/, "").toLowerCase();
        const targetClean = cleanCheckName.toLowerCase();
        return key.toLowerCase() === checkName.toLowerCase() ||
               (val.check_name && val.check_name.toLowerCase() === checkName.toLowerCase()) ||
               nameClean === targetClean;
      });

      if (!matchedEntry) return;

      const [_, checkDetail] = matchedEntry;
      const res = checkDetail.final_result || (checkDetail as any).status || "FAIL";
      const isFail = res === "FAIL";

      if (!isFail) return; // Not failing on this product

      // Calculate total failed blockers for this product
      const failedBlockersCount = Object.values(checksObj).filter(
        (c) => c.severity === "Blocker" && (c.final_result === "FAIL" || (c as any).status === "FAIL")
      ).length;

      const isBlocker = checkDetail.severity === "Blocker";
      const remaining = isBlocker ? Math.max(0, failedBlockersCount - 1) : failedBlockersCount;
      const readyIfFixed = isBlocker && remaining === 0;

      affectedList.push({
        product: p,
        currentBlockers: failedBlockersCount,
        remainingAfterFix: remaining,
        willBecomeLaunchReady: readyIfFixed,
        isBlockerCheck: isBlocker,
      });
    });

    const readyCount = affectedList.filter((item) => item.willBecomeLaunchReady).length;
    const blockedCount = affectedList.length - readyCount;

    return {
      affectedList,
      totalAffected: affectedList.length,
      readyCount,
      blockedCount,
    };
  }, [products, checkName, cleanCheckName]);

  const filteredList = useMemo(() => {
    if (filter === "READY") {
      return analysis.affectedList.filter((item) => item.willBecomeLaunchReady);
    }
    if (filter === "BLOCKED") {
      return analysis.affectedList.filter((item) => !item.willBecomeLaunchReady);
    }
    return analysis.affectedList;
  }, [analysis, filter]);

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(15, 23, 42, 0.5)",
        backdropFilter: "blur(4px)",
        zIndex: 9900,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#ffffff",
          borderRadius: 12,
          maxWidth: 850,
          width: "100%",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          overflow: "hidden",
          border: "1px solid #e2e8f0",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            background: "#f8fafc",
          }}
        >
          <div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Generic Validation Issue Impact Analysis
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: "4px 0 0" }}>
              {checkName}
            </h2>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              fontSize: 24,
              color: "#64748b",
              cursor: "pointer",
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* Impact Summary Banner */}
        <div
          style={{
            padding: "16px 24px",
            background: "#ffffff",
            borderBottom: "1px solid #e2e8f0",
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 16,
          }}
        >
          <div
            style={{
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: 12,
            }}
          >
            <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>
              AFFECTED PRODUCTS
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: "#0f172a", marginTop: 2 }}>
              {analysis.totalAffected}
            </div>
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>Failing this validation rule</div>
          </div>

          <div
            style={{
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
              borderRadius: 8,
              padding: 12,
            }}
          >
            <div style={{ fontSize: 11, color: "#166534", fontWeight: 700, textTransform: "uppercase" }}>
              WILL BECOME LAUNCH READY
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: "#16a34a", marginTop: 2 }}>
              {analysis.readyCount}
            </div>
            <div style={{ fontSize: 11, color: "#15803d", marginTop: 2 }}>
              This is their ONLY failing blocker
            </div>
          </div>

          <div
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: 8,
              padding: 12,
            }}
          >
            <div style={{ fontSize: 11, color: "#991b1b", fontWeight: 700, textTransform: "uppercase" }}>
              STILL BLOCKED BY OTHER ISSUES
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: "#dc2626", marginTop: 2 }}>
              {analysis.blockedCount}
            </div>
            <div style={{ fontSize: 11, color: "#b91c1c", marginTop: 2 }}>
              Additional blockers must be resolved
            </div>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div
          style={{
            padding: "12px 24px",
            background: "#f8fafc",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => setFilter("ALL")}
              style={{
                background: filter === "ALL" ? "#2563eb" : "#ffffff",
                color: filter === "ALL" ? "#ffffff" : "#334155",
                border: filter === "ALL" ? "1px solid #2563eb" : "1px solid #cbd5e1",
                padding: "5px 12px",
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 6,
                cursor: "pointer",
              }}
            >
              All Affected ({analysis.totalAffected})
            </button>
            <button
              onClick={() => setFilter("READY")}
              style={{
                background: filter === "READY" ? "#16a34a" : "#ffffff",
                color: filter === "READY" ? "#ffffff" : "#334155",
                border: filter === "READY" ? "1px solid #16a34a" : "1px solid #cbd5e1",
                padding: "5px 12px",
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 6,
                cursor: "pointer",
              }}
            >
              Will Become Launch Ready ({analysis.readyCount})
            </button>
            <button
              onClick={() => setFilter("BLOCKED")}
              style={{
                background: filter === "BLOCKED" ? "#dc2626" : "#ffffff",
                color: filter === "BLOCKED" ? "#ffffff" : "#334155",
                border: filter === "BLOCKED" ? "1px solid #dc2626" : "1px solid #cbd5e1",
                padding: "5px 12px",
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 6,
                cursor: "pointer",
              }}
            >
              Still Blocked ({analysis.blockedCount})
            </button>
          </div>

          <div style={{ fontSize: 11.5, color: "#64748b" }}>
            Showing {filteredList.length} of {analysis.totalAffected} affected products
          </div>
        </div>

        {/* Affected Products Table */}
        <div style={{ flex: 1, overflowY: "auto", padding: "0 24px" }}>
          {filteredList.length === 0 ? (
            <div style={{ padding: "40px 0", textAlign: "center", color: "#64748b", fontSize: 13 }}>
              No products found for the selected filter.
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12.5 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e2e8f0", color: "#64748b" }}>
                  <th style={{ padding: "12px 8px", fontWeight: 700 }}>PRODUCT</th>
                  <th style={{ padding: "12px 8px", fontWeight: 700, textAlign: "center" }}>CURRENT BLOCKERS</th>
                  <th style={{ padding: "12px 8px", fontWeight: 700, textAlign: "center" }}>REMAINING AFTER FIX</th>
                  <th style={{ padding: "12px 8px", fontWeight: 700, textAlign: "center" }}>PREDICTED RESULT</th>
                  <th style={{ padding: "12px 8px", fontWeight: 700, textAlign: "right" }}>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {filteredList.map((item) => (
                  <tr
                    key={item.product.product_name}
                    style={{ borderBottom: "1px solid #f1f5f9", transition: "background 0.1s ease" }}
                  >
                    <td style={{ padding: "12px 8px" }}>
                      <div style={{ fontWeight: 700, color: "#0f172a" }}>{item.product.product_name}</div>
                      <div style={{ fontSize: 11, color: "#64748b" }}>{item.product.mvp_category}</div>
                    </td>

                    <td style={{ padding: "12px 8px", textAlign: "center" }}>
                      <span
                        style={{
                          background: "#fef2f2",
                          color: "#dc2626",
                          padding: "2px 8px",
                          borderRadius: 12,
                          fontWeight: 700,
                          fontSize: 11.5,
                        }}
                      >
                        {item.currentBlockers} {item.currentBlockers === 1 ? "blocker" : "blockers"}
                      </span>
                    </td>

                    <td style={{ padding: "12px 8px", textAlign: "center" }}>
                      <span style={{ fontWeight: 700, color: "#334155" }}>
                        {item.currentBlockers} → {item.remainingAfterFix} remaining
                      </span>
                    </td>

                    <td style={{ padding: "12px 8px", textAlign: "center" }}>
                      {item.willBecomeLaunchReady ? (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            background: "#f0fdf4",
                            border: "1px solid #bbf7d0",
                            color: "#16a34a",
                            padding: "3px 10px",
                            borderRadius: 12,
                            fontWeight: 700,
                            fontSize: 11.5,
                          }}
                        >
                          🟢 Launch Ready
                        </span>
                      ) : (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            background: "#fef2f2",
                            border: "1px solid #fecaca",
                            color: "#dc2626",
                            padding: "3px 10px",
                            borderRadius: 12,
                            fontWeight: 700,
                            fontSize: 11.5,
                          }}
                        >
                          🔴 Still Blocked ({item.remainingAfterFix} left)
                        </span>
                      )}
                    </td>

                    <td style={{ padding: "12px 8px", textAlign: "right" }}>
                      <button
                        onClick={() => {
                          onClose();
                          onSelectProduct(item.product);
                        }}
                        style={{
                          background: "#2563eb",
                          color: "#ffffff",
                          border: "none",
                          padding: "5px 12px",
                          borderRadius: 6,
                          fontSize: 11.5,
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        View Audit →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid #e2e8f0",
            background: "#f8fafc",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 11.5,
            color: "#64748b",
          }}
        >
          <div>
            Note: <strong>Predicted Launch Ready</strong> status is an impact prediction. Re-run validation to confirm actual launch state.
          </div>
          <button
            onClick={onClose}
            style={{
              background: "#ffffff",
              border: "1px solid #cbd5e1",
              padding: "6px 16px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              color: "#334155",
              cursor: "pointer",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
