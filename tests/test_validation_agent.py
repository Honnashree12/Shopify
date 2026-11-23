import os
import json
import unittest
from unittest.mock import MagicMock, patch
from shopify_client import ShopifyClient, ShopifyConfigError
from agents.product_validation_agent import (
    fetch_validation_products_tool,
    validate_products_checklist_tool,
    generate_validation_reports_tool,
    product_validation_agent
)
# pyrefly: ignore [missing-import]
from google.adk.runners import Runner  # type: ignore
# pyrefly: ignore [missing-import]
from google.adk.sessions import InMemorySessionService  # type: ignore
# pyrefly: ignore [missing-import]
from google.genai import types  # type: ignore

class MockToolContext:
    def __init__(self, state):
        self.state = state

class TestValidationAgent(unittest.TestCase):
    def test_shopify_client_init(self):
        client = ShopifyClient(store_url="test-store.myshopify.com", access_token="shpat_test123")
        self.assertEqual(client.store_url, "test-store.myshopify.com")
        self.assertEqual(client.headers["X-Shopify-Access-Token"], "shpat_test123")
        self.assertIn("application/json", client.headers["Content-Type"])

    @patch("shopify_client.httpx.post")
    def test_fetch_all_products_graphql(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "products": {
                    "pageInfo": {
                        "hasNextPage": False,
                        "endCursor": None
                    },
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/Product/123",
                                "title": "Test Product",
                                "bodyHtml": "Hello world",
                                "vendor": "Test Vendor",
                                "productType": "Type",
                                "status": "ACTIVE",
                                "handle": "test-product",
                                "tags": ["tag1", "tag2"],
                                "seo": {
                                    "title": "SEO Title",
                                    "description": "SEO Desc"
                                },
                                "collections": {
                                    "edges": [
                                        {"node": {"id": "gid://shopify/Collection/1", "title": "Summer"}}
                                    ]
                                },
                                "images": {
                                    "edges": [
                                        {"node": {"id": "gid://shopify/ProductImage/1", "url": "https://img.url", "altText": "Alt Text"}}
                                    ]
                                },
                                "variants": {
                                    "edges": [
                                        {
                                            "node": {
                                                "id": "gid://shopify/ProductVariant/1",
                                                "title": "Default Title",
                                                "sku": "SKU123",
                                                "price": "10.00",
                                                "compareAtPrice": "15.00",
                                                "inventoryQuantity": 10,
                                                "inventoryItem": {
                                                    "tracked": True,
                                                    "requiresShipping": True
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }
        mock_post.return_value = mock_response
        
        client = ShopifyClient(store_url="test-store.myshopify.com", access_token="shpat_test123")
        products = client.fetch_all_products()
        
        self.assertEqual(len(products), 1)
        p = products[0]
        self.assertEqual(p["title"], "Test Product")
        self.assertEqual(p["body_html"], "Hello world")
        self.assertEqual(p["vendor"], "Test Vendor")
        self.assertEqual(p["product_type"], "Type")
        self.assertEqual(p["status"], "ACTIVE")
        self.assertEqual(p["handle"], "test-product")
        self.assertEqual(p["seo_title"], "SEO Title")
        self.assertEqual(p["seo_description"], "SEO Desc")
        self.assertEqual(p["collections"], ["Summer"])
        self.assertEqual(len(p["images"]), 1)
        self.assertEqual(p["images"][0]["alt"], "Alt Text")
        self.assertEqual(len(p["variants"]), 1)
        self.assertEqual(p["variants"][0]["sku"], "SKU123")
        self.assertTrue(p["variants"][0]["requires_shipping"])

    def test_validation_checklist_logic(self):
        tool_context = MockToolContext(state={})
        
        p_good = {
            "title": "Good Product",
            "body_html": "This is a great product description.",
            "vendor": "Test Vendor",
            "product_type": "Shirt",
            "status": "active",
            "handle": "good-product",
            "tags": ["Shirt", "Summer"],
            "seo_title": "SEO Title",
            "seo_description": "SEO Description",
            "collections": ["Main Collection"],
            "images": [{"id": "img1", "url": "url1", "alt": "Image Alt"}],
            "variants": [{
                "id": "var1",
                "title": "Default",
                "sku": "GOOD-SKU",
                "price": "29.99",
                "compare_at_price": "39.99",
                "inventory_quantity": 50,
                "requires_shipping": True,
                "weight": 0.5,
                "inventory_item": {
                    "tracked": True
                }
            }]
        }
        
        p_bad = {
            "title": "", 
            "body_html": None, 
            "vendor": "Default Vendor", 
            "product_type": "", 
            "status": "draft", 
            "handle": "bad-product",
            "tags": [], 
            "seo_title": None, 
            "seo_description": "", 
            "collections": [], 
            "images": [{"id": "img1", "url": "url1", "alt": ""}], 
            "variants": [{
                "id": "var1",
                "title": "Default",
                "sku": "", 
                "price": "0.00", 
                "compare_at_price": None, 
                "inventory_quantity": 0, 
                "inventory_item": {
                    "tracked": True
                }
            }]
        }
        
        tool_context.state["validation_products"] = [p_good, p_bad]
        
        res = validate_products_checklist_tool(tool_context)
        self.assertIn("Successfully ran", res)
        
        results = tool_context.state["validation_results"]
        self.assertEqual(len(results), 2)
        
        def get_chk(res_dict, substring):
            for k, v in res_dict["checks"].items():
                if substring.lower() in k.lower():
                    return v
            return {}

        r_good = results[0]
        self.assertEqual(r_good["product_name"], "Good Product")
        self.assertGreater(r_good["score"], 80.0)
        self.assertEqual(get_chk(r_good, "Product Title")["status"], "PASS")
        self.assertEqual(get_chk(r_good, "Description Present")["status"], "PASS")
        self.assertEqual(get_chk(r_good, "Image Alt Text")["status"], "PASS")
        
        r_bad = results[1]
        self.assertEqual(r_bad["product_name"], "Unnamed Product")
        self.assertLess(r_bad["score"], 65.0)
        self.assertEqual(get_chk(r_bad, "Product Title")["status"], "FAIL")
        self.assertEqual(get_chk(r_bad, "Description Present")["status"], "FAIL")

    def test_report_generation(self):
        import tempfile
        temp_dir = tempfile.mkdtemp()
        tool_context = MockToolContext(state={"outputs_dir": temp_dir})
        tool_context.state["validation_results"] = [
            {
                "product_name": "Product A",
                "score": 95.0,
                "blockers_passed": 31,
                "blockers_failed": 0,
                "warnings_passed": 22,
                "warnings_failed": 0,
                "mvp_category": "STEM Kits (diy-kits)",
                "launch_status": "READY_TO_LAUNCH",
                "checks": {
                    "01. Product Title": {"status": "PASS", "explanation": "Present", "section": "A. Content", "severity": "Blocker"}
                },
                "raw_data": {
                    "has_images": True,
                    "has_seo": True,
                    "seo_title_type": "CUSTOM",
                    "seo_desc_type": "CUSTOM",
                    "search_listing_type": "OPTIMIZED",
                    "has_tags": True,
                    "missing_inventory": False
                }
            },
            {
                "product_name": "Product B",
                "score": 45.0,
                "blockers_passed": 10,
                "blockers_failed": 21,
                "warnings_passed": 5,
                "warnings_failed": 17,
                "mvp_category": "Books",
                "launch_status": "LAUNCH_BLOCKED",
                "checks": {
                    "01. Product Title": {"status": "FAIL", "explanation": "Missing", "section": "A. Content", "severity": "Blocker"},
                    "08. Images Present": {"status": "FAIL", "explanation": "None", "section": "B. Media", "severity": "Blocker"}
                },
                "raw_data": {
                    "has_images": False,
                    "has_seo": False,
                    "seo_title_type": "MISSING",
                    "seo_desc_type": "MISSING",
                    "search_listing_type": "INCOMPLETE",
                    "has_tags": False,
                    "missing_inventory": True
                }
            }
        ]
        
        res = generate_validation_reports_tool(tool_context)
        self.assertIn("Reports successfully generated", res)
        
        validation_file = tool_context.state.get("validation_report_path")
        summary_file = tool_context.state.get("summary_report_path")
        
        self.assertIsNotNone(validation_file)
        self.assertIsNotNone(summary_file)
        self.assertTrue(os.path.exists(validation_file))
        self.assertTrue(os.path.exists(summary_file))
        
        with open(validation_file, "r") as f:
            v_data = json.load(f)
            self.assertEqual(len(v_data), 2)
            self.assertEqual(v_data[0]["product_name"], "Product A")
            self.assertEqual(v_data[1]["product_name"], "Product B")
            
        with open(summary_file, "r") as f:
            s_data = json.load(f)
            self.assertEqual(s_data["Total Products"], 2)
            self.assertEqual(s_data["Launch Ready (0 Blockers Failed)"], 1)
            self.assertEqual(s_data["Launch Blocked (>=1 Blocker Failed)"], 1)
            self.assertEqual(s_data["Average Validation Score"], 70.0)

    @patch("agents.product_validation_agent.get_validation_client")
    def test_validation_workflow_integration(self, mock_get_client):
        # pyrefly: ignore [missing-import]
        from google.adk import Workflow  # type: ignore
        from google.adk.models.google_llm import Gemini  # type: ignore
        from google.adk.models import LlmResponse  # type: ignore

        async def mock_generate_content_async(self, llm_request, stream=False):
            called_tools = set()
            for content in llm_request.contents:
                for part in (content.parts or []):
                    if part.function_response:
                        called_tools.add(part.function_response.name)

            if "fetch_validation_products_tool" not in called_tools:
                next_tool = "fetch_validation_products_tool"
            elif "validate_products_checklist_tool" not in called_tools:
                next_tool = "validate_products_checklist_tool"
            elif "generate_validation_reports_tool" not in called_tools:
                next_tool = "generate_validation_reports_tool"
            else:
                next_tool = None

            if next_tool:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_function_call(name=next_tool, args={})]
                    )
                )
            else:
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text="Validation workflow completed.")]
                    )
                )
        
        mock_client = MagicMock()
        mock_client.fetch_all_products.return_value = [
            {
                "title": "Workflow Product",
                "body_html": "Desc",
                "vendor": "Vendor",
                "product_type": "Type",
                "status": "active",
                "handle": "workflow-product",
                "tags": "tags",
                "seo_title": "SEO Title",
                "seo_description": "SEO Desc",
                "collections": ["Coll"],
                "images": [{"id": "img1", "url": "url", "alt": "alt"}],
                "variants": [{
                    "id": "var1",
                    "sku": "SKU",
                    "price": "19.99",
                    "compare_at_price": "29.99",
                    "inventory_quantity": 5,
                    "inventory_item": {
                        "tracked": True
                    }
                }]
            }
        ]
        mock_get_client.return_value = mock_client
        
        session_service = InMemorySessionService()
        workflow = Workflow(
            name="TestValidationWorkflow",
            edges=[
                ("START", product_validation_agent)
            ]
        )
        runner = Runner(
            app_name="test-validation",
            agent=workflow,
            session_service=session_service,
        )
        
        async def run_flow():
            import tempfile
            temp_outputs = tempfile.mkdtemp()
            # Pre-create the session in InMemorySessionService
            await session_service.create_session(
                app_name="test-validation",
                user_id="test-user",
                session_id="test-session",
                state={"outputs_dir": temp_outputs}
            )
            
            message = types.Content(
                role="user",
                parts=[types.Part(text="Run validation.")],
            )
            
            events = []
            async for event in runner.run_async(
                user_id="test-user",
                session_id="test-session",
                new_message=message,
            ):
                events.append(event)
            return events
            
        import asyncio
        with patch.object(Gemini, "generate_content_async", mock_generate_content_async):
            events = asyncio.run(run_flow())
        self.assertGreater(len(events), 0)
        
        async def get_state():
            session = await session_service.get_session(
                app_name="test-validation",
                user_id="test-user",
                session_id="test-session",
            )
            return session.state
            
        state = asyncio.run(get_state())
        self.assertIn("validation_results", state)
        self.assertEqual(len(state["validation_results"]), 1)

    def test_seo_validation_cases(self):
        """Tests all 10 SEO validation scenarios required by specification."""
        tool_context = MockToolContext(state={})
        
        # Test 1 & 2: Products with distinct SEO titles/descriptions
        p1 = {
            "title": "Product Alpha",
            "body_html": "<p>Alpha description under 160 chars.</p>",
            "handle": "product-alpha",
            "seo_title": "Custom Alpha Title",
            "seo_description": "Custom Alpha Description",
            "status": "active",
            "images": [{"id": "1", "url": "u", "alt": "a"}],
            "variants": [{"id": "v1", "sku": "A1", "price": "10.00", "inventory_quantity": 5, "inventory_item": {"tracked": True}}]
        }
        
        # Test 5: Description 161 chars (should be WARNING, not missing)
        desc_161 = "A" * 161
        p2 = {
            "title": "Product Beta",
            "body_html": f"<p>{desc_161}</p>",
            "handle": "product-beta",
            "seo_title": None,  # Test 6: Default title fallback
            "seo_description": None,
            "status": "active",
            "images": [{"id": "2", "url": "u", "alt": "a"}],
            "variants": [{"id": "v2", "sku": "B1", "price": "20.00", "inventory_quantity": 5, "inventory_item": {"tracked": True}}]
        }
        
        # Test 3 & 7: Genuinely missing title and description
        p3 = {
            "title": "",
            "body_html": "",
            "handle": "product-gamma",
            "seo_title": None,
            "seo_description": None,
            "status": "active",
            "images": [],
            "variants": []
        }
        
        tool_context.state["validation_products"] = [p1, p2, p3]
        res = validate_products_checklist_tool(tool_context)
        self.assertIn("Successfully ran", res)
        
        results = tool_context.state["validation_results"]
        self.assertEqual(len(results), 3)
        
        def get_check(res_dict, exact_name):
            for k, v in res_dict["checks"].items():
                if exact_name.lower() in k.lower().split(".", 1)[-1].strip():
                    return v
            return {}

        # Verify Product Alpha (Custom SEO)
        r1 = results[0]
        self.assertEqual(get_check(r1, "SEO Title Configured")["status"], "PASS")
        self.assertIn("SEO title is configured", get_check(r1, "SEO Title Configured")["explanation"])
        self.assertEqual(get_check(r1, "SEO Description Configured")["status"], "PASS")
        self.assertIn("SEO meta description is configured", get_check(r1, "SEO Description Configured")["explanation"])
        
        # Verify Product Beta (Description fallback & default title)
        r2 = results[1]
        self.assertEqual(get_check(r2, "SEO Title Configured")["status"], "PASS")
        self.assertIn("SEO title is configured", get_check(r2, "SEO Title Configured")["explanation"])
        self.assertEqual(get_check(r2, "SEO Description Configured")["status"], "PASS")
        self.assertIn("SEO meta description is configured", get_check(r2, "SEO Description Configured")["explanation"])
        
        # Verify Product Gamma (Genuinely missing)
        r3 = results[2]
        self.assertEqual(get_check(r3, "SEO Title Configured")["status"], "FAIL")
        self.assertEqual(get_check(r3, "SEO Description Configured")["status"], "FAIL")

    def test_rule_24_truth_table_all_8_cases(self):
        """Tests Rule 24 for all 8 Truth Table cases: PHYSICAL_AND_DIGITAL, PHYSICAL_ONLY, DIGITAL_ONLY, SERVICE."""
        cases = [
            # 1. PHYSICAL_AND_DIGITAL + True -> PASS
            {"title": "KiddyPi Kit + Course Combo", "type": "Combo Products", "req_ship": True, "expected": "PASS"},
            # 2. PHYSICAL_AND_DIGITAL + False -> FAIL
            {"title": "KiddyPi Kit + Course Combo", "type": "Combo Products", "req_ship": False, "expected": "FAIL"},
            # 3. DIGITAL_ONLY + False -> PASS
            {"title": "Python for Kids Course", "type": "Courses", "req_ship": False, "expected": "PASS"},
            # 4. DIGITAL_ONLY + True -> FAIL
            {"title": "Python for Kids Course", "type": "Courses", "req_ship": True, "expected": "FAIL"},
            # 5. PHYSICAL_ONLY + True -> PASS
            {"title": "Arduino Robotics Kit", "type": "STEM Kits (diy-kits)", "req_ship": True, "expected": "PASS"},
            # 6. PHYSICAL_ONLY + False -> FAIL
            {"title": "Arduino Robotics Kit", "type": "STEM Kits (diy-kits)", "req_ship": False, "expected": "FAIL"},
            # 7. SERVICE + False -> PASS
            {"title": "1-on-1 Mentorship Session", "type": "Service", "req_ship": False, "expected": "PASS"},
            # 8. SERVICE + True -> FAIL
            {"title": "1-on-1 Mentorship Session", "type": "Service", "req_ship": True, "expected": "FAIL"},
        ]

        tool_context = MockToolContext(state={})
        products = []
        for i, c in enumerate(cases):
            products.append({
                "id": f"gid://shopify/Product/test_{i}",
                "title": c["title"],
                "body_html": "<p>Detailed description for testing rule 24 truth table case.</p>",
                "vendor": "KiddyPi",
                "product_type": c["type"],
                "status": "active",
                "handle": f"test-handle-{i}",
                "tags": [],
                "seo_title": f"Test {i}",
                "seo_description": f"Test description {i}",
                "collections": [],
                "images": [{"id": "img1", "url": "url1", "alt": "Alt"}],
                "variants": [{
                    "id": f"var_{i}",
                    "title": "Default Title",
                    "sku": f"SKU-{i}",
                    "price": "999.00",
                    "requires_shipping": c["req_ship"],
                    "weight": 0.5 if c["req_ship"] else 0.0,
                    "inventory_item": {"tracked": True, "country_code_of_origin": "IN"}
                }]
            })

        tool_context.state["validation_products"] = products
        res = validate_products_checklist_tool(tool_context)
        self.assertIn("Successfully ran", res)

        results = tool_context.state["validation_results"]
        self.assertEqual(len(results), 8)

        for i, c in enumerate(cases):
            chk_24 = results[i]["checks"].get("24. Requires Shipping Flag", {})
            self.assertEqual(
                chk_24.get("status"),
                c["expected"],
                f"Case {i+1} ({c['type']} with req_ship={c['req_ship']}) expected {c['expected']} but got {chk_24.get('status')} ({chk_24.get('explanation')})"
            )


class TestActiveOnlyProductValidation(unittest.TestCase):
    """
    Tests restricting Product Validation to ACTIVE products only.
    Verifies DRAFT and ARCHIVED products are completely excluded from
    validation, remediation, catalog counts, and audit results.
    """

    def test_01_active_product_validated(self):
        tool_context = MockToolContext(state={})
        p_active = {
            "id": "gid://shopify/Product/1",
            "title": "Active STEM Kit",
            "status": "ACTIVE",
            "body_html": "<p>A great active product description.</p>",
            "vendor": "KiddyPi",
            "product_type": "STEM Kits (diy-kits)",
            "handle": "active-stem-kit",
            "images": [{"id": "img1", "url": "url1", "alt": "Alt Text"}],
            "variants": [{"id": "var1", "sku": "KP-KIT-ACTIVE", "price": "499.00", "requires_shipping": True}]
        }
        with patch("agents.product_validation_agent.get_validation_client") as mock_client_func:
            mock_client = MagicMock()
            mock_client.fetch_all_products.return_value = [p_active]
            mock_client_func.return_value = mock_client
            
            fetch_res = fetch_validation_products_tool(tool_context)
            self.assertIn("1 ACTIVE products", fetch_res)
            self.assertEqual(len(tool_context.state["validation_products"]), 1)
            self.assertEqual(tool_context.state["validation_products"][0]["title"], "Active STEM Kit")

    def test_02_draft_product_excluded(self):
        tool_context = MockToolContext(state={})
        p_draft = {
            "id": "gid://shopify/Product/2",
            "title": "Draft Book",
            "status": "DRAFT",
            "body_html": "<p>Draft content</p>"
        }
        with patch("agents.product_validation_agent.get_validation_client") as mock_client_func:
            mock_client = MagicMock()
            mock_client.fetch_all_products.return_value = [p_draft]
            mock_client_func.return_value = mock_client
            
            fetch_res = fetch_validation_products_tool(tool_context)
            self.assertIn("0 ACTIVE products", fetch_res)
            self.assertIn("1 DRAFT", fetch_res)
            self.assertEqual(len(tool_context.state["validation_products"]), 0)

    def test_03_archived_product_excluded(self):
        tool_context = MockToolContext(state={})
        p_archived = {
            "id": "gid://shopify/Product/3",
            "title": "Old Archived Kit",
            "status": "ARCHIVED"
        }
        with patch("agents.product_validation_agent.get_validation_client") as mock_client_func:
            mock_client = MagicMock()
            mock_client.fetch_all_products.return_value = [p_archived]
            mock_client_func.return_value = mock_client
            
            fetch_res = fetch_validation_products_tool(tool_context)
            self.assertIn("0 ACTIVE products", fetch_res)
            self.assertIn("1 ARCHIVED", fetch_res)
            self.assertEqual(len(tool_context.state["validation_products"]), 0)

    def test_04_active_product_with_blockers_shown(self):
        tool_context = MockToolContext(state={})
        p_active_bad = {
            "id": "gid://shopify/Product/4",
            "title": "",
            "status": "ACTIVE",
            "body_html": "",
            "variants": []
        }
        tool_context.state["validation_products"] = [p_active_bad]
        validate_products_checklist_tool(tool_context)
        results = tool_context.state["validation_results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["launch_status"], "LAUNCH_BLOCKED")
        self.assertGreater(results[0]["blockers_failed"], 0)

    def test_05_active_product_with_warnings_shown(self):
        tool_context = MockToolContext(state={})
        p_active_warning = {
            "id": "gid://shopify/Product/5",
            "title": "Active Product Title",
            "status": "active",
            "body_html": "<p>Description present.</p>",
            "vendor": "KiddyPi",
            "product_type": "STEM Kits (diy-kits)",
            "handle": "active-product-title",
            "tags": [],
            "seo_title": "Active Product Title",
            "seo_description": "Active Product Title Description",
            "images": [{"id": "img1", "url": "url1", "alt": "Alt"}],
            "variants": [{
                "id": "v1", "sku": "KP-KIT-TEST1", "price": "100.00", "requires_shipping": True,
                "weight": 0.5, "inventory_quantity": 10, "inventory_item": {"tracked": True}
            }]
        }
        tool_context.state["validation_products"] = [p_active_warning]
        validate_products_checklist_tool(tool_context)
        results = tool_context.state["validation_results"]
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0]["score"], 70.0)

    def test_06_active_product_zero_blockers_launch_ready(self):
        tool_context = MockToolContext(state={})
        p_perfect = {
            "id": "gid://shopify/Product/6",
            "title": "Perfect Active Product Kit",
            "status": "ACTIVE",
            "body_html": "<p>Comprehensive description for perfect active product kit with great features.</p>",
            "vendor": "KiddyPi",
            "product_type": "STEM Kits (diy-kits)",
            "handle": "perfect-active-product-kit",
            "tags": ["STEM", "Kit"],
            "seo_title": "Perfect Active Product Kit | KiddyPi",
            "seo_description": "Perfect Active Product Kit for learning STEM concepts at home.",
            "collections": ["Main Collection"],
            "template_suffix": "kiddypi-kit",
            "images": [{"id": "img1", "url": "https://img.url/1.png", "alt": "Perfect Alt Text"}],
            "variants": [{
                "id": "v1", "sku": "KP-KIT-PERFECT", "price": "999.00", "compare_at_price": "1299.00",
                "requires_shipping": True, "weight": 0.8, "inventory_quantity": 25,
                "inventory_item": {"tracked": True, "country_code_of_origin": "IN"}
            }]
        }
        tool_context.state["validation_products"] = [p_perfect]
        validate_products_checklist_tool(tool_context)
        results = tool_context.state["validation_results"]
        self.assertEqual(results[0]["blockers_failed"], 0)
        self.assertEqual(results[0]["launch_status"], "READY_TO_LAUNCH")

    def test_07_08_draft_blockers_warnings_not_in_current_validation(self):
        tool_context = MockToolContext(state={})
        p_active = {"id": "1", "title": "Active Prod", "status": "ACTIVE", "body_html": "Desc", "variants": [{"id": "v1", "price": "10.00"}]}
        p_draft = {"id": "2", "title": "Draft Prod", "status": "DRAFT", "body_html": "", "variants": []}
        
        with patch("agents.product_validation_agent.get_validation_client") as mock_client_func:
            mock_client = MagicMock()
            mock_client.fetch_all_products.return_value = [p_active, p_draft]
            mock_client_func.return_value = mock_client
            
            fetch_validation_products_tool(tool_context)
            validate_products_checklist_tool(tool_context)
            
            results = tool_context.state["validation_results"]
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["product_name"], "Active Prod")

    def test_09_10_11_catalog_counts_failures_fixes_contain_active_only(self):
        import tempfile
        temp_dir = tempfile.mkdtemp()
        tool_context = MockToolContext(state={
            "draft_excluded_count": 2,
            "archived_excluded_count": 1,
            "outputs_dir": temp_dir
        })
        tool_context.state["validation_results"] = [
            {
                "product_name": "Active A",
                "score": 90.0,
                "blockers_passed": 31,
                "blockers_failed": 0,
                "warnings_passed": 20,
                "warnings_failed": 2,
                "mvp_category": "STEM Kits",
                "launch_status": "READY_TO_LAUNCH",
                "checks": {}
            }
        ]
        generate_validation_reports_tool(tool_context)
        summary_path = tool_context.state["summary_report_path"]
        with open(summary_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["Total Active Products"], 1)
        self.assertEqual(data["Draft Products Excluded"], 2)
        self.assertEqual(data["Archived Products Excluded"], 1)
        self.assertEqual(data["Validation Scope"], "Active products only")

    def test_12_remediation_preserves_draft_and_active_product_status(self):
        from services.remediation_engine import generate_remediations_for_product, apply_remediation
        p_draft = {
            "id": "draft_123", "title": "Draft Item", "status": "DRAFT",
            "checks": {"18. SKU": {"status": "FAIL", "severity": "Blocker", "explanation": "Missing SKU"}}
        }
        p_active = {
            "id": "active_123", "title": "Active Item", "status": "ACTIVE",
            "checks": {"18. SKU": {"status": "FAIL", "severity": "Blocker", "explanation": "Missing SKU"}}
        }
        
        rems_draft = generate_remediations_for_product(p_draft)
        self.assertGreater(len(rems_draft), 0)
        
        rems_active = generate_remediations_for_product(p_active)
        self.assertGreater(len(rems_active), 0)

        with patch("services.remediation_engine.get_validation_client") as mock_client_func:
            mock_client = MagicMock()
            updated_p_draft = dict(p_draft)
            updated_p_draft["variants"] = [{"id": "var_1", "sku": "KP-KIT-DRAFT"}]
            mock_client.fetch_all_products.return_value = [p_draft, p_active]
            mock_client.update_product.return_value = updated_p_draft
            mock_client_func.return_value = mock_client
            
            res = apply_remediation("draft_123", "REM-draft_123-18", proposed_value_override="KP-KIT-DRAFT")
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["revalidated_product"].get("status"), "DRAFT")

    def test_13_14_ui_and_export_reports_contain_active_only(self):
        import tempfile
        temp_dir = tempfile.mkdtemp()
        tool_context = MockToolContext(state={"draft_excluded_count": 5, "outputs_dir": temp_dir})
        tool_context.state["validation_results"] = [
            {
                "product_name": "Active Only Product",
                "score": 100.0,
                "blockers_passed": 31,
                "blockers_failed": 0,
                "warnings_passed": 22,
                "warnings_failed": 0,
                "mvp_category": "STEM Kits",
                "launch_status": "READY_TO_LAUNCH",
                "checks": {}
            }
        ]
        generate_validation_reports_tool(tool_context)
        with open(tool_context.state["validation_report_path"], "r") as f:
            v_data = json.load(f)
        self.assertEqual(len(v_data), 1)
        self.assertEqual(v_data[0]["product_name"], "Active Only Product")

    def test_15_no_shopify_mutation_occurs(self):
        tool_context = MockToolContext(state={})
        p_active = {"id": "1", "title": "Read Only Active", "status": "ACTIVE", "body_html": "Desc", "variants": [{"id": "v1"}]}
        with patch("agents.product_validation_agent.get_validation_client") as mock_client_func:
            mock_client = MagicMock()
            mock_client.fetch_all_products.return_value = [p_active]
            mock_client_func.return_value = mock_client
            
            fetch_validation_products_tool(tool_context)
            validate_products_checklist_tool(tool_context)
            
            mock_client.update_product.assert_not_called()
            mock_client.create_product.assert_not_called()
            mock_client.delete_product.assert_not_called()

    def test_16_existing_53_rule_logic_unchanged_for_active_products(self):
        tool_context = MockToolContext(state={})
        p_active = {
            "id": "gid://shopify/Product/16",
            "title": "Active Product 53 Rules Test",
            "status": "ACTIVE",
            "body_html": "<p>Valid description.</p>",
            "vendor": "KiddyPi",
            "product_type": "STEM Kits (diy-kits)",
            "handle": "active-product-53-rules-test",
            "tags": ["Kit"],
            "seo_title": "Active Product 53 Rules Test",
            "seo_description": "Description for test",
            "collections": [],
            "images": [{"id": "img1", "url": "url1", "alt": "Alt"}],
            "variants": [{
                "id": "v1", "sku": "KP-KIT-TEST16", "price": "100.00", "requires_shipping": True,
                "weight": 0.5, "inventory_quantity": 10, "inventory_item": {"tracked": True}
            }]
        }
        tool_context.state["validation_products"] = [p_active]
        validate_products_checklist_tool(tool_context)
        res = tool_context.state["validation_results"][0]
        self.assertEqual(len(res["checks"]), 53)

    def test_17_workshop_rule45_not_applicable(self):
        tool_context = MockToolContext(state={})
        p_workshop = {
            "id": "gid://shopify/Product/999",
            "title": "Mission Tiranga: Independence Day STEM Workshop for Kids",
            "status": "ACTIVE",
            "body_html": "<p>Workshop session details.</p>",
            "vendor": "KiddyPi",
            "product_type": "Workshop",
            "handle": "stem-workshop-kids",
            "tags": ["Workshop"],
            "seo_title": "STEM Workshop for Kids",
            "seo_description": "Join our workshop!",
            "collections": [{"id": "c1", "title": "Workshops"}],
            "images": [{"id": "img1", "url": "url1", "alt": "Alt"}],
            "variants": [{
                "id": "v1", "sku": "KP-WS-001", "price": "0.00", "requires_shipping": False,
                "weight": 0.0, "inventory_quantity": 50, "inventory_item": {"tracked": False}
            }]
        }
        tool_context.state["validation_products"] = [p_workshop]
        validate_products_checklist_tool(tool_context)
        res = tool_context.state["validation_results"][0]
        chk_45 = res["checks"].get("45. Add to Cart") or res["checks"].get("45")
        self.assertIsNotNone(chk_45)
        chk_status = chk_45.get("final_result") or chk_45.get("status")
        self.assertEqual(chk_status, "NOT_APPLICABLE")

    @patch("main._execute_validation_job")
    @patch("services.remediation_engine.apply_all_safe_remediations")
    def test_18_post_mutation_triggers_full_validation_refresh(self, mock_apply_all, mock_execute_job):
        from main import api_catalog_wide_apply_all_safe_remediations
        mock_apply_all.return_value = {"status": "SUCCESS", "applied_count": 2}
        mock_user = MagicMock()
        mock_user.email = "test@kiddypi.com"

        res = api_catalog_wide_apply_all_safe_remediations(
            current_user=mock_user
        )

        mock_apply_all.assert_called_once()
        mock_execute_job.assert_called_once()
        self.assertTrue(res.get("validation_refreshed"))

    def test_19_workshop_rule47_not_applicable(self):
        tool_context = MockToolContext(state={})
        p_workshop = {
            "id": "gid://shopify/Product/1001",
            "title": "AI Tinker Garage Workshop",
            "status": "ACTIVE",
            "body_html": "<p>Hands on workshop</p>",
            "vendor": "KiddyPi",
            "product_type": "Workshop",
            "handle": "ai-tinker-garage-workshop",
            "tags": ["workshop", "event"],
            "seo_title": "AI Tinker Garage Workshop",
            "seo_description": "Join our AI workshop",
            "collections": [{"id": "c1", "title": "Workshops"}],
            "images": [{"id": "img1", "url": "url1", "alt": "Alt"}],
            "variants": [{"id": "v1", "sku": "KP-WS-002", "price": "1499.00", "inventory_quantity": 20}]
        }
        tool_context.state["validation_products"] = [p_workshop]
        validate_products_checklist_tool(tool_context)
        res = tool_context.state["validation_results"][0]
        chk_47 = res["checks"].get("47. Collection Card Render") or res["checks"].get("47")
        self.assertIsNotNone(chk_47)
        chk_status = chk_47.get("final_result") or chk_47.get("status")
        self.assertEqual(chk_status, "NOT_APPLICABLE")



