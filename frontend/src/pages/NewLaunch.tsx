import { useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { useAuth } from "../components/AuthContext";
import { api, ApiError } from "../api/client";

type DirectoryInputProps = React.DetailedHTMLProps<React.InputHTMLAttributes<HTMLInputElement>, HTMLInputElement> & {
  webkitdirectory?: string;
  directory?: string;
};

export default function NewLaunch() {
  const { currentUser, loading: authLoading } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [folderName, setFolderName] = useState<string | null>(null);
  const [preview] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (authLoading) return;
    if (!currentUser) {
      navigate("/login");
      return;
    }
    if (currentUser.role !== "CATALOGUE_ADMIN") {
      navigate("/");
    }
  }, [currentUser, authLoading, navigate]);

  if (authLoading) {
    return (
      <AppShell title="Loading Ingest" crumbs="Initializing workspace...">
        <div className="page">
          <div className="skeleton" style={{ height: 200, width: "100%", borderRadius: "var(--radius-lg)" }} />
        </div>
      </AppShell>
    );
  }

  if (!currentUser || currentUser.role !== "CATALOGUE_ADMIN") return null;

  const hasProductJson = files.some((f) => f.webkitRelativePath?.toLowerCase().endsWith("product.json") || f.name.toLowerCase() === "product.json");
  const imagesCount = files.filter(f => /\.(png|jpe?g|webp)$/i.test(f.name)).length;
  const videosCount = files.filter(f => /\.(mp4|mov|avi|mkv)$/i.test(f.name)).length;

  function onFilesSelected(list: FileList | null) {
    if (!list || list.length === 0) return;
    const arr = Array.from(list);
    setFiles(arr);
    const rel = arr[0].webkitRelativePath || arr[0].name;
    setFolderName(rel.split("/")[0] || null);
  }

  async function submit() {
    if (files.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.launchFolder(files, preview);
      navigate(`/launches/${res.session_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the launch. Check the backend connection.");
      setSubmitting(false);
    }
  }

  const dirInputProps: DirectoryInputProps = {
    webkitdirectory: "true",
    directory: "true",
  };

  return (
    <AppShell title="Launch New Product" crumbs="Ingest new product listing from media folder">
      <div className="page fade-in-up" style={{ maxWidth: 880 }}>
        <div className="page-header" style={{ borderBottom: "1px solid var(--surface-border-soft)", paddingBottom: 16, marginBottom: 28 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: "var(--brand-ink)" }}>Launch New Product</h1>
            <p style={{ color: "var(--text-secondary)", marginTop: 4 }}>Prepare and publish a product directly from your local product workspace.</p>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 28 }}>
          {/* LEFT COLUMN: upload details card */}
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <div className="card-premium card-premium--blue" style={{ padding: 24 }}>
              <div className="section-title" style={{ marginBottom: 16 }}>Product Source</div>
              
              <div
                className="dropzone dropzone-premium"
                role="button"
                tabIndex={0}
                onClick={() => inputRef.current?.click()}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
                style={{
                  borderRadius: "var(--radius-lg)",
                  padding: "48px 24px",
                  textAlign: "center",
                  cursor: "pointer",
                  transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                  boxShadow: "inset 0 2px 4px rgba(0,0,0,0.01)"
                }}
              >
                <div style={{ fontSize: 42, marginBottom: 14, animation: "heartbeat 2.5s ease infinite" }} aria-hidden="true">📁</div>
                <strong style={{ fontSize: 16, display: "block", color: "var(--text-primary)" }}>Select Local Product Folder</strong>
                <span style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8, display: "block", lineHeight: 1.4 }}>
                  Drag & drop a product folder here, or click to browse
                </span>
                <span style={{ fontSize: 11, marginTop: 6, background: "var(--brand-accent-soft)", color: "var(--brand-accent)", padding: "4px 10px", borderRadius: 4, display: "inline-block", fontWeight: 700 }}>
                  Folder structure: product.json + media assets
                </span>
              </div>

              <input
                ref={inputRef}
                type="file"
                className="visually-hidden"
                onChange={(e) => onFilesSelected(e.target.files)}
                {...dirInputProps}
              />
            </div>

            {/* Folder contents and validations checklist */}
            {folderName && (
              <div className="card-premium card-premium--emerald fade-in-up" style={{ padding: 24 }}>
                <div className="section-title" style={{ borderBottom: "1px solid var(--surface-border-soft)", paddingBottom: 10, marginBottom: 16 }}>Workspace Analysis</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                  <div>
                    <span style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.03em" }}>Selected Product Directory</span>
                    <strong style={{ display: "block", fontSize: 16, color: "var(--text-primary)", marginTop: 4, background: "var(--surface-2)", padding: "10px 14px", borderRadius: 8, border: "1px solid var(--surface-border-soft)" }}>
                      📁 {folderName}
                    </strong>
                  </div>

                  <div>
                    <span style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.03em" }}>Detected File Manifest</span>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 8 }}>
                      <div className="file-item-animated" style={{ display: "flex", justifyContent: "space-between", fontSize: 13.5, background: "var(--surface-2)", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--surface-border-soft)" }}>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>📄 Product details (product.json)</span>
                        <strong style={{ color: hasProductJson ? "var(--status-success)" : "var(--status-warning)" }}>
                          {hasProductJson ? "Detected ✓" : "Missing ✕"}
                        </strong>
                      </div>
                      <div className="file-item-animated" style={{ display: "flex", justifyContent: "space-between", fontSize: 13.5, background: "var(--surface-2)", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--surface-border-soft)", animationDelay: "0.05s" }}>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>🖼️ Image assets</span>
                        <strong style={{ color: "var(--brand-primary)" }}>{imagesCount} file{imagesCount === 1 ? "" : "s"} ✓</strong>
                      </div>
                      <div className="file-item-animated" style={{ display: "flex", justifyContent: "space-between", fontSize: 13.5, background: "var(--surface-2)", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--surface-border-soft)", animationDelay: "0.1s" }}>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>🎥 Video assets</span>
                        <strong style={{ color: "var(--brand-accent)" }}>{videosCount} file{videosCount === 1 ? "" : "s"} ✓</strong>
                      </div>
                    </div>
                  </div>

                  <div style={{ borderTop: "1px solid var(--surface-border-soft)", paddingTop: 16, marginTop: 4, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 800, textTransform: "uppercase" }}>Validation Status</span>
                      <strong style={{ display: "block", color: "var(--status-success)", fontSize: 14.5, marginTop: 4 }}>Ready to Ingest ✓</strong>
                    </div>
                    
                    <button 
                      className="btn btn-primary" 
                      disabled={submitting || !hasProductJson} 
                      onClick={submit} 
                      style={{ 
                        padding: "12px 24px", 
                        borderRadius: 8, 
                        fontWeight: 700, 
                        background: "linear-gradient(135deg, var(--brand-primary), var(--brand-accent))", 
                        borderColor: "transparent",
                        boxShadow: "0 4px 12px rgba(59, 130, 246, 0.25)" 
                      }}
                    >
                      {submitting ? "Processing Ingest..." : "Start Launch Pipeline"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {error && <div className="callout callout-danger fade-in-up" style={{ boxShadow: "var(--shadow-md)" }}>{error}</div>}
          </div>

          {/* RIGHT COLUMN: how it works guide */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div className="card-premium card-premium--indigo" style={{ padding: 24, background: "linear-gradient(to bottom, #ffffff, #fbfbfe)" }}>
              <div className="section-title" style={{ borderBottom: "1px solid var(--surface-border-soft)", paddingBottom: 10, marginBottom: 16 }}>Launch Pipeline Process</div>
              
              <div style={{ display: "flex", flexDirection: "column", gap: 22, position: "relative" }}>
                {/* Visual vertical connector line */}
                <div style={{ position: "absolute", left: 15, top: 16, bottom: 16, width: 2, background: "rgba(99, 102, 241, 0.15)" }} />

                <div style={{ display: "flex", gap: 14, position: "relative" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg, #3b82f6, #6366f1)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: "#fff", flex: "none", boxShadow: "0 2px 6px rgba(59, 130, 246, 0.2)" }}>01</div>
                  <div>
                    <strong style={{ fontSize: 14, display: "block", color: "var(--text-primary)" }}>Select Product</strong>
                    <span style={{ fontSize: 12.5, color: "var(--text-secondary)", display: "block", marginTop: 4, lineHeight: 1.45 }}>
                      Choose your local folder containing the product schema (`product.json`) and media folders.
                    </span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 14, position: "relative" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg, #6366f1, #a855f7)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: "#fff", flex: "none", boxShadow: "0 2px 6px rgba(99, 102, 241, 0.2)" }}>02</div>
                  <div>
                    <strong style={{ fontSize: 14, display: "block", color: "var(--text-primary)" }}>Validate Data</strong>
                    <span style={{ fontSize: 12.5, color: "var(--text-secondary)", display: "block", marginTop: 4, lineHeight: 1.45 }}>
                      The AI Ingest Agent reads values, checks fields, and runs active duplicate checks against live Shopify catalogs.
                    </span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 14, position: "relative" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg, #a855f7, #ec4899)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: "#fff", flex: "none", boxShadow: "0 2px 6px rgba(168, 85, 247, 0.2)" }}>03</div>
                  <div>
                    <strong style={{ fontSize: 14, display: "block", color: "var(--text-primary)" }}>Stage Media</strong>
                    <span style={{ fontSize: 12.5, color: "var(--text-secondary)", display: "block", marginTop: 4, lineHeight: 1.45 }}>
                      Images and videos are ranked, resized/scaled dynamically, and uploaded to Shopify staged CDN storage.
                    </span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 14, position: "relative" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "linear-gradient(135deg, #10b981, #059669)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: "#fff", flex: "none", boxShadow: "0 2px 6px rgba(16, 185, 129, 0.2)" }}>04</div>
                  <div>
                    <strong style={{ fontSize: 14, display: "block", color: "var(--text-primary)" }}>Publish to Shopify</strong>
                    <span style={{ fontSize: 12.5, color: "var(--text-secondary)", display: "block", marginTop: 4, lineHeight: 1.45 }}>
                      Once approved by the manager, listings are published live.
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
