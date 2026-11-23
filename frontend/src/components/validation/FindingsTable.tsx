import React, { useState, useMemo } from "react";
import type { AuditedProduct } from "../../pages/Validation";

interface FindingItem {
  productName: string;
  category: string;
  checkId?: number;
  checkKey: string;
  checkName: string;
  section: string;
  severity: "Blocker" | "Warning";
  authority: "API" | "Browser";
  result: "PASS" | "FAIL" | "WARNING";
  explanation: string;
  screenshotUrl: string | null;
  productRef: AuditedProduct;
}

interface FindingsTableProps {
  products: AuditedProduct[];
  sections: string[];
  onOpenProductAudit: (product: AuditedProduct) => void;
  onOpenEvidence: (title: string, checkName: string, authority: string, result: string, explanation: string, imageUrl: string | null) => void;
}

function getScreenshotUrl(rawPath?: string | null): string | null {
  if (!rawPath || rawPath === "N/A") return null;
  const clean = rawPath.replace(/\\/g, "/");
  const parts = clean.split("/");
  const filename = parts[parts.length - 1];
  if (!filename) return null;
  return `/screenshots/${filename}`;
}

export const FindingsTable: React.FC<FindingsTableProps> = ({
  products,
  sections,
  onOpenProductAudit,
  onOpenEvidence,
}) => {
  const [priorityFilter, setPriorityFilter] = useState<string>("All");
  const [authorityFilter, setAuthorityFilter] = useState<string>("All");
  const [sectionFilter, setSectionFilter] = useState<string>("All");
  const [resultFilter, setResultFilter] = useState<string>("FAIL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const allFindings = useMemo(() => {
    const list: FindingItem[] = [];

    products.forEach(p => {
      Object.entries(p.checks || {}).forEach(([key, check]) => {
        const res = check.final_result || (check as any).status || "FAIL";
        const explanation = check.final_evidence?.explanation || check.api_evidence?.explanation || check.explanation || "Evaluation detail recorded.";
        const rawScreenshot = check.browser_evidence?.screenshot || check.final_evidence?.screenshot;

        list.push({
          productName: p.product_name,
          category: p.mvp_category,
          checkId: check.check_id,
          checkKey: key,
          checkName: check.check_name || key,
          section: check.section || "Unknown",
          severity: check.severity || "Warning",
          authority: check.authority || "API",
          result: res as any,
          explanation,
          screenshotUrl: getScreenshotUrl(rawScreenshot),
          productRef: p
        });
      });
    });

    return list;
  }, [products]);

  const filteredFindings = useMemo(() => {
    return allFindings.filter(f => {
      if (priorityFilter === "Blockers" && f.severity !== "Blocker") return false;
      if (priorityFilter === "Warnings" && f.severity !== "Warning") return false;
      if (authorityFilter !== "All" && f.authority !== authorityFilter) return false;
      if (sectionFilter !== "All" && f.section !== sectionFilter) return false;
      if (resultFilter !== "All" && f.result !== resultFilter) return false;

      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchProd = f.productName.toLowerCase().includes(q);
        const matchCheck = f.checkName.toLowerCase().includes(q);
        const matchExp = f.explanation.toLowerCase().includes(q);
        if (!matchProd && !matchCheck && !matchExp) return false;
      }
      return true;
    });
  }, [allFindings, priorityFilter, authorityFilter, sectionFilter, resultFilter, searchQuery]);

  const failCount = filteredFindings.filter(f => f.result === "FAIL").length;
  const warnCount = filteredFindings.filter(f => f.result === "WARNING").length;

  return (
    <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: 20, boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)" }}>
      
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: "#0f172a" }}>Validation Findings Work Queue</h3>
          <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 0" }}>
            <strong style={{ color: "#dc2626" }}>{failCount}</strong> failures · <strong style={{ color: "#d97706" }}>{warnCount}</strong> warnings matching active filters
          </p>
        </div>

        {(priorityFilter !== "All" || authorityFilter !== "All" || sectionFilter !== "All" || resultFilter !== "FAIL" || searchQuery !== "") && (
          <button
            onClick={() => {
              setPriorityFilter("All");
              setAuthorityFilter("All");
              setSectionFilter("All");
              setResultFilter("FAIL");
              setSearchQuery("");
            }}
            style={{ background: "#f1f5f9", border: "1px solid #cbd5e1", padding: "4px 10px", borderRadius: 4, fontSize: 11.5, cursor: "pointer", color: "#334155" }}
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Toolbar Filters */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "6px 10px", width: 240 }}>
          <input
            type="text"
            placeholder="Search check or product..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ background: "transparent", border: "none", outline: "none", width: "100%", fontSize: 12, color: "#0f172a" }}
          />
        </div>

        <select
          value={resultFilter}
          onChange={(e) => setResultFilter(e.target.value)}
          style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "6px 10px", fontSize: 12, color: "#334155" }}
        >
          <option value="All">Result: All</option>
          <option value="FAIL">FAIL Only</option>
          <option value="WARNING">WARNING Only</option>
          <option value="PASS">PASS Only</option>
        </select>

        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "6px 10px", fontSize: 12, color: "#334155" }}
        >
          <option value="All">Severity: All</option>
          <option value="Blockers">Blockers Only</option>
          <option value="Warnings">Warnings Only</option>
        </select>

        <select
          value={authorityFilter}
          onChange={(e) => setAuthorityFilter(e.target.value)}
          style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "6px 10px", fontSize: 12, color: "#334155" }}
        >
          <option value="All">Authority: All</option>
          <option value="API">API Verified</option>
          <option value="Browser">Browser Verified</option>
        </select>

        <select
          value={sectionFilter}
          onChange={(e) => setSectionFilter(e.target.value)}
          style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: "6px 10px", fontSize: 12, color: "#334155" }}
        >
          <option value="All">Section: All 9 Sections</option>
          {sections.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Findings Table */}
      {filteredFindings.length === 0 ? (
        <div style={{ padding: "40px 0", textAlign: "center", color: "#64748b", fontSize: 13 }}>
          No validation findings match your active search and filter criteria.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #e2e8f0", color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                <th style={{ padding: "8px 10px" }}>CHECK</th>
                <th style={{ padding: "8px 10px" }}>PRODUCT</th>
                <th style={{ padding: "8px 10px" }}>SECTION</th>
                <th style={{ padding: "8px 10px" }}>SEVERITY</th>
                <th style={{ padding: "8px 10px" }}>AUTHORITY</th>
                <th style={{ padding: "8px 10px" }}>RESULT</th>
                <th style={{ padding: "8px 10px" }}>ISSUE / EXPLANATION</th>
                <th style={{ padding: "8px 10px", textAlign: "right" }}>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {filteredFindings.map((f, idx) => {
                const isNotApp = f.result === ("NOT_APPLICABLE" as any) || f.explanation.includes("Not Applicable");
                const isFail = !isNotApp && f.result === "FAIL";
                const isWarn = !isNotApp && f.result === "WARNING";
                const resultColor = isNotApp ? "#2563eb" : isFail ? "#dc2626" : isWarn ? "#d97706" : "#16a34a";
                const resultLabel = isNotApp ? "NOT APPLICABLE" : f.result;
                return (
                  <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "10px", fontWeight: 700, color: isFail ? "#dc2626" : isWarn ? "#d97706" : "#16a34a" }}>
                      {f.checkName}
                    </td>
                    <td style={{ padding: "10px", fontWeight: 600, color: "#0f172a" }}>
                      {f.productName}
                    </td>
                    <td style={{ padding: "10px", color: "#64748b", fontSize: 11.5 }}>
                      {f.section}
                    </td>
                    <td style={{ padding: "10px" }}>
                      <span style={{
                        padding: "2px 6px",
                        borderRadius: 3,
                        fontSize: 10.5,
                        fontWeight: 700,
                        background: f.severity === "Blocker" ? "#fef2f2" : "#fffbeb",
                        color: f.severity === "Blocker" ? "#dc2626" : "#d97706"
                      }}>
                        {f.severity}
                      </span>
                    </td>
                    <td style={{ padding: "10px" }}>
                      <span style={{
                        padding: "2px 6px",
                        borderRadius: 3,
                        fontSize: 10.5,
                        fontWeight: 700,
                        background: f.authority === "Browser" ? "#faf5ff" : "#eff6ff",
                        color: f.authority === "Browser" ? "#9333ea" : "#2563eb"
                      }}>
                        {f.authority === "Browser" ? "BROWSER" : "API"}
                      </span>
                    </td>
                    <td style={{ padding: "10px", fontWeight: 700, color: resultColor }}>
                      {resultLabel}
                    </td>
                    <td style={{ padding: "10px", color: "#475569", maxWidth: 280 }}>
                      {f.explanation}
                    </td>
                    <td style={{ padding: "10px", textAlign: "right", whiteSpace: "nowrap" }}>
                      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                        {f.screenshotUrl && (
                          <button
                            onClick={() => onOpenEvidence(f.productName, f.checkName, f.authority, f.result, f.explanation, f.screenshotUrl)}
                            style={{ background: "#ffffff", border: "1px solid #cbd5e1", padding: "3px 8px", fontSize: 11, borderRadius: 4, cursor: "pointer", color: "#334155" }}
                          >
                            Evidence
                          </button>
                        )}
                        <button
                          onClick={() => onOpenProductAudit(f.productRef)}
                          style={{ background: "#f1f5f9", border: "1px solid #cbd5e1", padding: "3px 8px", fontSize: 11, borderRadius: 4, cursor: "pointer", color: "#2563eb", fontWeight: 600 }}
                        >
                          View audit →
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
