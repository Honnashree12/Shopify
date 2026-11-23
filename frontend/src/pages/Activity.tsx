import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { useAuth, getDisplayRole } from "../components/AuthContext";
import { api } from "../api/client";

export default function Activity() {
  const { currentUser, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [logs, setLogs] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!currentUser) {
      navigate("/login");
      return;
    }
    if (currentUser.role !== "PLATFORM_ADMIN") {
      navigate("/");
      return;
    }

    let active = true;
    api.getAuditLogs().then(
      (res) => {
        if (active) {
          setLogs(res);
          setLoading(false);
        }
      },
      () => {
        if (active) {
          setLogs([]);
          setLoading(false);
        }
      }
    );

    return () => {
      active = false;
    };
  }, [currentUser, authLoading, navigate]);

  if (authLoading) {
    return (
      <AppShell title="Loading Activity" crumbs="Retrieving audit log stream...">
        <div className="page">
          <div className="skeleton" style={{ height: 200, width: "100%", borderRadius: "var(--radius-lg)" }} />
        </div>
      </AppShell>
    );
  }

  if (!currentUser || currentUser.role !== "PLATFORM_ADMIN") return null;

  return (
    <AppShell title="System Audit Logs" crumbs="Platform Administration / Audit Logs">
      <div className="page">
        <div className="page-header">
          <div>
            <h1>System Audit Logs</h1>
            <p>Chronological trace of operations, user logins, and launch executions across the workspace.</p>
          </div>
        </div>

        <div className="card">
          {loading ? (
            <div style={{ padding: 18 }}>
              <div className="skeleton" style={{ height: 16, marginBottom: 10 }} />
              <div className="skeleton" style={{ height: 16, width: "80%" }} />
            </div>
          ) : !logs || logs.length === 0 ? (
            <div className="empty-state">No audit logs found.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Actor</th>
                  <th>Role</th>
                  <th>Action</th>
                  <th>Details / Description</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, idx) => (
                  <tr key={idx}>
                    <td style={{ color: "var(--text-muted)", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                      {log.timestamp}
                    </td>
                    <td><strong>{log.actor}</strong></td>
                    <td>
                      <span className="pill pill-pending" style={{ fontSize: 11 }}>
                        {getDisplayRole(log.role)}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, fontSize: 12.5, color: "var(--brand-primary)" }}>
                        {log.action}
                      </span>
                    </td>
                    <td style={{ color: "var(--text-secondary)", fontSize: 13 }}>
                      {log.description}
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
