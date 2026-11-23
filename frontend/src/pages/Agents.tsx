import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { useAuth } from "../components/AuthContext";
import { api } from "../api/client";

export default function Agents() {
  const { currentUser, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!currentUser) {
      navigate("/login");
      return;
    }

    let active = true;
    api.health().then(
      (res) => {
        if (active) {
          setHealth(res);
          setLoading(false);
        }
      },
      () => {
        if (active) {
          setHealth({ status: "offline" });
          setLoading(false);
        }
      }
    );

    return () => {
      active = false;
    };
  }, [currentUser, authLoading, navigate]);

  if (authLoading || !currentUser) {
    return (
      <AppShell title="Loading Agents" crumbs="Checking connections...">
        <div className="page">
          <div className="skeleton" style={{ height: 200, width: "100%", borderRadius: "var(--radius-lg)" }} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="PRODUCT LAUNCH AGENTS" crumbs="Operations / Launch Agents">
      <div className="page" style={{ maxWidth: 1000 }}>
        <div className="page-header" style={{ marginBottom: 28 }}>
          <div>
            <h1>Product Launch Agents</h1>
            <p>Orchestrate asset ingestion, automated validation checks, and secure publishing loops.</p>
          </div>
        </div>

        {loading ? (
          <div className="skeleton" style={{ height: 260, width: "100%", borderRadius: "var(--radius-lg)" }} />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
            
            {/* Agent Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20 }}>
              
              {/* Card 1: Ingestion Agent */}
              <div className="card card-hover" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <span style={{ fontSize: 24 }} aria-hidden="true">📥</span>
                    <h3 style={{ fontSize: 16, fontWeight: 700, margin: "6px 0 2px 0", color: "var(--text-primary)" }}>Product Ingestion Agent</h3>
                    <span style={{ fontSize: 11.5, color: "var(--text-muted)" }}>Media & attributes parser</span>
                  </div>
                  <span className="pill pill-success">
                    <span className="pill-dot" />
                    ONLINE
                  </span>
                </div>
                <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0, lineHeight: 1.45 }}>
                  Reads local product metadata folders, extracts catalog attributes, and converts media assets into web-ready formats.
                </p>
                <div style={{ borderTop: "1px solid var(--surface-border)", paddingTop: 12, fontSize: 11.5, display: "flex", flexDirection: "column", gap: 4 }}>
                  <div><span style={{ color: "var(--text-muted)" }}>Current task:</span> Standby</div>
                  <div><span style={{ color: "var(--text-muted)" }}>Engine:</span> Gemini Flash 1.5</div>
                </div>
              </div>

              {/* Card 2: Validation Agent */}
              <div className="card card-hover" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <span style={{ fontSize: 24 }} aria-hidden="true">🛡️</span>
                    <h3 style={{ fontSize: 16, fontWeight: 700, margin: "6px 0 2px 0", color: "var(--text-primary)" }}>Product Validation Agent</h3>
                    <span style={{ fontSize: 11.5, color: "var(--text-muted)" }}>Compliance & safety engine</span>
                  </div>
                  <span className="pill pill-success">
                    <span className="pill-dot" />
                    ONLINE
                  </span>
                </div>
                <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0, lineHeight: 1.45 }}>
                  Performs data integrity checks, price bounds validation, and scans descriptions for complete formatting.
                </p>
                <div style={{ borderTop: "1px solid var(--surface-border)", paddingTop: 12, fontSize: 11.5, display: "flex", flexDirection: "column", gap: 4 }}>
                  <div><span style={{ color: "var(--text-muted)" }}>Current task:</span> Idle</div>
                  <div><span style={{ color: "var(--text-muted)" }}>Storage Sync:</span> Firestore DB</div>
                </div>
              </div>

              {/* Card 3: Publishing Agent */}
              <div className="card card-hover" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <span style={{ fontSize: 24 }} aria-hidden="true">🚀</span>
                    <h3 style={{ fontSize: 16, fontWeight: 700, margin: "6px 0 2px 0", color: "var(--text-primary)" }}>Shopify Publishing Agent</h3>
                    <span style={{ fontSize: 11.5, color: "var(--text-muted)" }}>Sync & storefront linker</span>
                  </div>
                  <span className="pill pill-success">
                    <span className="pill-dot" />
                    ONLINE
                  </span>
                </div>
                <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0, lineHeight: 1.45 }}>
                  Initiates connections to Shopify REST API, uploads confirmed catalog data, and verifies Live product listings.
                </p>
                <div style={{ borderTop: "1px solid var(--surface-border)", paddingTop: 12, fontSize: 11.5, display: "flex", flexDirection: "column", gap: 4 }}>
                  <div><span style={{ color: "var(--text-muted)" }}>Current task:</span> Standby</div>
                  <div><span style={{ color: "var(--text-muted)" }}>API Target:</span> Shopify Admin v2024-04</div>
                </div>
              </div>

            </div>

            {/* System connectivity card */}
            <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 24 }} className="workspace-grid">
              
              <div className="card" style={{ padding: 20 }}>
                <div className="section-title">Connectivity Status</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13.5 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--surface-border)", paddingBottom: 8 }}>
                    <strong>Product Launch Agent Engine:</strong>
                    <span style={{ color: "var(--status-success)", fontWeight: 700 }}>● Online & Active</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--surface-border)", paddingBottom: 8 }}>
                    <strong>Google ADK Core Engine:</strong>
                    <span style={{ color: health?.adk_ready ? "var(--status-success)" : "var(--status-danger)", fontWeight: 700 }}>
                      {health?.adk_ready ? "✓ Ready" : "✗ Error / Not Initialized"}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--surface-border)", paddingBottom: 8 }}>
                    <strong>Shopify API Connection:</strong>
                    <span style={{ color: health?.shopify_connectivity === "connected" ? "var(--status-success)" : "var(--status-danger)", fontWeight: 700 }}>
                      {health?.shopify_connectivity === "connected" ? "✓ Connected" : "✗ Connection Required"}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong>Firebase Firestore Connectivity:</strong>
                    <span style={{ color: health?.firestore_connectivity === "connected" ? "var(--status-success)" : "var(--status-warning)", fontWeight: 700 }}>
                      {health?.firestore_connectivity === "connected" ? "✓ Connected" : "⚠ Configuration Required (Local Fallback)"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="card" style={{ padding: 20 }}>
                <div className="section-title">AI Engine Config</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12.5, fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                  <div>MODEL: gemini-1.5-flash</div>
                  <div>MAX_IMAGE_WIDTH: 2048px</div>
                  <div>MEDIA_CONVERSION: ENABLED</div>
                  <div>VERIFICATION: LIVE_MOCK</div>
                </div>
              </div>

            </div>

          </div>
        )}
      </div>
    </AppShell>
  );
}
