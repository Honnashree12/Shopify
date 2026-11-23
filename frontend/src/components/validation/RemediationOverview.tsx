import React, { useState, useMemo } from "react";
import type { AuditedProduct } from "../../pages/Validation";

interface RemediationOverviewProps {
  products: AuditedProduct[];
  onSelectProduct: (product: AuditedProduct) => void;
  onSelectCheck: (checkName: string) => void;
}

export const RemediationOverview: React.FC<RemediationOverviewProps> = ({
  products,
  onSelectProduct,
  onSelectCheck,
}) => {
  const [filterCategory, setFilterCategory] = useState<"ALL" | "QUICK_WINS" | "MULTI_FIX" | "HIGH_REMEDIATION">("ALL");

  // Dynamic Remediation Analysis across all products
  const data = useMemo(() => {
    const quickWins: Array<{
      product: AuditedProduct;
      onlyBlocker: { check_name: string; section: string };
    }> = [];

    const multiFix: Array<{
      product: AuditedProduct;
      blockerCount: number;
      topBlocker: { check_name: string; section: string };
    }> = [];

    const highRemediation: Array<{
      product: AuditedProduct;
      blockerCount: number;
      topBlocker: { check_name: string; section: string };
    }> = [];

    const launchReady: AuditedProduct[] = [];

    products.forEach((p) => {
      const checksObj = p.checks || {};
      const failedBlockers = Object.entries(checksObj).filter(
        ([_, c]) => c.severity === "Blocker" && (c.final_result === "FAIL" || (c as any).status === "FAIL")
      ).map(([key, val]) => ({
        check_name: val.check_name || key,
        section: val.section || "General",
      }));

      const cnt = failedBlockers.length;

      if (cnt === 0) {
        launchReady.push(p);
      } else if (cnt === 1) {
        quickWins.push({
          product: p,
          onlyBlocker: failedBlockers[0],
        });
      } else if (cnt >= 2 && cnt <= 5) {
        multiFix.push({
          product: p,
          blockerCount: cnt,
          topBlocker: failedBlockers[0],
        });
      } else {
        highRemediation.push({
          product: p,
          blockerCount: cnt,
          topBlocker: failedBlockers[0],
        });
      }
    });

    return {
      quickWins,
      multiFix,
      highRemediation,
      launchReady,
      totalBlocked: quickWins.length + multiFix.length + highRemediation.length,
    };
  }, [products]);

  const displayedProducts = useMemo(() => {
    const list: Array<{
      product: AuditedProduct;
      blockerCount: number;
      categoryLabel: "Quick Win (1)" | "Multi-Fix (2-5)" | "High Remediation (6+)";
      nextBestAction: string;
    }> = [];

    products.forEach((p) => {
      const checksObj = p.checks || {};
      const failedBlockers = Object.entries(checksObj).filter(
        ([_, c]) => c.severity === "Blocker" && (c.final_result === "FAIL" || (c as any).status === "FAIL")
      ).map(([key, val]) => val.check_name || key);

      const cnt = failedBlockers.length;
      if (cnt === 0) return;

      let cat: "Quick Win (1)" | "Multi-Fix (2-5)" | "High Remediation (6+)" = "Multi-Fix (2-5)";
      if (cnt === 1) cat = "Quick Win (1)";
      if (cnt >= 6) cat = "High Remediation (6+)";

      if (filterCategory === "QUICK_WINS" && cnt !== 1) return;
      if (filterCategory === "MULTI_FIX" && (cnt < 2 || cnt > 5)) return;
      if (filterCategory === "HIGH_REMEDIATION" && cnt < 6) return;

      list.push({
        product: p,
        blockerCount: cnt,
        categoryLabel: cat,
        nextBestAction: failedBlockers[0] || "Check required fields",
      });
    });

    // Sort by blocker count ascending (closest to launch first)
    return list.sort((a, b) => a.blockerCount - b.blockerCount);
  }, [products, filterCategory]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Overview Stat Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
        <div
          onClick={() => setFilterCategory("QUICK_WINS")}
          style={{
            background: filterCategory === "QUICK_WINS" ? "#f0fdf4" : "#ffffff",
            border: filterCategory === "QUICK_WINS" ? "2px solid #16a34a" : "1px solid #e2e8f0",
            borderRadius: 8,
            padding: "16px 18px",
            cursor: "pointer",
            boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", textTransform: "uppercase" }}>
            🚀 QUICK WINS (1 FIX TO LAUNCH)
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#16a34a", marginTop: 4 }}>
            {data.quickWins.length}
          </div>
          <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4 }}>
            Products with exactly 1 blocker
          </div>
        </div>

        <div
          onClick={() => setFilterCategory("MULTI_FIX")}
          style={{
            background: filterCategory === "MULTI_FIX" ? "#fffbebe" : "#ffffff",
            border: filterCategory === "MULTI_FIX" ? "2px solid #d97706" : "1px solid #e2e8f0",
            borderRadius: 8,
            padding: "16px 18px",
            cursor: "pointer",
            boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: "#d97706", textTransform: "uppercase" }}>
            🔧 MULTI-FIX PRODUCTS (2–5)
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#d97706", marginTop: 4 }}>
            {data.multiFix.length}
          </div>
          <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4 }}>
            Products requiring 2–5 fixes
          </div>
        </div>

        <div
          onClick={() => setFilterCategory("HIGH_REMEDIATION")}
          style={{
            background: filterCategory === "HIGH_REMEDIATION" ? "#fef2f2" : "#ffffff",
            border: filterCategory === "HIGH_REMEDIATION" ? "2px solid #dc2626" : "1px solid #e2e8f0",
            borderRadius: 8,
            padding: "16px 18px",
            cursor: "pointer",
            boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: "#dc2626", textTransform: "uppercase" }}>
            🛑 HIGH REMEDIATION (6+)
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#dc2626", marginTop: 4 }}>
            {data.highRemediation.length}
          </div>
          <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4 }}>
            Products requiring 6+ fixes
          </div>
        </div>

        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            padding: "16px 18px",
            boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: "#2563eb", textTransform: "uppercase" }}>
            🟢 LAUNCH READY
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#2563eb", marginTop: 4 }}>
            {data.launchReady.length}
          </div>
          <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4 }}>
            0 remaining blockers
          </div>
        </div>
      </div>

      {/* SECTION 1: FIX TO LAUNCH READY — QUICK WINS */}
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: 8,
          padding: 20,
          boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <h3 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>
              FIX TO LAUNCH READY — QUICK WINS
            </h3>
            <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 0" }}>
              Products that will become Launch Ready with only <strong>ONE fix</strong>
            </p>
          </div>
          <span
            style={{
              background: "#f0fdf4",
              color: "#16a34a",
              border: "1px solid #bbf7d0",
              padding: "4px 10px",
              borderRadius: 20,
              fontSize: 11.5,
              fontWeight: 700,
            }}
          >
            {data.quickWins.length} Quick Win Candidates
          </span>
        </div>

        {data.quickWins.length === 0 ? (
          <div
            style={{
              background: "#f8fafc",
              border: "1px border #e2e8f0",
              borderRadius: 8,
              padding: 24,
              textAlign: "center",
              color: "#64748b",
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>
              No products currently have exactly 1 blocker remaining.
            </div>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              Inspect multi-fix products below to resolve initial blockers and promote them into Quick Wins!
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
            {data.quickWins.map((item) => (
              <div
                key={item.product.product_name}
                style={{
                  background: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  borderRadius: 8,
                  padding: 16,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 700, color: "#166534", textTransform: "uppercase" }}>
                        {item.product.mvp_category}
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", marginTop: 2 }}>
                        {item.product.product_name}
                      </div>
                    </div>
                    <span
                      style={{
                        background: "#ffffff",
                        color: "#16a34a",
                        border: "1px solid #16a34a",
                        padding: "2px 8px",
                        borderRadius: 12,
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      Score: {item.product.score.toFixed(1)}
                    </span>
                  </div>

                  {/* Fix Details */}
                  <div
                    style={{
                      background: "#ffffff",
                      border: "1px solid #cbd5e1",
                      borderRadius: 6,
                      padding: 10,
                      marginTop: 12,
                    }}
                  >
                    <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>REQUIRED FIX:</div>
                    <div
                      onClick={() => onSelectCheck(item.onlyBlocker.check_name)}
                      style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: "#dc2626",
                        marginTop: 2,
                        cursor: "pointer",
                        textDecoration: "underline",
                      }}
                    >
                      ❌ {item.onlyBlocker.check_name}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginTop: 8,
                        fontSize: 11.5,
                        color: "#334155",
                      }}
                    >
                      <span>1 blocker → 0 blockers</span>
                      <strong style={{ color: "#16a34a" }}>🟢 Predicted Launch Ready</strong>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => onSelectProduct(item.product)}
                  style={{
                    background: "#16a34a",
                    color: "#ffffff",
                    border: "none",
                    padding: "8px 14px",
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    marginTop: 14,
                    width: "100%",
                  }}
                >
                  View Product Audit &amp; Remediate →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SECTION 2: PRIORITIZATION BOARD */}
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: 8,
          padding: 20,
          boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <h3 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>
              NEXT PRODUCT TO FIX — REMEDIATION PRIORITIZATION
            </h3>
            <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 0" }}>
              Products prioritized by distance to Launch Ready status
            </p>
          </div>

          <div style={{ display: "flex", gap: 6 }}>
            <button
              onClick={() => setFilterCategory("ALL")}
              style={{
                background: filterCategory === "ALL" ? "#2563eb" : "#ffffff",
                color: filterCategory === "ALL" ? "#ffffff" : "#334155",
                border: filterCategory === "ALL" ? "1px solid #2563eb" : "1px solid #cbd5e1",
                padding: "4px 10px",
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              All Blocked ({data.totalBlocked})
            </button>
            <button
              onClick={() => setFilterCategory("QUICK_WINS")}
              style={{
                background: filterCategory === "QUICK_WINS" ? "#16a34a" : "#ffffff",
                color: filterCategory === "QUICK_WINS" ? "#ffffff" : "#334155",
                border: filterCategory === "QUICK_WINS" ? "1px solid #16a34a" : "1px solid #cbd5e1",
                padding: "4px 10px",
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              Quick Wins (1)
            </button>
            <button
              onClick={() => setFilterCategory("MULTI_FIX")}
              style={{
                background: filterCategory === "MULTI_FIX" ? "#d97706" : "#ffffff",
                color: filterCategory === "MULTI_FIX" ? "#ffffff" : "#334155",
                border: filterCategory === "MULTI_FIX" ? "1px solid #d97706" : "1px solid #cbd5e1",
                padding: "4px 10px",
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              Multi-Fix (2–5)
            </button>
            <button
              onClick={() => setFilterCategory("HIGH_REMEDIATION")}
              style={{
                background: filterCategory === "HIGH_REMEDIATION" ? "#dc2626" : "#ffffff",
                color: filterCategory === "HIGH_REMEDIATION" ? "#ffffff" : "#334155",
                border: filterCategory === "HIGH_REMEDIATION" ? "1px solid #dc2626" : "1px solid #cbd5e1",
                padding: "4px 10px",
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              High Remediation (6+)
            </button>
          </div>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12.5 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e2e8f0", color: "#64748b" }}>
              <th style={{ padding: "10px 8px", fontWeight: 700 }}>PRODUCT</th>
              <th style={{ padding: "10px 8px", fontWeight: 700, textAlign: "center" }}>CATEGORY</th>
              <th style={{ padding: "10px 8px", fontWeight: 700, textAlign: "center" }}>CURRENT BLOCKERS</th>
              <th style={{ padding: "10px 8px", fontWeight: 700 }}>NEXT BEST ACTION</th>
              <th style={{ padding: "10px 8px", fontWeight: 700, textAlign: "center" }}>AFTER FIX</th>
              <th style={{ padding: "10px 8px", fontWeight: 700, textAlign: "right" }}>ACTION</th>
            </tr>
          </thead>
          <tbody>
            {displayedProducts.map((item) => {
              const remaining = item.blockerCount - 1;
              const willBeReady = remaining === 0;
              return (
                <tr key={item.product.product_name} style={{ borderBottom: "1px solid #f1f5f9" }}>
                  <td style={{ padding: "12px 8px" }}>
                    <div style={{ fontWeight: 700, color: "#0f172a" }}>{item.product.product_name}</div>
                    <div style={{ fontSize: 11, color: "#64748b" }}>
                      Score: <strong>{item.product.score.toFixed(1)}</strong>
                    </div>
                  </td>

                  <td style={{ padding: "12px 8px", textAlign: "center" }}>
                    <span
                      style={{
                        background:
                          item.categoryLabel === "Quick Win (1)"
                            ? "#f0fdf4"
                            : item.categoryLabel === "Multi-Fix (2-5)"
                            ? "#fffbebe"
                            : "#fef2f2",
                        color:
                          item.categoryLabel === "Quick Win (1)"
                            ? "#16a34a"
                            : item.categoryLabel === "Multi-Fix (2-5)"
                            ? "#d97706"
                            : "#dc2626",
                        padding: "2px 8px",
                        borderRadius: 12,
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      {item.categoryLabel}
                    </span>
                  </td>

                  <td style={{ padding: "12px 8px", textAlign: "center" }}>
                    <strong style={{ color: "#dc2626", fontSize: 13 }}>{item.blockerCount}</strong>
                  </td>

                  <td style={{ padding: "12px 8px" }}>
                    <span
                      onClick={() => onSelectCheck(item.nextBestAction)}
                      style={{
                        color: "#2563eb",
                        fontWeight: 700,
                        cursor: "pointer",
                        textDecoration: "underline",
                      }}
                    >
                      Fix: {item.nextBestAction}
                    </span>
                  </td>

                  <td style={{ padding: "12px 8px", textAlign: "center" }}>
                    {willBeReady ? (
                      <span style={{ color: "#16a34a", fontWeight: 700 }}>🟢 0 left (Ready)</span>
                    ) : (
                      <span style={{ color: "#dc2626", fontWeight: 600 }}>🔴 {remaining} left</span>
                    )}
                  </td>

                  <td style={{ padding: "12px 8px", textAlign: "right" }}>
                    <button
                      onClick={() => onSelectProduct(item.product)}
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
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
