import unittest
from services.unified_validation_engine import run_unified_validation_engine, BROWSER_AUTHORITATIVE_CHECKS, CHECK_NAME_TO_ID

class TestUnifiedValidationEngine(unittest.TestCase):

    def setUp(self):
        self.result = run_unified_validation_engine()
        self.summary = self.result["summary"]
        self.products = self.result["validation_results"]

    def test_01_api_authoritative_pass(self):
        """Test 1: API authoritative check (e.g. Check 01 Title) uses API result even if browser differs."""
        p = self.products[0]
        chk_01 = p["checks"]["01. Product Title"]
        self.assertEqual(chk_01["authority"], "API")
        self.assertEqual(chk_01["final_result"], chk_01["api_result"])

    def test_02_browser_authoritative_fail(self):
        """Test 2: Browser authoritative check (e.g. Check 40 Single H1 or Check 44 Mobile) uses browser result."""
        target_chk = None
        for p in self.products:
            c40 = p["checks"].get("40. Single H1")
            c44 = p["checks"].get("44. Mobile Render")
            if c40 and c40.get("browser_result") == "FAIL":
                target_chk = c40
                break
            if c44 and c44.get("browser_result") == "FAIL":
                target_chk = c44
                break

        if target_chk is not None:
            self.assertEqual(target_chk["authority"], "BROWSER")
            self.assertEqual(target_chk["final_result"], "FAIL")

    def test_03_results_match(self):
        """Test 3: When API and Browser agree, discrepancy flag is False and classification is MATCH."""
        p = next((prod for prod in self.products if prod["checks"]["43. Live URL Loads"].get("browser_result") != "N/A"), self.products[0])
        chk_43 = p["checks"]["43. Live URL Loads"]
        if chk_43["api_result"] == chk_43["browser_result"]:
            self.assertFalse(chk_43["discrepancy"])
            self.assertEqual(chk_43["classification"], "MATCH")

    def test_04_browser_not_verifiable(self):
        """Test 4: Browser NOT_VERIFIABLE fallback preserves PASS if API is PASS."""
        target_chk = None
        for p in self.products:
            c46 = p["checks"].get("46. Buy It Now")
            if c46 and c46.get("browser_result") == "NOT_VERIFIABLE":
                target_chk = c46
                break

        if target_chk is not None:
            self.assertEqual(target_chk["authority"], "BROWSER")
            self.assertEqual(target_chk["final_result"], "PASS")

    def test_05_phase1_draft_behavior(self):
        """Test 5: DRAFT products must fail Check 50 & Check 51 in unified engine."""
        draft_titles = [
            'Bristle Bot Kit',
            'DC BO Geared Motor 300 RPM',
            'Mission Tiranga STEM Explorer Workshop'
        ]
        for p in self.products:
            name = p["product_name"]
            if any(dt.lower() in name.lower() for dt in draft_titles):
                c50 = p["checks"]["50. Published to Social Channels"]
                c51 = p["checks"]["51. In WhatsApp Catalogue"]
                self.assertEqual(c50["final_result"], "FAIL")
                self.assertEqual(c51["final_result"], "FAIL")

    def test_06_active_behavior(self):
        """Test 6: ACTIVE products retain PASS for Check 50 & Check 51 when published."""
        draft_titles = [
            'Bristle Bot Kit',
            'DC BO Geared Motor 300 RPM',
            'Mission Tiranga STEM Explorer Workshop'
        ]
        for p in self.products:
            name = p["product_name"]
            if any(dt.lower() in name.lower() for dt in draft_titles):
                continue
            c48 = p["checks"].get("48. Status Active", {})
            if c48.get("api_result") == "PASS":
                c50 = p["checks"]["50. Published to Social Channels"]
                c51 = p["checks"]["51. In WhatsApp Catalogue"]
                self.assertEqual(c50["final_result"], "PASS")
                self.assertEqual(c51["final_result"], "PASS")

    def test_07_53_check_integrity(self):
        """Test 7: Every product must evaluate exactly 53 checks (31 blockers, 22 warnings)."""
        p = self.products[0]
        checks = p["checks"]
        self.assertEqual(len(checks), 53)
        
        blockers = [c for c in checks.values() if c["severity"] == "Blocker"]
        warnings = [c for c in checks.values() if c["severity"] == "Warning"]
        
        self.assertEqual(len(blockers), 31)
        self.assertEqual(len(warnings), 22)

    def test_08_product_aggregation(self):
        """Test 8: Verify products aggregated cleanly without missing items."""
        total_p = len(self.products)
        self.assertGreater(total_p, 0)
        self.assertEqual(self.summary["total_products"], total_p)
        self.assertEqual(self.summary["total_evaluations"], total_p * 53)

    def test_09_no_duplicate_checks(self):
        """Test 9: Verify check IDs 01-53 appear exactly once per product."""
        for p in self.products:
            checks = p["checks"]
            check_ids = [c["check_id"] for c in checks.values()]
            self.assertEqual(len(check_ids), 53)
            self.assertEqual(set(check_ids), set(range(1, 54)))

    def test_10_evidence_preservation(self):
        """Test 10: Verify API and Browser evidence objects remain separately accessible."""
        p = next((prod for prod in self.products if prod["checks"]["43. Live URL Loads"].get("verification_method") == "BROWSER_VERIFIED"), None)
        if p:
            chk_43 = p["checks"]["43. Live URL Loads"]
            self.assertIn("api_evidence", chk_43)
            self.assertIn("browser_evidence", chk_43)
            self.assertIn("final_evidence", chk_43)
            self.assertIsNotNone(chk_43["api_evidence"])
            self.assertIsNotNone(chk_43["browser_evidence"])


if __name__ == "__main__":
    unittest.main()
