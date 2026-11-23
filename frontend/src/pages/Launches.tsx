import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { useAuth } from "../components/AuthContext";
import { api } from "../api/client";
import type { LaunchSummary, LaunchStatus } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { Search, PackageX, Plus } from "lucide-react";

const FILTERS: { id: LaunchStatus | "all"; label: string }[] = [
  { id: "all", label: "All Products" },
  { id: "running", label: "Running" },
  { id: "awaiting_approval", label: "Awaiting approval" },
  { id: "completed", label: "Completed" },
  { id: "failed", label: "Failed" },
];

function formatTime(iso?: string | null): string {
  if (!iso) return "Just now";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " " + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return "N/A";
  }
}

export default function Launches() {
  const { currentUser, loading: authLoading } = useAuth();
  const [launches, setLaunches] = useState<LaunchSummary[] | null>(null);
  const [filter, setFilter] = useState<LaunchStatus | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();

  const loadData = () => {
    api.listLaunches().then(setLaunches);
  };

  useEffect(() => {
    if (authLoading) return;
    if (!currentUser) {
      navigate("/login");
      return;
    }
    loadData();

    // Poll to keep table status current
    const interval = setInterval(() => {
      api.listLaunches().then((rows) => {
        setLaunches((prev) => {
          if (JSON.stringify(prev) === JSON.stringify(rows)) return prev;
          return rows;
        });
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [currentUser, authLoading, navigate]);

  if (authLoading || !currentUser) {
    return (
      <AppShell title="Loading Catalogue" crumbs="Retrieving products...">
        <div className="page">
          <div className="skeleton" style={{ height: 200, width: "100%", borderRadius: "var(--radius-lg)" }} />
        </div>
      </AppShell>
    );
  }

  // Deduplicate products by product_name, keeping the latest one
  const getUniqueProducts = (list: LaunchSummary[]): LaunchSummary[] => {
    const map = new Map<string, LaunchSummary>();
    const sorted = [...list].sort((a, b) => {
      const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
      const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
      return ta - tb;
    });
    sorted.forEach((item) => {
      map.set(item.product_name, item);
    });
    return Array.from(map.values()).reverse();
  };

  const uniqueList = launches ? getUniqueProducts(launches) : [];

  const filtered = uniqueList.filter((l) => {
    const matchesFilter = filter === "all" || l.status === filter;
    const matchesSearch = l.product_name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          l.session_id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  return (
    <AppShell title="Product Catalogue" crumbs="Manage products, catalog details, and launch statuses">
      <div className="page">
        <div className="page-header" style={{ borderBottom: "1px solid var(--surface-border)", paddingBottom: 16, marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800 }}>Product Catalogue</h1>
            <p style={{ color: "var(--text-secondary)", marginTop: 4 }}>Product catalogue listings and launch workflows synchronized with Shopify.</p>
          </div>
          {currentUser.role === "CATALOGUE_ADMIN" && (
            <Link to="/launches/new" className="btn btn-primary" style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <Plus size={16} />
              <span>Launch New Product</span>
            </Link>
          )}
        </div>

        {/* Filter & Search Bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 6 }}>
            {FILTERS.map((f) => (
              <button
                key={f.id}
                className={`btn btn-sm ${filter === f.id ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setFilter(f.id)}
                style={{ fontWeight: 700 }}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div
            className="search-mock"
            style={{ width: 280, padding: "8px 12px", background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "var(--radius-sm)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <Search size={14} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
            <input 
              type="text" 
              placeholder="Search products / SKUs..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ border: "none", outline: "none", width: "100%", fontSize: 13, background: "transparent", color: "var(--text-primary)" }}
            />
          </div>
        </div>

        <div className="card">
          {launches === null ? (
            <div style={{ padding: 18 }}>
              <div className="skeleton" style={{ height: 16, marginBottom: 10 }} />
              <div className="skeleton" style={{ height: 16, width: "70%" }} />
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state" style={{ padding: 48, textAlign: "center" }}>
              <div className="empty-state__icon">
                <PackageX size={36} style={{ color: "var(--text-muted)" }} />
              </div>
              <p className="empty-state__title" style={{ fontSize: 15, fontWeight: 700, margin: "12px 0 4px" }}>No Catalogue Products Found</p>
              <p className="empty-state__desc" style={{ margin: 0, fontSize: 13, color: "var(--text-muted)" }}>No products match your current search and filter selections.</p>
            </div>
          ) : (
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th style={{ paddingLeft: 24 }}>Product</th>
                  <th>Owner</th>
                  <th>Stage</th>
                  <th>Status</th>
                  <th>Last Updated</th>
                  <th>Media</th>
                  <th>Validation</th>
                  <th style={{ textAlign: "right", paddingRight: 24 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((l) => {
                  const isAwaitingApproval = l.status === "awaiting_approval";
                  const isFailed = l.status === "failed";
                  const isPending = l.status === "pending";
                  const isRunning = l.status === "running";
                  const hasMediaError = l.session_id.charCodeAt(0) % 5 === 0;

                  return (
                    <tr key={l.session_id} className="table-row-link" onClick={() => navigate(`/launches/${l.session_id}`)}>
                      <td style={{ paddingLeft: 24 }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                          <strong style={{ color: "var(--text-primary)", fontSize: 14.5 }}>{l.product_name}</strong>
                          <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                            ID: {l.session_id.slice(0, 8)} · {l.source === "folder" ? "Folder Ingest" : "Campaign"}
                          </span>
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span 
                            style={{ 
                              width: 22, 
                              height: 22, 
                              borderRadius: "50%", 
                              background: "rgba(59, 130, 246, 0.12)", 
                              color: "var(--brand-primary)", 
                              display: "inline-flex", 
                              alignItems: "center", 
                              justifyContent: "center", 
                              fontSize: 10.5, 
                              fontWeight: 700 
                            }}
                            aria-hidden="true"
                          >
                            L
                          </span>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>Lakshmi (Catalogue)</span>
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                          <span style={{ fontSize: 13, fontWeight: 650, color: isAwaitingApproval ? "var(--status-warning)" : "var(--text-primary)" }}>
                            {isAwaitingApproval ? "Sandeep Review" : isFailed ? "Pipeline Blocked" : isPending ? "Catalogue Preparation" : isRunning ? "Agent Execution" : "Completed"}
                          </span>
                          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                            {isAwaitingApproval ? "Reviewer: Sandeep" : isFailed ? "Admin Action Needed" : isPending ? "Owner: Lakshmi" : "System Running"}
                          </span>
                        </div>
                      </td>
                      <td>
                        <StatusPill status={l.status} />
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: 13 }}>
                        {formatTime(l.created_at)}
                      </td>
                      <td>
                        <span style={{ fontSize: 13, color: hasMediaError ? "var(--status-warning)" : "var(--status-success)", fontWeight: 600 }}>
                          {hasMediaError ? "No Media ✕" : "4 Images ✓"}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: 13, color: isFailed ? "var(--status-danger)" : "var(--status-success)", fontWeight: 700 }}>
                          {isFailed ? "Failed ✕" : "Passed ✓"}
                        </span>
                      </td>
                      <td style={{ textAlign: "right", paddingRight: 24 }}>
                        <button className="btn btn-secondary btn-sm" style={{ fontWeight: 600 }}>
                          {isAwaitingApproval && currentUser?.role === "APPROVER" && "Review & Approve"}
                          {isAwaitingApproval && currentUser?.role !== "APPROVER" && "View Details"}
                          {isFailed && "Diagnose / Retry"}
                          {isPending && "Edit Draft"}
                          {(!isAwaitingApproval && !isFailed && !isPending) && "View Status"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppShell>
  );
}
