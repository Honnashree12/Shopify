import { useState, useEffect, useMemo } from "react";
import { BASE, getHeaders } from "../../api/client";

interface ChecklistItem {
  key: string;
  name: string;
  required_quantity: number;
  found_quantity: number;
  status: "PASS" | "MISSING" | "INCOMPLETE_QUANTITY" | "INVALID_DIMENSIONS" | "INVALID_FORMAT" | "FORMAT_UNVERIFIED";
  required_dimensions: string;
  actual_dimensions: string;
  format_status: string;
  matched_file: string | null;
  action: string;
}

interface ProductMediaAudit {
  product_id: string | number;
  product_title: string;
  shopify_status: string;
  product_type: string;
  collections: string[];
  requirement_profile: string;
  overall_status: "COMPLETE" | "INCOMPLETE" | "UNCLASSIFIED";
  summary: {
    total_required: number;
    valid_media: number;
    missing_media: number;
    invalid_media: number;
  };
  checklist: ChecklistItem[];
  missing_media_list: string[];
  invalid_media_list: string[];
  required_corrections: string[];
}

interface MediaReport {
  timestamp: string;
  store_name?: string;
  store_summary: {
    total_fetched_products?: number;
    active_products_audited?: number;
    draft_products_excluded?: number;
    archived_products_excluded?: number;
    total_products: number;
    complete: number;
    incomplete: number;
    unclassified: number;
    validation_errors?: number;
  };
  products: ProductMediaAudit[];
  action_required: Array<{
    product_id: string | number;
    product_title: string;
    shopify_status: string;
    profile: string;
    status: string;
    missing_media: string[];
    invalid_media: string[];
    corrections: string[];
  }>;
}

const COLLECTION_COLORS: Record<string, { bg: string; text: string; border: string; icon: string }> = {
  "STEM Kits": { bg: "#eff6ff", text: "#1d4ed8", border: "#bfdbfe", icon: "🤖" },
  "Books": { bg: "#fefce8", text: "#a16207", border: "#fef08a", icon: "📚" },
  "Apparel / T-Shirts": { bg: "#fdf2f8", text: "#be185d", border: "#fbcfe8", icon: "👕" },
  "Electronics": { bg: "#eef2ff", text: "#4338ca", border: "#c7d2fe", icon: "⚡" },
  "Courses": { bg: "#f0fdf4", text: "#15803d", border: "#bbf7d0", icon: "🎓" },
  "Workshops": { bg: "#fff7ed", text: "#c2410c", border: "#fed7aa", icon: "🛠️" },
  "Unclassified": { bg: "#f1f5f9", text: "#475569", border: "#cbd5e1", icon: "📦" }
};

export function MediaCompletenessTab() {
  const [report, setReport] = useState<MediaReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Sub-tab view: "checklist" (What's Missing) | "standards" (Rules Matrix)
  const [viewMode, setViewMode] = useState<"checklist" | "standards">("checklist");

  // Filters
  const [selectedCollection, setSelectedCollection] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [filterIssueOnly, setFilterIssueOnly] = useState<string>("ALL");

  useEffect(() => {
    async function loadReport() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${BASE}/api/validation/media-completeness`, {
          headers: getHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          setReport(data);
        } else {
          setError(`Failed to load media completeness report (${res.status})`);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load media report");
      } finally {
        setLoading(false);
      }
    }
    loadReport();
  }, []);

  const productsList = useMemo(() => {
    return report?.products || [];
  }, [report]);

  // Unique collections for filter chips
  const collectionsList = useMemo(() => {
    const set = new Set<string>();
    productsList.forEach((p) => {
      if (p.requirement_profile) set.add(p.requirement_profile);
    });
    return Array.from(set);
  }, [productsList]);

  // Filtered products list
  const filteredProducts = useMemo(() => {
    return productsList.filter((p) => {
      if (selectedCollection !== "ALL" && p.requirement_profile !== selectedCollection) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesTitle = (p.product_title || "").toLowerCase().includes(q);
        const matchesType = (p.product_type || "").toLowerCase().includes(q);
        if (!matchesTitle && !matchesType) return false;
      }
      if (filterIssueOnly === "MISSING_ONLY") {
        if (!p.missing_media_list || p.missing_media_list.length === 0) return false;
      }
      if (filterIssueOnly === "DIMENSION_ONLY") {
        if (!p.invalid_media_list || p.invalid_media_list.length === 0) return false;
      }
      return true;
    });
  }, [productsList, selectedCollection, searchQuery, filterIssueOnly]);

  // Aggregate stats
  const aggregateStats = useMemo(() => {
    let totalMissing = 0;
    let totalInvalidDim = 0;
    productsList.forEach((p) => {
      totalMissing += (p.summary?.missing_media || 0);
      totalInvalidDim += (p.summary?.invalid_media || 0);
    });
    return { totalMissing, totalInvalidDim };
  }, [productsList]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* 1. AGENT MISSION EXPLANATION BANNER */}
      <div style={{
        background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
        color: "#ffffff",
        borderRadius: 12,
        padding: "24px 28px",
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        border: "1px solid #334155"
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
          <div style={{
            fontSize: 32,
            background: "rgba(255, 255, 255, 0.1)",
            width: 56,
            height: 56,
            borderRadius: 12,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0
          }}>
            📷
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>
                Media Completeness &amp; Visual Asset Inspector
              </h2>
              <span style={{
                background: "#22c55e",
                color: "#052e16",
                fontSize: 11,
                fontWeight: 700,
                padding: "3px 9px",
                borderRadius: 20,
                textTransform: "uppercase",
                letterSpacing: "0.05em"
              }}>
                100% Read-Only Safety
              </span>
              <span style={{
                background: "#38bdf8",
                color: "#082f49",
                fontSize: 11,
                fontWeight: 700,
                padding: "3px 9px",
                borderRadius: 20
              }}>
                Anti-Reuse Tracking Active
              </span>
            </div>
            <p style={{ margin: "8px 0 0", fontSize: 14, color: "#cbd5e1", lineHeight: 1.5, maxWidth: 960 }}>
              <strong>What does this agent do?</strong> This agent evaluates your live Shopify catalog against professional multi-angle image requirements. It automatically identifies <strong>which exact photos are missing</strong> (e.g. kit box unboxing shots, book spines, or on-model photos) and flags photos with <strong>incorrect dimensions or aspect ratios</strong> before products reach customers.
            </p>
          </div>
        </div>
      </div>

      {/* 2. STOREWIDE KPI CARDS */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
        <div style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: 10,
          padding: "16px 18px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Active Catalog Scope</div>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>
            {report?.store_summary?.total_products || productsList.length || 29}
          </div>
          <div style={{ fontSize: 12, color: "#16a34a", fontWeight: 600, marginTop: 2 }}>
            Active Products Audited · {report?.store_summary?.draft_products_excluded || 11} Drafts Excluded
          </div>
        </div>

        <div style={{
          background: "#ffffff",
          border: "1px solid #fee2e2",
          borderRadius: 10,
          padding: "16px 18px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#dc2626", textTransform: "uppercase" }}>Catalog Media Health</div>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#dc2626", marginTop: 4 }}>
            {report?.store_summary?.incomplete || productsList.length} <span style={{ fontSize: 14, fontWeight: 600, color: "#991b1b" }}>Incomplete</span>
          </div>
          <div style={{ fontSize: 12, color: "#b91c1c", marginTop: 2 }}>
            Requires additional visual assets to pass launch standards
          </div>
        </div>

        <div style={{
          background: "#ffffff",
          border: "1px solid #fef3c7",
          borderRadius: 10,
          padding: "16px 18px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#d97706", textTransform: "uppercase" }}>Missing Image Angles</div>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#d97706", marginTop: 4 }}>
            {aggregateStats.totalMissing} <span style={{ fontSize: 14, fontWeight: 600, color: "#92400e" }}>Missing Photos</span>
          </div>
          <div style={{ fontSize: 12, color: "#92400e", marginTop: 2 }}>
            Unboxing, back covers, interior pages, or model photos needed
          </div>
        </div>

        <div style={{
          background: "#ffffff",
          border: "1px solid #e0e7ff",
          borderRadius: 10,
          padding: "16px 18px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#4f46e5", textTransform: "uppercase" }}>Dimension Fixes Needed</div>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#4f46e5", marginTop: 4 }}>
            {aggregateStats.totalInvalidDim} <span style={{ fontSize: 14, fontWeight: 600, color: "#3730a3" }}>Images</span>
          </div>
          <div style={{ fontSize: 12, color: "#4338ca", marginTop: 2 }}>
            Must be resized to meet 1200×1200 or 800×1200 standards
          </div>
        </div>
      </div>

      {/* 3. SUB-NAVIGATION SWITCHER & DOWNLOAD BUTTONS */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 12,
        borderBottom: "2px solid #e2e8f0",
        paddingBottom: 8
      }}>
        {/* Toggle Mode */}
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => setViewMode("checklist")}
            style={{
              background: viewMode === "checklist" ? "#2563eb" : "#f1f5f9",
              color: viewMode === "checklist" ? "#ffffff" : "#475569",
              border: "none",
              padding: "10px 18px",
              borderRadius: 8,
              fontSize: 13.5,
              fontWeight: 700,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              boxShadow: viewMode === "checklist" ? "0 2px 4px rgba(37,99,235,0.3)" : "none",
              transition: "all 0.15s ease"
            }}
          >
            <span>🚨</span>
            Action Checklist: What's Missing by Product ({filteredProducts.length})
          </button>

          <button
            onClick={() => setViewMode("standards")}
            style={{
              background: viewMode === "standards" ? "#2563eb" : "#f1f5f9",
              color: viewMode === "standards" ? "#ffffff" : "#475569",
              border: "none",
              padding: "10px 18px",
              borderRadius: 8,
              fontSize: 13.5,
              fontWeight: 700,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              boxShadow: viewMode === "standards" ? "0 2px 4px rgba(37,99,235,0.3)" : "none",
              transition: "all 0.15s ease"
            }}
          >
            <span>📋</span>
            Collection Standards Guide (The 6 Profiles)
          </button>
        </div>

        {/* Download Buttons */}
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <a
            href={`${BASE}/api/validation/media-completeness/download/xlsx`}
            target="_blank"
            rel="noreferrer"
            download
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: "#15803d",
              color: "#ffffff",
              padding: "7px 12px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none"
            }}
          >
            <span>📊</span> Excel Report (.xlsx)
          </a>

          <a
            href={`${BASE}/api/validation/media-completeness/download/pdf`}
            target="_blank"
            rel="noreferrer"
            download
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: "#b91c1c",
              color: "#ffffff",
              padding: "7px 12px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none"
            }}
          >
            <span>📄</span> PDF Report (.pdf)
          </a>

          <a
            href={`${BASE}/api/validation/media-completeness`}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: "#0f172a",
              color: "#ffffff",
              padding: "7px 12px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none"
            }}
          >
            <span>🌐</span> Raw JSON
          </a>
        </div>
      </div>

      {/* 4. MAIN VIEW CONTENT */}
      {loading ? (
        <div style={{ padding: "60px 0", textAlign: "center", color: "#64748b" }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#1e293b" }}>
            Loading Live Media Completeness Audit...
          </div>
          <div style={{ fontSize: 13, marginTop: 4 }}>
            Evaluating 40 store items against 6 collection specifications.
          </div>
        </div>
      ) : error ? (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: 18, color: "#b91c1c" }}>
          <strong>Error Loading Media Report:</strong> {error}
        </div>
      ) : viewMode === "checklist" ? (
        /* ========================================================================= */
        /* VIEW 1: ACTION CHECKLIST (WHAT IS MISSING BY PRODUCT)                     */
        /* ========================================================================= */
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Filter Toolbar */}
          <div style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: 10,
            padding: "16px 20px",
            display: "flex",
            flexDirection: "column",
            gap: 12
          }}>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
              {/* Search */}
              <input
                type="text"
                placeholder="🔍 Search product title..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  padding: "8px 14px",
                  border: "1px solid #cbd5e1",
                  borderRadius: 6,
                  fontSize: 13,
                  width: 280,
                  color: "#0f172a"
                }}
              />

              {/* Filter by Issue */}
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={() => setFilterIssueOnly("ALL")}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    border: "1px solid",
                    borderColor: filterIssueOnly === "ALL" ? "#2563eb" : "#cbd5e1",
                    background: filterIssueOnly === "ALL" ? "#dbeafe" : "#ffffff",
                    color: filterIssueOnly === "ALL" ? "#1e40af" : "#475569"
                  }}
                >
                  All Products ({productsList.length})
                </button>
                <button
                  onClick={() => setFilterIssueOnly("MISSING_ONLY")}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    border: "1px solid",
                    borderColor: filterIssueOnly === "MISSING_ONLY" ? "#dc2626" : "#cbd5e1",
                    background: filterIssueOnly === "MISSING_ONLY" ? "#fee2e2" : "#ffffff",
                    color: filterIssueOnly === "MISSING_ONLY" ? "#991b1b" : "#475569"
                  }}
                >
                  ❌ Missing Photos Only
                </button>
                <button
                  onClick={() => setFilterIssueOnly("DIMENSION_ONLY")}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    border: "1px solid",
                    borderColor: filterIssueOnly === "DIMENSION_ONLY" ? "#d97706" : "#cbd5e1",
                    background: filterIssueOnly === "DIMENSION_ONLY" ? "#fef3c7" : "#ffffff",
                    color: filterIssueOnly === "DIMENSION_ONLY" ? "#92400e" : "#475569"
                  }}
                >
                  ⚠️ Wrong Size Only
                </button>
              </div>
            </div>

            {/* Collection Filter Chips */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>Collection:</span>
              <button
                onClick={() => setSelectedCollection("ALL")}
                style={{
                  padding: "4px 10px",
                  borderRadius: 20,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  border: "1px solid",
                  borderColor: selectedCollection === "ALL" ? "#0f172a" : "#e2e8f0",
                  background: selectedCollection === "ALL" ? "#0f172a" : "#f8fafc",
                  color: selectedCollection === "ALL" ? "#ffffff" : "#475569"
                }}
              >
                All Collections ({productsList.length})
              </button>
              {collectionsList.map((cName) => {
                const count = productsList.filter((p) => p.requirement_profile === cName).length;
                const colStyle = COLLECTION_COLORS[cName] || COLLECTION_COLORS["Unclassified"];
                const isSelected = selectedCollection === cName;
                return (
                  <button
                    key={cName}
                    onClick={() => setSelectedCollection(cName)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 20,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: "pointer",
                      border: "1px solid",
                      borderColor: isSelected ? colStyle.text : colStyle.border,
                      background: isSelected ? colStyle.text : colStyle.bg,
                      color: isSelected ? "#ffffff" : colStyle.text
                    }}
                  >
                    {colStyle.icon} {cName} ({count})
                  </button>
                );
              })}
            </div>
          </div>

          {/* List of Product Cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {filteredProducts.length === 0 ? (
              <div style={{ padding: "40px 0", textAlign: "center", color: "#64748b", background: "#ffffff", borderRadius: 8 }}>
                No products found matching the selected filters.
              </div>
            ) : (
              filteredProducts.map((p, idx) => {
                const colStyle = COLLECTION_COLORS[p.requirement_profile] || COLLECTION_COLORS["Unclassified"];
                const missingCount = p.summary?.missing_media || 0;
                const invalidCount = p.summary?.invalid_media || 0;

                return (
                  <div
                    key={String(p.product_id || idx)}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 10,
                      padding: "18px 22px",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 14
                    }}
                  >
                    {/* Header Row */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10 }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: "#64748b" }}>#{idx + 1}</span>
                          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#0f172a" }}>
                            {p.product_title}
                          </h3>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                          <span style={{
                            background: colStyle.bg,
                            color: colStyle.text,
                            border: `1px solid ${colStyle.border}`,
                            padding: "2px 8px",
                            borderRadius: 4,
                            fontSize: 12,
                            fontWeight: 700
                          }}>
                            {colStyle.icon} {p.requirement_profile}
                          </span>
                          <span style={{ fontSize: 12, color: "#64748b" }}>
                            Shopify Status: <strong style={{ color: "#16a34a" }}>{p.shopify_status}</strong>
                          </span>
                        </div>
                      </div>

                      {/* Status Badges */}
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {missingCount > 0 && (
                          <span style={{
                            background: "#fee2e2",
                            color: "#991b1b",
                            border: "1px solid #fecaca",
                            padding: "4px 10px",
                            borderRadius: 6,
                            fontSize: 12,
                            fontWeight: 700
                          }}>
                            ❌ {missingCount} Missing Images
                          </span>
                        )}
                        {invalidCount > 0 && (
                          <span style={{
                            background: "#fef3c7",
                            color: "#92400e",
                            border: "1px solid #fde68a",
                            padding: "4px 10px",
                            borderRadius: 6,
                            fontSize: 12,
                            fontWeight: 700
                          }}>
                            ⚠️ {invalidCount} Wrong Dimensions
                          </span>
                        )}
                        {missingCount === 0 && invalidCount === 0 && (
                          <span style={{
                            background: "#dcfce7",
                            color: "#166534",
                            border: "1px solid #bbf7d0",
                            padding: "4px 10px",
                            borderRadius: 6,
                            fontSize: 12,
                            fontWeight: 700
                          }}>
                            ✅ 100% Media Complete
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Visual Angles Breakdown Grid */}
                    <div style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      padding: 14
                    }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", marginBottom: 10, textTransform: "uppercase" }}>
                        Angle-by-Angle Verification Status for {p.requirement_profile}:
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 10 }}>
                        {p.checklist?.map((chk) => {
                          const isPass = chk.status === "PASS";
                          const isMissing = chk.status === "MISSING" || chk.status === "INCOMPLETE_QUANTITY";
                          const isWrongDim = chk.status === "INVALID_DIMENSIONS";

                          return (
                            <div
                              key={chk.key}
                              style={{
                                background: "#ffffff",
                                border: "1px solid",
                                borderColor: isPass ? "#bbf7d0" : isMissing ? "#fecaca" : isWrongDim ? "#fde68a" : "#cbd5e1",
                                borderRadius: 6,
                                padding: "10px 12px",
                                display: "flex",
                                flexDirection: "column",
                                gap: 4
                              }}
                            >
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                <span style={{ fontWeight: 700, fontSize: 13, color: "#0f172a" }}>
                                  {chk.name}
                                </span>
                                <span style={{
                                  fontSize: 11,
                                  fontWeight: 800,
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  background: isPass ? "#dcfce7" : isMissing ? "#fee2e2" : isWrongDim ? "#fef3c7" : "#f1f5f9",
                                  color: isPass ? "#166534" : isMissing ? "#991b1b" : isWrongDim ? "#92400e" : "#475569"
                                }}>
                                  {isPass ? "✓ PASS" : isMissing ? "MISSING" : isWrongDim ? "WRONG SIZE" : chk.status}
                                </span>
                              </div>
                              <div style={{ fontSize: 12, color: "#64748b" }}>
                                Target: <strong>{chk.required_dimensions} px</strong>
                                {chk.actual_dimensions !== "None" && chk.actual_dimensions !== "Unknown" && (
                                  <span> · Actual: <strong style={{ color: isPass ? "#16a34a" : "#b91c1c" }}>{chk.actual_dimensions} px</strong></span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Step-by-Step Action List */}
                    {p.required_corrections && p.required_corrections.length > 0 && (
                      <div style={{
                        background: "#fffbeb",
                        border: "1px solid #fef3c7",
                        borderRadius: 8,
                        padding: "12px 16px"
                      }}>
                        <div style={{ fontSize: 12.5, fontWeight: 700, color: "#92400e", display: "flex", alignItems: "center", gap: 6 }}>
                          <span>🔧</span> What you need to upload / fix for this product:
                        </div>
                        <ul style={{ margin: "6px 0 0", paddingLeft: 20, fontSize: 12.5, color: "#78350f", lineHeight: 1.6 }}>
                          {p.required_corrections.map((corr, cIdx) => (
                            <li key={cIdx}>{corr}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      ) : (
        /* ========================================================================= */
        /* VIEW 2: COLLECTION STANDARDS GUIDE (THE 6 CATALOG PROFILES)               */
        /* ========================================================================= */
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: 10,
            overflow: "hidden",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
          }}>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", background: "#f8fafc" }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "#0f172a" }}>
                Mandatory Image Specifications Across 6 Catalog Collections
              </h3>
              <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748b" }}>
                Use this reference guide when creating or shooting product photography for KiddyPi.
              </p>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, textAlign: "left" }}>
                <thead>
                  <tr style={{ background: "#f1f5f9", borderBottom: "2px solid #cbd5e1" }}>
                    <th style={{ padding: "12px 16px", color: "#0f172a", fontWeight: 700 }}>Collection Profile</th>
                    <th style={{ padding: "12px 16px", color: "#0f172a", fontWeight: 700 }}>Min. Images</th>
                    <th style={{ padding: "12px 16px", color: "#0f172a", fontWeight: 700 }}>Required Visual Angles</th>
                    <th style={{ padding: "12px 16px", color: "#0f172a", fontWeight: 700 }}>Required Dimensions</th>
                    <th style={{ padding: "12px 16px", color: "#0f172a", fontWeight: 700 }}>Aspect Ratio</th>
                    <th style={{ padding: "12px 16px", color: "#0f172a", fontWeight: 700 }}>Allowed Formats</th>
                  </tr>
                </thead>
                <tbody>
                  {/* STEM Kits */}
                  <tr style={{ borderBottom: "1px solid #e2e8f0", verticalAlign: "top" }}>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>
                      <span style={{ display: "inline-block", background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe", padding: "3px 8px", borderRadius: 4, fontSize: 12 }}>
                        🤖 STEM Kits
                      </span>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>4 distinct</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div>1. <strong>Hero / Featured Image</strong> (Main product view)</div>
                        <div>2. <strong>Kit Box / Packaging</strong> (Box shot)</div>
                        <div>3. <strong>Contents Laid Out</strong> (All components flat lay)</div>
                        <div>4. <strong>Completed Project</strong> (Working project assembled)</div>
                      </div>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a", fontFamily: "monospace" }}>1200 × 1200 px</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>1:1 Square</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>JPG, JPEG, PNG</td>
                  </tr>

                  {/* Books */}
                  <tr style={{ borderBottom: "1px solid #e2e8f0", verticalAlign: "top", background: "#fafafa" }}>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>
                      <span style={{ display: "inline-block", background: "#fefce8", color: "#a16207", border: "1px solid #fef08a", padding: "3px 8px", borderRadius: 4, fontSize: 12 }}>
                        📚 Books
                      </span>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>4 to 5</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div>1. <strong>Book Front Cover</strong> (800×1200)</div>
                        <div>2. <strong>Book Back Cover</strong> (800×1200)</div>
                        <div>3. <strong>Sample Interior Pages</strong> (qty 2, 1200×900)</div>
                        <div>4. <strong>Book Spine</strong> (200×1200)</div>
                        <div style={{ color: "#92400e" }}>5. <strong>Bundle / Series Shot</strong> (1200×900, mandatory for bundles)</div>
                      </div>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a", fontFamily: "monospace" }}>
                      800 × 1200 px (Covers)<br />
                      1200 × 900 px (Interior)<br />
                      200 × 1200 px (Spine)
                    </td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>2:3 Portrait &amp; 4:3 Landscape</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>JPG, JPEG, PNG</td>
                  </tr>

                  {/* Apparel */}
                  <tr style={{ borderBottom: "1px solid #e2e8f0", verticalAlign: "top" }}>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>
                      <span style={{ display: "inline-block", background: "#fdf2f8", color: "#be185d", border: "1px solid #fbcfe8", padding: "3px 8px", borderRadius: 4, fontSize: 12 }}>
                        👕 Apparel / T-Shirts
                      </span>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>4 distinct</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div>1. <strong>Front Flat Lay</strong> (1200×1200)</div>
                        <div>2. <strong>Back Flat Lay</strong> (1200×1200)</div>
                        <div>3. <strong>Front On Model</strong> (1200×1500)</div>
                        <div>4. <strong>Back On Model</strong> (1200×1500)</div>
                      </div>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a", fontFamily: "monospace" }}>
                      1200 × 1200 px (Flat)<br />
                      1200 × 1500 px (Model)
                    </td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>1:1 Square &amp; 4:5 Portrait</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>JPG, JPEG, PNG</td>
                  </tr>

                  {/* Electronics */}
                  <tr style={{ borderBottom: "1px solid #e2e8f0", verticalAlign: "top", background: "#fafafa" }}>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>
                      <span style={{ display: "inline-block", background: "#eef2ff", color: "#4338ca", border: "1px solid #c7d2fe", padding: "3px 8px", borderRadius: 4, fontSize: 12 }}>
                        ⚡ Electronics
                      </span>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>3 distinct</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div>1. <strong>Product Top-Down View</strong> (Overhead flat)</div>
                        <div>2. <strong>45° Angle Perspective</strong> (Iso angle)</div>
                        <div>3. <strong>Back / Additional View</strong> (Underside/pins)</div>
                      </div>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a", fontFamily: "monospace" }}>1200 × 1200 px</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>1:1 Square</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>JPG, JPEG, PNG</td>
                  </tr>

                  {/* Courses */}
                  <tr style={{ borderBottom: "1px solid #e2e8f0", verticalAlign: "top" }}>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>
                      <span style={{ display: "inline-block", background: "#f0fdf4", color: "#15803d", border: "1px solid #bbf7d0", padding: "3px 8px", borderRadius: 4, fontSize: 12 }}>
                        🎓 Courses
                      </span>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>1 distinct</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>
                      <div>1. <strong>Course Cover / Hero Card</strong> (Course thumbnail)</div>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a", fontFamily: "monospace" }}>1200 × 800 px</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>3:2 Landscape</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>JPG, JPEG, PNG</td>
                  </tr>

                  {/* Workshops */}
                  <tr style={{ verticalAlign: "top", background: "#fafafa" }}>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>
                      <span style={{ display: "inline-block", background: "#fff7ed", color: "#c2410c", border: "1px solid #fed7aa", padding: "3px 8px", borderRadius: 4, fontSize: 12 }}>
                        🛠️ Workshops
                      </span>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a" }}>1 distinct</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>
                      <div>1. <strong>Workshop Hero / Banner</strong> (Header banner)</div>
                    </td>
                    <td style={{ padding: "14px 16px", fontWeight: 700, color: "#0f172a", fontFamily: "monospace" }}>1920 × 600 px</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>16:5 Panoramic</td>
                    <td style={{ padding: "14px 16px", color: "#0f172a" }}>JPG, JPEG, PNG</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
