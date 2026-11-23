import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { PipelineTimeline } from "../components/PipelineTimeline";
import { StatusPill } from "../components/StatusPill";
import { useAuth } from "../components/AuthContext";
import { api, ApiError } from "../api/client";
import { deriveActivityFeed } from "../api/pipeline";
import type { ProductLaunchState } from "../api/types";

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const { currentUser, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [state, setState] = useState<ProductLaunchState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit fields for Catalogue Admin (Lakshmi) resubmission
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPrice, setEditPrice] = useState("");
  const [editSku, setEditSku] = useState("");
  const [editQty, setEditQty] = useState("");

  // Review comment for Approver (Sandeep)
  const [reviewComment, setReviewComment] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);
  const [showApproveConfirm, setShowApproveConfirm] = useState(false);
  const [duplicateAction, setDuplicateAction] = useState<string>("CREATE");
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    if (!currentUser) {
      navigate("/login");
    }
  }, [currentUser, authLoading, navigate]);

  useEffect(() => {
    if (authLoading || !currentUser) return;
    let cancelled = false;
    if (!id) return;

    const loadData = () => {
      api.getStatus(id).then(
        (res) => {
          if (cancelled) return;
          setState(res);
          setLoading(false);
          // Prefill edit values
          setEditName(res.product_name || "");
          setEditDesc(res.raw_description || "");
          setEditPrice(res.price?.toString() || "");
          setEditSku(res.sku || "");
          setEditQty(res.inventory_quantity?.toString() || "");
          if (res.duplicate_action) {
            setDuplicateAction(res.duplicate_action);
          }
        },
        (err) => {
          if (cancelled) return;
          setError(err instanceof ApiError ? err.message : "Failed to load product status.");
          setLoading(false);
        }
      );
    };

    loadData();

    // Poll if status is running, pending, or awaiting_approval to capture transitions instantly
    const timer = setInterval(() => {
      if (state && (state.status === "running" || state.status === "pending" || state.status === "awaiting_approval")) {
        api.getStatus(id).then((res) => {
          if (!cancelled) setState(res);
        });
      }
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [id, state?.status, currentUser, authLoading]);

  if (authLoading || loading) {
    return (
      <AppShell title="Loading Product" crumbs="Retrieving pipeline status...">
        <div className="page">
          <div className="skeleton" style={{ height: 200, width: "100%", borderRadius: "var(--radius-lg)" }} />
        </div>
      </AppShell>
    );
  }

  if (error || !state) {
    return (
      <AppShell title="Error" crumbs="Failed to find launch session">
        <div className="page">
          <div className="card" style={{ padding: 30, textAlign: "center" }}>
            <span style={{ fontSize: 32 }} aria-hidden="true">✕</span>
            <h2 style={{ fontSize: 18, fontWeight: 800, color: "var(--status-danger)", marginTop: 12 }}>Launch Session Not Found</h2>
            <p style={{ color: "var(--text-secondary)", marginTop: 6 }}>{error || "The session details could not be loaded from database."}</p>
            <Link to="/" className="btn btn-primary" style={{ marginTop: 16 }}>Back to Cockpit</Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const handleApprove = async () => {
    setSubmittingReview(true);
    try {
      if (state.source === "folder") {
        await api.approveFolderLaunch(id!, {
          approved_to_publish: true,
          duplicate_action: duplicateAction,
          product_name: editName || state.product_name,
          product_description: editDesc || state.raw_description,
          product_price: editPrice ? parseFloat(editPrice) : (state.price ?? undefined),
          sku: editSku || state.sku || undefined,
          inventory_quantity: editQty ? parseInt(editQty) : (state.inventory_quantity ?? undefined),
        });
      } else {
        await api.approveProduct(id!);
      }
      const updated = await api.getStatus(id!);
      setState(updated);
      setShowApproveConfirm(false);
      setReviewComment("");
    } catch (e: any) {
      alert("Failed to approve product: " + e.message);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleRequestChanges = async () => {
    if (!reviewComment.trim()) return;
    setSubmittingReview(true);
    try {
      await api.requestProductChanges(id!, reviewComment);
      const updated = await api.getStatus(id!);
      setState(updated);
      setReviewComment("");
    } catch (e: any) {
      alert("Failed to request changes: " + e.message);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleUpdateDetails = async () => {
    setSubmittingReview(true);
    try {
      await api.updateProduct(id!, {
        product_name: editName,
        product_description: editDesc,
        product_price: editPrice ? parseFloat(editPrice) : undefined,
        sku: editSku,
        inventory_quantity: editQty ? parseInt(editQty) : undefined,
      });
      const updated = await api.getStatus(id!);
      setState(updated);
      setIsEditing(false);
      if (state.status === "completed") {
        alert("Product edits saved successfully! The product status has reverted to Pending Draft. Please submit for review to publish live.");
      } else {
        alert("Product details updated successfully.");
      }
    } catch (e: any) {
      alert("Failed to update product details: " + e.message);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleResubmit = async () => {
    setSubmittingReview(true);
    try {
      await api.updateProduct(id!, {
        product_name: editName,
        product_description: editDesc,
        product_price: editPrice ? parseFloat(editPrice) : undefined,
        sku: editSku,
        inventory_quantity: editQty ? parseInt(editQty) : undefined,
      });
      await api.submitProduct(id!);
      const updated = await api.getStatus(id!);
      setState(updated);
      setIsEditing(false);
      alert("Product changes saved and submitted for review successfully.");
    } catch (e: any) {
      alert("Failed to submit: " + e.message);
    } finally {
      setSubmittingReview(false);
    }
  };

  const changesComment = state.errors["review_comment"];
  const activities = deriveActivityFeed(state);

  const hasMedia = (state.detected_images?.length ?? 0) > 0;
  const isMissingProductIdError = state.status === "failed" && 
    (state.errors["workflow_error"]?.toLowerCase().includes("product id") || 
     state.errors["workflow_error"]?.toLowerCase().includes("product_id") || 
     !state.shopify_product_id && state.failed_stage === "create");

  return (
    <AppShell title={state.product_name} crumbs={`Product Catalogue / Launch Session: ${id?.slice(0, 8)}`}>
      <div className="page fade-in-up">
        <div style={{ marginBottom: 20 }}>
          <Link to="/" className="btn btn-secondary btn-sm" style={{ boxShadow: "var(--shadow-sm)", gap: 6 }}>
            <span>←</span> Back to Cockpit
          </Link>
        </div>

        {changesComment && (
          <div className="callout callout-warning fade-in-up" style={{ marginBottom: 24, borderLeft: "4px solid var(--status-warning)", boxShadow: "var(--shadow-md)" }}>
            <strong>⚠ Product Launch Manager Feedback (Sandeep):</strong>
            <p style={{ marginTop: 6, marginBottom: 0, lineHeight: 1.5 }}>{changesComment}</p>
          </div>
        )}

        {/* Horizontal Stepper Timeline */}
        <div className="card-premium card-premium--blue fade-in-up" style={{ marginBottom: 32, padding: "20px 24px" }}>
          <div className="section-title" style={{ marginBottom: 16 }}>Launch Pipeline Status</div>
          <PipelineTimeline state={state} />
        </div>

        <div className="workspace-grid">
          {/* LEFT PANEL: PRODUCT DATA CATEGORIES */}
          <div className="card-premium card-premium--blue workspace-panel fade-in-up" style={{ display: "flex", flexDirection: "column", gap: 18, animationDelay: "0.1s" }}>
            <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--surface-border-soft)", paddingBottom: 10 }}>
              <span>Product Details</span>
              {state.status !== "running" && !isEditing && (currentUser?.role === "CATALOGUE_ADMIN" || currentUser?.role === "APPROVER") && (
                <button 
                  className="btn btn-secondary btn-sm"
                  onClick={() => setIsEditing(true)}
                  style={{ padding: "6px 12px", fontSize: 11, fontWeight: 700, borderRadius: 6, boxShadow: "var(--shadow-sm)" }}
                >
                  ✏️ Edit Details
                </button>
              )}
            </div>

            {isEditing ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase" }}>Title</label>
                  <input className="input" type="text" value={editName} onChange={(e) => setEditName(e.target.value)} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--surface-border)" }} />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase" }}>Description</label>
                  <textarea className="input" rows={5} value={editDesc} onChange={(e) => setEditDesc(e.target.value)} style={{ fontFamily: "inherit", padding: "10px 12px", borderRadius: 8, border: "1px solid var(--surface-border)" }} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase" }}>Price (₹)</label>
                    <input className="input" type="number" value={editPrice} onChange={(e) => setEditPrice(e.target.value)} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--surface-border)" }} />
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase" }}>SKU</label>
                    <input className="input" type="text" value={editSku} onChange={(e) => setEditSku(e.target.value)} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--surface-border)" }} />
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase" }}>Inventory Quantity</label>
                  <input className="input" type="number" value={editQty} onChange={(e) => setEditQty(e.target.value)} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--surface-border)" }} />
                </div>
                
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  {currentUser?.role === "CATALOGUE_ADMIN" ? (
                    <>
                      <button className="btn btn-primary btn-sm" style={{ flex: 1, padding: "8px 12px" }} onClick={handleUpdateDetails} disabled={submittingReview}>
                        Save Changes
                      </button>
                      {(state.status === "failed" || state.status === "pending") && (
                        <button className="btn btn-primary btn-sm" style={{ flex: 1, background: "var(--brand-accent)", borderColor: "var(--brand-accent)", padding: "8px 12px" }} onClick={handleResubmit} disabled={submittingReview}>
                          Save & Submit
                        </button>
                      )}
                    </>
                  ) : (
                    <button className="btn btn-primary btn-sm" style={{ flex: 1, padding: "8px 12px" }} onClick={() => setIsEditing(false)} disabled={submittingReview}>
                      Apply Local Edits
                    </button>
                  )}
                  <button className="btn btn-secondary btn-sm" style={{ padding: "8px 12px" }} onClick={() => {
                    setEditName(state.product_name || "");
                    setEditDesc(state.raw_description || "");
                    setEditPrice(state.price?.toString() || "");
                    setEditSku(state.sku || "");
                    setEditQty(state.inventory_quantity?.toString() || "");
                    setIsEditing(false);
                  }}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div className="field-row" style={{ padding: "10px 0" }}>
                  <span className="field-row__label" style={{ fontWeight: 600 }}>Product Title</span>
                  <span className="field-row__value" style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                    {editName || state.product_name}
                    {editName && editName !== state.product_name && (
                      <span className="pill pill-warning" style={{ fontSize: 9, marginLeft: 6, padding: "2px 6px", borderRadius: 4 }}>Modified</span>
                    )}
                  </span>
                </div>
                <div className="field-row" style={{ padding: "10px 0" }}>
                  <span className="field-row__label" style={{ fontWeight: 600 }}>Price</span>
                  <span className="field-row__value" style={{ fontWeight: 800, color: "var(--brand-primary)" }}>
                    ₹{editPrice || state.price || "N/A"}
                    {editPrice && editPrice !== state.price?.toString() && (
                      <span className="pill pill-warning" style={{ fontSize: 9, marginLeft: 6, padding: "2px 6px", borderRadius: 4 }}>Modified</span>
                    )}
                  </span>
                </div>
                <div className="field-row" style={{ padding: "10px 0" }}>
                  <span className="field-row__label" style={{ fontWeight: 600 }}>Category</span>
                  <span className="field-row__value">{state.category || "N/A"}</span>
                </div>
                <div className="field-row" style={{ padding: "10px 0" }}>
                  <span className="field-row__label" style={{ fontWeight: 600 }}>SKU</span>
                  <span className="field-row__value" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
                    {editSku || state.sku || "N/A"}
                    {editSku && editSku !== state.sku && (
                      <span className="pill pill-warning" style={{ fontSize: 9, marginLeft: 6, padding: "2px 6px", borderRadius: 4 }}>Modified</span>
                    )}
                  </span>
                </div>
                <div className="field-row" style={{ padding: "10px 0" }}>
                  <span className="field-row__label" style={{ fontWeight: 600 }}>Stock Quantity</span>
                  <span className="field-row__value">
                    {editQty || (state.inventory_quantity ?? "N/A")}
                    {editQty && editQty !== state.inventory_quantity?.toString() && (
                      <span className="pill pill-warning" style={{ fontSize: 9, marginLeft: 6, padding: "2px 6px", borderRadius: 4 }}>Modified</span>
                    )}
                  </span>
                </div>
                <div className="field-row" style={{ padding: "10px 0" }}>
                  <span className="field-row__label" style={{ fontWeight: 600 }}>Vendor</span>
                  <span className="field-row__value" style={{ fontWeight: 500 }}>{state.vendor || "Subhanu"}</span>
                </div>
                <div className="field-row" style={{ padding: "10px 0" }}>
                  <span className="field-row__label" style={{ fontWeight: 600 }}>Tags</span>
                  <span className="field-row__value">
                    {state.tags?.map((tag, i) => (
                      <span key={i} className="pill" style={{ background: "var(--surface-2)", border: "1px solid var(--surface-border)", fontSize: 11, padding: "2px 6px", borderRadius: 4, marginRight: 4 }}>
                        {tag}
                      </span>
                    )) || "None"}
                  </span>
                </div>
                <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--surface-border-soft)" }}>
                  <span className="field-row__label" style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>
                    Description
                    {editDesc && editDesc !== state.raw_description && (
                      <span className="pill pill-warning" style={{ fontSize: 9, marginLeft: 6, padding: "2px 6px", borderRadius: 4 }}>Modified</span>
                    )}
                  </span>
                  <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0, whiteSpace: "pre-wrap" }}>
                    {editDesc || state.raw_description}
                  </p>
                </div>

                {currentUser?.role === "CATALOGUE_ADMIN" && (state.status === "failed" || state.status === "pending") && (
                  <button className="btn btn-primary" onClick={handleResubmit} disabled={submittingReview} style={{ marginTop: 20, width: "100%", padding: "12px", borderRadius: 8 }}>
                    {submittingReview ? "Submitting..." : "Submit for Review"}
                  </button>
                )}
              </div>
            )}

            {/* Media list section */}
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--surface-border-soft)" }}>
              <div className="section-title" style={{ marginBottom: 12 }}>Media Files</div>
              {state.detected_images && state.detected_images.length > 0 ? (
                <div style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 6 }}>
                  {state.detected_images.map((_, idx) => (
                    <div key={idx} className="file-item-animated" style={{ position: "relative", flex: "none", width: 68, height: 68, borderRadius: "var(--radius-md)", border: "1px solid var(--surface-border)", overflow: "hidden", background: "#fbfbfb", boxShadow: "var(--shadow-sm)", animationDelay: `${idx * 0.05}s` }}>
                      <span style={{ position: "absolute", bottom: 4, right: 4, background: "rgba(15, 20, 31, 0.75)", color: "#fff", padding: "2px 4px", borderRadius: 4, fontSize: 8, fontWeight: 700 }}>IMG</span>
                      <div style={{ display: "flex", alignItems: "center", justifyItems: "center", width: "100%", height: "100%", fontSize: 20, justifyContent: "center" }}>🖼️</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12.5, color: "var(--text-muted)", fontStyle: "italic" }}>No media files detected.</div>
              )}
            </div>
          </div>

          {/* MIDDLE PANEL: STOREFRONT PREVIEW */}
          <div className="card-premium card-premium--indigo workspace-panel fade-in-up" style={{ display: "flex", flexDirection: "column", gap: 18, animationDelay: "0.2s" }}>
            <div className="section-title" style={{ borderBottom: "1px solid var(--surface-border-soft)", paddingBottom: 10 }}>Shopify Storefront Preview</div>
            <div className="browser-mock" style={{ boxShadow: "var(--shadow-pop)", borderRadius: "var(--radius-lg)", border: "1px solid var(--surface-border)" }}>
              <div className="browser-mock__header" style={{ background: "linear-gradient(to bottom, #f8fafc, #f1f5f9)" }}>
                <div className="browser-mock__dots">
                  <span className="browser-mock__dot browser-mock__dot--red" style={{ width: 10, height: 10 }} />
                  <span className="browser-mock__dot browser-mock__dot--yellow" style={{ width: 10, height: 10 }} />
                  <span className="browser-mock__dot browser-mock__dot--green" style={{ width: 10, height: 10 }} />
                </div>
                <div className="browser-mock__url" style={{ padding: "4px 20px", fontSize: 11, borderRadius: 8 }}>
                  shop.subhanu.in/products/{(state.sku || "product").toLowerCase()}
                </div>
                <div className="browser-mock__live-tag" style={{ background: "rgba(16, 185, 129, 0.12)", padding: "3px 8px", borderRadius: 12 }}>
                  <span className="browser-mock__live-dot" style={{ background: "var(--status-success)" }} />
                  <span style={{ fontSize: 9.5, fontWeight: 800 }}>PREVIEW</span>
                </div>
              </div>
              
              <div className="browser-mock__body" style={{ padding: 24, background: "#ffffff" }}>
                {hasMedia ? (
                  <div 
                    style={{ 
                      background: "linear-gradient(135deg, #e0e7ff 0%, #e0f2fe 100%)", 
                      borderRadius: "var(--radius-md)", 
                      height: 190, 
                      display: "flex", 
                      alignItems: "center", 
                      justifyContent: "center", 
                      fontSize: 54, 
                      marginBottom: 20,
                      border: "1px solid rgba(99, 102, 241, 0.1)",
                      boxShadow: "inset 0 2px 8px rgba(99, 102, 241, 0.05)"
                    }}
                  >
                    🛍️
                  </div>
                ) : (
                  <div 
                    style={{ 
                      background: "var(--surface-2)", 
                      height: 190, 
                      borderRadius: "var(--radius-md)", 
                      display: "flex", 
                      flexDirection: "column", 
                      alignItems: "center", 
                      justifyContent: "center", 
                      border: "1px dashed rgba(94, 114, 228, 0.3)", 
                      color: "var(--text-muted)", 
                      fontSize: 13, 
                      textAlign: "center", 
                      padding: 16,
                      marginBottom: 20
                    }}
                  >
                    <span style={{ fontSize: 28, marginBottom: 8 }} aria-hidden="true">🖼️</span>
                    <strong style={{ fontSize: 12, letterSpacing: "0.06em", color: "var(--text-secondary)" }}>MEDIA PREVIEW UNAVAILABLE</strong>
                    <span style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>No product media detected.</span>
                  </div>
                )}
                
                <span className="pill" style={{ background: "rgba(99, 102, 241, 0.1)", color: "var(--brand-accent)", fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, display: "inline-block", marginBottom: 8 }}>
                  {state.category || "STOREFRONT item"}
                </span>
                
                <h3 style={{ fontSize: 20, fontWeight: 800, margin: "0 0 8px 0", color: "var(--text-primary)", letterSpacing: "-0.01em" }}>
                  {editName || state.product_name}
                </h3>
                
                <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 16 }}>
                  <span style={{ fontSize: 22, fontWeight: 850, color: "var(--brand-primary)" }}>₹{editPrice || state.price || "0.00"}</span>
                  <span style={{ fontSize: 13, color: "var(--text-muted)", textDecoration: "line-through" }}>
                    ₹{((editPrice ? parseFloat(editPrice) : (state.price || 0)) * 1.25).toFixed(2)}
                  </span>
                  <span className="pill pill-success" style={{ fontSize: 9.5, padding: "1px 6px", borderRadius: 4, fontWeight: 700 }}>20% OFF</span>
                </div>
                
                <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, margin: "0 0 24px 0", height: 80, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical" }}>
                  {editDesc || state.raw_description || "No product description available."}
                </p>
                
                {state.status === "completed" && state.shopify_url ? (
                  <a 
                    href={state.shopify_url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-primary"
                    style={{ 
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "100%", 
                      background: "linear-gradient(135deg, var(--brand-primary), var(--brand-accent))", 
                      borderColor: "transparent", 
                      padding: "13px 18px",
                      textDecoration: "none",
                      color: "#fff",
                      cursor: "pointer",
                      borderRadius: 8,
                      fontWeight: 700,
                      boxShadow: "0 4px 12px rgba(59, 130, 246, 0.3)"
                    }}
                  >
                    View Storefront Listing ↗
                  </a>
                ) : (
                  <button 
                    disabled 
                    className="btn btn-primary"
                    style={{ width: "100%", background: "var(--brand-ink)", borderColor: "transparent", cursor: "not-allowed", opacity: 0.8, padding: "13px 18px", borderRadius: 8, fontWeight: 750 }}
                  >
                    Publish Pending Approve
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* RIGHT PANEL: ACTIONS & TIMELINE LOGS */}
          <div className="card-premium card-premium--slate workspace-panel fade-in-up" style={{ display: "flex", flexDirection: "column", gap: 18, animationDelay: "0.3s" }}>
            <div className="section-title" style={{ borderBottom: "1px solid var(--surface-border-soft)", paddingBottom: 10 }}>Workflow Logs & Actions</div>

            {/* Status box */}
            <div style={{ display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "space-between", background: "var(--surface-2)", padding: 14, borderRadius: "var(--radius-md)", border: "1px solid var(--surface-border)" }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)" }}>Workflow status:</span>
              <StatusPill status={state.status} />
            </div>

            {state.status === "running" && state.current_stage && (
              <div style={{ fontSize: 12.5, color: "var(--text-secondary)", textAlign: "center", fontWeight: 600, background: "rgba(59, 130, 246, 0.08)", padding: "10px", borderRadius: 8 }}>
                Publishing agent is currently on: <strong style={{ color: "var(--brand-primary)" }}>{String(state.current_stage).toUpperCase()}</strong>
              </div>
            )}

            {state.status === "awaiting_approval" && (
              <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic", textAlign: "center", lineHeight: 1.4 }}>
                Awaiting Product Launch Manager authorization before publishing.
              </div>
            )}

            {state.status === "completed" && state.shopify_product_id && (
              <div style={{ background: "var(--status-success-bg)", padding: 14, borderRadius: "var(--radius-md)", border: "1px solid #a7f3d0" }}>
                <div style={{ fontSize: 13, fontWeight: 850, marginBottom: 10, color: "var(--status-success)" }}>Shopify Live Manifest</div>
                <div className="field-row">
                  <span className="field-row__label">Shopify Product ID</span>
                  <span className="field-row__value">{state.shopify_product_id}</span>
                </div>
                {state.shopify_url && (
                  <div className="field-row">
                    <span className="field-row__label">Storefront URL</span>
                    <a href={state.shopify_url} target="_blank" rel="noreferrer" className="field-row__value" style={{ color: "var(--brand-primary)", textDecoration: "underline" }}>
                      View on Shopify ↗
                    </a>
                  </div>
                )}
                <div className="field-row">
                  <span className="field-row__label">Verification</span>
                  <span className="field-row__value" style={{ color: "var(--status-success)" }}>
                    {(state.verification_result as { purchasable?: boolean } | null)?.purchasable ? "Passed (Active)" : "Passed (Draft)"}
                  </span>
                </div>
              </div>
            )}

            {/* Awaiting human review card */}
            {currentUser?.role === "APPROVER" && state.status === "awaiting_approval" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12, background: "var(--status-warning-bg)", padding: 18, borderRadius: "var(--radius-lg)", border: "1px solid #fde68a" }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "var(--status-warning)" }}>Approval Decision Required</span>
                
                {/* Duplicate options warning inside Detail review */}
                {state.duplicate_detected && (
                  <div style={{ background: "#ffffff", border: "1px dashed #fcd34d", borderRadius: 8, padding: 10, fontSize: 12 }}>
                    <strong style={{ color: "var(--status-warning)", display: "block", marginBottom: 4 }}>Duplicate Detected</strong>
                    An existing product matching title was found on Shopify storefront (ID: {state.existing_product_id}).
                    <div style={{ marginTop: 6 }}>
                      <select 
                        className="input" 
                        value={duplicateAction} 
                        onChange={(e) => setDuplicateAction(e.target.value)} 
                        style={{ padding: "4px 8px", fontSize: 12, background: "#fff" }}
                      >
                        <option value="CREATE">Create New Duplicate Anyway</option>
                        <option value="UPDATE">Update Existing Listing</option>
                        <option value="SKIP">Skip Creation & Link</option>
                      </select>
                    </div>
                  </div>
                )}

                {showApproveConfirm ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    <p style={{ fontSize: 12.5, color: "var(--text-primary)", margin: 0, lineHeight: 1.4 }}>Are you sure you want to approve this product to publish live on Shopify?</p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-primary btn-sm" onClick={handleApprove} disabled={submittingReview}>
                        {submittingReview ? "Confirming..." : "Yes, Approve"}
                      </button>
                      <button className="btn btn-secondary btn-sm" onClick={() => setShowApproveConfirm(false)}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <textarea
                      placeholder="Add review feedback comment here (Required for Change Requests)..."
                      value={reviewComment}
                      onChange={(e) => setReviewComment(e.target.value)}
                      rows={3}
                      className="input"
                      style={{ background: "#ffffff", border: "1px solid var(--surface-border)", fontSize: 13, fontFamily: "inherit" }}
                    />
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={() => setShowApproveConfirm(true)}>Approve & Publish</button>
                      <button
                        className="btn btn-danger btn-sm"
                        style={{ flex: 1 }}
                        onClick={handleRequestChanges}
                        disabled={!reviewComment.trim() || submittingReview}
                      >
                        Request Changes
                      </button>
                    </div>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      * Changes request comment is mandatory.
                    </span>
                  </>
                )}
              </div>
            )}

            {/* Product ID is missing error layout */}
            {isMissingProductIdError && (
              <div style={{ background: "var(--status-danger-bg)", padding: 18, borderRadius: "var(--radius-lg)", border: "1px solid #fecaca", display: "flex", flexDirection: "column", gap: 12 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "var(--status-danger)", textTransform: "uppercase" }}>VALIDATION FAILED</span>
                <p style={{ fontSize: 12.5, color: "var(--text-primary)", margin: 0, lineHeight: 1.4 }}>
                  Shopify product ID is missing from the current launch state.
                </p>
                <div style={{ background: "#ffffff", border: "1px solid var(--surface-border)", padding: 10, borderRadius: 8, fontSize: 12 }}>
                  <strong style={{ display: "block", marginBottom: 2 }}>WHY THIS HAPPENED</strong>
                  The product creation step did not return a valid Shopify product identifier.
                </div>
                <div style={{ background: "#ffffff", border: "1px solid var(--surface-border)", padding: 10, borderRadius: 8, fontSize: 12 }}>
                  <strong style={{ display: "block", marginBottom: 2 }}>RECOMMENDED ACTION</strong>
                  Retry product creation or inspect the workflow state logs.
                </div>
                {currentUser?.role === "PLATFORM_ADMIN" && (
                  <button
                    className="btn btn-danger"
                    style={{ width: "100%" }}
                    disabled={submittingReview}
                    onClick={async () => {
                      setSubmittingReview(true);
                      try {
                        await api.retryProduct(id!);
                        const updated = await api.getStatus(id!);
                        setState(updated);
                      } catch (e: any) {
                        alert("Retry failed: " + e.message);
                      } finally {
                        setSubmittingReview(false);
                      }
                    }}
                  >
                    {submittingReview ? "Retrying..." : "Retry Create"}
                  </button>
                )}
              </div>
            )}

            {/* Standard technical error diagnostics block for Admin */}
            {!isMissingProductIdError && state.status === "failed" && (
              <div style={{ background: "var(--status-danger-bg)", padding: 14, borderRadius: "var(--radius-lg)", border: "1px solid #fecaca", display: "flex", flexDirection: "column", gap: 12 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "var(--status-danger)", display: "block" }}>Pipeline Error Diagnostics</span>
                <div className="error-block">
                  {state.errors["workflow_error"] || "Unknown error inside Google ADK module."}
                </div>
                {currentUser?.role === "PLATFORM_ADMIN" && (
                  <button
                    className="btn btn-danger"
                    style={{ width: "100%" }}
                    disabled={submittingReview}
                    onClick={async () => {
                      setSubmittingReview(true);
                      try {
                        await api.retryProduct(id!);
                        const updated = await api.getStatus(id!);
                        setState(updated);
                      } catch (e: any) {
                        alert("Retry failed: " + e.message);
                      } finally {
                        setSubmittingReview(false);
                      }
                    }}
                  >
                    {submittingReview ? "Retrying..." : `Retry From Failed Stage (${String(state.failed_stage || "unknown").toUpperCase()})`}
                  </button>
                )}
              </div>
            )}

            {/* Duplicate product warning card if not review page */}
            {state.duplicate_detected && state.status !== "awaiting_approval" && (
              <div style={{ background: "var(--status-warning-bg)", padding: 14, borderRadius: "var(--radius-lg)", border: "1px solid #fde68a", display: "flex", flexDirection: "column", gap: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "var(--status-warning)", textTransform: "uppercase" }}>DUPLICATE PRODUCT DETECTED</span>
                <p style={{ fontSize: 12.5, color: "var(--text-primary)", margin: 0, lineHeight: 1.4 }}>
                  "{state.product_name}" already exists on Shopify storefront.
                </p>
                <div style={{ fontSize: 12 }}>
                  Existing Product ID: <strong>{state.existing_product_id}</strong>
                </div>
                {state.existing_product_url && (
                  <a href={state.existing_product_url} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm" style={{ width: "100%" }}>
                    View Existing Product
                  </a>
                )}
              </div>
            )}

            {/* Activity log feed */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div className="section-title">Activity Feed</div>
              {activities.length > 0 ? (
                <ul className="activity-feed" style={{ marginTop: 8 }}>
                  {activities.map((item, idx) => {
                    let tone: "success" | "warning" | "danger" | "info" = "info";
                    if (item.status === "done") tone = "success";
                    else if (item.status === "error") tone = "danger";
                    else if (item.status === "pending") tone = "warning";
                    
                    return (
                      <li key={idx}>
                        <span className={`activity-feed__icon activity-feed__icon--${item.status}`} aria-hidden="true">
                          {tone === "success" ? "✓" : tone === "danger" ? "✕" : tone === "warning" ? "⚠" : "○"}
                        </span>
                        <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{item.label}</span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div style={{ fontSize: 12.5, color: "var(--text-muted)", fontStyle: "italic", padding: "10px 0" }}>Timeline history starting...</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
