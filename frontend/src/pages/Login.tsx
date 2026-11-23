import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../components/AuthContext";
import { auth as firebaseAuthInstance } from "../lib/firebase";

export default function Login() {
  const { login, loginAs } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showDevPanel, setShowDevPanel] = useState(false);

  // Check if Firebase is actually configured/initialized
  const isFirebaseEnabled = !!firebaseAuthInstance;
  const isDevMode = import.meta.env.DEV;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Please enter both email and password.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err: any) {
      console.error("Login failed:", err);
      if (err.message === "Authentication provider not configured.") {
        setError("Firebase Authentication is not configured. Please supply VITE_FIREBASE_* environment variables in your frontend .env file.");
      } else if (err.code === "auth/invalid-credential" || err.code === "auth/user-not-found" || err.code === "auth/wrong-password") {
        setError("Incorrect email or password.");
      } else if (err.code === "auth/too-many-requests") {
        setError("Too many login attempts. Please try again later.");
      } else if (err.code === "auth/user-disabled") {
        setError("This account has been disabled.");
      } else if (err.code === "auth/network-request-failed") {
        setError("Network error. Please check your connection and try again.");
      } else {
        setError(err.message || "An unexpected authentication error occurred.");
      }
    } finally {
      setLoading(false);
    }
  };

  const selectMockRole = (key: "catalogue" | "approver" | "admin") => {
    loginAs(key);
    navigate("/");
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "radial-gradient(circle at top left, #0b1220, #040814)",
        padding: 40,
        color: "#fff",
        position: "relative",
        overflow: "hidden"
      }}
    >
      {/* Grid overlay */}
      <div
        style={{
          position: "absolute",
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundImage: "linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
          pointerEvents: "none"
        }}
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.2fr 1fr",
          maxWidth: 1200,
          width: "100%",
          gap: 60,
          alignItems: "center",
          zIndex: 2,
        }}
        className="login-container"
      >
        {/* LEFT COLUMN: BRAND & WIDGETS */}
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }} className="login-brand-section">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: "linear-gradient(135deg, var(--brand-primary), var(--brand-accent))",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 800,
                fontSize: 18,
                color: "#fff",
                boxShadow: "0 0 20px rgba(36, 84, 255, 0.3)"
              }}
            >
              S
            </div>
            <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
              <strong style={{ fontSize: 16, fontWeight: 800, letterSpacing: "0.03em" }}>SUBHANU COCKPIT</strong>
              <span style={{ fontSize: 11, color: "var(--text-on-dark-muted)" }}>PRODUCT LAUNCH MANAGEMENT</span>
            </div>
          </div>

          <div style={{ display: "inline-flex" }}>
            <span
              style={{
                padding: "4px 12px",
                borderRadius: 999,
                background: "rgba(20, 184, 166, 0.1)",
                border: "1px solid rgba(20, 184, 166, 0.2)",
                color: "var(--brand-accent)",
                fontSize: 11.5,
                fontWeight: 700,
                letterSpacing: "0.03em",
                display: "flex",
                alignItems: "center",
                gap: 6
              }}
            >
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--brand-accent)", animation: "pulse 1.4s ease infinite" }} />
              PRODUCT LAUNCH AGENT • ONLINE • {new Date().toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }).toUpperCase()}
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <h1 style={{ fontSize: 44, fontWeight: 800, margin: 0, lineHeight: 1.15, letterSpacing: "-0.02em" }}>
              Secure <span style={{ background: "linear-gradient(135deg, #2454ff, #14b8a6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>product launch</span> operations workspace for Shopify.
            </h1>
            <p style={{ color: "var(--text-on-dark-muted)", fontSize: 15, lineHeight: 1.5, margin: 0, maxWidth: 520 }}>
              SUBHANU COCKPIT orchestrates your Shopify product ingestions, validation agents, human review gates, and live publishing runs into one unified operations control surface.
            </p>
          </div>

          {/* Grid cards */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)", padding: 16, borderRadius: 12, display: "flex", gap: 12 }}>
              <span style={{ fontSize: 20 }}>🧠</span>
              <div>
                <strong style={{ display: "block", fontSize: 13, fontWeight: 700 }}>LAUNCH AGENT</strong>
                <span style={{ fontSize: 11.5, color: "var(--text-on-dark-muted)" }}>Automated ingest runs</span>
              </div>
            </div>
            <div style={{ background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)", padding: 16, borderRadius: 12, display: "flex", gap: 12 }}>
              <span style={{ fontSize: 20 }}>🚀</span>
              <div>
                <strong style={{ display: "block", fontSize: 13, fontWeight: 700 }}>SHOPIFY PUBLISH</strong>
                <span style={{ fontSize: 11.5, color: "var(--text-on-dark-muted)" }}>Sync live listings</span>
              </div>
            </div>
            <div style={{ background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)", padding: 16, borderRadius: 12, display: "flex", gap: 12 }}>
              <span style={{ fontSize: 20 }}>⚡</span>
              <div>
                <strong style={{ display: "block", fontSize: 13, fontWeight: 700 }}>VALIDATION GATES</strong>
                <span style={{ fontSize: 11.5, color: "var(--text-on-dark-muted)" }}>Automated sanity checks</span>
              </div>
            </div>
            <div style={{ background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)", padding: 16, borderRadius: 12, display: "flex", gap: 12 }}>
              <span style={{ fontSize: 20 }}>🛡️</span>
              <div>
                <strong style={{ display: "block", fontSize: 13, fontWeight: 700 }}>HUMAN APPROVALS</strong>
                <span style={{ fontSize: 11.5, color: "var(--text-on-dark-muted)" }}>Separation of duty guards</span>
              </div>
            </div>
          </div>

          {/* Specs status bar */}
          <div style={{ fontSize: 10.5, fontFamily: "var(--font-mono)", color: "var(--text-on-dark-muted)", display: "flex", gap: 16, opacity: 0.6 }}>
            <span>COCKPIT.V1.2</span>
            <span>●</span>
            <span>NOMINAL</span>
            <span>●</span>
            <span>LATENCY 18MS</span>
            <span>●</span>
            <span>AGENTS • 3 / 3</span>
          </div>
        </div>

        {/* RIGHT COLUMN: LOGIN GLASS CARD */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }} className="login-card-section">
          <div
            className="card card-dark"
            style={{
              width: "100%",
              padding: "40px 32px",
              display: "flex",
              flexDirection: "column",
              gap: 24,
              borderRadius: 16
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "inline-flex" }}>
                <span
                  style={{
                    padding: "3px 10px",
                    borderRadius: 999,
                    background: "rgba(36, 84, 255, 0.1)",
                    border: "1px solid rgba(36, 84, 255, 0.2)",
                    color: "var(--brand-primary)",
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.05em"
                  }}
                >
                  ● SECURE PRODUCT LAUNCH WORKSPACE
                </span>
              </div>
              <h2 style={{ fontSize: 28, fontWeight: 800, margin: 0, color: "#fff", letterSpacing: "-0.02em" }}>
                Welcome to <span style={{ color: "#4f73ff" }}>SUBHANU COCKPIT</span>
              </h2>
              <p style={{ color: "var(--text-on-dark-muted)", fontSize: 13, margin: 0 }}>
                Sign in to your product launch workspace
              </p>
            </div>

            {!isFirebaseEnabled && (
              <div 
                style={{
                  padding: "10px 14px",
                  borderRadius: "var(--radius-md)",
                  background: "rgba(234, 179, 8, 0.1)",
                  border: "1px solid rgba(234, 179, 8, 0.2)",
                  color: "#fbbf24",
                  fontSize: 12.5,
                  fontWeight: 500,
                  lineHeight: 1.4
                }}
              >
                ⚠️ Firebase Authentication is not configured. Supply VITE_FIREBASE_* public variables in the frontend environment to use real sign-in.
              </div>
            )}

            {error && (
              <div 
                style={{
                  padding: "10px 14px",
                  borderRadius: "var(--radius-md)",
                  background: "rgba(220, 38, 38, 0.15)",
                  border: "1px solid rgba(220, 38, 38, 0.25)",
                  color: "#f87171",
                  fontSize: 13,
                  fontWeight: 500,
                  lineHeight: 1.4
                }}
              >
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label htmlFor="email" style={{ fontSize: 11, fontWeight: 700, color: "var(--text-on-dark-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  required
                  placeholder="name@email.com"
                  style={{ 
                    background: "rgba(255, 255, 255, 0.03)", 
                    border: "1px solid rgba(255, 255, 255, 0.1)", 
                    color: "#fff" 
                  }}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <label htmlFor="password" style={{ fontSize: 11, fontWeight: 700, color: "var(--text-on-dark-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                     Password
                  </label>
                  <a href="#forgot" style={{ fontSize: 11, color: "var(--brand-primary)", fontWeight: 700, letterSpacing: "0.05em" }} onClick={(e) => { e.preventDefault(); alert("Please contact Lakshmi or Sandeep to reset your Firebase authentication credentials."); }}>FORGOT?</a>
                </div>
                <div style={{ position: "relative" }}>
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    className="input"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                    required
                    placeholder="••••••••"
                    style={{ 
                      background: "rgba(255, 255, 255, 0.03)", 
                      border: "1px solid rgba(255, 255, 255, 0.1)", 
                      color: "#fff",
                      paddingRight: 40 
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: "absolute",
                      right: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      color: "var(--text-on-dark-muted)",
                      fontSize: 14,
                      cursor: "pointer",
                      padding: 0
                    }}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? "👁️" : "👁️‍🗨️"}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
                style={{
                  padding: "12px",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 700,
                  fontSize: 13.5,
                  marginTop: 10,
                  justifyContent: "center",
                  background: "linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark))",
                  boxShadow: "0 4px 20px rgba(36, 84, 255, 0.3)",
                  border: "none"
                }}
              >
                {loading ? "Verifying..." : "SIGN IN"}
              </button>
            </form>

            {isDevMode && showDevPanel && (
              <div 
                style={{ 
                  marginTop: 8,
                  paddingTop: 20, 
                  borderTop: "1px dashed rgba(255, 255, 255, 0.1)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: 11, color: "#eab308", fontWeight: 700, letterSpacing: 0.5 }}>
                    DEVELOPMENT ONLY · MOCK AUTHENTICATION
                  </strong>
                  <button 
                    type="button" 
                    onClick={() => setShowDevPanel(false)}
                    style={{ background: "none", border: "none", color: "var(--text-on-dark-muted)", fontSize: 11, cursor: "pointer", fontWeight: 600 }}
                  >
                    Hide
                  </button>
                </div>
                
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => selectMockRole("catalogue")}
                    style={{
                      justifyContent: "flex-start",
                      padding: "10px 14px",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid rgba(234, 179, 8, 0.2)",
                      background: "rgba(255, 255, 255, 0.03)",
                      color: "#fff"
                    }}
                  >
                    <span style={{ fontSize: 15, marginRight: 6 }}>✍</span>
                    <div style={{ textAlign: "left", lineHeight: 1.2 }}>
                      <strong style={{ display: "block", fontSize: 13 }}>Catalogue Manager (Mock)</strong>
                      <span style={{ fontSize: 11, color: "var(--text-on-dark-muted)" }}>Lakshmi (Prepare drafts & submit)</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => selectMockRole("approver")}
                    style={{
                      justifyContent: "flex-start",
                      padding: "10px 14px",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid rgba(234, 179, 8, 0.2)",
                      background: "rgba(255, 255, 255, 0.03)",
                      color: "#fff"
                    }}
                  >
                    <span style={{ fontSize: 15, marginRight: 6 }}>✓</span>
                    <div style={{ textAlign: "left", lineHeight: 1.2 }}>
                      <strong style={{ display: "block", fontSize: 13 }}>Product Launch Manager (Mock)</strong>
                      <span style={{ fontSize: 11, color: "var(--text-on-dark-muted)" }}>Sandeep (Review and approve)</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => selectMockRole("admin")}
                    style={{
                      justifyContent: "flex-start",
                      padding: "10px 14px",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid rgba(234, 179, 8, 0.2)",
                      background: "rgba(255, 255, 255, 0.03)",
                      color: "#fff"
                    }}
                  >
                    <span style={{ fontSize: 15, marginRight: 6 }}>⚙</span>
                    <div style={{ textAlign: "left", lineHeight: 1.2 }}>
                      <strong style={{ display: "block", fontSize: 13 }}>Platform Administrator (Mock)</strong>
                      <span style={{ fontSize: 11, color: "var(--text-on-dark-muted)" }}>Monitor system metrics & audit logs</span>
                    </div>
                  </button>
                </div>
              </div>
            )}

            {isDevMode && !showDevPanel && (
              <div style={{ textAlign: "center", marginTop: 4 }}>
                <button
                  type="button"
                  onClick={() => setShowDevPanel(true)}
                  style={{
                    background: "none",
                    border: "none",
                    fontSize: 12,
                    color: "#eab308",
                    cursor: "pointer",
                    fontWeight: 600,
                    textDecoration: "underline"
                  }}
                >
                  Development Testing Mode
                </button>
              </div>
            )}

            <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: 16, textAlign: "center" }}>
              <span style={{ fontSize: 11, color: "var(--text-on-dark-muted)", fontWeight: 500 }}>
                Authorized users only. Access is monitored and audited.
              </span>
            </div>
          </div>
        </div>
      </div>
      
      {/* CSS style tag specifically for split screen layout responsive media queries */}
      <style>{`
        @media (max-width: 900px) {
          .login-container {
            grid-template-columns: 1fr !important;
            gap: 40px !important;
          }
          .login-brand-section {
            text-align: center;
            align-items: center;
          }
          .login-brand-section p {
            margin: 0 auto !important;
          }
        }
      `}</style>
    </div>
  );
}
