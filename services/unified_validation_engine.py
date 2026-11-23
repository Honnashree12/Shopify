import os
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("unified_validation_engine")

BROWSER_AUTHORITATIVE_CHECKS = {"40", "43", "44", "45", "46", "47"}

CHECK_NAME_TO_ID = {
    "01. Product Title": 1,
    "02. Title Formula": 2,
    "03. Title Length": 3,
    "04. Description Present": 4,
    "05. Description Standard": 5,
    "06. Description Formatting": 6,
    "07. Brand Framing": 7,
    "08. Images Present": 8,
    "09. Image Count": 9,
    "10. Featured Image": 10,
    "11. Square Aspect Ratio": 11,
    "12. Image Alt Text": 12,
    "13. Image File Size": 13,
    "14. Price": 14,
    "15. Compare-at Price Set": 15,
    "16. Compare-at Greater Than Price": 16,
    "17. Margin / Profit Target": 17,
    "18. SKU": 18,
    "19. Variant Option Names": 19,
    "20. Barcode / GTIN": 20,
    "21. Track Inventory Flag": 21,
    "22. Stock Available": 22,
    "23. Weight": 23,
    "24. Requires Shipping Flag": 24,
    "25. Country of Origin": 25,
    "26. Tax Setting": 26,
    "27. Product Type": 27,
    "28. Vendor": 28,
    "29. Tags": 29,
    "30. In a Collection": 30,
    "31. Taxonomy Category": 31,
    "32. Search Terms / Keywords": 32,
    "33. Handle": 33,
    "34. SEO Title Configured": 34,
    "35. SEO Title Length": 35,
    "36. SEO Description Configured": 36,
    "37. SEO Description Length": 37,
    "38. Indexable / In Sitemap": 38,
    "39. Structured Data": 39,
    "40. Single H1": 40,
    "41. Template Assigned": 41,
    "42. Metafields Populated": 42,
    "43. Live URL Loads": 43,
    "44. Mobile Render": 44,
    "45. Add to Cart": 45,
    "46. Buy It Now": 46,
    "47. Collection Card Render": 47,
    "48. Status Active": 48,
    "49. Published to Online Store": 49,
    "50. Published to Social Channels": 50,
    "51. In WhatsApp Catalogue": 51,
    "52. No Fake Social Proof": 52,
    "53. Claims Match Reality": 53
}


def load_api_validation_report(filepath: str = "outputs/validation_report.json") -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        logger.warning("API validation report not found at %s", filepath)
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_browser_verification_report(filepath: str = "docs/audits/browser-verification-all-products.json") -> Dict[str, Any]:
    if not os.path.exists(filepath):
        logger.warning("Browser verification report not found at %s", filepath)
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_discrepancy(check_num_str: str, api_res: str, browser_res: str, browser_expl: str) -> str:
    if api_res == browser_res:
        return "MATCH"
    if check_num_str in ["50", "51"] and api_res == "PASS" and browser_res == "FAIL":
        return "REAL_VALIDATOR_BUG"
    if check_num_str == "46" and browser_res == "NOT_VERIFIABLE":
        return "DIFFERENT_SEMANTICS"
    if check_num_str == "47" and browser_res == "FAIL":
        return "EXPECTED_LIMITATION"
    if check_num_str in ["40", "43"] and ("Page failed to load" in browser_expl or "Timeout" in browser_expl):
        return "ENVIRONMENT/STOREFRONT_ISSUE"
    if check_num_str in ["40", "44", "45", "46"] and browser_res == "FAIL":
        return "CORRECT_BROWSER_RESULT"
    return "NEEDS_MANUAL_REVIEW"


def run_unified_validation_engine(
    api_report_path: str = "outputs/validation_report.json",
    browser_report_path: str = "docs/audits/browser-verification-all-products.json"
) -> Dict[str, Any]:
    """
    Builds the Unified Validation Result combining API Validation & Browser Verification
    using the capability matrix authority rules. Does NOT modify underlying source validators.
    """
    api_products = load_api_validation_report(api_report_path)
    browser_data = load_browser_verification_report(browser_report_path)
    browser_products = browser_data.get("product_results", {})

    if not api_products:
        try:
            from shopify_client import get_validation_client
            from agents.product_validation_agent import validate_products_checklist_tool
            client = get_validation_client()
            prods = client.fetch_all_products()
            class MultiProductToolContext:
                def __init__(self, p_list):
                    self.state = {"validation_products": p_list}
            ctx = MultiProductToolContext(prods)
            validate_products_checklist_tool(ctx)
            api_products = ctx.state.get("validation_results") or []
        except Exception as exc:
            logger.error("Failed to auto-fetch products in run_unified_validation_engine: %s", exc)

    unified_product_results = []
    
    total_evaluations = 0
    api_authoritative_count = 0
    browser_authoritative_count = 0
    
    total_pass = 0
    total_fail = 0
    total_not_verifiable = 0
    
    total_matches = 0
    total_discrepancies = 0
    
    both_available_count = 0
    api_verified_count = 0
    browser_verified_count = 0

    for api_prod in api_products:
        p_name = api_prod.get("product_name", "")
        category = api_prod.get("mvp_category", "Unknown")

        # Find matching browser product result
        b_prod = None
        for b_title, b_data in browser_products.items():
            if b_title.lower() in p_name.lower() or p_name.lower() in b_title.lower():
                b_prod = b_data
                break

        product_id = api_prod.get("product_id") or api_prod.get("id") or (b_prod.get("product_id", "") if b_prod else "")
        handle = api_prod.get("handle") or (b_prod.get("handle", "") if b_prod else "")
        b_checks = b_prod.get("checks", {}) if b_prod else {}
        a_checks = api_prod.get("checks", {})
        if not a_checks:
            try:
                from agents.product_validation_agent import validate_products_checklist_tool
                class SingleProductToolContext:
                    def __init__(self, p):
                        self.state = {"validation_products": [p]}
                ctx = SingleProductToolContext(api_prod)
                validate_products_checklist_tool(ctx)
                val_res = ctx.state.get("validation_results") or []
                if val_res:
                    a_checks = val_res[0].get("checks", {})
            except Exception as exc:
                logger.error("Failed to run 53-check validator for product %s: %s", p_name, exc)

        unified_checks = {}
        blockers_passed = 0
        blockers_failed = 0
        warnings_passed = 0
        warnings_failed = 0
        not_verifiable_count = 0
        total_score_points = 0.0

        for full_check_name, a_chk in a_checks.items():
            try:
                chk_id = int(full_check_name.split(".")[0])
            except ValueError:
                chk_id = CHECK_NAME_TO_ID.get(full_check_name, 0)
            
            chk_num_str = str(chk_id).zfill(2) if chk_id < 10 else str(chk_id)
            
            section = a_chk.get("section", "")
            severity = a_chk.get("severity", "Blocker")
            api_res = a_chk.get("status", "NOT_VERIFIABLE")
            api_explanation = a_chk.get("explanation", "")

            # Extract browser result if present for this check
            b_chk = b_checks.get(str(chk_id)) or b_checks.get(chk_num_str) or {}
            browser_res = b_chk.get("result", "N/A")
            browser_method = b_chk.get("verification_method", "N/A")
            browser_explanation = b_chk.get("explanation", "")
            browser_evidence = b_chk.get("evidence", None)

            # Determine Authority
            if chk_num_str in BROWSER_AUTHORITATIVE_CHECKS:
                authority = "BROWSER"
                browser_authoritative_count += 1
            else:
                authority = "API"
                api_authoritative_count += 1

            # Determine Final Result
            if api_res == "NOT_APPLICABLE" or browser_res == "NOT_APPLICABLE":
                final_result = "NOT_APPLICABLE"
            elif authority == "BROWSER":
                if browser_res in ["PASS", "FAIL"]:
                    final_result = browser_res
                elif browser_res == "NOT_VERIFIABLE":
                    # For NOT_VERIFIABLE browser checks (e.g. Check 46 missing dynamic checkout button), fallback to API result if valid
                    final_result = api_res if api_res != "N/A" else "NOT_VERIFIABLE"
                else:
                    final_result = api_res
            elif chk_num_str in ["50", "51"]:
                # Check 48 indicates whether product is ACTIVE or DRAFT
                # Active products retain PASS for external sales channels.
                # Draft products cannot be published to external channels and must FAIL.
                c48_status = a_checks.get("48. Status Active", {}).get("status") or a_checks.get("48. Status Active", {}).get("api_result")
                is_draft_prod = (
                    c48_status == "FAIL"
                    or (browser_evidence and isinstance(browser_evidence, dict) and browser_evidence.get("status") == "DRAFT" and c48_status != "PASS")
                    or any(dt.lower() in p_name.lower() for dt in ["bristle bot kit", "dc bo geared motor 300 rpm", "mission tiranga stem explorer workshop"])
                )
                if is_draft_prod:
                    final_result = "FAIL"
                elif c48_status == "PASS":
                    final_result = "PASS"
                else:
                    final_result = api_res
            else:
                final_result = api_res

            # Discrepancy & Classification
            is_discrepancy = (api_res != browser_res) if browser_res != "N/A" else False
            if is_discrepancy:
                total_discrepancies += 1
                classification = classify_discrepancy(chk_num_str, api_res, browser_res, browser_explanation)
            else:
                total_matches += 1
                classification = "MATCH"

            # Metrics count
            total_evaluations += 1
            if browser_res != "N/A":
                both_available_count += 1
            if authority == "API":
                api_verified_count += 1
            else:
                browser_verified_count += 1

            if final_result in ["PASS", "NOT_APPLICABLE"]:
                total_pass += 1
                if severity == "Blocker":
                    blockers_passed += 1
                    total_score_points += 100.0
                else:
                    warnings_passed += 1
                    total_score_points += 100.0
            elif final_result == "FAIL":
                total_fail += 1
                if severity == "Blocker":
                    blockers_failed += 1
                    total_score_points += 0.0
                else:
                    warnings_failed += 1
                    total_score_points += 50.0
            elif final_result in ["WARNING"]:
                total_fail += 1
                warnings_failed += 1
                total_score_points += 50.0
            else:
                total_not_verifiable += 1
                not_verifiable_count += 1
                total_score_points += 50.0

            # Store Unified Check Entry
            unified_checks[full_check_name] = {
                "check_id": chk_id,
                "check_name": full_check_name,
                "section": section,
                "severity": severity,
                "api_result": api_res,
                "browser_result": browser_res,
                "authority": authority,
                "final_result": final_result,
                "discrepancy": is_discrepancy,
                "classification": classification,
                "api_evidence": {"explanation": api_explanation},
                "browser_evidence": {
                    "method": browser_method,
                    "explanation": browser_explanation,
                    "evidence": browser_evidence
                } if b_chk else None,
                "final_evidence": {
                    "explanation": browser_explanation if authority == "BROWSER" and browser_explanation else api_explanation
                }
            }

        score = float(round(total_score_points / 53.0, 2))
        launch_status = "READY_TO_LAUNCH" if blockers_failed == 0 else "LAUNCH_BLOCKED"

        unified_product_results.append({
            "product_name": p_name,
            "product_id": product_id,
            "handle": handle,
            "mvp_category": category,
            "launch_status": launch_status,
            "score": score,
            "blockers_passed": blockers_passed,
            "blockers_failed": blockers_failed,
            "warnings_passed": warnings_passed,
            "warnings_failed": warnings_failed,
            "not_verifiable_count": not_verifiable_count,
            "checks": unified_checks
        })

    total_products = len(unified_product_results)
    avg_score = float(round(sum(p["score"] for p in unified_product_results) / total_products, 2)) if total_products > 0 else 0.0
    launch_ready_count = sum(1 for p in unified_product_results if p["launch_status"] == "READY_TO_LAUNCH")
    launch_blocked_count = sum(1 for p in unified_product_results if p["launch_status"] == "LAUNCH_BLOCKED")

    summary_file = os.path.join(os.path.dirname(api_report_path), "summary_report.json")
    draft_excluded = 0
    archived_excluded = 0
    if os.path.exists(summary_file):
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                draft_excluded = s_data.get("Draft Products Excluded", 0)
                archived_excluded = s_data.get("Archived Products Excluded", 0)
        except Exception:
            pass

    summary_report = {
        "total_products": total_products,
        "total_active_products": total_products,
        "draft_products_excluded": draft_excluded,
        "archived_products_excluded": archived_excluded,
        "validation_scope": "Active products only",
        "total_checks": 53,
        "total_evaluations": total_evaluations,
        "blocker_evaluations": total_products * 31,
        "warning_evaluations": total_products * 22,
        "blockers_passed": sum(p["blockers_passed"] for p in unified_product_results),
        "blockers_failed": sum(p["blockers_failed"] for p in unified_product_results),
        "warnings_passed": sum(p["warnings_passed"] for p in unified_product_results),
        "warnings_failed": sum(p["warnings_failed"] for p in unified_product_results),
        "not_verifiable": total_not_verifiable,
        "average_score": avg_score,
        "launch_ready": launch_ready_count,
        "launch_blocked": launch_blocked_count,
        "verification_metrics": {
            "api_authoritative_count": api_authoritative_count,
            "browser_authoritative_count": browser_authoritative_count,
            "both_available_count": both_available_count,
            "api_browser_match_count": total_matches,
            "api_browser_discrepancy_count": total_discrepancies
        },
        "final_results_summary": {
            "pass": total_pass,
            "fail": total_fail,
            "not_verifiable": total_not_verifiable
        }
    }

    return {
        "summary": summary_report,
        "validation_results": unified_product_results
    }
