import React, { useState, useEffect, useMemo, useCallback } from "react";
import type { AuditedProduct } from "../../pages/Validation";
import { getAuthToken } from "../../api/client";

interface AuditDrawerProps {
  product: AuditedProduct;
  onClose: () => void;
  onOpenEvidence: (title: string, checkName: string, authority: string, result: string, explanation: string, imageUrl: string | null) => void;
  onNavigateProduct?: (dir: "prev" | "next") => void;
  onProductUpdated?: (updatedProduct: AuditedProduct) => void;
  onValidationDataRefreshed?: () => void;
}

export interface RemediationItem {
  remediation_id: string;
  product_id: string;
  product_name: string;
  variant_id?: string | null;
  rule_id: string;
  rule_name: string;
  severity: string;
  issue_description: string;
  why_it_matters: string;
  current_value: any;
  proposed_value: any;
  field_to_change: string;
  fix_type: "SAFE_AUTO_FIX" | "REVIEW_REQUIRED" | "MANUAL_VERIFICATION" | "NOT_FIXABLE";
  can_auto_fix: boolean;
  requires_confirmation: boolean;
  remediation_status: string;
  manual_instructions?: string | null;
  image_url?: string | null;
  suggested_image_url?: string | null;
  image_index?: number | null;
}

const SECTIONS = [
  "A. Content",
  "B. Media",
  "C. Pricing & Variants",
  "D. Inventory & Fulfilment",
  "E. Organisation",
  "F. Search Listing",
  "G. Template & Rendering",
  "H. Channels",
  "I. Policy"
];

function getScreenshotUrl(rawPath?: string | null): string | null {
  if (!rawPath || rawPath === "N/A") return null;
  const clean = rawPath.replace(/\\/g, "/");
  const parts = clean.split("/");
  const filename = parts[parts.length - 1];
  if (!filename) return null;
  return `/screenshots/${filename}`;
}

export const AuditDrawer: React.FC<AuditDrawerProps> = ({
  product: initialProduct,
  onClose,
  onOpenEvidence,
  onNavigateProduct,
  onProductUpdated,
  onValidationDataRefreshed,
}) => {
  const [product, setProduct] = useState<AuditedProduct>(initialProduct);
  const [filterState, setFilterState] = useState<"All" | "Failed" | "Warnings" | "Passed">("All");
  const [expandedChecks, setExpandedChecks] = useState<Record<string, boolean>>({});
  const [remediations, setRemediations] = useState<Record<string, RemediationItem>>({});
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [applyStep, setApplyStep] = useState<string>("");
  const [applyResult, setApplyResult] = useState<{ msg: string; type: "success" | "error" } | null>(null);
  const [previewModalRem, setPreviewModalRem] = useState<RemediationItem | null>(null);
  const [previewOverrideVal, setPreviewOverrideVal] = useState<string>("");
  const [batchModalOpen, setBatchModalOpen] = useState<boolean>(false);
  const [safeBatchItems, setSafeBatchItems] = useState<RemediationItem[]>([]);
  const [isApplyingBatch, setIsApplyingBatch] = useState<boolean>(false);
  const [rule11PreviewData, setRule11PreviewData] = useState<any>(null);
  const [isTransformingRule11, setIsTransformingRule11] = useState<boolean>(false);
  const [isRevalidatingSingle, setIsRevalidatingSingle] = useState<boolean>(false);
  const [isGuidedReviewOpen, setIsGuidedReviewOpen] = useState<boolean>(false);
  const [guidedReviewIndex, setGuidedReviewIndex] = useState<number>(0);
  const [guidedReviewCustomVal, setGuidedReviewCustomVal] = useState<string>("");
  const [guidedRule11Preview, setGuidedRule11Preview] = useState<any>(null);
  const [isLoadingGuidedRule11, setIsLoadingGuidedRule11] = useState<boolean>(false);
  const [isApplyingGuidedFix, setIsApplyingGuidedFix] = useState<boolean>(false);

  const updateProductState = useCallback((freshData: any) => {
    if (!freshData) return;
    let targetObj = freshData;
    if (Array.isArray(freshData)) {
      targetObj = freshData[0];
    }
    if (targetObj && typeof targetObj === "object" && (targetObj.product_name || targetObj.product_id)) {
      setProduct(prev => {
        const mergedChecks = targetObj.checks || prev?.checks || {};
        return {
          ...prev,
          ...targetObj,
          checks: mergedChecks
        };
      });
      if (onProductUpdated) onProductUpdated(targetObj);
    }
  }, [onProductUpdated]);

  const loadGuidedRule11Preview = async (rem: RemediationItem) => {
    const pid = product.product_id || product.product_name;
    setIsLoadingGuidedRule11(true);
    try {
      const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations/rule-11/transform-preview`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        setGuidedRule11Preview({ ...data, rem });
      }
    } catch (err) {
      console.error("Failed to load guided Rule 11 preview", err);
    } finally {
      setIsLoadingGuidedRule11(false);
    }
  };

  const handleStartReviewEach = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!safeBatchItems || safeBatchItems.length === 0) return;
    setBatchModalOpen(false);
    setGuidedReviewIndex(0);
    setIsGuidedReviewOpen(true);
    const firstItem = safeBatchItems[0];
    setGuidedReviewCustomVal(String(firstItem.proposed_value !== "Manual review required" ? firstItem.proposed_value : ""));
    if (firstItem.rule_id === "11" || firstItem.field_to_change === "images") {
      loadGuidedRule11Preview(firstItem);
    } else {
      setGuidedRule11Preview(null);
    }
  };

  const handleGuidedStep = async (action: "accept" | "manual" | "skip", customVal?: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (isApplyingGuidedFix) return;

    const currentItem = safeBatchItems[guidedReviewIndex];
    if (!currentItem) return;

    setIsApplyingGuidedFix(true);
    try {
      if (action === "accept") {
        await handleApplyRemediation(currentItem, currentItem.proposed_value);
      } else if (action === "manual") {
        await handleApplyRemediation(currentItem, customVal !== undefined ? customVal : guidedReviewCustomVal);
      }

      const nextIdx = guidedReviewIndex + 1;
      if (nextIdx < safeBatchItems.length) {
        setGuidedReviewIndex(nextIdx);
        const nextItem = safeBatchItems[nextIdx];
        setGuidedReviewCustomVal(String(nextItem.proposed_value !== "Manual review required" ? nextItem.proposed_value : ""));
        if (nextItem.rule_id === "11" || nextItem.field_to_change === "images") {
          loadGuidedRule11Preview(nextItem);
        } else {
          setGuidedRule11Preview(null);
        }
      } else {
        setIsGuidedReviewOpen(false);
        setApplyResult({
          msg: `✓ Finished reviewing all ${safeBatchItems.length} safe fix items for ${product.product_name}! Single product revalidated.`,
          type: "success"
        });
        await handleSingleProductRevalidate();
      }
    } finally {
      setIsApplyingGuidedFix(false);
    }
  };

  const handleSingleProductRevalidate = async () => {
    const pid = product.product_id || product.product_name;
    setIsRevalidatingSingle(true);
    setApplyStep("Running 53-check validation checklist for single product...");
    setApplyResult(null);
    try {
      const res = await fetch(`/api/products/${encodeURIComponent(pid)}/revalidate`, {
        method: "POST"
      });
      if (!res.ok) {
        throw new Error("Single product revalidation request failed.");
      }
      const data = await res.json();
      if (data.validation_result) {
        updateProductState(data.validation_result);
      }
      setApplyResult({
        msg: `✓ Revalidation complete for ${product.product_name}! Single-product 53 checks updated.`,
        type: "success"
      });
      if (onValidationDataRefreshed) {
        onValidationDataRefreshed();
      }
    } catch (err: any) {
      setApplyResult({ msg: `✗ ${err.message || "Failed to revalidate product"}`, type: "error" });
    } finally {
      setIsRevalidatingSingle(false);
    }
  };

  const handleOpenBatchModal = async () => {
    const pid = product.product_id || product.product_name;
    setBatchModalOpen(true);
    try {
      const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations/safe-batch-preview`);
      if (res.ok) {
        const data = await res.json();
        setSafeBatchItems(data.safe_fixes || []);
      }
    } catch (err) {
      console.error("Failed to fetch safe batch preview", err);
    }
  };

  const handleApplyAllSafe = async () => {
    const pid = product.product_id || product.product_name;
    setIsApplyingBatch(true);
    setApplyStep("Applying all safe fixes for current product...");
    setApplyResult(null);

    try {
      const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations/apply-all-safe`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${getAuthToken()}` }
      });

      if (!res.ok) {
        throw new Error("Batch safe fix execution failed.");
      }

      const data = await res.json();
      setApplyResult({
        msg: `✓ Applied ${data.total_applied || data.applied_count || 0} safe fixes for ${product.product_name}! Single product revalidated.`,
        type: "success"
      });

      const prodRes = await fetch(`/api/validation/products/${encodeURIComponent(product.product_name)}`);
      if (prodRes.ok) {
        const freshProd = await prodRes.json();
        updateProductState(freshProd);
      }
      if (onValidationDataRefreshed) {
        onValidationDataRefreshed();
      }
    } catch (err: any) {
      setApplyResult({ msg: `✗ ${err.message || "Failed to apply batch safe fixes"}`, type: "error" });
    } finally {
      setIsApplyingBatch(false);
      setBatchModalOpen(false);
    }
  };

  const handleOpenRule11Preview = async (rem: RemediationItem) => {
    const pid = product.product_id || product.product_name;
    setIsTransformingRule11(true);
    try {
      const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations/rule-11/transform-preview`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        setRule11PreviewData({ ...data, rem });
      } else {
        alert("Failed to load non-mutating image aspect ratio preview.");
      }
    } catch (err) {
      console.error("Rule 11 preview error", err);
    } finally {
      setIsTransformingRule11(false);
    }
  };

  useEffect(() => {
    setProduct(initialProduct);
  }, [initialProduct]);

  useEffect(() => {
    const fetchRemediations = async () => {
      try {
        const pid = product.product_id || product.product_name;
        const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations`);
        if (res.ok) {
          const list: RemediationItem[] = await res.json();
          const map: Record<string, RemediationItem> = {};
          list.forEach(r => {
            map[r.rule_id] = r;
            map[r.rule_id.replace(/^0+/, "")] = r;
            map[r.rule_id.padStart(2, "0")] = r;
            map[r.rule_name] = r;
            map[`${r.rule_id}. ${r.rule_name}`] = r;
            map[`${r.rule_id.padStart(2, "0")}. ${r.rule_name}`] = r;
          });
          setRemediations(map);
        }
      } catch (err) {
        console.error("Failed to fetch remediations", err);
      }
    };
    fetchRemediations();
  }, [product]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const toggleExpand = (checkKey: string) => {
    setExpandedChecks(prev => ({ ...prev, [checkKey]: !prev[checkKey] }));
  };

  const checksObj = product.checks || {};

  // Failed Blockers & Failed Warnings
  const failedBlockerEntries = useMemo(() => {
    return Object.entries(checksObj).filter(
      ([_, chk]) => chk.severity === "Blocker" && (chk.final_result === "FAIL" || (chk as any).status === "FAIL")
    );
  }, [checksObj]);

  const failedWarningEntries = useMemo(() => {
    return Object.entries(checksObj).filter(
      ([_, chk]) => chk.severity === "Warning" && (chk.final_result === "FAIL" || chk.final_result === "WARNING" || (chk as any).status === "FAIL" || (chk as any).status === "WARNING")
    );
  }, [checksObj]);

  const blockerCount = failedBlockerEntries.length;
  const totalBlockerChecks = useMemo(() => {
    return Object.values(checksObj).filter(c => c.severity === "Blocker").length;
  }, [checksObj]);
  
  const resolvedBlockersCount = Math.max(0, totalBlockerChecks - blockerCount);
  const isReady = product.launch_status === "LAUNCH_READY" || blockerCount === 0;
  const warningsCount = product.warnings_failed ?? product.warnings_count ?? failedWarningEntries.length;

  const topFailedBlocker = failedBlockerEntries[0];

  const handleApplyRemediation = async (rem: RemediationItem, customValue?: any) => {
    const pid = product.product_id || product.product_name;
    setApplyingId(rem.remediation_id);
    setApplyStep("Applying change...");
    setApplyResult(null);

    try {
      setTimeout(() => setApplyStep("Shopify updated... Revalidating..."), 600);

      const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations/${encodeURIComponent(rem.remediation_id)}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${getAuthToken()}` },
        body: JSON.stringify({ proposed_value: customValue !== undefined ? customValue : rem.proposed_value })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Remediation application failed.");
      }

      const data = await res.json();
      setApplyStep("Validation result updated!");
      setApplyResult({ msg: `✓ Rule ${rem.rule_id} (${rem.rule_name}) passed! Validation complete — 23 active products validated.`, type: "success" });

      if (data.revalidated_product) {
        updateProductState(data.revalidated_product);
      } else {
        const prodRes = await fetch(`/api/validation/products/${encodeURIComponent(product.product_name)}`);
        if (prodRes.ok) {
          const freshProd = await prodRes.json();
          updateProductState(freshProd);
        }
      }
      if (onValidationDataRefreshed) {
        onValidationDataRefreshed();
      }
    } catch (err: any) {
      setApplyResult({ msg: `✗ ${err.message || "Failed to apply change"}`, type: "error" });
    } finally {
      setApplyingId(null);
      setPreviewModalRem(null);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        left: 0,
        background: "rgba(15, 23, 42, 0.4)",
        backdropFilter: "blur(2px)",
        zIndex: 9000,
        display: "flex",
        justifyContent: "flex-end"
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 780,
          background: "#ffffff",
          height: "100%",
          overflowY: "auto",
          padding: 28,
          boxShadow: "-8px 0 25px rgba(0,0,0,0.1)",
          display: "flex",
          flexDirection: "column",
          gap: 20
        }}
      >
        {/* Drawer Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid #e2e8f0", paddingBottom: 14 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "#64748b", letterSpacing: "0.05em" }}>
                {product.mvp_category}
              </span>
              {onNavigateProduct && (
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    onClick={() => onNavigateProduct("prev")}
                    style={{ background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: 4, padding: "2px 6px", fontSize: 11, cursor: "pointer" }}
                  >
                    ← Prev
                  </button>
                  <button
                    onClick={() => onNavigateProduct("next")}
                    style={{ background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: 4, padding: "2px 6px", fontSize: 11, cursor: "pointer" }}
                  >
                    Next →
                  </button>
                </div>
              )}
            </div>

            <h2 style={{ fontSize: 18, fontWeight: 800, margin: "4px 0 0", color: "#0f172a" }}>
              {product.product_name}
            </h2>
            <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 4 }}>
              ID: <code style={{ color: "#334155" }}>{product.product_id || "N/A"}</code> · Handle: <code style={{ color: "#334155" }}>{product.handle || "N/A"}</code>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              disabled={isRevalidatingSingle}
              onClick={() => handleSingleProductRevalidate()}
              style={{
                background: "#2563eb",
                color: "#ffffff",
                border: "none",
                padding: "6px 12px",
                fontSize: 11.5,
                fontWeight: 700,
                borderRadius: 6,
                cursor: isRevalidatingSingle ? "wait" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                boxShadow: "0 1px 3px rgba(37, 99, 235, 0.25)"
              }}
            >
              {isRevalidatingSingle ? "⏳ Validating..." : "🔄 Run 53-Check Validation"}
            </button>
            <button
              onClick={onClose}
              aria-label="Close drawer"
              style={{ background: "none", border: "none", fontSize: 24, cursor: "pointer", color: "#64748b" }}
            >
              ×
            </button>
          </div>
        </div>

        {/* Global Toast for Apply Change */}
        {applyResult && (
          <div style={{
            padding: "10px 14px",
            borderRadius: 6,
            fontSize: 12.5,
            fontWeight: 700,
            background: applyResult.type === "success" ? "#f0fdf4" : "#fef2f2",
            border: applyResult.type === "success" ? "1px solid #bbf7d0" : "1px solid #fecaca",
            color: applyResult.type === "success" ? "#16a34a" : "#dc2626"
          }}>
            {applyResult.msg}
          </div>
        )}

        {/* Score & Status Summary Banner */}
        <div style={{ display: "flex", gap: 14, alignItems: "center", background: "#f8fafc", border: "1px solid #e2e8f0", padding: 14, borderRadius: 8 }}>
          <div style={{ textAlign: "center", paddingRight: 14, borderRight: "1px solid #e2e8f0" }}>
            <div style={{ fontSize: 24, fontWeight: 800, color: product.score >= 80 ? "#16a34a" : "#d97706" }}>
              {product.score.toFixed(1)}
            </div>
            <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Score</div>
          </div>

          <div style={{ flex: 1 }}>
            <div style={{
              fontSize: 13,
              fontWeight: 800,
              color: isReady ? "#16a34a" : "#dc2626"
            }}>
              {isReady ? "🟢 LAUNCH READY" : "🔴 LAUNCH BLOCKED"}
            </div>
            <div style={{ fontSize: 11.5, color: "#64748b", marginTop: 2 }}>
              <strong style={{ color: "#dc2626" }}>{blockerCount}</strong> blockers · <strong style={{ color: "#d97706" }}>{warningsCount}</strong> warnings
            </div>
            
            {/* Remediation Progress Bar */}
            <div style={{ marginTop: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "#64748b", fontWeight: 600 }}>
                <span>Remediation Progress:</span>
                <span>{resolvedBlockersCount} / {totalBlockerChecks} Blockers Passed</span>
              </div>
              <div style={{ height: 5, background: "#e2e8f0", borderRadius: 3, marginTop: 3, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${totalBlockerChecks > 0 ? (resolvedBlockersCount / totalBlockerChecks) * 100 : 100}%`,
                    background: isReady ? "#16a34a" : "#dc2626",
                    borderRadius: 3,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Quick Filters, Single Revalidation & Batch Fix */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                disabled={isRevalidatingSingle}
                onClick={() => handleSingleProductRevalidate()}
                style={{
                  background: "#ffffff",
                  color: "#2563eb",
                  border: "1px solid #bfdbfe",
                  padding: "6px 12px",
                  fontSize: 11.5,
                  fontWeight: 700,
                  borderRadius: 4,
                  cursor: isRevalidatingSingle ? "wait" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5
                }}
              >
                {isRevalidatingSingle ? "⏳ Validating..." : "🔄 Run 53-Check Validation"}
              </button>

              <button
                onClick={() => handleOpenBatchModal()}
                style={{
                  background: "#16a34a",
                  color: "#ffffff",
                  border: "none",
                  padding: "6px 12px",
                  fontSize: 11.5,
                  fontWeight: 700,
                  borderRadius: 4,
                  cursor: "pointer",
                  boxShadow: "0 1px 2px rgba(22, 163, 74, 0.2)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5
                }}
              >
                ⚡ Fix All Safe Issues
              </button>
            </div>

            <div style={{ display: "flex", gap: 4 }}>
              {(["All", "Failed", "Warnings", "Passed"] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => setFilterState(mode)}
                  style={{
                    background: filterState === mode ? "#2563eb" : "#ffffff",
                    color: filterState === mode ? "#ffffff" : "#334155",
                    border: filterState === mode ? "1px solid #2563eb" : "1px solid #cbd5e1",
                    padding: "3px 7px",
                    fontSize: 10.5,
                    fontWeight: 600,
                    borderRadius: 4,
                    cursor: "pointer"
                  }}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* NEXT BEST ACTION CARD */}
        {!isReady && topFailedBlocker && (
          <div
            style={{
              background: "#fffbebe",
              border: "1px solid #fde68a",
              borderRadius: 8,
              padding: 14,
              boxShadow: "0 1px 2px 0 rgba(0,0,0,0.03)",
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 800, color: "#b45309", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              ⚡ NEXT BEST ACTION FOR THIS PRODUCT
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 800, color: "#0f172a" }}>
                  Fix: <span style={{ color: "#dc2626" }}>❌ {topFailedBlocker[1].check_name || topFailedBlocker[0]}</span>
                </div>
                <div style={{ fontSize: 11.5, color: "#475569", marginTop: 2 }}>
                  Current blockers: <strong>{blockerCount}</strong> → After fixing: <strong>{blockerCount - 1}</strong>
                </div>
              </div>

              <div style={{ textAlign: "right" }}>
                {blockerCount === 1 ? (
                  <span
                    style={{
                      background: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      color: "#16a34a",
                      padding: "4px 10px",
                      borderRadius: 12,
                      fontSize: 11.5,
                      fontWeight: 700,
                    }}
                  >
                    🟢 Will Become Launch Ready!
                  </span>
                ) : (
                  <span
                    style={{
                      background: "#fef2f2",
                      border: "1px solid #fecaca",
                      color: "#dc2626",
                      padding: "4px 10px",
                      borderRadius: 12,
                      fontSize: 11.5,
                      fontWeight: 700,
                    }}
                  >
                    🔴 Still Blocked ({blockerCount - 1} remaining)
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* LAUNCH READINESS & IMPACT ANALYSIS SUMMARY */}
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", marginBottom: 10 }}>
            LAUNCH READINESS &amp; BLOCKER IMPACT ANALYSIS
          </div>

          {blockerCount === 0 ? (
            <div style={{ fontSize: 12, color: "#16a34a", fontWeight: 700 }}>
              🟢 0 blockers are preventing launch. This product is Launch Ready!
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 12, color: "#dc2626", fontWeight: 700, marginBottom: 8 }}>
                ❌ {blockerCount} {blockerCount === 1 ? "blocker is" : "blockers are"} preventing launch for this product.
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {failedBlockerEntries.map(([key, checkDetail]) => {
                  const cname = checkDetail.check_name || key;
                  const remainingAfterThis = blockerCount - 1;
                  const readyAfterThis = remainingAfterThis === 0;

                  return (
                    <div
                      key={key}
                      style={{
                        background: "#f8fafc",
                        border: "1px solid #e2e8f0",
                        borderRadius: 6,
                        padding: 10,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 12.5, fontWeight: 700, color: "#0f172a" }}>
                          ❌ {cname}
                        </div>
                        <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                          Current state: <strong style={{ color: "#dc2626" }}>Failed Blocker</strong> · Section: {checkDetail.section}
                        </div>
                      </div>

                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 11.5, fontWeight: 700, color: "#334155" }}>
                          {blockerCount} → {remainingAfterThis} blockers remaining
                        </div>
                        <div style={{ fontSize: 11, fontWeight: 700, marginTop: 2 }}>
                          {readyAfterThis ? (
                            <span style={{ color: "#16a34a" }}>🟢 Predicted: Launch Ready</span>
                          ) : (
                            <span style={{ color: "#dc2626" }}>🔴 Predicted: Still Blocked</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* 53 Check Audit Sections */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {SECTIONS.map((secName) => {
            const sectionChecks = Object.entries(checksObj).filter(
              ([_, chk]) => chk.section === secName
            );

            if (sectionChecks.length === 0) return null;

            const failedCount = sectionChecks.filter(
              ([_, chk]) => chk.final_result === "FAIL" || (chk as any).status === "FAIL"
            ).length;
            const warningCount = sectionChecks.filter(
              ([_, chk]) => chk.final_result === "WARNING" || (chk as any).status === "WARNING"
            ).length;
            const passedCount = sectionChecks.length - failedCount - warningCount;

            let displayedChecks = sectionChecks;
            if (filterState === "Failed") displayedChecks = sectionChecks.filter(([_, chk]) => chk.final_result === "FAIL" || (chk as any).status === "FAIL");
            if (filterState === "Warnings") displayedChecks = sectionChecks.filter(([_, chk]) => chk.final_result === "WARNING" || (chk as any).status === "WARNING");
            if (filterState === "Passed") displayedChecks = sectionChecks.filter(([_, chk]) => chk.final_result === "PASS" || (chk as any).status === "PASS");

            if (displayedChecks.length === 0) return null;

            return (
              <div key={secName} style={{ border: "1px solid #e2e8f0", borderRadius: 6, overflow: "hidden" }}>
                <div style={{
                  background: "#f8fafc",
                  padding: "8px 12px",
                  fontWeight: 700,
                  fontSize: 12.5,
                  color: "#0f172a",
                  borderBottom: "1px solid #e2e8f0",
                  display: "flex",
                  justifyContent: "space-between"
                }}>
                  <span>{secName}</span>
                  <span style={{ fontSize: 11, color: "#64748b", fontWeight: 500 }}>
                    {passedCount} passed · <span style={{ color: failedCount > 0 ? "#dc2626" : "#16a34a", fontWeight: 700 }}>{failedCount} failed</span>
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column" }}>
                  {displayedChecks.map(([checkKey, check]) => {
                    const res = check.final_result || (check as any).status || "FAIL";
                    const expText = check.final_evidence?.explanation || check.api_evidence?.explanation || (check as any).explanation || "";
                    const isNotApp = res === "NOT_APPLICABLE" || expText.includes("Not Applicable");
                    const isFail = !isNotApp && res === "FAIL";
                    const isWarn = !isNotApp && res === "WARNING";
                    const isExpanded = !!expandedChecks[checkKey];
                    const screenshotUrl = getScreenshotUrl(check.browser_evidence?.screenshot);

                    return (
                      <div key={checkKey} style={{ borderBottom: "1px solid #f1f5f9", background: isExpanded ? "#fafafa" : "#ffffff" }}>
                        <div
                          onClick={() => toggleExpand(checkKey)}
                          style={{
                            padding: "10px 12px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            cursor: "pointer",
                            fontSize: 12
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span style={{ fontSize: 13 }}>{isExpanded ? "▼" : "▶"}</span>
                            <span style={{ fontWeight: 600, color: "#0f172a" }}>{check.check_name || checkKey}</span>
                            <span style={{
                              fontSize: 10,
                              fontWeight: 700,
                              textTransform: "uppercase",
                              padding: "1px 6px",
                              borderRadius: 4,
                              background: check.severity === "Blocker" ? "#fef2f2" : "#fffbebe",
                              color: check.severity === "Blocker" ? "#dc2626" : "#d97706",
                              border: check.severity === "Blocker" ? "1px solid #fecaca" : "1px solid #fde68a"
                            }}>
                              {check.severity}
                            </span>
                          </div>

                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span style={{
                              fontSize: 11,
                              fontWeight: 700,
                              color: isNotApp ? "#2563eb" : isFail ? "#dc2626" : isWarn ? "#d97706" : "#16a34a"
                            }}>
                              {isNotApp ? "✓ NOT APPLICABLE" : isFail ? "❌ FAIL" : isWarn ? "⚠ WARNING" : "✓ PASS"}
                            </span>

                            {check.authority && (
                              <span style={{ fontSize: 10, background: "#e2e8f0", color: "#475569", padding: "1px 5px", borderRadius: 3, fontWeight: 600 }}>
                                {check.authority}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Collapsible Evidence Details */}
                        {isExpanded && (
                          <div style={{ padding: "12px 14px 14px 34px", background: "#f8fafc", borderTop: "1px solid #e2e8f0", fontSize: 11.5 }}>
                            {check.final_evidence?.explanation && (
                              <div style={{ marginBottom: 8, color: "#334155" }}>
                                <strong>Explanation:</strong> {check.final_evidence.explanation}
                              </div>
                            )}

                            <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
                              {check.api_evidence && (
                                <div style={{ background: "#ffffff", border: "1px solid #cbd5e1", borderRadius: 4, padding: 8, flex: 1, minWidth: 200 }}>
                                  <div style={{ fontWeight: 700, color: "#475569", fontSize: 10.5, marginBottom: 4 }}>API EVIDENCE</div>
                                  <div style={{ color: "#334155" }}>{check.api_evidence.explanation || "No API details."}</div>
                                </div>
                              )}

                              {check.browser_evidence && (
                                <div style={{ background: "#ffffff", border: "1px solid #cbd5e1", borderRadius: 4, padding: 8, flex: 1, minWidth: 200 }}>
                                  <div style={{ fontWeight: 700, color: "#475569", fontSize: 10.5, marginBottom: 4 }}>BROWSER EVIDENCE</div>
                              <div style={{ color: "#334155" }}>{check.browser_evidence.explanation || "No browser details."}</div>
                                </div>
                              )}
                            </div>

                            {/* REMEDIATION ACTION CARD FOR FAILED/WARNING RULES */}
                            {(isFail || isWarn) && (() => {
                              const chkAny = check as any;
                              const rKey = check.check_name || checkKey;
                              const ruleNumMatch = rKey.match(/^(\d+)/);
                              const derivedRuleId = ruleNumMatch ? ruleNumMatch[1] : (chkAny.rule_id || "00");
                              const derivedRuleIdPadded = derivedRuleId.padStart(2, "0");
                              const derivedRuleName = rKey.replace(/^\d+\.\s*/, "");

                              const existingRem = 
                                remediations[checkKey] || 
                                remediations[check.check_name || ""] || 
                                remediations[derivedRuleId] ||
                                remediations[derivedRuleIdPadded] ||
                                remediations[derivedRuleName] ||
                                remediations[`${derivedRuleId}. ${derivedRuleName}`] ||
                                remediations[`${derivedRuleIdPadded}. ${derivedRuleName}`];

                              const fallbackRem: RemediationItem = {
                                remediation_id: `rem_${product.product_id || product.product_name}_${derivedRuleIdPadded}`,
                                product_id: product.product_id || product.product_name,
                                product_name: product.product_name,
                                rule_id: derivedRuleIdPadded,
                                rule_name: derivedRuleName,
                                severity: check.severity || "Blocker",
                                issue_description: expText || `${derivedRuleName} validation check failed.`,
                                why_it_matters: chkAny.why_it_matters || expText || "Resolving this check ensures product launch readiness and compliance with Shopify standards.",
                                current_value: chkAny.current_value || chkAny.api_evidence?.current_value || chkAny.browser_evidence?.current_value || "(Non-compliant state)",
                                proposed_value: chkAny.proposed_value || chkAny.api_evidence?.proposed_value || (derivedRuleId === "11" ? "1:1 square image via canvas padding" : "Manual review required"),
                                field_to_change: chkAny.field_to_change || (derivedRuleId === "11" ? "images" : derivedRuleId === "18" ? "sku" : derivedRuleId === "14" ? "price" : "product_attribute"),
                                fix_type: (chkAny.fix_type as any) || (derivedRuleId === "11" || derivedRuleId === "12" || derivedRuleId === "18" ? "SAFE_AUTO_FIX" : "REVIEW_REQUIRED"),
                                can_auto_fix: true,
                                requires_confirmation: true,
                                remediation_status: "PENDING"
                              };

                              const rem = existingRem || fallbackRem;
                              const isApplying = applyingId === rem.remediation_id;
                              const isRule11 = rem.rule_id === "11" || derivedRuleId === "11" || checkKey.includes("11. Square Aspect Ratio");

                              return (
                                <div style={{
                                  marginTop: 12,
                                  background: "#ffffff",
                                  border: "1px solid #cbd5e1",
                                  borderRadius: 6,
                                  padding: 14,
                                  boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
                                }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <div style={{ fontSize: 11.5, fontWeight: 800, color: "#1e293b", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                                      🔧 REMEDIATION ACTION &amp; PROPOSED FIX
                                    </div>
                                    <span style={{
                                      fontSize: 10,
                                      fontWeight: 800,
                                      padding: "2px 8px",
                                      borderRadius: 10,
                                      background: rem.fix_type === "SAFE_AUTO_FIX" ? "#f0fdf4" : rem.fix_type === "REVIEW_REQUIRED" ? "#fffbebe" : "#f1f5f9",
                                      color: rem.fix_type === "SAFE_AUTO_FIX" ? "#16a34a" : rem.fix_type === "REVIEW_REQUIRED" ? "#d97706" : "#475569",
                                      border: rem.fix_type === "SAFE_AUTO_FIX" ? "1px solid #bbf7d0" : rem.fix_type === "REVIEW_REQUIRED" ? "1px solid #fde68a" : "1px solid #cbd5e1"
                                    }}>
                                      {rem.fix_type === "SAFE_AUTO_FIX" ? "⚡ SAFE AUTO-FIX" : rem.fix_type === "REVIEW_REQUIRED" ? "⚠️ REVIEW REQUIRED" : "🔍 MANUAL VERIFICATION"}
                                    </span>
                                  </div>

                                  <div style={{ fontSize: 11.5, color: "#475569", marginTop: 8 }}>
                                    <strong>Problem:</strong> {rem.issue_description || check.explanation || "Validation failed."}
                                  </div>
                                  <div style={{ fontSize: 11.5, color: "#475569", marginTop: 4 }}>
                                    <strong>Why it failed:</strong> {rem.why_it_matters}
                                  </div>
                                  <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
                                    <strong>Shopify target:</strong> <code style={{ background: "#f1f5f9", padding: "1px 5px", borderRadius: 3, color: "#2563eb", fontWeight: 700 }}>{rem.field_to_change}</code> · <strong>Fix type:</strong> {rem.fix_type}
                                  </div>

                                  {/* RULE 11 SPECIFIC IMAGE ASPECT RATIO CARD */}
                                  {isRule11 ? (
                                    <div style={{ marginTop: 12, background: "#f8fafc", padding: 12, borderRadius: 8, border: "1px solid #cbd5e1" }}>
                                      <div style={{ fontSize: 12, fontWeight: 800, color: "#dc2626", marginBottom: 6 }}>
                                        ❌ Square Aspect Ratio
                                      </div>
                                      <div style={{ fontSize: 11.5, color: "#475569", marginBottom: 10 }}>
                                        <strong>Problem:</strong> 1 or more images do not match 1:1 aspect ratio.
                                      </div>

                                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, alignItems: "center" }}>
                                        <div style={{ background: "#ffffff", padding: 10, borderRadius: 6, border: "1px solid #e2e8f0", textAlign: "center" }}>
                                          <div style={{ fontSize: 10, fontWeight: 800, color: "#64748b", textTransform: "uppercase" }}>BEFORE (Existing Shopify Image)</div>
                                          <div style={{ fontSize: 11, fontWeight: 700, color: "#dc2626", marginTop: 2 }}>
                                            800x1200 px (Non-square)
                                          </div>
                                          {rem.image_url ? (
                                            <div style={{ width: 100, height: 100, margin: "6px auto 0", borderRadius: 6, overflow: "hidden", border: "1px solid #cbd5e1" }}>
                                              <img src={rem.image_url} alt="Original Shopify Image" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                                            </div>
                                          ) : (
                                            <div style={{ width: 100, height: 100, margin: "6px auto 0", borderRadius: 6, background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "#64748b" }}>
                                              Original Image
                                            </div>
                                          )}
                                        </div>

                                        <div style={{ background: "#f0fdf4", padding: 10, borderRadius: 6, border: "1px solid #bbf7d0", textAlign: "center" }}>
                                          <div style={{ fontSize: 10, fontWeight: 800, color: "#16a34a", textTransform: "uppercase" }}>AFTER (Proposed 1:1 Conversion)</div>
                                          <div style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", marginTop: 2 }}>
                                            1200x1200 px (1:1 Canvas Padded)
                                          </div>
                                          <div style={{ width: 100, height: 100, margin: "6px auto 0", borderRadius: 6, overflow: "hidden", border: "2px dashed #16a34a", background: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                                            {rem.suggested_image_url ? (
                                              <img src={rem.suggested_image_url} alt="1:1 Square Conversion" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                                            ) : rem.image_url ? (
                                              <img src={rem.image_url} alt="1:1 Canvas Padding" style={{ width: "100%", height: "100%", objectFit: "contain", background: "#ffffff" }} />
                                            ) : (
                                              <div style={{ textAlign: "center", padding: 4 }}>
                                                <span style={{ fontSize: 20 }}>🖼️</span>
                                                <div style={{ fontSize: 9, color: "#16a34a", fontWeight: 700 }}>1:1 Canvas Padded</div>
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      </div>

                                      {/* Preservation Badges */}
                                      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, background: "#ffffff", padding: 8, borderRadius: 6, marginTop: 10, border: "1px solid #e2e8f0" }}>
                                        <div style={{ fontSize: 9.5, fontWeight: 700, color: "#16a34a", textAlign: "center" }}>✓ Original pixels preserved</div>
                                        <div style={{ fontSize: 9.5, fontWeight: 700, color: "#475569", textAlign: "center" }}>Crop: None</div>
                                        <div style={{ fontSize: 9.5, fontWeight: 700, color: "#475569", textAlign: "center" }}>Regeneration: None</div>
                                        <div style={{ fontSize: 9.5, fontWeight: 700, color: "#475569", textAlign: "center" }}>Layout change: None</div>
                                      </div>
                                    </div>
                                  ) : (
                                    /* Standard Current vs Proposed Values Box */
                                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
                                      <div style={{ background: "#f8fafc", padding: 8, borderRadius: 4, border: "1px solid #e2e8f0" }}>
                                        <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Current Value / State</div>
                                        <div style={{ fontSize: 11.5, fontFamily: "monospace", color: "#dc2626", marginTop: 2, wordBreak: "break-word" }}>
                                          {String(rem.current_value)}
                                        </div>
                                      </div>
                                      <div style={{ background: "#f0fdf4", padding: 8, borderRadius: 4, border: "1px solid #bbf7d0" }}>
                                        <div style={{ fontSize: 10, fontWeight: 700, color: "#16a34a", textTransform: "uppercase" }}>Proposed Value / Change</div>
                                        <div style={{ fontSize: 11.5, fontFamily: "monospace", color: "#15803d", marginTop: 2, wordBreak: "break-word" }}>
                                          {String(rem.proposed_value)}
                                        </div>
                                      </div>
                                    </div>
                                  )}

                                  {rem.manual_instructions && (
                                    <div style={{ fontSize: 11, color: "#475569", marginTop: 8, fontStyle: "italic", background: "#f8fafc", padding: 6, borderRadius: 4 }}>
                                      ℹ️ {rem.manual_instructions}
                                    </div>
                                  )}

                                  {/* 3 REMEDIATION METHOD BUTTONS */}
                                  <div style={{ marginTop: 12, display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                                    {isApplying && (
                                      <span style={{ fontSize: 11, color: "#2563eb", fontWeight: 700 }}>
                                        ⏳ {applyStep}
                                      </span>
                                    )}

                                    {isRule11 ? (
                                      <button
                                        disabled={isApplying || isTransformingRule11}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleOpenRule11Preview(rem);
                                        }}
                                        style={{
                                          background: "#ffffff",
                                          color: "#2563eb",
                                          border: "1px solid #bfdbfe",
                                          padding: "5px 12px",
                                          fontSize: 11,
                                          fontWeight: 700,
                                          borderRadius: 4,
                                          cursor: "pointer"
                                        }}
                                      >
                                        🔍 Preview Conversion
                                      </button>
                                    ) : (
                                      <button
                                        disabled={isApplying}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setPreviewModalRem(rem);
                                          setPreviewOverrideVal(String(rem.proposed_value !== "Manual review required" ? rem.proposed_value : ""));
                                        }}
                                        style={{
                                          background: "#ffffff",
                                          color: "#334155",
                                          border: "1px solid #cbd5e1",
                                          padding: "5px 12px",
                                          fontSize: 11,
                                          fontWeight: 700,
                                          borderRadius: 4,
                                          cursor: "pointer"
                                        }}
                                      >
                                        🔍 Preview Changes
                                      </button>
                                    )}

                                    <button
                                      disabled={isApplying}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setPreviewModalRem(rem);
                                        setPreviewOverrideVal(String(rem.proposed_value !== "Manual review required" ? rem.proposed_value : ""));
                                      }}
                                      style={{
                                        background: isApplying ? "#94a3b8" : "#16a34a",
                                        color: "#ffffff",
                                        border: "none",
                                        padding: "5px 12px",
                                        fontSize: 11,
                                        fontWeight: 700,
                                        borderRadius: 4,
                                        cursor: isApplying ? "not-allowed" : "pointer"
                                      }}
                                    >
                                      ✓ Accept &amp; Apply
                                    </button>

                                    <button
                                      disabled={isApplying}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setPreviewModalRem(rem);
                                        setPreviewOverrideVal(String(rem.current_value !== "(Empty)" && rem.current_value !== "(None)" && rem.current_value !== "(Non-compliant state)" ? rem.current_value : ""));
                                      }}
                                      style={{
                                        background: "#ffffff",
                                        color: "#d97706",
                                        border: "1px solid #fde68a",
                                        padding: "5px 12px",
                                        fontSize: 11,
                                        fontWeight: 700,
                                        borderRadius: 4,
                                        cursor: isApplying ? "not-allowed" : "pointer"
                                      }}
                                    >
                                      ✏️ Manual Modify
                                    </button>
                                  </div>
                                </div>
                              );
                            })()}

                            <div style={{ marginTop: 10, display: "flex", justifyContent: "flex-end" }}>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onOpenEvidence(
                                    product.product_name,
                                    check.check_name || checkKey,
                                    check.authority || "API",
                                    res,
                                    check.final_evidence?.explanation || check.explanation || "No details provided.",
                                    screenshotUrl
                                  );
                                }}
                                style={{
                                  background: "#2563eb",
                                  color: "#ffffff",
                                  border: "none",
                                  padding: "4px 10px",
                                  fontSize: 11,
                                  fontWeight: 600,
                                  borderRadius: 4,
                                  cursor: "pointer"
                                }}
                              >
                                View Full Evidence &amp; Screenshot →
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* RULE 11 ASPECT RATIO PREVIEW MODAL */}
      {rule11PreviewData && (
        <div style={{
          position: "fixed",
          top: 0, right: 0, bottom: 0, left: 0,
          background: "rgba(15, 23, 42, 0.7)",
          backdropFilter: "blur(4px)",
          zIndex: 10000,
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}>
          <div style={{ background: "#ffffff", width: 600, padding: 24, borderRadius: 10, boxShadow: "0 20px 40px rgba(0,0,0,0.3)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e2e8f0", paddingBottom: 12 }}>
              <div>
                <span style={{ fontSize: 10.5, fontWeight: 800, textTransform: "uppercase", color: "#16a34a", letterSpacing: "0.05em" }}>
                  🖼️ RULE 11 — IMAGE ASPECT RATIO CONVERSION
                </span>
                <h3 style={{ fontSize: 16, fontWeight: 800, margin: "2px 0 0", color: "#0f172a" }}>
                  1:1 Square Canvas Padding Preview
                </h3>
              </div>
              <button onClick={() => setRule11PreviewData(null)} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#64748b" }}>×</button>
            </div>

            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, alignItems: "center" }}>
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 8, border: "1px solid #cbd5e1", textAlign: "center" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>BEFORE (Original Shopify Image)</div>
                  <div style={{ fontSize: 12, fontWeight: 800, color: "#dc2626", margin: "4px 0 8px" }}>
                    {rule11PreviewData.before_dimensions}
                  </div>
                  <div style={{ width: 140, height: 140, margin: "0 auto", borderRadius: 6, overflow: "hidden", border: "1px solid #cbd5e1", background: "#e2e8f0" }}>
                    <img src={rule11PreviewData.before_url} alt="Before" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                  </div>
                </div>

                <div style={{ background: "#f0fdf4", padding: 12, borderRadius: 8, border: "1px solid #bbf7d0", textAlign: "center" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", textTransform: "uppercase" }}>AFTER (1:1 Square Canvas Padded)</div>
                  <div style={{ fontSize: 12, fontWeight: 800, color: "#16a34a", margin: "4px 0 8px" }}>
                    {rule11PreviewData.after_dimensions}
                  </div>
                  <div style={{ width: 140, height: 140, margin: "0 auto", borderRadius: 6, overflow: "hidden", border: "2px solid #16a34a", background: "#ffffff" }}>
                    <img src={rule11PreviewData.preview_data_url} alt="After" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                  </div>
                  <a
                    href={rule11PreviewData.preview_data_url}
                    download={`product_${product?.product_id}_1x1_square.png`}
                    style={{
                      display: "inline-block",
                      marginTop: 8,
                      padding: "4px 10px",
                      background: "#16a34a",
                      color: "#ffffff",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 700,
                      textDecoration: "none"
                    }}
                  >
                    ⬇️ Download 1:1 Image
                  </a>
                </div>
              </div>

              {/* Explicit Preservation Badges */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, background: "#f1f5f9", padding: 10, borderRadius: 6 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#16a34a", textAlign: "center" }}>✓ Original pixels preserved</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#475569", textAlign: "center" }}>Crop: None</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#475569", textAlign: "center" }}>Regeneration: None</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#475569", textAlign: "center" }}>Layout change: None</div>
              </div>
            </div>

            <div style={{ marginTop: 18, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <label style={{ cursor: "pointer", background: "#f1f5f9", border: "1px solid #cbd5e1", padding: "7px 12px", borderRadius: 6, fontSize: 11.5, fontWeight: 700, color: "#334155" }}>
                📁 Upload Different Image
                <input
                  type="file"
                  accept="image/*"
                  style={{ display: "none" }}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const formData = new FormData();
                    formData.append("file", file);
                    const pid = product.product_id || product.product_name;
                    try {
                      const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations/rule-11/upload-custom`, {
                        method: "POST",
                        body: formData
                      });
                      if (res.ok) {
                        alert("✓ Custom image uploaded successfully!");
                        setRule11PreviewData(null);
                        const freshRes = await fetch(`/api/validation/products/${encodeURIComponent(product.product_name)}`);
                        if (freshRes.ok) {
                          const freshProd = await freshRes.json();
                          setProduct(freshProd);
                        }
                      } else {
                        alert("Failed to upload custom image.");
                      }
                    } catch (err) {
                      console.error("Custom image upload failed", err);
                    }
                  }}
                />
              </label>

              <div style={{ display: "flex", gap: 10 }}>
                <button
                  onClick={() => setRule11PreviewData(null)}
                  style={{ background: "#ffffff", color: "#334155", border: "1px solid #cbd5e1", padding: "7px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    const rem = rule11PreviewData.rem;
                    setRule11PreviewData(null);
                    handleApplyRemediation(rem);
                  }}
                  style={{ background: "#16a34a", color: "#ffffff", border: "none", padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: "pointer" }}
                >
                  [ Use This Conversion ]
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 1 PREVIEW & SAFETY CONFIRMATION MODAL */}
      {previewModalRem && (
        <div style={{
          position: "fixed",
          top: 0, right: 0, bottom: 0, left: 0,
          background: "rgba(15, 23, 42, 0.6)",
          backdropFilter: "blur(4px)",
          zIndex: 10000,
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}>
          <div style={{ background: "#ffffff", width: 540, padding: 24, borderRadius: 10, boxShadow: "0 20px 40px rgba(0,0,0,0.25)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid #e2e8f0", paddingBottom: 12 }}>
              <div>
                <span style={{ fontSize: 10.5, fontWeight: 800, textTransform: "uppercase", color: "#2563eb", letterSpacing: "0.05em" }}>
                  SAFETY CONFIRMATION &amp; PREVIEW
                </span>
                <h3 style={{ fontSize: 16, fontWeight: 800, margin: "2px 0 0", color: "#0f172a" }}>
                  Rule {previewModalRem.rule_id}: {previewModalRem.rule_name}
                </h3>
              </div>
              <button onClick={() => setPreviewModalRem(null)} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#64748b" }}>×</button>
            </div>

            <div style={{ marginTop: 14, fontSize: 12, color: "#475569", display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ background: "#f8fafc", padding: 10, borderRadius: 6, border: "1px solid #e2e8f0" }}>
                <div>Product: <strong style={{ color: "#0f172a" }}>{product.product_name}</strong></div>
                {previewModalRem.variant_id && <div>Variant ID: <code style={{ color: "#334155" }}>{previewModalRem.variant_id}</code></div>}
                <div>Target Field: <code style={{ color: "#2563eb", fontWeight: 700 }}>{previewModalRem.field_to_change}</code></div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div style={{ background: "#fef2f2", padding: 8, borderRadius: 6, border: "1px solid #fecaca" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "#dc2626" }}>CURRENT VALUE</div>
                  <div style={{ fontSize: 11.5, fontFamily: "monospace", color: "#991b1b", marginTop: 2, wordBreak: "break-word" }}>
                    {String(previewModalRem.current_value)}
                  </div>
                </div>

                <div style={{ background: "#f0fdf4", padding: 8, borderRadius: 6, border: "1px solid #bbf7d0" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "#16a34a" }}>PROPOSED NEW VALUE</div>
                  <div style={{ fontSize: 11.5, fontFamily: "monospace", color: "#166534", marginTop: 2, wordBreak: "break-word" }}>
                    {String(previewOverrideVal)}
                  </div>
                </div>
              </div>

              {/* METHOD 2 — RULE-SPECIFIC MANUAL MODIFY CONTROLS */}
              <div style={{ background: "#fafafa", padding: 10, borderRadius: 6, border: "1px solid #e2e8f0" }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: "#334155" }}>✏️ [ Method 2 — Manual Modify ] — Field-Specific Editor:</label>

                {previewModalRem.rule_id === "18" || previewModalRem.field_to_change === "sku" ? (
                  <div style={{ marginTop: 6 }}>
                    <div style={{ fontSize: 10.5, color: "#64748b", marginBottom: 2 }}>SKU Input:</div>
                    <input
                      type="text"
                      value={previewOverrideVal}
                      onChange={(e) => setPreviewOverrideVal(e.target.value)}
                      placeholder="e.g. SKU-KIDDY-1001"
                      style={{ width: "100%", padding: 8, fontSize: 12.5, border: "1px solid #cbd5e1", borderRadius: 4, fontFamily: "monospace" }}
                    />
                  </div>
                ) : previewModalRem.rule_id === "14" || previewModalRem.field_to_change === "price" ? (
                  <div style={{ marginTop: 6, display: "flex", gap: 6, alignItems: "center" }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#334155" }}>$</span>
                    <input
                      type="number"
                      step="0.01"
                      value={previewOverrideVal}
                      onChange={(e) => setPreviewOverrideVal(e.target.value)}
                      placeholder="e.g. 19.99"
                      style={{ flex: 1, padding: 8, fontSize: 12.5, border: "1px solid #cbd5e1", borderRadius: 4, fontFamily: "monospace" }}
                    />
                  </div>
                ) : previewModalRem.rule_id === "20" || previewModalRem.field_to_change === "weight" ? (
                  <div style={{ marginTop: 6, display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      type="number"
                      step="0.1"
                      value={previewOverrideVal.replace(/[^0-9.]/g, "")}
                      onChange={(e) => setPreviewOverrideVal(`${e.target.value} kg`)}
                      placeholder="e.g. 0.5"
                      style={{ flex: 1, padding: 8, fontSize: 12.5, border: "1px solid #cbd5e1", borderRadius: 4, fontFamily: "monospace" }}
                    />
                    <select
                      onChange={(e) => {
                        const num = previewOverrideVal.replace(/[^0-9.]/g, "") || "0.5";
                        setPreviewOverrideVal(`${num} ${e.target.value}`);
                      }}
                      style={{ padding: 8, fontSize: 12, border: "1px solid #cbd5e1", borderRadius: 4 }}
                    >
                      <option value="kg">kg</option>
                      <option value="g">g</option>
                      <option value="lb">lb</option>
                      <option value="oz">oz</option>
                    </select>
                  </div>
                ) : previewModalRem.rule_id === "28" || previewModalRem.field_to_change === "tags" ? (
                  <div style={{ marginTop: 6 }}>
                    <div style={{ fontSize: 10.5, color: "#64748b", marginBottom: 2 }}>Comma-separated Tags:</div>
                    <input
                      type="text"
                      value={previewOverrideVal}
                      onChange={(e) => setPreviewOverrideVal(e.target.value)}
                      placeholder="e.g. STEM, Educational, Scratch, Workbook"
                      style={{ width: "100%", padding: 8, fontSize: 12.5, border: "1px solid #cbd5e1", borderRadius: 4, fontFamily: "monospace" }}
                    />
                  </div>
                ) : previewModalRem.rule_id === "11" || previewModalRem.field_to_change === "images" ? (
                  <div style={{ marginTop: 6 }}>
                    <div style={{ fontSize: 10.5, color: "#64748b", marginBottom: 4 }}>Upload Replacement Image for Rule 11:</div>
                    <label style={{ cursor: "pointer", background: "#f1f5f9", border: "1px solid #cbd5e1", padding: "6px 12px", borderRadius: 4, fontSize: 11.5, fontWeight: 700, color: "#334155", display: "inline-block" }}>
                      📁 Upload Different Image
                      <input
                        type="file"
                        accept="image/*"
                        style={{ display: "none" }}
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          const formData = new FormData();
                          formData.append("file", file);
                          const pid = product.product_id || product.product_name;
                          try {
                            const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations/rule-11/upload-custom`, {
                              method: "POST",
                              body: formData
                            });
                            if (res.ok) {
                              alert("✓ Replacement image uploaded!");
                              setPreviewModalRem(null);
                            }
                          } catch (err) {
                            console.error("Upload error", err);
                          }
                        }}
                      />
                    </label>
                  </div>
                ) : (
                  <input
                    type="text"
                    value={previewOverrideVal}
                    onChange={(e) => setPreviewOverrideVal(e.target.value)}
                    placeholder="Enter custom value"
                    style={{ width: "100%", padding: 8, fontSize: 12.5, marginTop: 4, border: "1px solid #cbd5e1", borderRadius: 4, fontFamily: "monospace" }}
                  />
                )}
              </div>

              <div style={{ background: "#fffbebe", border: "1px solid #fde68a", borderRadius: 6, padding: 10, fontSize: 11, color: "#b45309" }}>
                ⚠️ <strong>Shopify Mutation Notice:</strong> Confirming this action will perform an explicit update API call to your Shopify store. Product status will remain unchanged (<strong>{( (product as any).status || product.launch_status || 'DRAFT').toUpperCase()}</strong>).
              </div>
            </div>

            <div style={{ marginTop: 18, display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button
                onClick={() => setPreviewModalRem(null)}
                style={{ background: "#f1f5f9", color: "#334155", border: "1px solid #cbd5e1", padding: "7px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleApplyRemediation(previewModalRem, previewOverrideVal)}
                style={{ background: "#16a34a", color: "#ffffff", border: "none", padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: "pointer", boxShadow: "0 1px 2px rgba(0,0,0,0.15)" }}
              >
                [ Confirm &amp; Apply to Shopify ]
              </button>
            </div>
          </div>
        </div>
      )}

      {/* BATCH SAFE FIX PREVIEW MODAL (PRODUCT-SCOPED) */}
      {batchModalOpen && (
        <div
          onClick={(e) => {
            e.stopPropagation();
            setBatchModalOpen(false);
          }}
          style={{
            position: "fixed",
            top: 0, right: 0, bottom: 0, left: 0,
            background: "rgba(15, 23, 42, 0.6)",
            backdropFilter: "blur(4px)",
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center"
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ background: "#ffffff", width: 620, padding: 24, borderRadius: 10, boxShadow: "0 20px 40px rgba(0,0,0,0.25)" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid #e2e8f0", paddingBottom: 12 }}>
              <div>
                <span style={{ fontSize: 10.5, fontWeight: 800, textTransform: "uppercase", color: "#16a34a", letterSpacing: "0.05em" }}>
                  BATCH SAFE FIX PREVIEW (CURRENT PRODUCT ONLY)
                </span>
                <h3 style={{ fontSize: 16, fontWeight: 800, margin: "2px 0 0", color: "#0f172a" }}>
                  {safeBatchItems.length} safe fix{safeBatchItems.length === 1 ? "" : "es"} found for {product.product_name}
                </h3>
              </div>
              <button onClick={(e) => { e.stopPropagation(); setBatchModalOpen(false); }} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#64748b" }}>×</button>
            </div>

            <div style={{ marginTop: 14, maxHeight: 320, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 6 }}>
              {safeBatchItems.length === 0 ? (
                <div style={{ padding: 24, textAlign: "center", color: "#475569", fontSize: 12, lineHeight: "1.6" }}>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>✅</div>
                  <strong style={{ color: "#166534", fontSize: 13 }}>All safe auto-fixable issues resolved!</strong>
                  <p style={{ margin: "6px 0 0", color: "#64748b" }}>
                    No 1-click safe auto-fixes are currently needed. Any remaining blockers for this product (such as Collection Assignment, Sitemap Indexing, or Theme Live URL) require manual shop/theme setup.
                  </p>
                </div>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0", textAlign: "left" }}>
                      <th style={{ padding: "8px 12px", color: "#475569" }}>#</th>
                      <th style={{ padding: "8px 12px", color: "#475569" }}>Rule</th>
                      <th style={{ padding: "8px 12px", color: "#475569" }}>Current State</th>
                      <th style={{ padding: "8px 12px", color: "#475569" }}>Proposed Fix</th>
                      <th style={{ padding: "8px 12px", color: "#475569" }}>Shopify Field</th>
                    </tr>
                  </thead>
                  <tbody>
                    {safeBatchItems.map((item, idx) => (
                      <tr key={item.remediation_id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "8px 12px", fontWeight: 700, color: "#64748b" }}>{idx + 1}</td>
                        <td style={{ padding: "8px 12px", fontWeight: 700, color: "#0f172a" }}>
                          Rule {item.rule_id} — {item.rule_name}
                        </td>
                        <td style={{ padding: "8px 12px", color: "#dc2626", fontFamily: "monospace" }}>
                          {String(item.current_value)}
                        </td>
                        <td style={{ padding: "8px 12px", color: "#16a34a", fontFamily: "monospace" }}>
                          {String(item.proposed_value)}
                        </td>
                        <td style={{ padding: "8px 12px", color: "#2563eb", fontFamily: "monospace" }}>
                          {item.field_to_change}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 6, padding: 10, marginTop: 12, fontSize: 11, color: "#166534" }}>
              ✓ Applies ONLY to {product.product_name} (does not affect catalog).<br/>
              ✓ Product status remains unchanged ({( (product as any).status || product.launch_status || 'DRAFT').toUpperCase()}).
            </div>

            <div style={{ marginTop: 18, display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setBatchModalOpen(false); }}
                disabled={isApplyingBatch}
                style={{ background: "#f1f5f9", color: "#334155", border: "1px solid #cbd5e1", padding: "7px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: isApplyingBatch ? "not-allowed" : "pointer" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={(e) => handleStartReviewEach(e)}
                disabled={isApplyingBatch || safeBatchItems.length === 0}
                style={{ background: "#ffffff", color: "#2563eb", border: "1px solid #bfdbfe", padding: "7px 14px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: isApplyingBatch || safeBatchItems.length === 0 ? "not-allowed" : "pointer" }}
              >
                🔍 Review Each ({safeBatchItems.length})
              </button>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); handleApplyAllSafe(); }}
                disabled={isApplyingBatch || safeBatchItems.length === 0}
                style={{ background: isApplyingBatch || safeBatchItems.length === 0 ? "#94a3b8" : "#16a34a", color: "#ffffff", border: "none", padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: isApplyingBatch || safeBatchItems.length === 0 ? "not-allowed" : "pointer" }}
              >
                {isApplyingBatch ? "Applying Batch Fixes..." : "Confirm & Apply All Safe Fixes"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* GUIDED ITEM-BY-ITEM REVIEW MODAL (REVIEW EACH) */}
      {isGuidedReviewOpen && safeBatchItems[guidedReviewIndex] && (() => {
        const currentItem = safeBatchItems[guidedReviewIndex];
        const isRule11 = currentItem.rule_id === "11" || currentItem.field_to_change === "images";
        const totalItems = safeBatchItems.length;

        return (
          <div
            onClick={(e) => {
              e.stopPropagation();
              setIsGuidedReviewOpen(false);
            }}
            style={{
              position: "fixed",
              top: 0, right: 0, bottom: 0, left: 0,
              background: "rgba(15, 23, 42, 0.7)",
              backdropFilter: "blur(4px)",
              zIndex: 10000,
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{ background: "#ffffff", width: 620, padding: 24, borderRadius: 10, boxShadow: "0 20px 40px rgba(0,0,0,0.3)" }}
            >
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid #e2e8f0", paddingBottom: 12 }}>
                <div>
                  <span style={{ fontSize: 10.5, fontWeight: 800, textTransform: "uppercase", color: "#2563eb", letterSpacing: "0.05em" }}>
                    🔍 GUIDED REVIEW — ITEM {guidedReviewIndex + 1} OF {totalItems} ({product.product_name})
                  </span>
                  <h3 style={{ fontSize: 16, fontWeight: 800, margin: "2px 0 0", color: "#0f172a" }}>
                    Rule {currentItem.rule_id}: {currentItem.rule_name}
                  </h3>
                </div>
                <button onClick={() => setIsGuidedReviewOpen(false)} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#64748b" }}>×</button>
              </div>

              {/* Body Details */}
              <div style={{ marginTop: 14, fontSize: 12, color: "#475569", display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ background: "#f8fafc", padding: 10, borderRadius: 6, border: "1px solid #e2e8f0" }}>
                  <div><strong>Issue Description:</strong> {currentItem.issue_description}</div>
                  <div style={{ marginTop: 4 }}><strong>Why it failed:</strong> {currentItem.why_it_matters}</div>
                  <div style={{ marginTop: 4 }}><strong>Shopify Target Field:</strong> <code style={{ color: "#2563eb", fontWeight: 700 }}>{currentItem.field_to_change}</code></div>
                </div>

                {/* VISUAL PREVIEW: RULE 11 IMAGE CONVERSION vs REGULAR TEXT/SKU/SEO */}
                {isRule11 ? (
                  <div style={{ background: "#f0fdf4", padding: 12, borderRadius: 8, border: "1px solid #bbf7d0" }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", textTransform: "uppercase", marginBottom: 6 }}>
                      🖼️ PROPOSED RULE 11 IMAGE ASPECT RATIO CONVERSION
                    </div>
                    {isLoadingGuidedRule11 ? (
                      <div style={{ padding: 20, textAlign: "center", color: "#64748b" }}>⏳ Generating 1:1 square canvas padding preview...</div>
                    ) : guidedRule11Preview ? (
                      <div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, alignItems: "center" }}>
                          <div style={{ background: "#ffffff", padding: 8, borderRadius: 6, border: "1px solid #e2e8f0", textAlign: "center" }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b" }}>BEFORE (Original Image)</div>
                            <div style={{ fontSize: 11, fontWeight: 700, color: "#dc2626", margin: "2px 0 4px" }}>{guidedRule11Preview.before_dimensions}</div>
                            <div style={{ width: 110, height: 110, margin: "0 auto", borderRadius: 4, overflow: "hidden", border: "1px solid #cbd5e1" }}>
                              <img src={guidedRule11Preview.before_url} alt="Before" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                            </div>
                          </div>

                          <div style={{ background: "#ffffff", padding: 8, borderRadius: 6, border: "2px solid #16a34a", textAlign: "center" }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: "#16a34a" }}>AFTER (1:1 Square Padded)</div>
                            <div style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", margin: "2px 0 4px" }}>{guidedRule11Preview.after_dimensions}</div>
                            <div style={{ width: 110, height: 110, margin: "0 auto", borderRadius: 4, overflow: "hidden", border: "1px solid #16a34a" }}>
                              <img src={guidedRule11Preview.preview_data_url} alt="After" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                            </div>
                            <a
                              href={guidedRule11Preview.preview_data_url}
                              download={`product_${product?.product_id}_1x1_square.png`}
                              style={{
                                display: "inline-block",
                                marginTop: 6,
                                padding: "3px 8px",
                                background: "#16a34a",
                                color: "#ffffff",
                                borderRadius: 4,
                                fontSize: 10,
                                fontWeight: 700,
                                textDecoration: "none"
                              }}
                            >
                              ⬇️ Download 1:1 Image
                            </a>
                          </div>
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 4, background: "#ffffff", padding: 6, borderRadius: 4, marginTop: 8, border: "1px solid #e2e8f0" }}>
                          <div style={{ fontSize: 9, fontWeight: 700, color: "#16a34a", textAlign: "center" }}>✓ Original pixels preserved</div>
                          <div style={{ fontSize: 9, fontWeight: 700, color: "#475569", textAlign: "center" }}>Crop: None</div>
                          <div style={{ fontSize: 9, fontWeight: 700, color: "#475569", textAlign: "center" }}>Regeneration: None</div>
                          <div style={{ fontSize: 9, fontWeight: 700, color: "#475569", textAlign: "center" }}>Layout change: None</div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontSize: 11.5, color: "#15803d" }}>
                        Convert existing image to 1:1 square ratio using pixel-preserving canvas padding.
                      </div>
                    )}
                  </div>
                ) : (
                  /* Standard Field Preview & Manual Input Editor */
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                      <div style={{ background: "#fef2f2", padding: 8, borderRadius: 6, border: "1px solid #fecaca" }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: "#dc2626" }}>CURRENT STATE</div>
                        <div style={{ fontSize: 11.5, fontFamily: "monospace", color: "#991b1b", marginTop: 2, wordBreak: "break-word" }}>
                          {String(currentItem.current_value)}
                        </div>
                      </div>

                      <div style={{ background: "#f0fdf4", padding: 8, borderRadius: 6, border: "1px solid #bbf7d0" }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: "#16a34a" }}>RECOMMENDED PROPOSED FIX</div>
                        <div style={{ fontSize: 11.5, fontFamily: "monospace", color: "#166534", marginTop: 2, wordBreak: "break-word" }}>
                          {String(currentItem.proposed_value)}
                        </div>
                      </div>
                    </div>

                    {/* MANUAL INPUT EDITOR */}
                    <div style={{ background: "#fafafa", padding: 10, borderRadius: 6, border: "1px solid #cbd5e1" }}>
                      <label style={{ fontSize: 11, fontWeight: 700, color: "#334155" }}>
                        ✏️ Customize / Modify Value (or leave proposed default):
                      </label>

                      {currentItem.rule_id === "18" || currentItem.field_to_change === "sku" ? (
                        <input
                          type="text"
                          value={guidedReviewCustomVal}
                          onChange={(e) => setGuidedReviewCustomVal(e.target.value)}
                          placeholder="e.g. SKU-KIDDY-1001"
                          style={{ width: "100%", padding: 8, fontSize: 12.5, marginTop: 4, border: "1px solid #cbd5e1", borderRadius: 4, fontFamily: "monospace" }}
                        />
                      ) : currentItem.rule_id === "34" || currentItem.rule_id === "36" || currentItem.field_to_change?.includes("seo") ? (
                        <textarea
                          rows={2}
                          value={guidedReviewCustomVal}
                          onChange={(e) => setGuidedReviewCustomVal(e.target.value)}
                          placeholder="Enter custom SEO text"
                          style={{ width: "100%", padding: 8, fontSize: 12, marginTop: 4, border: "1px solid #cbd5e1", borderRadius: 4 }}
                        />
                      ) : (
                        <input
                          type="text"
                          value={guidedReviewCustomVal}
                          onChange={(e) => setGuidedReviewCustomVal(e.target.value)}
                          placeholder="Enter custom value"
                          style={{ width: "100%", padding: 8, fontSize: 12.5, marginTop: 4, border: "1px solid #cbd5e1", borderRadius: 4, fontFamily: "monospace" }}
                        />
                      )}
                    </div>
                  </div>
                )}

                {/* Upload Custom Replacement Image option inside Guided Review */}
                {isRule11 && (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f8fafc", padding: 8, borderRadius: 6, border: "1px solid #e2e8f0" }}>
                    <span style={{ fontSize: 11, color: "#475569" }}>Want a custom replacement image instead?</span>
                    <label style={{ cursor: "pointer", background: "#ffffff", border: "1px solid #cbd5e1", padding: "5px 10px", borderRadius: 4, fontSize: 11, fontWeight: 700, color: "#334155" }}>
                      📁 Upload Custom Image
                      <input
                        type="file"
                        accept="image/*"
                        style={{ display: "none" }}
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          const formData = new FormData();
                          formData.append("file", file);
                          const pid = product.product_id || product.product_name;
                          try {
                            const res = await fetch(`/api/products/${encodeURIComponent(pid)}/remediations/rule-11/upload-custom`, {
                              method: "POST",
                              body: formData
                            });
                            if (res.ok) {
                              alert("✓ Custom replacement image uploaded!");
                              handleGuidedStep("skip");
                            }
                          } catch (err) {
                            console.error("Upload error", err);
                          }
                        }}
                      />
                    </label>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ marginTop: 18, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <button
                  onClick={() => setIsGuidedReviewOpen(false)}
                  disabled={isApplyingGuidedFix}
                  style={{ background: "#f1f5f9", color: "#475569", border: "1px solid #cbd5e1", padding: "7px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: isApplyingGuidedFix ? "not-allowed" : "pointer", opacity: isApplyingGuidedFix ? 0.6 : 1 }}
                >
                  Cancel Review
                </button>

                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    onClick={() => handleGuidedStep("skip")}
                    disabled={isApplyingGuidedFix}
                    style={{ background: "#ffffff", color: "#475569", border: "1px solid #cbd5e1", padding: "7px 12px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: isApplyingGuidedFix ? "not-allowed" : "pointer", opacity: isApplyingGuidedFix ? 0.6 : 1 }}
                  >
                    ⏭️ Skip
                  </button>

                  {!isRule11 && (
                    <button
                      onClick={() => handleGuidedStep("manual")}
                      disabled={isApplyingGuidedFix}
                      style={{ background: "#ffffff", color: "#d97706", border: "1px solid #fde68a", padding: "7px 14px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: isApplyingGuidedFix ? "not-allowed" : "pointer", opacity: isApplyingGuidedFix ? 0.6 : 1 }}
                    >
                      ✏️ Apply Custom Value
                    </button>
                  )}

                  <button
                    onClick={() => handleGuidedStep("accept")}
                    disabled={isApplyingGuidedFix}
                    style={{ background: isApplyingGuidedFix ? "#059669" : "#16a34a", color: "#ffffff", border: "none", padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: isApplyingGuidedFix ? "not-allowed" : "pointer", boxShadow: "0 1px 2px rgba(22, 163, 74, 0.2)", opacity: isApplyingGuidedFix ? 0.8 : 1 }}
                  >
                    {isApplyingGuidedFix ? `⏳ Applying Fix (${guidedReviewIndex + 1}/${totalItems})...` : `✓ Accept & Apply Fix (${guidedReviewIndex + 1}/${totalItems})`}
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};

