import { useState, useEffect, useMemo } from "react";
import { AppShell } from "../components/AppShell";
import { BASE, getHeaders } from "../api/client";

interface Issue {
  code: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  field: string;
  message: string;
  recommendation: string;
}

interface ImageAltRec {
  image_id: number | string;
  current_alt: string;
  recommended_alt: string;
}

interface AuditedSEOProduct {
  product_id: string;
  title: string;
  handle: string;
  seo_title: string;
  seo_description: string;
  tags: string[];
  images_count: number;
  images_missing_alt: number;
  seo_score: number;
  status: "OPTIMIZED" | "CAN_IMPROVE" | "NEEDS_OPTIMIZATION";
  issue_count: number;
  issues: Issue[];
  disclaimer: string;
}

interface SEOAuditReport {
  total_audited: number;
  total_store_products?: number;
  draft_excluded_count?: number;
  archived_excluded_count?: number;
  scope?: string;
  products_with_issues: number;
  optimized_products: number;
  average_seo_score: number;
  issue_breakdown: Record<string, number>;
  products: AuditedSEOProduct[];
  disclaimer: string;
}

interface ProposalItem {
  product_id: string;
  product_title: string;
  before: {
    seo_title: string;
    seo_description: string;
    handle: string;
    tags: string[];
    images: Array<{ id: any; alt: string }>;
  };
  after: {
    seo_title: string;
    seo_description: string;
    handle: string;
    handle_changed: boolean;
    tags: string[];
    image_alts: ImageAltRec[];
  };
  validation: {
    is_valid: boolean;
    errors: string[];
    warnings: string[];
  };
  changes_summary: string[];
  approve_handle_change?: boolean;
}

interface TopQueryItem {
  query: string;
  clicks: number;
  impressions: number;
  ctr: number;
  average_position: number;
}

interface GSCPerformanceData {
  success: boolean;
  status: string;
  site_url?: string;
  date_range?: { start: string; end: string };
  summary?: {
    total_clicks: number;
    total_impressions: number;
    average_ctr: number;
    average_position: number;
  };
  top_queries?: TopQueryItem[];
  shopify_mapping?: {
    total_shopify_products: number;
    matched_count: number;
    top_performing_count?: number;
    low_visibility_count?: number;
    unranked_count: number;
    unmatched_pages_count: number;
    matched_products: Array<{
      product_id: string;
      title: string;
      handle: string;
      page_url: string;
      clicks: number;
      impressions: number;
      ctr: number;
      average_position: number;
      queries: Array<{ query: string; clicks: number; impressions: number; position: number }>;
    }>;
    top_performing_products?: Array<{
      product_id: string;
      title: string;
      handle: string;
      page_url: string;
      clicks: number;
      impressions: number;
      ctr: number;
      average_position: number;
      queries: Array<{ query: string; clicks: number; impressions: number; position: number }>;
    }>;
    low_visibility_products?: Array<{
      product_id: string;
      title: string;
      handle: string;
      page_url: string;
      clicks: number;
      impressions: number;
      ctr: number;
      average_position: number;
      queries: Array<{ query: string; clicks: number; impressions: number; position: number }>;
    }>;
    unranked_products: Array<{
      product_id: string;
      title: string;
      handle: string;
      status: string;
    }>;
    unmatched_pages: Array<{
      page_url: string;
      clicks: number;
      impressions: number;
      ctr: number;
      position: number;
    }>;
  };
  error?: string;
  disclaimer?: string;
}

export default function SEODashboard() {
  const [loading, setLoading] = useState<boolean>(true);
  const [auditData, setAuditData] = useState<SEOAuditReport | null>(null);
  const [proposals, setProposals] = useState<Record<string, ProposalItem>>({});
  const [history, setHistory] = useState<any[]>([]);

  // Search Console state
  const [gscStatus, setGscStatus] = useState<any | null>(null);
  const [gscData, setGscData] = useState<GSCPerformanceData | null>(null);
  const [gscLoading, setGscLoading] = useState<boolean>(false);
  const [dateRangeFilter, setDateRangeFilter] = useState<string>("28d");

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");

  // Selection & Action state
  const [selectedProductIds, setSelectedProductIds] = useState<Set<string>>(new Set());
  const [expandedProductId, setExpandedProductId] = useState<string | null>(null);
  const [preserveHandles, setPreserveHandles] = useState<boolean>(true);
  const [dryRunMode, setDryRunMode] = useState<boolean>(true);

  // Execution feedback
  const [applying, setApplying] = useState<boolean>(false);
  const [executionResult, setExecutionResult] = useState<any | null>(null);
  const [confirmModalOpen, setConfirmModalOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"audit" | "performance" | "history">("audit");
  const [auditError, setAuditError] = useState<string | null>(null);

  const fetchAuditData = async () => {
    setLoading(true);
    setAuditError(null);
    try {
      const res = await fetch(`${BASE}/api/seo/audit`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setAuditData(data);
      } else {
        const errJson = await res.json().catch(() => ({}));
        setAuditError(errJson.detail || `Server returned status ${res.status} when fetching SEO audit.`);
      }
    } catch (err: any) {
      console.error("Error fetching SEO audit:", err);
      setAuditError(err.message || "Network error fetching SEO audit.");
    } finally {
      setLoading(false);
    }
  };

  const fetchProposals = async () => {
    try {
      const res = await fetch(`${BASE}/api/seo/proposals`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        const map: Record<string, ProposalItem> = {};
        (data.proposals || []).forEach((p: ProposalItem) => {
          map[p.product_id] = p;
        });
        setProposals(map);
      }
    } catch (err) {
      console.error("Error fetching proposals:", err);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${BASE}/api/seo/history`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.error("Error fetching SEO history:", err);
    }
  };

  const fetchGSCStatus = async () => {
    try {
      const res = await fetch(`${BASE}/api/seo/search-console/status`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setGscStatus(data);
      }
    } catch (err) {
      console.error("Error fetching GSC status:", err);
    }
  };

  const fetchGSCPerformance = async (rangeKey: string = "28d") => {
    setGscLoading(true);
    try {
      const now = new Date();
      let days = 28;
      if (rangeKey === "7d") days = 7;
      if (rangeKey === "90d") days = 90;

      const endDate = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
      const startDate = new Date(now.getTime() - (days + 2) * 24 * 60 * 60 * 1000).toISOString().split("T")[0];

      const res = await fetch(`${BASE}/api/seo/search-console/performance?start_date=${startDate}&end_date=${endDate}`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setGscData(data);
      }
    } catch (err) {
      console.error("Error fetching GSC performance:", err);
    } finally {
      setGscLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditData();
    fetchProposals();
    fetchHistory();
    fetchGSCStatus();
  }, []);

  useEffect(() => {
    if (activeTab === "performance") {
      fetchGSCPerformance(dateRangeFilter);
    }
  }, [activeTab, dateRangeFilter]);

  // Filtered products list
  const filteredProducts = useMemo(() => {
    if (!auditData?.products) return [];
    return auditData.products.filter((p) => {
      const matchesSearch =
        searchQuery === "" ||
        p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.handle.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus =
        statusFilter === "ALL" || p.status === statusFilter;

      const matchesSeverity =
        severityFilter === "ALL" ||
        p.issues.some((i) => i.severity === severityFilter);

      return matchesSearch && matchesStatus && matchesSeverity;
    });
  }, [auditData, searchQuery, statusFilter, severityFilter]);

  const handleSelectAll = () => {
    const next = new Set<string>();
    filteredProducts.forEach((p) => next.add(p.product_id));
    setSelectedProductIds(next);
  };

  const handleDeselectAll = () => {
    setSelectedProductIds(new Set());
  };

  const toggleSelect = (id: string) => {
    const next = new Set(selectedProductIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedProductIds(next);
  };

  const handleApplySelected = async (forceLive: boolean = false) => {
    const targets = Array.from(selectedProductIds);
    if (targets.length === 0) return;

    const approvedPayload: any[] = [];
    targets.forEach((id) => {
      const prop = proposals[id];
      if (prop) {
        approvedPayload.push({
          product_id: id,
          after: prop.after,
          approve_handle_change: !preserveHandles
        });
      }
    });

    setApplying(true);
    setConfirmModalOpen(false);
    try {
      const res = await fetch(`${BASE}/api/seo/apply`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          approved_proposals: approvedPayload,
          dry_run: forceLive ? false : dryRunMode,
          preserve_handles: preserveHandles
        })
      });

      if (res.ok) {
        const result = await res.json();
        setExecutionResult(result);
        fetchHistory();
        if (!dryRunMode && forceLive) {
          fetchAuditData();
        }
      } else {
        const err = await res.json();
        alert(`Failed to apply SEO updates: ${err.detail || "Server error"}`);
      }
    } catch (err: any) {
      alert(`Error applying updates: ${err.message}`);
    } finally {
      setApplying(false);
    }
  };

  const handleConnectGSC = async () => {
    try {
      const res = await fetch(`${BASE}/api/seo/search-console/auth-url`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        if (data.auth_url) {
          window.location.href = data.auth_url;
        } else {
          alert(data.error || "Could not generate authorization URL.");
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(errData.detail || errData.error || `HTTP ${res.status}: Permission denied or Google OAuth unconfigured.`);
      }
    } catch (err: any) {
      alert(`Error starting OAuth: ${err.message}`);
    }
  };

  return (
    <AppShell title="SEO Dashboard" crumbs="Operations / SEO">
      <div style={{ padding: "24px", maxWidth: "1400px", margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <div>
            <h1 style={{ fontSize: "26px", fontWeight: "700", color: "#111827", margin: "0 0 6px 0" }}>
              Shopify SEO Optimization & Performance Dashboard
            </h1>
            <p style={{ color: "#6B7280", margin: 0, fontSize: "14px" }}>
              Catalogue-wide SEO health, verified metadata optimization, and organic search performance.
            </p>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button
              onClick={() => { fetchAuditData(); fetchProposals(); if (activeTab === "performance") fetchGSCPerformance(dateRangeFilter); }}
              style={{
                backgroundColor: "#F3F4F6",
                color: "#374151",
                padding: "8px 16px",
                borderRadius: "6px",
                border: "1px solid #D1D5DB",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              🔄 Refresh
            </button>
            <div style={{ display: "flex", backgroundColor: "#E5E7EB", borderRadius: "6px", padding: "2px" }}>
              <button
                onClick={() => setActiveTab("audit")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "5px",
                  border: "none",
                  fontWeight: "600",
                  backgroundColor: activeTab === "audit" ? "#FFFFFF" : "transparent",
                  color: activeTab === "audit" ? "#111827" : "#4B5563",
                  cursor: "pointer"
                }}
              >
                Catalogue Audit
              </button>
              <button
                onClick={() => setActiveTab("performance")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "5px",
                  border: "none",
                  fontWeight: "600",
                  backgroundColor: activeTab === "performance" ? "#FFFFFF" : "transparent",
                  color: activeTab === "performance" ? "#111827" : "#4B5563",
                  cursor: "pointer"
                }}
              >
                Search Performance (GSC)
              </button>
              <button
                onClick={() => setActiveTab("history")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "5px",
                  border: "none",
                  fontWeight: "600",
                  backgroundColor: activeTab === "history" ? "#FFFFFF" : "transparent",
                  color: activeTab === "history" ? "#111827" : "#4B5563",
                  cursor: "pointer"
                }}
              >
                History ({history.length})
              </button>
            </div>
          </div>
        </div>

        {/* Technical Checklist Notice */}
        <div style={{
          backgroundColor: "#EFF6FF",
          border: "1px solid #BFDBFE",
          borderRadius: "8px",
          padding: "12px 16px",
          marginBottom: "20px",
          fontSize: "13px",
          color: "#1E40AF",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "8px"
        }}>
          <div>
            ℹ️ <strong>Technical Checklist Notice:</strong> Scores (0–100) evaluate content completeness, title/description boundaries, and structured tags. They reflect technical checklist compliance and do not guarantee or predict Google search rankings.
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span style={{
              backgroundColor: "#DBEAFE",
              color: "#1E40AF",
              padding: "3px 9px",
              borderRadius: "4px",
              fontWeight: "600",
              fontSize: "12px"
            }}>
              ● Scope: Active Products Only
            </span>
            {auditData?.draft_excluded_count !== undefined && auditData.draft_excluded_count > 0 && (
              <span style={{
                backgroundColor: "#FEF3C7",
                color: "#92400E",
                padding: "3px 9px",
                borderRadius: "4px",
                fontWeight: "600",
                fontSize: "12px"
              }}>
                Draft products excluded: {auditData.draft_excluded_count}
              </span>
            )}
          </div>
        </div>

        {/* TAB 1: CATALOGUE AUDIT */}
        {activeTab === "audit" && (
          <>
            {/* Metric KPI Cards */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: "16px",
              marginBottom: "24px"
            }}>
              <div style={{ backgroundColor: "#FFFFFF", padding: "18px", borderRadius: "8px", border: "1px solid #E5E7EB" }}>
                <span style={{ fontSize: "13px", color: "#6B7280", fontWeight: "600" }}>TOTAL PRODUCTS AUDITED</span>
                <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "4px" }}>
                  <span style={{ fontSize: "30px", fontWeight: "700", color: "#111827" }}>
                    {loading ? "..." : auditData?.total_audited || 0}
                  </span>
                  {auditData?.draft_excluded_count !== undefined && auditData.draft_excluded_count > 0 && (
                    <span style={{
                      fontSize: "11px",
                      color: "#92400E",
                      backgroundColor: "#FEF3C7",
                      padding: "2px 6px",
                      borderRadius: "10px",
                      fontWeight: "600"
                    }}>
                      {auditData.draft_excluded_count} draft excluded
                    </span>
                  )}
                </div>
                <span style={{ fontSize: "12px", color: "#10B981" }}>Active products only</span>
              </div>

              <div style={{ backgroundColor: "#FFFFFF", padding: "18px", borderRadius: "8px", border: "1px solid #E5E7EB" }}>
                <span style={{ fontSize: "13px", color: "#6B7280", fontWeight: "600" }}>PRODUCTS WITH ISSUES</span>
                <div style={{ fontSize: "30px", fontWeight: "700", color: "#EF4444", marginTop: "4px" }}>
                  {loading ? "..." : auditData?.products_with_issues || 0}
                </div>
                <span style={{ fontSize: "12px", color: "#EF4444" }}>Requires SEO optimization</span>
              </div>

              <div style={{ backgroundColor: "#FFFFFF", padding: "18px", borderRadius: "8px", border: "1px solid #E5E7EB" }}>
                <span style={{ fontSize: "13px", color: "#6B7280", fontWeight: "600" }}>OPTIMIZED PRODUCTS</span>
                <div style={{ fontSize: "30px", fontWeight: "700", color: "#10B981", marginTop: "4px" }}>
                  {loading ? "..." : auditData?.optimized_products || 0}
                </div>
                <span style={{ fontSize: "12px", color: "#10B981" }}>Meeting all standards</span>
              </div>

              <div style={{ backgroundColor: "#FFFFFF", padding: "18px", borderRadius: "8px", border: "1px solid #E5E7EB" }}>
                <span style={{ fontSize: "13px", color: "#6B7280", fontWeight: "600" }}>AVERAGE SEO SCORE</span>
                <div style={{ fontSize: "30px", fontWeight: "700", color: "#4F46E5", marginTop: "4px" }}>
                  {loading ? "..." : `${auditData?.average_seo_score || 0}/100`}
                </div>
                <span style={{ fontSize: "12px", color: "#6B7280" }}>Checklist compliance</span>
              </div>
            </div>

            {/* Severity Breakdown */}
            {auditData?.issue_breakdown && (
              <div style={{
                backgroundColor: "#FFFFFF",
                padding: "16px 20px",
                borderRadius: "8px",
                border: "1px solid #E5E7EB",
                marginBottom: "24px"
              }}>
                <span style={{ fontSize: "13px", fontWeight: "700", color: "#374151", textTransform: "uppercase" }}>
                  Issue Breakdown Across Store:
                </span>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "10px" }}>
                  {Object.entries(auditData.issue_breakdown).map(([code, count]) => {
                    const isCritical = code.includes("MISSING") || code.includes("WEAK");
                    return (
                      <span
                        key={code}
                        style={{
                          backgroundColor: isCritical ? "#FEE2E2" : "#FEF3C7",
                          color: isCritical ? "#991B1B" : "#92400E",
                          padding: "4px 10px",
                          borderRadius: "16px",
                          fontSize: "12px",
                          fontWeight: "600"
                        }}
                      >
                        {code.replace(/_/g, " ")}: {count}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Filter and Action Bar */}
            <div style={{
              backgroundColor: "#FFFFFF",
              padding: "16px",
              borderRadius: "8px",
              border: "1px solid #E5E7EB",
              marginBottom: "20px",
              display: "flex",
              flexWrap: "wrap",
              gap: "14px",
              alignItems: "center",
              justifyContent: "space-between"
            }}>
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", flex: 1, minWidth: "300px" }}>
                <input
                  type="text"
                  placeholder="🔍 Search product title or URL handle..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    padding: "8px 14px",
                    borderRadius: "6px",
                    border: "1px solid #D1D5DB",
                    fontSize: "14px",
                    width: "280px"
                  }}
                />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  style={{
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #D1D5DB",
                    fontSize: "14px",
                    backgroundColor: "#FFFFFF"
                  }}
                >
                  <option value="ALL">All Statuses</option>
                  <option value="NEEDS_OPTIMIZATION">Needs Optimization</option>
                  <option value="CAN_IMPROVE">Can Improve</option>
                  <option value="OPTIMIZED">Optimized</option>
                </select>

                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  style={{
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #D1D5DB",
                    fontSize: "14px",
                    backgroundColor: "#FFFFFF"
                  }}
                >
                  <option value="ALL">All Severities</option>
                  <option value="CRITICAL">Has Critical Issues</option>
                  <option value="WARNING">Has Warnings</option>
                  <option value="INFO">Has Recommendations</option>
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "#374151" }}>
                  <input
                    type="checkbox"
                    checked={preserveHandles}
                    onChange={(e) => setPreserveHandles(e.target.checked)}
                  />
                  <span>Preserve Handles (Safe)</span>
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "#374151" }}>
                  <input
                    type="checkbox"
                    checked={dryRunMode}
                    onChange={(e) => setDryRunMode(e.target.checked)}
                  />
                  <span>Dry-Run Simulation Mode</span>
                </label>

                <button
                  disabled={selectedProductIds.size === 0 || applying}
                  onClick={() => {
                    if (dryRunMode) {
                      handleApplySelected(false);
                    } else {
                      setConfirmModalOpen(true);
                    }
                  }}
                  style={{
                    backgroundColor: dryRunMode ? "#4F46E5" : "#DC2626",
                    color: "#FFFFFF",
                    padding: "8px 18px",
                    borderRadius: "6px",
                    border: "none",
                    fontWeight: "600",
                    fontSize: "14px",
                    cursor: selectedProductIds.size === 0 || applying ? "not-allowed" : "pointer",
                    opacity: selectedProductIds.size === 0 || applying ? 0.6 : 1
                  }}
                >
                  {applying
                    ? "Applying..."
                    : dryRunMode
                    ? `Simulate Dry-Run (${selectedProductIds.size})`
                    : `Apply Live Updates (${selectedProductIds.size})`}
                </button>
              </div>
            </div>

            {/* Execution / Verification Result Feedback Banner */}
            {executionResult && (
              <div style={{
                backgroundColor: executionResult.dry_run ? "#EEF2FF" : "#F0FDF4",
                border: `1px solid ${executionResult.dry_run ? "#C7D2FE" : "#BBF7D0"}`,
                borderRadius: "8px",
                padding: "16px",
                marginBottom: "20px"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: "700", color: executionResult.dry_run ? "#3730A3" : "#166534" }}>
                    {executionResult.dry_run ? "Simulation Report (Dry-Run)" : "Live Shopify Execution Report"}
                  </span>
                  <button
                    onClick={() => setExecutionResult(null)}
                    style={{ background: "none", border: "none", cursor: "pointer", fontSize: "14px" }}
                  >
                    ✕
                  </button>
                </div>
                <p style={{ margin: "6px 0 10px 0", fontSize: "13px", color: "#374151" }}>
                  Total: {executionResult.total_requested} | Succeeded: {executionResult.successful_updates} | Failed: {executionResult.failed_updates}
                </p>
                <div style={{ maxHeight: "220px", overflowY: "auto", fontSize: "12px", backgroundColor: "#FFFFFF", padding: "12px", borderRadius: "6px", border: "1px solid #E5E7EB" }}>
                  {executionResult.details.map((d: any, idx: number) => (
                    <div key={idx} style={{ marginBottom: "8px", paddingBottom: "6px", borderBottom: idx < executionResult.details.length - 1 ? "1px solid #F3F4F6" : "none" }}>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        <span style={{
                          padding: "2px 6px",
                          borderRadius: "4px",
                          fontWeight: "700",
                          fontSize: "11px",
                          backgroundColor: d.status.includes("SUCCESS") ? "#D1FAE5" : "#FEE2E2",
                          color: d.status.includes("SUCCESS") ? "#065F46" : "#991B1B"
                        }}>
                          {d.status}
                        </span>
                        <strong style={{ color: "#111827" }}>Product: {d.product_id}</strong>
                      </div>
                      {d.fields_to_update && (
                        <div style={{ marginTop: "4px", color: "#4B5563", fontSize: "11px", paddingLeft: "4px" }}>
                          {d.fields_to_update.seo_title && <div>• <strong>Validated SEO Title:</strong> "{d.fields_to_update.seo_title}"</div>}
                          {d.fields_to_update.seo_description && <div>• <strong>Validated Meta Description:</strong> "{d.fields_to_update.seo_description}"</div>}
                          {d.fields_to_update.tags && <div>• <strong>Tags:</strong> {d.fields_to_update.tags}</div>}
                          <div>• <strong>Handle:</strong> {d.fields_to_update.handle ? `/${d.fields_to_update.handle}` : "Preserved safely (unchanged)"}</div>
                        </div>
                      )}
                      {d.saved_seo_title && <div style={{ color: "#059669", marginTop: "2px" }}>✓ Live Verified Title: "{d.saved_seo_title}"</div>}
                      {d.error && <div style={{ color: "#DC2626", marginTop: "2px" }}>⚠️ Error: {d.error}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Product Audit Table */}
            <div style={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #E5E7EB", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", backgroundColor: "#F9FAFB", borderBottom: "1px solid #E5E7EB", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                  <button
                    onClick={handleSelectAll}
                    style={{ background: "none", border: "none", color: "#4F46E5", fontSize: "13px", cursor: "pointer", fontWeight: "600" }}
                  >
                    Select All ({filteredProducts.length})
                  </button>
                  <span style={{ color: "#D1D5DB" }}>|</span>
                  <button
                    onClick={handleDeselectAll}
                    style={{ background: "none", border: "none", color: "#6B7280", fontSize: "13px", cursor: "pointer" }}
                  >
                    Deselect All
                  </button>
                </div>
                <span style={{ fontSize: "13px", color: "#6B7280" }}>
                  Showing {loading ? "..." : filteredProducts.length} products
                </span>
              </div>

              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#F9FAFB", borderBottom: "1px solid #E5E7EB", color: "#4B5563" }}>
                      <th style={{ padding: "12px 16px", width: "40px" }}></th>
                      <th style={{ padding: "12px 16px" }}>Product & Handle</th>
                      <th style={{ padding: "12px 16px", width: "140px" }}>Checklist Score</th>
                      <th style={{ padding: "12px 16px", width: "160px" }}>Status</th>
                      <th style={{ padding: "12px 16px" }}>Identified Issues</th>
                      <th style={{ padding: "12px 16px", width: "180px", textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading && (
                      <tr>
                        <td colSpan={6} style={{ padding: "48px 16px", textAlign: "center", color: "#6B7280" }}>
                          <div style={{ display: "inline-flex", alignItems: "center", gap: 10, fontSize: "14px" }}>
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2.5" style={{ animation: "spin 1s linear infinite" }}>
                              <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
                              <path d="M21 3v5h-5" />
                            </svg>
                            <span style={{ fontWeight: 500 }}>Fetching Shopify live store products & evaluating SEO checklist...</span>
                          </div>
                        </td>
                      </tr>
                    )}
                    {!loading && filteredProducts.length === 0 && (
                      <tr>
                        <td colSpan={6} style={{ padding: "48px 16px", textAlign: "center", color: "#6B7280" }}>
                          {auditError ? (
                            <div style={{ maxWidth: 450, margin: "0 auto" }}>
                              <div style={{ color: "#DC2626", fontWeight: 600, marginBottom: 8 }}>⚠️ {auditError}</div>
                              <p style={{ fontSize: 13, color: "#6B7280", marginBottom: 16 }}>Check backend logs or verify that you are logged in with appropriate permissions.</p>
                              <button
                                onClick={fetchAuditData}
                                style={{
                                  padding: "8px 18px",
                                  backgroundColor: "#4F46E5",
                                  color: "#FFF",
                                  border: "none",
                                  borderRadius: 6,
                                  cursor: "pointer",
                                  fontWeight: 600
                                }}
                              >
                                Retry SEO Audit
                              </button>
                            </div>
                          ) : (
                            <span>No active products found matching the selected filters.</span>
                          )}
                        </td>
                      </tr>
                    )}
                    {!loading && filteredProducts.map((p) => {
                      const isSelected = selectedProductIds.has(p.product_id);
                      const isExpanded = expandedProductId === p.product_id;
                      const prop = proposals[p.product_id];

                      return (
                        <>
                          <tr
                            key={p.product_id}
                            style={{
                              borderBottom: "1px solid #E5E7EB",
                              backgroundColor: isSelected ? "#F5F3FF" : "#FFFFFF"
                            }}
                          >
                            <td style={{ padding: "12px 16px" }}>
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => toggleSelect(p.product_id)}
                              />
                            </td>
                            <td style={{ padding: "12px 16px" }}>
                              <div style={{ fontWeight: "600", color: "#111827" }}>{p.title}</div>
                              <div style={{ fontSize: "12px", color: "#6B7280" }}>handle: /{p.handle}</div>
                            </td>
                            <td style={{ padding: "12px 16px" }}>
                              <span style={{
                                fontWeight: "700",
                                color: p.seo_score >= 80 ? "#059669" : p.seo_score >= 50 ? "#D97706" : "#DC2626"
                              }}>
                                {p.seo_score} / 100
                              </span>
                            </td>
                            <td style={{ padding: "12px 16px" }}>
                              <span style={{
                                padding: "3px 8px",
                                borderRadius: "12px",
                                fontSize: "11px",
                                fontWeight: "700",
                                backgroundColor:
                                  p.status === "OPTIMIZED" ? "#D1FAE5" : p.status === "CAN_IMPROVE" ? "#FEF3C7" : "#FEE2E2",
                                color:
                                  p.status === "OPTIMIZED" ? "#065F46" : p.status === "CAN_IMPROVE" ? "#92400E" : "#991B1B"
                              }}>
                                {p.status.replace(/_/g, " ")}
                              </span>
                            </td>
                            <td style={{ padding: "12px 16px" }}>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                                {p.issues.slice(0, 3).map((iss, i) => (
                                  <span
                                    key={i}
                                    style={{
                                      fontSize: "11px",
                                      padding: "2px 6px",
                                      borderRadius: "4px",
                                      backgroundColor: iss.severity === "CRITICAL" ? "#FEE2E2" : "#FEF3C7",
                                      color: iss.severity === "CRITICAL" ? "#B91C1C" : "#92400E"
                                    }}
                                  >
                                    {iss.code.replace(/_/g, " ")}
                                  </span>
                                ))}
                                {p.issues.length > 3 && (
                                  <span style={{ fontSize: "11px", color: "#6B7280" }}>
                                    +{p.issues.length - 3} more
                                  </span>
                                )}
                              </div>
                            </td>
                            <td style={{ padding: "12px 16px", textAlign: "right" }}>
                              <button
                                onClick={() => setExpandedProductId(isExpanded ? null : p.product_id)}
                                style={{
                                  backgroundColor: "#F3F4F6",
                                  border: "1px solid #D1D5DB",
                                  borderRadius: "4px",
                                  padding: "5px 10px",
                                  fontSize: "12px",
                                  fontWeight: "600",
                                  cursor: "pointer"
                                }}
                              >
                                {isExpanded ? "Hide Preview ▲" : "View Proposal ▼"}
                              </button>
                            </td>
                          </tr>

                          {/* Expandable Before & After Preview Row */}
                          {isExpanded && prop && (
                            <tr style={{ backgroundColor: "#F9FAFB" }}>
                              <td colSpan={6} style={{ padding: "16px 24px" }}>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "14px" }}>
                                  {/* Current Values (Before) */}
                                  <div style={{ backgroundColor: "#FFFFFF", padding: "14px", borderRadius: "6px", border: "1px solid #E5E7EB" }}>
                                    <h4 style={{ margin: "0 0 10px 0", fontSize: "13px", color: "#6B7280", textTransform: "uppercase" }}>
                                      Current Shopify SEO Values
                                    </h4>
                                    <div style={{ marginBottom: "8px" }}>
                                      <strong style={{ fontSize: "12px" }}>SEO Title:</strong>
                                      <p style={{ margin: "2px 0", fontSize: "13px", color: prop.before.seo_title.includes("Default") ? "#6B7280" : "#374151" }}>
                                        {prop.before.seo_title.includes("Default") 
                                          ? `(Default: using "${prop.product_title}" — no custom SEO title configured in Shopify)` 
                                          : prop.before.seo_title}
                                      </p>
                                    </div>
                                    <div style={{ marginBottom: "8px" }}>
                                      <strong style={{ fontSize: "12px" }}>Meta Description:</strong>
                                      <p style={{ margin: "2px 0", fontSize: "13px", color: prop.before.seo_description.includes("No meta") ? "#6B7280" : "#374151" }}>
                                        {prop.before.seo_description.includes("No meta")
                                          ? "(No custom meta description configured in Shopify)"
                                          : prop.before.seo_description}
                                      </p>
                                    </div>
                                    <div style={{ marginBottom: "8px" }}>
                                      <strong style={{ fontSize: "12px" }}>URL Handle:</strong>
                                      <p style={{ margin: "2px 0", fontSize: "13px", color: "#374151" }}>/{prop.before.handle}</p>
                                    </div>
                                    <div>
                                      <strong style={{ fontSize: "12px" }}>Tags:</strong>
                                      <p style={{ margin: "2px 0", fontSize: "13px", color: "#374151" }}>{prop.before.tags.join(", ") || "(None)"}</p>
                                    </div>
                                  </div>

                                  {/* Proposed Improvements (After) */}
                                  <div style={{ backgroundColor: "#F0FDF4", padding: "14px", borderRadius: "6px", border: "1px solid #BBF7D0" }}>
                                    <h4 style={{ margin: "0 0 10px 0", fontSize: "13px", color: "#166534", textTransform: "uppercase" }}>
                                      Proposed Verified Improvements
                                    </h4>
                                    <div style={{ marginBottom: "8px" }}>
                                      <strong style={{ fontSize: "12px" }}>Optimized SEO Title:</strong>
                                      <p style={{ margin: "2px 0", fontSize: "13px", color: "#111827", fontWeight: "600" }}>{prop.after.seo_title}</p>
                                    </div>
                                    <div style={{ marginBottom: "8px" }}>
                                      <strong style={{ fontSize: "12px" }}>Optimized Meta Description:</strong>
                                      <p style={{ margin: "2px 0", fontSize: "13px", color: "#111827" }}>{prop.after.seo_description}</p>
                                    </div>
                                    <div style={{ marginBottom: "8px" }}>
                                      <strong style={{ fontSize: "12px" }}>Recommended Handle:</strong>
                                      <p style={{ margin: "2px 0", fontSize: "13px", color: "#111827" }}>
                                        /{prop.after.handle} {prop.after.handle_changed ? "(Change Suggested)" : "(Preserved)"}
                                      </p>
                                    </div>
                                    <div>
                                      <strong style={{ fontSize: "12px" }}>Enriched Tags:</strong>
                                      <p style={{ margin: "2px 0", fontSize: "13px", color: "#111827" }}>{prop.after.tags.join(", ")}</p>
                                    </div>
                                  </div>
                                </div>

                                <div style={{ backgroundColor: "#FFFFFF", padding: "12px 16px", borderRadius: "6px", border: "1px solid #E5E7EB" }}>
                                  <strong style={{ fontSize: "12px", color: "#4B5563" }}>Reasons for Recommendations:</strong>
                                  <ul style={{ margin: "6px 0 0 0", paddingLeft: "20px", fontSize: "13px", color: "#374151" }}>
                                    {prop.changes_summary.map((reason, rIdx) => (
                                      <li key={rIdx}>{reason}</li>
                                    ))}
                                  </ul>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* TAB 2: SEARCH PERFORMANCE (GOOGLE SEARCH CONSOLE) */}
        {activeTab === "performance" && (
          <div>
            {/* Status & Connection Banner */}
            <div style={{
              backgroundColor: gscStatus?.connected ? "#F0FDF4" : "#FFFBEB",
              border: `1px solid ${gscStatus?.connected ? "#BBF7D0" : "#FDE68A"}`,
              borderRadius: "8px",
              padding: "16px 20px",
              marginBottom: "24px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center"
            }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{
                    padding: "3px 8px",
                    borderRadius: "12px",
                    fontSize: "12px",
                    fontWeight: "700",
                    backgroundColor: gscStatus?.connected ? "#D1FAE5" : "#FEF3C7",
                    color: gscStatus?.connected ? "#065F46" : "#92400E"
                  }}>
                    {gscStatus?.status || "UNCONFIGURED"}
                  </span>
                  <span style={{
                    padding: "3px 8px",
                    borderRadius: "12px",
                    fontSize: "12px",
                    fontWeight: "700",
                    backgroundColor: gscStatus?.verified ? "#DBEAFE" : "#FEE2E2",
                    color: gscStatus?.verified ? "#1E40AF" : "#991B1B"
                  }}>
                    {gscStatus?.verified ? "✓ Verified Property" : "⚠️ Verification Required"}
                  </span>
                  <span style={{ fontWeight: "700", color: "#111827", fontSize: "15px" }}>
                    Property: {gscStatus?.site_url || "https://kinq5t-q5.myshopify.com"}
                  </span>
                </div>
                <p style={{ margin: "6px 0 0 0", fontSize: "13px", color: "#4B5563" }}>
                  {gscStatus?.message}
                </p>
              </div>

              {!gscStatus?.connected ? (
                <button
                  onClick={handleConnectGSC}
                  style={{
                    backgroundColor: "#2563EB",
                    color: "#FFFFFF",
                    padding: "10px 18px",
                    borderRadius: "6px",
                    border: "none",
                    fontWeight: "600",
                    fontSize: "13px",
                    cursor: "pointer"
                  }}
                >
                  🔗 Connect Google Search Console
                </button>
              ) : (
                <button
                  onClick={() => fetchGSCPerformance(dateRangeFilter)}
                  style={{
                    backgroundColor: "#F3F4F6",
                    color: "#374151",
                    padding: "8px 14px",
                    borderRadius: "6px",
                    border: "1px solid #D1D5DB",
                    fontWeight: "600",
                    fontSize: "13px",
                    cursor: "pointer"
                  }}
                >
                  🔄 Refresh Data
                </button>
              )}
            </div>

            {/* Date Range Selector */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ margin: 0, fontSize: "18px", fontWeight: "700" }}>Organic Search Performance</h3>
              <div style={{ display: "flex", gap: "8px" }}>
                {["7d", "28d", "90d"].map((r) => (
                  <button
                    key={r}
                    onClick={() => setDateRangeFilter(r)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "5px",
                      border: "1px solid #D1D5DB",
                      backgroundColor: dateRangeFilter === r ? "#4F46E5" : "#FFFFFF",
                      color: dateRangeFilter === r ? "#FFFFFF" : "#374151",
                      fontSize: "13px",
                      fontWeight: "600",
                      cursor: "pointer"
                    }}
                  >
                    Last {r === "7d" ? "7 Days" : r === "28d" ? "28 Days" : "3 Months"}
                  </button>
                ))}
              </div>
            </div>

            {/* Performance Metric Cards */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "16px",
              marginBottom: "24px"
            }}>
              <div style={{ backgroundColor: "#FFFFFF", padding: "18px", borderRadius: "8px", border: "1px solid #E5E7EB" }}>
                <span style={{ fontSize: "12px", color: "#6B7280", fontWeight: "600" }}>TOTAL CLICKS</span>
                <div style={{ fontSize: "28px", fontWeight: "700", color: "#2563EB", marginTop: "4px" }}>
                  {gscLoading ? "..." : gscData?.summary?.total_clicks ?? "Unavailable"}
                </div>
                <span style={{ fontSize: "12px", color: "#6B7280" }}>Organic Google clicks</span>
              </div>

              <div style={{ backgroundColor: "#FFFFFF", padding: "18px", borderRadius: "8px", border: "1px solid #E5E7EB" }}>
                <span style={{ fontSize: "12px", color: "#6B7280", fontWeight: "600" }}>TOTAL IMPRESSIONS</span>
                <div style={{ fontSize: "28px", fontWeight: "700", color: "#4F46E5", marginTop: "4px" }}>
                  {gscLoading ? "..." : gscData?.summary?.total_impressions ?? "Unavailable"}
                </div>
                <span style={{ fontSize: "12px", color: "#6B7280" }}>Appeared in search</span>
              </div>

              <div style={{ backgroundColor: "#FFFFFF", padding: "18px", borderRadius: "8px", border: "1px solid #E5E7EB" }}>
                <span style={{ fontSize: "12px", color: "#6B7280", fontWeight: "600" }}>AVERAGE CTR</span>
                <div style={{ fontSize: "28px", fontWeight: "700", color: "#059669", marginTop: "4px" }}>
                  {gscLoading ? "..." : gscData?.summary?.average_ctr !== undefined ? `${gscData.summary.average_ctr}%` : "Unavailable"}
                </div>
                <span style={{ fontSize: "12px", color: "#6B7280" }}>Click-through rate</span>
              </div>

              <div style={{ backgroundColor: "#FFFFFF", padding: "18px", borderRadius: "8px", border: "1px solid #E5E7EB" }}>
                <span style={{ fontSize: "12px", color: "#6B7280", fontWeight: "600" }}>AVERAGE POSITION</span>
                <div style={{ fontSize: "28px", fontWeight: "700", color: "#D97706", marginTop: "4px" }}>
                  {gscLoading ? "..." : gscData?.summary?.average_position ?? "Unavailable"}
                </div>
                <span style={{ fontSize: "12px", color: "#6B7280" }}>Weighted SERP rank</span>
              </div>
            </div>

            {/* Top Search Queries Table */}
            {gscData?.top_queries && gscData.top_queries.length > 0 && (
              <div style={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #E5E7EB", overflow: "hidden", marginBottom: "24px" }}>
                <div style={{ padding: "14px 18px", backgroundColor: "#F9FAFB", borderBottom: "1px solid #E5E7EB" }}>
                  <h4 style={{ margin: 0, fontSize: "15px", color: "#111827" }}>
                    Top Search Queries Driving Organic Traffic ({gscData.top_queries.length} queries)
                  </h4>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#F9FAFB", borderBottom: "1px solid #E5E7EB", color: "#4B5563" }}>
                      <th style={{ padding: "10px 16px" }}>Query</th>
                      <th style={{ padding: "10px 16px", width: "100px" }}>Clicks</th>
                      <th style={{ padding: "10px 16px", width: "120px" }}>Impressions</th>
                      <th style={{ padding: "10px 16px", width: "100px" }}>CTR</th>
                      <th style={{ padding: "10px 16px", width: "110px" }}>Avg Position</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gscData.top_queries.slice(0, 10).map((q, qIdx) => (
                      <tr key={qIdx} style={{ borderBottom: "1px solid #E5E7EB" }}>
                        <td style={{ padding: "10px 16px", fontWeight: "600", color: "#111827" }}>"{q.query}"</td>
                        <td style={{ padding: "10px 16px", fontWeight: "700", color: "#2563EB" }}>{q.clicks}</td>
                        <td style={{ padding: "10px 16px" }}>{q.impressions}</td>
                        <td style={{ padding: "10px 16px", color: "#059669", fontWeight: "600" }}>{q.ctr}%</td>
                        <td style={{ padding: "10px 16px" }}>{q.average_position}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Product-Level Mapped Performance Table */}
            <div style={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #E5E7EB", overflow: "hidden", marginBottom: "24px" }}>
              <div style={{ padding: "14px 18px", backgroundColor: "#F9FAFB", borderBottom: "1px solid #E5E7EB" }}>
                <h4 style={{ margin: 0, fontSize: "15px", color: "#111827" }}>
                  Shopify Product Search Performance Mapping ({gscData?.shopify_mapping?.matched_count || 0} matched products)
                </h4>
              </div>

              {gscData?.shopify_mapping?.matched_products && gscData.shopify_mapping.matched_products.length > 0 ? (
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#F9FAFB", borderBottom: "1px solid #E5E7EB", color: "#4B5563" }}>
                      <th style={{ padding: "12px 16px" }}>Shopify Product & URL</th>
                      <th style={{ padding: "12px 16px", width: "100px" }}>Clicks</th>
                      <th style={{ padding: "12px 16px", width: "120px" }}>Impressions</th>
                      <th style={{ padding: "12px 16px", width: "100px" }}>CTR</th>
                      <th style={{ padding: "12px 16px", width: "100px" }}>Avg Pos</th>
                      <th style={{ padding: "12px 16px" }}>Top Search Queries</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gscData.shopify_mapping.matched_products.map((mp) => (
                      <tr key={mp.product_id} style={{ borderBottom: "1px solid #E5E7EB" }}>
                        <td style={{ padding: "12px 16px" }}>
                          <div style={{ fontWeight: "600", color: "#111827" }}>{mp.title}</div>
                          <div style={{ fontSize: "12px", color: "#6B7280" }}>/{mp.handle}</div>
                        </td>
                        <td style={{ padding: "12px 16px", fontWeight: "700", color: "#2563EB" }}>{mp.clicks}</td>
                        <td style={{ padding: "12px 16px" }}>{mp.impressions}</td>
                        <td style={{ padding: "12px 16px", color: "#059669", fontWeight: "600" }}>{mp.ctr}%</td>
                        <td style={{ padding: "12px 16px", fontWeight: "600" }}>{mp.average_position}</td>
                        <td style={{ padding: "12px 16px" }}>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                            {mp.queries.slice(0, 3).map((q, idx) => (
                              <span key={idx} style={{ backgroundColor: "#F3F4F6", padding: "2px 6px", borderRadius: "4px", fontSize: "11px" }}>
                                "{q.query}" ({q.clicks} clicks)
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ padding: "30px", textAlign: "center", color: "#6B7280" }}>
                  {gscStatus?.connected
                    ? "No search console traffic recorded for Shopify products in this date range."
                    : "Connect Search Console with your Google Account above to view organic performance."}
                </div>
              )}
            </div>

            {/* Low Visibility Products Opportunity Section */}
            {gscData?.shopify_mapping?.low_visibility_products && gscData.shopify_mapping.low_visibility_products.length > 0 && (
              <div style={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #E5E7EB", padding: "18px", marginBottom: "20px" }}>
                <h4 style={{ margin: "0 0 8px 0", fontSize: "14px", color: "#D97706" }}>
                  🔍 Low-Visibility Products ({gscData.shopify_mapping.low_visibility_products.length} products with low impressions or 0 clicks)
                </h4>
                <p style={{ margin: "0 0 12px 0", fontSize: "13px", color: "#6B7280" }}>
                  These products appear in search results but receive few or no clicks. Optimizing their SEO titles and meta descriptions can improve click-through rates.
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "10px" }}>
                  {gscData.shopify_mapping.low_visibility_products.slice(0, 6).map((lp) => (
                    <div key={lp.product_id} style={{ border: "1px solid #FED7AA", backgroundColor: "#FFF7ED", padding: "10px 14px", borderRadius: "6px" }}>
                      <div style={{ fontWeight: "600", color: "#9A3412", fontSize: "13px" }}>{lp.title}</div>
                      <div style={{ fontSize: "12px", color: "#7C2D12", marginTop: "4px" }}>
                        Impressions: {lp.impressions} | Clicks: {lp.clicks} | CTR: {lp.ctr}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Unranked Products Indicator */}
            {gscData?.shopify_mapping?.unranked_products && gscData.shopify_mapping.unranked_products.length > 0 && (
              <div style={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #E5E7EB", padding: "18px" }}>
                <h4 style={{ margin: "0 0 8px 0", fontSize: "14px", color: "#B45309" }}>
                  ⚠️ Unranked Products ({gscData.shopify_mapping.unranked_count} products with 0 impressions)
                </h4>
                <p style={{ margin: "0 0 12px 0", fontSize: "13px", color: "#6B7280" }}>
                  These Shopify products currently have zero recorded appearances in Google search results for this date range. Check their indexing status or apply SEO optimizations.
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {gscData.shopify_mapping.unranked_products.slice(0, 15).map((up) => (
                    <span key={up.product_id} style={{ backgroundColor: "#FEF3C7", color: "#92400E", padding: "3px 8px", borderRadius: "4px", fontSize: "12px" }}>
                      {up.title}
                    </span>
                  ))}
                  {gscData.shopify_mapping.unranked_products.length > 15 && (
                    <span style={{ fontSize: "12px", color: "#6B7280", alignSelf: "center" }}>
                      +{gscData.shopify_mapping.unranked_products.length - 15} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: AUDIT HISTORY */}
        {activeTab === "history" && (
          <div style={{ backgroundColor: "#FFFFFF", borderRadius: "8px", border: "1px solid #E5E7EB", padding: "20px" }}>
            <h3 style={{ margin: "0 0 16px 0", fontSize: "18px" }}>SEO Optimization Audit History</h3>
            {history.length === 0 ? (
              <p style={{ color: "#6B7280" }}>No optimization runs recorded yet.</p>
            ) : (
              history.map((run, idx) => (
                <div key={idx} style={{ padding: "14px", border: "1px solid #E5E7EB", borderRadius: "6px", marginBottom: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ fontWeight: "700", color: run.dry_run ? "#4F46E5" : "#059669" }}>
                      {run.dry_run ? "Simulation (Dry Run)" : "Live Store Update"}
                    </span>
                    <span style={{ fontSize: "12px", color: "#6B7280" }}>{run.executed_at}</span>
                  </div>
                  <div style={{ fontSize: "13px", color: "#4B5563" }}>
                    Applied By: {run.applied_by} | Total: {run.total_requested} | Succeeded: {run.successful_updates} | Failed: {run.failed_updates}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Confirmation Modal for Live Updates */}
        {confirmModalOpen && (
          <div style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000
          }}>
            <div style={{
              backgroundColor: "#FFFFFF",
              borderRadius: "8px",
              padding: "24px",
              maxWidth: "500px",
              width: "100%",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)"
            }}>
              <h3 style={{ margin: "0 0 10px 0", color: "#DC2626", fontSize: "18px" }}>
                ⚠️ Confirm Live Shopify SEO Update
              </h3>
              <p style={{ fontSize: "14px", color: "#4B5563", lineHeight: "1.5" }}>
                You are about to apply SEO updates to <strong>{selectedProductIds.size} products</strong> directly on your live Shopify store.
              </p>
              <ul style={{ fontSize: "13px", color: "#4B5563", paddingLeft: "20px", marginBottom: "18px" }}>
                <li>Price, variants, inventory, and status will NOT be altered.</li>
                <li>Only SEO titles, meta descriptions, tags, and image ALTs will be updated.</li>
                <li>{preserveHandles ? "Existing URL handles will be preserved." : "URL handles will be updated."}</li>
              </ul>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  onClick={() => setConfirmModalOpen(false)}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "6px",
                    border: "1px solid #D1D5DB",
                    backgroundColor: "#FFFFFF",
                    cursor: "pointer"
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleApplySelected(true)}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "6px",
                    border: "none",
                    backgroundColor: "#DC2626",
                    color: "#FFFFFF",
                    fontWeight: "600",
                    cursor: "pointer"
                  }}
                >
                  Yes, Apply Live Updates
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
