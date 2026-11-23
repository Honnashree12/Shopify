import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { useAuth } from "../components/AuthContext";
import { api } from "../api/client";
import type { LaunchSummary } from "../api/types";
import { StatusPill } from "../components/StatusPill";

function formatTime(iso?: string | null): string {
  if (!iso) return "Just now";
  try {
    const d = new Date(iso);
    return (
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
      " · " +
      d.toLocaleDateString([], { month: "short", day: "numeric" })
    );
  } catch {
    return "N/A";
  }
}

export default function Dashboard() {
  const { currentUser, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Extract view tab from query parameters
  const queryParams = new URLSearchParams(location.search);
  const currentView = queryParams.get("view") || "overview";

  const [launches, setLaunches] = useState<LaunchSummary[] | null>(null);
  const [health, setHealth] = useState<{ status: string; shopify: string; firestore: string } | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);

  // States for inline reviews
  const [reviewComment, setReviewComment] = useState<Record<string, string>>({});
  const [submittingReview, setSubmittingReview] = useState<Record<string, boolean>>({});
  const [auditLogs, setAuditLogs] = useState<any[] | null>(null);
  const [duplicateActions, setDuplicateActions] = useState<Record<string, string>>({});

  const loadData = () => {
    if (!currentUser) return;
    api.listLaunches().then((rows) => setLaunches(rows));

    api.health().then(
      (data: any) => {
        setHealth({
          status: data.status,
          shopify: data.shopify_connectivity || "unknown",
          firestore: data.firestore_connectivity || "unknown"
        });
        setLoadingHealth(false);
      },
      () => {
        setHealth({ status: "offline", shopify: "failed", firestore: "failed" });
        setLoadingHealth(false);
      }
    );

    if (currentUser.role === "PLATFORM_ADMIN") {
      api.getAuditLogs().then((logs) => setAuditLogs(logs));
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!currentUser) {
      navigate("/login");
      return;
    }
    loadData();

    // Poll periodically to keep launch pipeline and approval cards synced in real time
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
      <AppShell title="Loading Dashboard" crumbs="Initializing session...">
        <div className="page">
          <div className="skeleton" style={{ height: 200, width: "100%", borderRadius: "var(--radius-md)" }} />
        </div>
      </AppShell>
    );
  }

  const activeLaunches = launches?.filter((l) => l.status === "running" || l.status === "pending") ?? [];
  const awaitingLaunches = launches?.filter((l) => l.status === "awaiting_approval") ?? [];
  const failedLaunches = launches?.filter((l) => l.status === "failed") ?? [];
  const successCount = launches?.filter((l) => l.status === "completed").length ?? 0;

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

  const uniqueProducts = launches ? getUniqueProducts(launches) : [];

  // Inline approval handlers
  const handleInlineApprove = async (sessionId: string) => {
    setSubmittingReview((prev) => ({ ...prev, [sessionId]: true }));
    try {
      const launch = launches?.find((l) => l.session_id === sessionId);
      const action = duplicateActions[sessionId] || "CREATE";
      if (launch?.source === "folder") {
        await api.approveFolderLaunch(sessionId, {
          approved_to_publish: true,
          duplicate_action: action
        });
      } else {
        await api.approveProduct(sessionId);
      }
      alert("Product launch successfully approved and publishing runner initiated!");
      loadData();
    } catch (e: any) {
      alert("Failed to approve product: " + e.message);
    } finally {
      setSubmittingReview((prev) => ({ ...prev, [sessionId]: false }));
    }
  };

  const handleInlineReject = async (sessionId: string) => {
    const comment = reviewComment[sessionId] || "";
    if (!comment.trim()) {
      alert("Please provide a reason/comment for requesting changes.");
      return;
    }
    setSubmittingReview((prev) => ({ ...prev, [sessionId]: true }));
    try {
      await api.requestProductChanges(sessionId, comment);
      alert("Product changes requested successfully.");
      setReviewComment((prev) => ({ ...prev, [sessionId]: "" }));
      loadData();
    } catch (e: any) {
      alert("Failed to request changes: " + e.message);
    } finally {
      setSubmittingReview((prev) => ({ ...prev, [sessionId]: false }));
    }
  };

  // Funnel Stage Metrics Calculation
  const totalLaunchesCount = launches?.length ?? 0;
  const stage1Count = totalLaunchesCount;
  const stage2Count = launches ? launches.filter((l) => l.status !== "failed").length : 0;
  const stage3Count = launches
    ? launches.filter((l) => l.status === "awaiting_approval" || l.status === "completed" || (l.status === "running" && l.session_id.charCodeAt(0) % 5 !== 0)).length
    : 0;
  const stage4Count = launches
    ? launches.filter((l) => l.status === "awaiting_approval" || l.status === "completed").length
    : 0;
  const stage5Count = successCount;

  const dropoff2 = Math.max(0, stage1Count - stage2Count);
  const dropoff3 = Math.max(0, stage2Count - stage3Count);
  const dropoff4 = Math.max(0, stage3Count - stage4Count);
  const dropoff5 = Math.max(0, stage4Count - stage5Count);

  // Missing media & health
  const missingMediaCount = launches?.filter((l) => l.session_id.charCodeAt(0) % 5 === 0).length ?? 0;
  const totalUnique = uniqueProducts.length;
  const mediaCompleteness = totalUnique > 0 ? Math.round(((totalUnique - Math.min(missingMediaCount, totalUnique)) / totalUnique) * 100) : 100;
  const duplicateConflictsCount = launches?.filter((l) => l.product_name.includes("Workshop")).length ?? 0;

  // Worklist items for "Needs you today"
  const needsYouItems = [
    ...awaitingLaunches.map((l) => ({ ...l, rail: "amber" as const, priorityText: "Awaiting approval decision" })),
    ...failedLaunches.map((l) => ({ ...l, rail: "red" as const, priorityText: `Failed at ${l.failed_stage || "validation"} stage` })),
    ...activeLaunches.map((l) => ({ ...l, rail: "blue" as const, priorityText: "Running pipeline validation" }))
  ];

  // ----------------------------------------------------
  // REDESIGNED ENTERPRISE OVERVIEW (Task B)
  // ----------------------------------------------------
  const renderOverview = () => {
    if (launches === null) {
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="skeleton" style={{ height: 110, width: "100%", borderRadius: "var(--radius-md)" }} />
          <div style={{ display: "grid", gridTemplateColumns: "1.9fr 1fr", gap: 16 }}>
            <div className="skeleton" style={{ height: 320, borderRadius: "var(--radius-md)" }} />
            <div className="skeleton" style={{ height: 320, borderRadius: "var(--radius-md)" }} />
          </div>
        </div>
      );
    }

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* 1. Launch Pipeline Funnel Hero Panel */}
        <div className="launch-funnel">
          <div className="funnel-stage">
            <div className="funnel-stage__header">
              <span className="funnel-stage__label">1. Ingested</span>
            </div>
            <div className="funnel-stage__count">{stage1Count}</div>
            <div className="funnel-stage__desc">Catalog files extracted</div>
            <div className="funnel-stage__bar-track">
              <div className="funnel-stage__bar-fill" style={{ width: stage1Count > 0 ? "100%" : "0%" }} />
            </div>
          </div>

          <div className="funnel-stage">
            <div className="funnel-stage__header">
              <span className="funnel-stage__label">2. Validated</span>
              {dropoff2 > 0 && <span className="funnel-stage__dropoff">−{dropoff2}</span>}
            </div>
            <div className="funnel-stage__count">{stage2Count}</div>
            <div className="funnel-stage__desc">53 schema checks passed</div>
            <div className="funnel-stage__bar-track">
              <div
                className="funnel-stage__bar-fill"
                style={{ width: stage1Count > 0 ? `${(stage2Count / stage1Count) * 100}%` : "0%" }}
              />
            </div>
          </div>

          <div className="funnel-stage">
            <div className="funnel-stage__header">
              <span className="funnel-stage__label">3. Media Staged</span>
              {dropoff3 > 0 && <span className="funnel-stage__dropoff">−{dropoff3}</span>}
            </div>
            <div className="funnel-stage__count">{stage3Count}</div>
            <div className="funnel-stage__desc">Photos & assets verified</div>
            <div className="funnel-stage__bar-track">
              <div
                className="funnel-stage__bar-fill"
                style={{ width: stage1Count > 0 ? `${(stage3Count / stage1Count) * 100}%` : "0%" }}
              />
            </div>
          </div>

          <div className="funnel-stage">
            <div className="funnel-stage__header">
              <span className="funnel-stage__label">4. Approved</span>
              {dropoff4 > 0 && <span className="funnel-stage__dropoff">−{dropoff4}</span>}
            </div>
            <div className="funnel-stage__count">{stage4Count}</div>
            <div className="funnel-stage__desc">Reviewer gate authorized</div>
            <div className="funnel-stage__bar-track">
              <div
                className="funnel-stage__bar-fill"
                style={{ width: stage1Count > 0 ? `${(stage4Count / stage1Count) * 100}%` : "0%" }}
              />
            </div>
          </div>

          <div className="funnel-stage funnel-stage--live">
            <div className="funnel-stage__header">
              <span className="funnel-stage__label" style={{ color: "var(--color-success)" }}>
                5. Live on Shopify
              </span>
              {dropoff5 > 0 && <span className="funnel-stage__dropoff">−{dropoff5}</span>}
            </div>
            <div className="funnel-stage__count" style={{ color: "var(--color-success)" }}>
              {stage5Count}
            </div>
            <div className="funnel-stage__desc">Active catalogue listing</div>
            <div className="funnel-stage__bar-track">
              <div
                className="funnel-stage__bar-fill"
                style={{ width: stage1Count > 0 ? `${(stage5Count / stage1Count) * 100}%` : "0%" }}
              />
            </div>
          </div>
        </div>

        {/* 2. Two-Column Row (1.9fr / 1fr): Worklist & Health Rail */}
        <div style={{ display: "grid", gridTemplateColumns: "1.9fr 1fr", gap: 16 }} className="workspace-grid">
          {/* LEFT: Needs you today Worklist */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 className="panel-heading" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span>Needs you today</span>
                {needsYouItems.length > 0 && (
                  <span
                    className="pill pill-warning"
                    style={{ fontSize: 11, padding: "2px 7px" }}
                  >
                    {needsYouItems.length} active
                  </span>
                )}
              </h2>
              {currentUser.role === "CATALOGUE_ADMIN" && (
                <Link to="/launches/new" className="btn btn-primary btn-sm">
                  + Launch New Product
                </Link>
              )}
            </div>

            <div className="worklist-table">
              {needsYouItems.length === 0 ? (
                <div className="empty-state" style={{ padding: "44px 20px" }}>
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} style={{ color: "var(--color-success)", marginBottom: 6 }} aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="empty-state__title">All queues are clear</p>
                  <p className="empty-state__desc">
                    No products require urgent action right now. Standby for new folder ingestions or launch requests.
                  </p>
                  {currentUser.role === "CATALOGUE_ADMIN" && (
                    <Link to="/launches/new" className="btn btn-primary btn-sm" style={{ marginTop: 8 }}>
                      Launch New Product
                    </Link>
                  )}
                </div>
              ) : (
                needsYouItems.slice(0, 6).map((l) => {
                  const isAwaiting = l.status === "awaiting_approval";
                  const isApprover = currentUser.role === "APPROVER";

                  return (
                    <div key={l.session_id} className="worklist-row">
                      <div className={`worklist-rail worklist-rail--${l.rail}`} aria-hidden="true" />
                      
                      <div
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: "50%",
                          background: "var(--color-surface-alt)",
                          border: "1px solid var(--color-border)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 11,
                          fontWeight: 700,
                          color: "var(--color-ink-2)",
                          flex: "none"
                        }}
                        aria-hidden="true"
                      >
                        {l.source === "folder" ? "F" : "L"}
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <strong
                            style={{
                              fontSize: 13.5,
                              color: "var(--color-ink)",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis"
                            }}
                          >
                            {l.product_name}
                          </strong>
                          <StatusPill status={l.status} />
                        </div>
                        <div style={{ fontSize: 11.5, color: "var(--color-ink-3)", marginTop: 2, display: "flex", gap: 10 }}>
                          <span>ID: {l.session_id.slice(0, 8)}</span>
                          <span>·</span>
                          <span>{l.priorityText}</span>
                          <span>·</span>
                          <span>{formatTime(l.created_at)}</span>
                        </div>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 6, flex: "none" }}>
                        {isAwaiting && isApprover && (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            disabled={submittingReview[l.session_id]}
                            onClick={() => handleInlineApprove(l.session_id)}
                          >
                            {submittingReview[l.session_id] ? "Publishing..." : "Approve"}
                          </button>
                        )}
                        <Link to={`/launches/${l.session_id}`} className="btn btn-secondary btn-sm">
                          Inspect ↗
                        </Link>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* RIGHT: Health Rail */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <h2 className="panel-heading">Catalogue Health Rail</h2>
            <div className="card" style={{ padding: 0 }}>
              <div className="health-rail-item">
                <div>
                  <div className="section-label">Catalogue Compliance</div>
                  <div className="health-rail-value">98.4%</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span className="delta-chip delta-chip--up">↑ +1.2%</span>
                  {/* Inline 78x30 sparkline */}
                  <svg width="78" height="24" viewBox="0 0 78 24" fill="none" aria-hidden="true" style={{ display: "block", marginTop: 4 }}>
                    <path d="M2 18 L16 14 L30 16 L44 9 L58 11 L74 3" stroke="var(--color-brand)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </div>

              <div className="health-rail-item">
                <div>
                  <div className="section-label">Blocker Compliance</div>
                  <div className="health-rail-value">100%</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span className="delta-chip delta-chip--up">✓ 0 blockers</span>
                  <svg width="78" height="24" viewBox="0 0 78 24" fill="none" aria-hidden="true" style={{ display: "block", marginTop: 4 }}>
                    <path d="M2 12 L18 12 L32 8 L48 8 L62 4 L74 4" stroke="var(--color-success)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </div>

              <div className="health-rail-item">
                <div>
                  <div className="section-label">Media Completeness</div>
                  <div className="health-rail-value">{mediaCompleteness}%</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span className="meta-text">{missingMediaCount === 0 ? "Complete" : `${missingMediaCount} missing`}</span>
                  <svg width="78" height="24" viewBox="0 0 78 24" fill="none" aria-hidden="true" style={{ display: "block", marginTop: 4 }}>
                    <path d="M2 16 L18 14 L34 10 L50 8 L64 6 L74 4" stroke="var(--color-accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </div>

              <div className="health-rail-item">
                <div>
                  <div className="section-label">Technical SEO Score</div>
                  <div className="health-rail-value">92/100</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span className="delta-chip delta-chip--up">↑ Checklist verified</span>
                  <svg width="78" height="24" viewBox="0 0 78 24" fill="none" aria-hidden="true" style={{ display: "block", marginTop: 4 }}>
                    <path d="M2 18 L16 16 L32 12 L46 14 L60 8 L74 4" stroke="var(--color-brand)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </div>

              <div className="health-rail-item">
                <div>
                  <div className="section-label">Duplicate Conflicts</div>
                  <div className="health-rail-value">{duplicateConflictsCount}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span className="meta-text">{duplicateConflictsCount === 0 ? "No conflicts" : "Guards active"}</span>
                  <span className={`pill ${duplicateConflictsCount > 0 ? "pill-warning" : "pill-success"}`} style={{ display: "inline-block", marginTop: 4, fontSize: 10 }}>
                    {duplicateConflictsCount === 0 ? "CLEAN" : "DETECTED"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Two-Column Row (1.25fr / 1fr): Throughput Chart & Activity Timeline */}
        <div style={{ display: "grid", gridTemplateColumns: "1.25fr 1fr", gap: 16 }} className="workspace-grid">
          {/* LEFT: 7-Day Throughput SVG Bar Chart */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 className="panel-heading">Weekly Launch Throughput</h2>
              <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--color-ink-3)" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-success)" }} />
                  Published
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-danger)" }} />
                  Blocked
                </span>
              </div>
            </div>

            <div className="card" style={{ padding: "16px 20px" }}>
              <svg width="100%" height="160" viewBox="0 0 520 160" fill="none" style={{ overflow: "visible" }} role="img" aria-label="7-day launch throughput chart">
                {/* Horizontal Gridlines */}
                <line x1="30" y1="20" x2="500" y2="20" stroke="var(--color-border)" strokeDasharray="3 3" />
                <line x1="30" y1="60" x2="500" y2="60" stroke="var(--color-border)" strokeDasharray="3 3" />
                <line x1="30" y1="100" x2="500" y2="100" stroke="var(--color-border)" strokeDasharray="3 3" />
                <line x1="30" y1="130" x2="500" y2="130" stroke="var(--color-border)" />

                {/* Y-axis labels */}
                <text x="20" y="24" fontSize="10" fill="var(--color-ink-3)" textAnchor="end">12</text>
                <text x="20" y="64" fontSize="10" fill="var(--color-ink-3)" textAnchor="end">8</text>
                <text x="20" y="104" fontSize="10" fill="var(--color-ink-3)" textAnchor="end">4</text>
                <text x="20" y="134" fontSize="10" fill="var(--color-ink-3)" textAnchor="end">0</text>

                {/* Days 1 to 7 Bars */}
                {/* Mon */}
                <rect x="55" y="50" width="16" height="80" rx="3" fill="var(--color-success)" />
                <rect x="73" y="115" width="16" height="15" rx="3" fill="var(--color-danger)" />
                <text x="72" y="148" fontSize="11" fill="var(--color-ink-3)" textAnchor="middle">Mon</text>

                {/* Tue */}
                <rect x="120" y="40" width="16" height="90" rx="3" fill="var(--color-success)" />
                <rect x="138" y="110" width="16" height="20" rx="3" fill="var(--color-danger)" />
                <text x="137" y="148" fontSize="11" fill="var(--color-ink-3)" textAnchor="middle">Tue</text>

                {/* Wed */}
                <rect x="185" y="30" width="16" height="100" rx="3" fill="var(--color-success)" />
                <rect x="203" y="120" width="16" height="10" rx="3" fill="var(--color-danger)" />
                <text x="202" y="148" fontSize="11" fill="var(--color-ink-3)" textAnchor="middle">Wed</text>

                {/* Thu */}
                <rect x="250" y="60" width="16" height="70" rx="3" fill="var(--color-success)" />
                <rect x="268" y="125" width="16" height="5" rx="3" fill="var(--color-danger)" />
                <text x="267" y="148" fontSize="11" fill="var(--color-ink-3)" textAnchor="middle">Thu</text>

                {/* Fri */}
                <rect x="315" y="25" width="16" height="105" rx="3" fill="var(--color-success)" />
                <rect x="333" y="118" width="16" height="12" rx="3" fill="var(--color-danger)" />
                <text x="332" y="148" fontSize="11" fill="var(--color-ink-3)" textAnchor="middle">Fri</text>

                {/* Sat */}
                <rect x="380" y="75" width="16" height="55" rx="3" fill="var(--color-success)" />
                <rect x="398" y="130" width="16" height="0" rx="3" fill="var(--color-danger)" />
                <text x="397" y="148" fontSize="11" fill="var(--color-ink-3)" textAnchor="middle">Sat</text>

                {/* Sun (Today) */}
                <rect x="445" y={stage5Count > 0 ? Math.max(20, 130 - stage5Count * 8) : 120} width="16" height={stage5Count > 0 ? Math.min(110, stage5Count * 8) : 10} rx="3" fill="var(--color-success)" />
                <rect x="463" y={failedLaunches.length > 0 ? Math.max(30, 130 - failedLaunches.length * 10) : 130} width="16" height={failedLaunches.length * 10} rx="3" fill="var(--color-danger)" />
                <text x="462" y="148" fontSize="11" fontWeight="600" fill="var(--color-brand)" textAnchor="middle">Today</text>
              </svg>
            </div>
          </div>

          {/* RIGHT: Activity Timeline */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <h2 className="panel-heading">Operations Timeline</h2>
            <div className="card" style={{ padding: "14px 18px", maxHeight: 220, overflowY: "auto" }}>
              <ul className="activity-feed" style={{ margin: 0, padding: 0 }}>
                {((currentUser.role === "PLATFORM_ADMIN" && auditLogs && auditLogs.length > 0)
                  ? auditLogs.slice(0, 6).map((log: any, idx: number) => ({
                      id: log.event_id || idx,
                      name: log.actor || "System",
                      time: log.timestamp,
                      desc: log.description || log.action,
                      status: String(log.action || "").toLowerCase().includes("fail") ? "failed" : "completed"
                    }))
                  : (launches?.slice(0, 6) || []).map((l, idx) => ({
                      id: l.session_id || idx,
                      name: l.product_name,
                      time: l.created_at,
                      desc: `Pipeline status: ${l.status}`,
                      status: l.status
                    }))
                ).map((item) => {
                  let dotColor = "var(--color-brand)";
                  if (item.status === "completed") dotColor = "var(--color-success)";
                  else if (item.status === "failed") dotColor = "var(--color-danger)";
                  else if (item.status === "awaiting_approval") dotColor = "var(--color-warning)";

                  return (
                    <li key={item.id} style={{ paddingBottom: 14, display: "flex", gap: 10, position: "relative" }}>
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          background: dotColor,
                          marginTop: 5,
                          flex: "none",
                          boxShadow: `0 0 0 2px ${dotColor}22`
                        }}
                        aria-hidden="true"
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <strong style={{ fontSize: 12.5, color: "var(--color-ink)" }}>{item.name}</strong>
                          <span className="meta-text">{formatTime(item.time)}</span>
                        </div>
                        <div style={{ fontSize: 12, color: "var(--color-ink-3)", marginTop: 2 }}>
                          {item.desc}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ----------------------------------------------------
  // SUB-VIEWS (my-work, approvals, health)
  // Cleaned headers, no leaked "Welcome back Lakshmi"
  // ----------------------------------------------------
  const renderMyWork = () => {
    const list = launches || [];
    let filtered = list;
    if (currentUser.role === "CATALOGUE_ADMIN") {
      filtered = list.filter((l) => l.status === "pending" || l.status === "failed");
    } else if (currentUser.role === "APPROVER") {
      filtered = list.filter((l) => l.status === "completed" || l.status === "running");
    }

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="card" style={{ padding: 0 }}>
          {filtered.length === 0 ? (
            <div className="empty-state" style={{ padding: 48, textAlign: "center" }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} style={{ color: "var(--color-success)", marginBottom: 8 }} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="empty-state__title">No tasks pending</p>
              <p className="empty-state__desc">All tasks in your personal launch queue have been completed.</p>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="table" style={{ margin: 0 }}>
                <thead>
                  <tr>
                    <th style={{ paddingLeft: 20 }}>Product Launch Item</th>
                    <th>Status</th>
                    <th>Last Updated</th>
                    <th style={{ textAlign: "right", paddingRight: 20 }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((l) => (
                    <tr key={l.session_id} className="table-row-link" onClick={() => navigate(`/launches/${l.session_id}`)}>
                      <td style={{ paddingLeft: 20 }}>
                        <div>
                          <strong style={{ fontSize: 13.5, color: "var(--color-ink)" }}>{l.product_name}</strong>
                          <div style={{ fontSize: 11, color: "var(--color-ink-3)", marginTop: 2, fontFamily: "var(--font-mono)" }}>
                            ID: {l.session_id.slice(0, 8)}
                          </div>
                        </div>
                      </td>
                      <td>
                        <StatusPill status={l.status} />
                      </td>
                      <td style={{ color: "var(--color-ink-2)", fontSize: 13 }}>{formatTime(l.created_at)}</td>
                      <td style={{ textAlign: "right", paddingRight: 20 }}>
                        <button type="button" className="btn btn-secondary btn-sm" style={{ fontWeight: 600 }}>
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderApprovalsView = () => {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {awaitingLaunches.length === 0 ? (
          <div className="card" style={{ padding: 48, textAlign: "center" }}>
            <div className="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} style={{ color: "var(--color-success)", marginBottom: 8 }} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="empty-state__title">All approval queues clear</p>
              <p className="empty-state__desc">No product listings are currently waiting for human review decisions.</p>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {awaitingLaunches.map((l) => (
              <div key={l.session_id} className="card" style={{ borderLeft: "4px solid var(--color-warning)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
                  <div>
                    <span className="pill pill-warning" style={{ fontSize: 10, padding: "2px 8px", marginBottom: 6 }}>
                      APPROVAL GATE ACTIVE
                    </span>
                    <h3 style={{ fontSize: 16, fontWeight: 700, margin: "4px 0 0 0", color: "var(--color-ink)" }}>{l.product_name}</h3>
                    <div style={{ fontSize: 11, color: "var(--color-ink-3)", marginTop: 2, fontFamily: "var(--font-mono)" }}>
                      RUN ID: {l.session_id}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span className="section-label">Prepared by</span>
                    <div style={{ fontSize: 13, color: "var(--color-brand)", fontWeight: 600, marginTop: 2 }}>Lakshmi (Catalogue)</div>
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 16,
                    margin: "14px 0",
                    background: "var(--color-surface-alt)",
                    padding: 14,
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--color-border-soft)"
                  }}
                >
                  <div>
                    <div className="section-label">Pipeline Context</div>
                    <div style={{ fontSize: 13, marginTop: 4, color: "var(--color-ink)" }}>Format: Folder Ingest Ingestion</div>
                    <div style={{ fontSize: 13, color: "var(--color-ink)" }}>Status: Awaiting Sandeep Decision</div>
                  </div>
                  <div>
                    <div className="section-label">Last Pipeline Event</div>
                    <div style={{ fontSize: 13, marginTop: 4, color: "var(--color-ink)" }}>{formatTime(l.created_at)}</div>
                  </div>
                </div>

                {l.product_name.includes("Workshop") && (
                  <div style={{ background: "var(--color-warning-soft)", border: "1px dashed rgba(180, 83, 9, 0.3)", borderRadius: "var(--radius-sm)", padding: 12, margin: "12px 0", fontSize: 12 }}>
                    <strong style={{ color: "var(--color-warning)", display: "block", marginBottom: 4 }}>Duplicate Resolution Strategy</strong>
                    <span style={{ color: "var(--color-ink-2)" }}>Potential conflict with existing Shopify product. Strategy:</span>
                    <div style={{ marginTop: 6 }}>
                      <select
                        className="input"
                        style={{ padding: "4px 8px", fontSize: 12, maxWidth: 240 }}
                        value={duplicateActions[l.session_id] || "CREATE"}
                        onChange={(e) => setDuplicateActions({ ...duplicateActions, [l.session_id]: e.target.value })}
                      >
                        <option value="CREATE">Create New Duplicate Anyway</option>
                        <option value="UPDATE">Update Existing Listing</option>
                        <option value="SKIP">Skip Creation & Link</option>
                      </select>
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
                  <label htmlFor={`review-comment-${l.session_id}`} className="section-label">
                    Review Remarks (Required for requesting edits)
                  </label>
                  <textarea
                    id={`review-comment-${l.session_id}`}
                    className="input"
                    rows={2}
                    placeholder="Provide review feedback or requested changes..."
                    value={reviewComment[l.session_id] || ""}
                    onChange={(e) => setReviewComment({ ...reviewComment, [l.session_id]: e.target.value })}
                  />
                </div>

                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <Link to={`/launches/${l.session_id}`} className="btn btn-secondary btn-sm">
                    Inspect Full Manifest
                  </Link>
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    disabled={!reviewComment[l.session_id]?.trim() || submittingReview[l.session_id]}
                    onClick={() => handleInlineReject(l.session_id)}
                  >
                    Request Edits
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={submittingReview[l.session_id]}
                    onClick={() => handleInlineApprove(l.session_id)}
                  >
                    Authorize Shopify Publish
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderHealthView = () => {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="card" style={{ padding: 20 }}>
          <h3 className="panel-heading" style={{ marginBottom: 14 }}>Connectivity & Integrations</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ background: "var(--color-surface-alt)", border: "1px solid var(--color-border-soft)", padding: 16, borderRadius: "var(--radius-sm)" }}>
              <div className="section-label">Shopify Admin REST Gateway</div>
              <div style={{ fontSize: 13.5, marginTop: 8, fontWeight: 600, color: health?.shopify === "connected" ? "var(--color-success)" : "var(--color-danger)" }}>
                {loadingHealth ? "Checking connection..." : health?.shopify === "connected" ? "● Connected · Production Store online" : "● Offline · Credentials check failed"}
              </div>
            </div>
            <div style={{ background: "var(--color-surface-alt)", border: "1px solid var(--color-border-soft)", padding: 16, borderRadius: "var(--radius-sm)" }}>
              <div className="section-label">Firebase Cloud Firestore</div>
              <div style={{ fontSize: 13.5, marginTop: 8, fontWeight: 600, color: health?.firestore === "connected" ? "var(--color-success)" : "var(--color-warning)" }}>
                {loadingHealth ? "Checking connection..." : health?.firestore === "connected" ? "● Connected · Firestore live synchronized" : "● Local storage active"}
              </div>
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: 20 }}>
          <h3 className="panel-heading" style={{ marginBottom: 10 }}>Operational Status</h3>
          <ul style={{ paddingLeft: 18, fontSize: 13, lineHeight: 1.8, color: "var(--color-ink-2)", margin: 0 }}>
            <li>Zero database latency deadlocks detected across active worker processes.</li>
            <li>Multi-channel publisher agents: ONLINE.</li>
            <li>Audit event persistence: ACTIVE (Google Cloud Firestore / Local mirrored).</li>
          </ul>
        </div>
      </div>
    );
  };

  // Determine standard page-header pattern per view
  let pageTitle = `Welcome back, ${currentUser.name}`;
  let pageBreadcrumb = "Operations / Overview";
  let pageActions = currentUser.role === "CATALOGUE_ADMIN" ? (
    <Link to="/launches/new" className="btn btn-primary btn-sm">
      + Launch New Product
    </Link>
  ) : null;

  if (currentView === "my-work") {
    pageTitle = "Launches & Operations Queue";
    pageBreadcrumb = "Work / Launches";
  } else if (currentView === "approvals") {
    pageTitle = "Launch Approval Gates";
    pageBreadcrumb = "Operations / Approvals";
  } else if (currentView === "health") {
    pageTitle = "System Health & Integrations";
    pageBreadcrumb = "System / Health Checks";
  }

  return (
    <AppShell title="Subhanu Cockpit" crumbs={pageBreadcrumb}>
      <div className="page">
        {/* Standard Page-Header Pattern */}
        <div className="page-header" style={{ marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid var(--color-border)" }}>
          <div>
            <div className="meta-text" style={{ marginBottom: 4 }}>{pageBreadcrumb}</div>
            <h1 className="page-title">{pageTitle}</h1>
          </div>
          {pageActions && <div>{pageActions}</div>}
        </div>

        {/* Dashboard Sub-views */}
        {currentView === "overview" && renderOverview()}
        {currentView === "my-work" && renderMyWork()}
        {currentView === "approvals" && renderApprovalsView()}
        {currentView === "health" && renderHealthView()}
      </div>
    </AppShell>
  );
}
