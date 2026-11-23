import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { workshopApi, type Workshop } from "../api/workshop";
import { ApiError } from "../api/client";

export default function Workshops() {
  const navigate = useNavigate();
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const fetchWorkshops = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await workshopApi.listWorkshops();
      setWorkshops(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Unable to connect to Workshop Agent Backend (${err.status}): ${err.message}`);
      } else {
        setError("Unable to connect to the Workshop Agent. Please make sure the FastAPI server is running on port 8000.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkshops();
  }, []);

  const getStatusBadge = (status: string) => {
    const s = (status || "draft").toLowerCase();
    if (s === "published") {
      return <span className="status-badge" style={{ background: "rgba(16, 185, 129, 0.15)", color: "#10b981", border: "1px solid rgba(16, 185, 129, 0.3)" }}>🟢 Published</span>;
    }
    if (s === "launch_ready" || s === "approved") {
      return <span className="status-badge" style={{ background: "rgba(139, 92, 246, 0.15)", color: "#a78bfa", border: "1px solid rgba(139, 92, 246, 0.3)" }}>🟣 Ready to Publish</span>;
    }
    if (s === "pending_approval" || s === "generating" || s === "understanding") {
      return <span className="status-badge" style={{ background: "rgba(245, 158, 11, 0.15)", color: "#fbbf24", border: "1px solid rgba(245, 158, 11, 0.3)" }}>🟠 Awaiting Approval</span>;
    }
    if (s === "running") {
      return <span className="status-badge" style={{ background: "rgba(59, 130, 246, 0.15)", color: "#60a5fa", border: "1px solid rgba(59, 130, 246, 0.3)" }}>🔵 Agent Running</span>;
    }
    if (s.includes("failed") || s.includes("error")) {
      return <span className="status-badge" style={{ background: "rgba(239, 68, 68, 0.15)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.3)" }}>🔴 Failed</span>;
    }
    return <span className="status-badge" style={{ background: "rgba(156, 163, 175, 0.15)", color: "#d1d5db", border: "1px solid rgba(156, 163, 175, 0.3)" }}>🟡 Draft</span>;
  };

  const filteredWorkshops = workshops.filter((w) => {
    const matchesSearch = w.name.toLowerCase().includes(search.toLowerCase()) || (w.venue && w.venue.toLowerCase().includes(search.toLowerCase()));
    if (statusFilter === "all") return matchesSearch;
    return matchesSearch && w.status.toLowerCase() === statusFilter.toLowerCase();
  });

  const totalCount = workshops.length;
  const draftCount = workshops.filter((w) => w.status === "draft").length;
  const pendingCount = workshops.filter((w) => ["pending_approval", "generating", "approved", "launch_ready"].includes(w.status.toLowerCase())).length;
  const publishedCount = workshops.filter((w) => w.status === "published").length;

  return (
    <AppShell title="Workshop Setup Agent" crumbs="OPERATIONS / WORKSHOPS">
      <div style={{ padding: "24px 32px", maxWidth: 1400, margin: "0 auto" }}>
        
        {/* Header Section */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.02em" }}>
              Workshop Setup Agent
            </h1>
            <p style={{ fontSize: 13.5, color: "var(--text-muted)", marginTop: 4, margin: 0 }}>
              Create, validate, approve and publish workshops with an AI-powered agent workflow.
            </p>
          </div>
          <Link
            to="/workshops/new"
            className="btn btn--primary"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 18px",
              fontSize: 13.5,
              fontWeight: 600,
              borderRadius: 6,
              textDecoration: "none"
            }}
          >
            <span>+</span> Create Workshop
          </Link>
        </div>

        {/* Summary Metric Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 28 }}>
          <div className="card" style={{ padding: "18px 20px" }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Total Workshops
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "var(--text-primary)", marginTop: 6 }}>
              {loading ? "..." : totalCount}
            </div>
          </div>

          <div className="card" style={{ padding: "18px 20px" }}>
            <div style={{ fontSize: 12, color: "#fbbf24", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Drafts
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#fbbf24", marginTop: 6 }}>
              {loading ? "..." : draftCount}
            </div>
          </div>

          <div className="card" style={{ padding: "18px 20px" }}>
            <div style={{ fontSize: 12, color: "#a78bfa", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Awaiting Approval
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#a78bfa", marginTop: 6 }}>
              {loading ? "..." : pendingCount}
            </div>
          </div>

          <div className="card" style={{ padding: "18px 20px" }}>
            <div style={{ fontSize: 12, color: "#10b981", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Published
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#10b981", marginTop: 6 }}>
              {loading ? "..." : publishedCount}
            </div>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div
            style={{
              padding: "14px 18px",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              borderRadius: 8,
              color: "#f87171",
              fontSize: 13.5,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 24
            }}
          >
            <span>{error}</span>
            <button
              onClick={fetchWorkshops}
              className="btn btn--secondary"
              style={{ padding: "4px 12px", fontSize: 12 }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Filter Controls */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, gap: 16 }}>
          <input
            type="text"
            placeholder="Search workshops by title or venue..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "8px 14px",
              borderRadius: 6,
              border: "1px solid var(--border-color)",
              background: "var(--bg-card)",
              color: "var(--text-primary)",
              fontSize: 13.5,
              width: 320
            }}
          />
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>Filter:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: 6,
                border: "1px solid var(--border-color)",
                background: "var(--bg-card)",
                color: "var(--text-primary)",
                fontSize: 13
              }}
            >
              <option value="all">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="pending_approval">Awaiting Approval</option>
              <option value="published">Published</option>
            </select>
          </div>
        </div>

        {/* Workshops Table */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
              Loading workshops...
            </div>
          ) : filteredWorkshops.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--text-muted)" }}>
              <p style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", margin: "0 0 8px" }}>
                No Workshops Found
              </p>
              <p style={{ fontSize: 13, margin: "0 0 20px" }}>
                {search ? "No workshops match your search filters." : "Create your first workshop to initiate the AI Setup workflow."}
              </p>
              {!search && (
                <Link to="/workshops/new" className="btn btn--primary" style={{ padding: "8px 16px", textDecoration: "none" }}>
                  + Create Workshop
                </Link>
              )}
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13.5 }}>
              <thead>
                <tr style={{ background: "rgba(255, 255, 255, 0.03)", borderBottom: "1px solid var(--border-color)" }}>
                  <th style={{ padding: "14px 20px", fontWeight: 600, color: "var(--text-muted)", fontSize: 12, textTransform: "uppercase" }}>Workshop</th>
                  <th style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text-muted)", fontSize: 12, textTransform: "uppercase" }}>Schedule</th>
                  <th style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text-muted)", fontSize: 12, textTransform: "uppercase" }}>Venue</th>
                  <th style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text-muted)", fontSize: 12, textTransform: "uppercase" }}>Age Group</th>
                  <th style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text-muted)", fontSize: 12, textTransform: "uppercase" }}>Price</th>
                  <th style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text-muted)", fontSize: 12, textTransform: "uppercase" }}>Status</th>
                  <th style={{ padding: "14px 20px", textAlign: "right", fontWeight: 600, color: "var(--text-muted)", fontSize: 12, textTransform: "uppercase" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredWorkshops.map((w) => (
                  <tr
                    key={w.id}
                    style={{
                      borderBottom: "1px solid var(--border-color)",
                      transition: "background 0.15s ease"
                    }}
                  >
                    <td style={{ padding: "16px 20px" }}>
                      <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{w.name}</div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>ID: {w.id}</div>
                    </td>
                    <td style={{ padding: "16px 16px", color: "var(--text-secondary)" }}>
                      {w.date || "TBD"} {w.time ? `• ${w.time}` : ""}
                    </td>
                    <td style={{ padding: "16px 16px", color: "var(--text-secondary)" }}>{w.venue || "Online / TBD"}</td>
                    <td style={{ padding: "16px 16px", color: "var(--text-secondary)" }}>{w.age_group || "All Ages"}</td>
                    <td style={{ padding: "16px 16px", fontWeight: 600, color: "var(--text-primary)" }}>₹{w.price}</td>
                    <td style={{ padding: "16px 16px" }}>{getStatusBadge(w.status)}</td>
                    <td style={{ padding: "16px 20px", textAlign: "right" }}>
                      <button
                        onClick={() => navigate(`/workshops/${w.id}`)}
                        className="btn btn--secondary"
                        style={{
                          padding: "6px 12px",
                          fontSize: 12.5,
                          fontWeight: 600,
                          borderRadius: 6
                        }}
                      >
                        {w.status === "draft"
                          ? "Run Agent"
                          : w.status === "published"
                          ? "View Workflow"
                          : "Review & Workflow"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </AppShell>
  );
}
