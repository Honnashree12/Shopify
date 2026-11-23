"""
Google Search Console (GSC) Integration Service.

Provides:
1. Google OAuth 2.0 Authorization & Token Refresh (Server-side only) and Service Account support.
   - Minimum required read-only scope: https://www.googleapis.com/auth/webmasters.readonly
   - Offline access to retrieve refresh tokens.
2. Property Verification Check:
   - Verifies target website property (Avenue Products) ownership and permission level.
   - Never assumes property is verified without API confirmation.
3. Search Analytics Data Retrieval:
   - Clicks, impressions, CTR, average position.
   - Date range filtering (startDate, endDate) and dimension grouping (query, page, date).
   - Pagination support (startRow, rowLimit).
   - Graceful handling of expired tokens, API rate limits (429), and permission denials (403).
4. Shopify URL Mapping:
   - Maps GSC page-level performance to existing Shopify product handles.
   - Categorizes top-performing products, low-visibility products, and unranked products.
   - Identifies unmatched site pages without modifying product handles.
5. Security & Read-Only Integrity:
   - Zero product modifications or auto-tuning.
   - Client secrets and access tokens remain strictly server-side.
   - Clear disclaimers that analytics data is descriptive and does not predict ranking algorithms.
"""

import os
import json
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

import httpx
from dotenv import load_dotenv

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

logger = logging.getLogger("google_search_console_service")

OUTPUTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
TOKEN_STORAGE_PATH = os.path.join(OUTPUTS_DIR, "gsc_token.json")

GSC_READONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GOOGLE_OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_API_BASE_URL = "https://www.googleapis.com/webmasters/v3"

DEFAULT_SITE_PROPERTY = "https://kinq5t-q5.myshopify.com"
DEFAULT_AVENUE_PROPERTY = DEFAULT_SITE_PROPERTY


class GoogleSearchConsoleService:
    """Decoupled client for Google Search Console API v3 with OAuth 2.0 & Service Account support."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        site_url: Optional[str] = None,
        token_path: Optional[str] = None,
        service_account_path: Optional[str] = None,
    ):
        if os.path.exists(ENV_PATH):
            load_dotenv(ENV_PATH, override=True)
        self.client_id = client_id if client_id is not None else (os.getenv("GOOGLE_CLIENT_ID") or "")
        self.client_secret = client_secret if client_secret is not None else (os.getenv("GOOGLE_CLIENT_SECRET") or "")
        self.redirect_uri = (
            redirect_uri
            or os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
            or "http://localhost:8000/api/seo/search-console/oauth/callback"
        )
        # Default to configured Search Console URL or active Shopify store domain
        from config import settings
        store_domain = os.getenv("SHOPIFY_STORE_URL") or settings.shopify_store_url or ""
        default_site = f"https://{store_domain}" if store_domain and not store_domain.startswith("http") else store_domain
        self.site_url = (
            site_url
            or os.getenv("SEARCH_CONSOLE_SITE_URL")
            or settings.effective_search_console_site_url
            or default_site
        )
        self.token_path = token_path or TOKEN_STORAGE_PATH
        self.service_account_path = (
            service_account_path
            or os.getenv("GSC_SERVICE_ACCOUNT_KEY")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )

    # ==========================================================================
    # 1. OAuth 2.0 Authorization & Token Management
    # ==========================================================================

    def get_authorization_url(self, state: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates Google OAuth 2.0 consent URL with minimum read-only permissions.
        """
        if not self.client_id:
            return {
                "success": False,
                "error": "GOOGLE_CLIENT_ID is not configured in environment.",
                "auth_url": None,
            }

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": GSC_READONLY_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        auth_url = f"{GOOGLE_OAUTH_AUTH_URL}?{urllib.parse.urlencode(params)}"
        return {
            "success": True,
            "auth_url": auth_url,
            "scope": GSC_READONLY_SCOPE,
        }

    def exchange_code(self, code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchanges authorization code for access and refresh tokens.
        Tokens are persisted securely server-side and never returned in full to the client.
        """
        if not self.client_id or not self.client_secret:
            return {
                "success": False,
                "error": "Google OAuth client credentials (ID/Secret) are missing.",
            }

        payload = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(GOOGLE_OAUTH_TOKEN_URL, data=payload)
                if res.status_code != 200:
                    logger.error("Token exchange failed (%d): %s", res.status_code, res.text)
                    return {
                        "success": False,
                        "error": f"Token exchange failed with HTTP {res.status_code}",
                        "details": res.text,
                    }

                token_data = res.json()
                self._save_token_data(token_data)
                return {
                    "success": True,
                    "connected": True,
                    "site_url": self.site_url,
                    "expires_in": token_data.get("expires_in"),
                }
        except Exception as exc:
            logger.exception("Unexpected error exchanging authorization code: %s", exc)
            return {"success": False, "error": str(exc)}

    def refresh_access_token(self) -> Optional[str]:
        """
        Uses stored refresh token to obtain a new access token.
        """
        stored = self._load_token_data()
        refresh_token = stored.get("refresh_token")
        if not refresh_token:
            logger.warning("No refresh token available to renew GSC credentials.")
            return None

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(GOOGLE_OAUTH_TOKEN_URL, data=payload)
                if res.status_code == 200:
                    new_data = res.json()
                    # Preserve existing refresh token if not returned in rotation
                    if "refresh_token" not in new_data:
                        new_data["refresh_token"] = refresh_token
                    self._save_token_data(new_data)
                    return new_data.get("access_token")
                else:
                    logger.error("Failed to refresh token: %s", res.text)
                    return None
        except Exception as exc:
            logger.error("Exception during token refresh: %s", exc)
            return None

    def _save_token_data(self, data: Dict[str, Any]) -> None:
        """Saves tokens to server-side JSON file with expiration timestamp."""
        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        expires_in = data.get("expires_in", 3600)
        data["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)).isoformat()
        try:
            with open(self.token_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Could not write GSC token file: %s", e)

    def _load_token_data(self) -> Dict[str, Any]:
        """Reads server-side tokens if present."""
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def get_valid_access_token(self) -> Optional[str]:
        """Returns active access token from Service Account or stored OAuth credentials."""
        # 1. Check Service Account if configured
        if self.service_account_path and os.path.exists(self.service_account_path):
            try:
                from google.oauth2 import service_account
                from google.auth.transport.requests import Request
                creds = service_account.Credentials.from_service_account_file(
                    self.service_account_path,
                    scopes=[GSC_READONLY_SCOPE]
                )
                creds.refresh(Request())
                if creds.token:
                    return creds.token
            except Exception as exc:
                logger.debug("Service account authentication skipped or failed: %s", exc)

        # 2. Check stored OAuth tokens
        data = self._load_token_data()
        token = data.get("access_token")
        if not token:
            return None

        expires_at_str = data.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now(timezone.utc) >= expires_at:
                    logger.info("Access token expired. Refreshing token...")
                    return self.refresh_access_token()
            except Exception:
                pass

        return token

    # ==========================================================================
    # 2. Property Verification Diagnostics
    # ==========================================================================

    def verify_site_property(self, site_url: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifies property ownership and permission level with Google Search Console API.
        Do not assume property is verified: inspects sites API.
        """
        target_site = site_url or self.site_url
        access_token = token or self.get_valid_access_token()

        if not access_token:
            return {
                "verified": False,
                "status": "NEEDS_AUTHENTICATION",
                "site_url": target_site,
                "message": "Authentication credentials not available.",
            }

        encoded_site = urllib.parse.quote(target_site, safe="")
        endpoint = f"{GSC_API_BASE_URL}/sites/{encoded_site}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(endpoint, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    permission_level = data.get("permissionLevel", "")
                    is_verified = permission_level in ["siteOwner", "siteFullUser", "siteRestrictedUser"]
                    return {
                        "verified": is_verified,
                        "status": "VERIFIED" if is_verified else "UNVERIFIED",
                        "site_url": target_site,
                        "permission_level": permission_level,
                        "message": f"Property '{target_site}' verified ({permission_level}).",
                    }
                elif res.status_code == 404:
                    return {
                        "verified": False,
                        "status": "NOT_FOUND",
                        "site_url": target_site,
                        "permission_level": None,
                        "message": (
                            f"Property '{target_site}' was not found in your Google Search Console account. "
                            f"Please add and verify ownership of '{target_site}' in Google Search Console."
                        ),
                    }
                elif res.status_code == 403:
                    return {
                        "verified": False,
                        "status": "PERMISSION_DENIED",
                        "site_url": target_site,
                        "permission_level": None,
                        "message": (
                            f"Permission denied for property '{target_site}'. "
                            "Ensure the authenticated account has owner or user access in Google Search Console."
                        ),
                    }
                else:
                    return {
                        "verified": False,
                        "status": f"HTTP_{res.status_code}",
                        "site_url": target_site,
                        "permission_level": None,
                        "message": f"GSC verification check returned HTTP {res.status_code}",
                    }
        except Exception as exc:
            logger.warning("Error verifying site property '%s': %s", target_site, exc)
            return {
                "verified": False,
                "status": "ERROR",
                "site_url": target_site,
                "message": str(exc),
            }

    def get_service_status(self) -> Dict[str, Any]:
        """
        Reports current connection and property verification status.
        Never fabricates data; distinguishes unconfigured, needs auth, unverified, and connected.
        """
        token = self.get_valid_access_token()
        has_sa = bool(self.service_account_path and os.path.exists(self.service_account_path))
        has_oauth = bool(self.client_id and self.client_secret)

        if not has_oauth and not has_sa:
            return {
                "status": "UNCONFIGURED",
                "connected": False,
                "verified": False,
                "site_url": self.site_url,
                "auth_method": None,
                "message": (
                    "Google Search Console credentials (OAuth GOOGLE_CLIENT_ID or Service Account GSC_SERVICE_ACCOUNT_KEY) are not set. "
                    "All Shopify SEO optimization and publishing features remain 100% operational."
                ),
                "scope_required": GSC_READONLY_SCOPE,
                "disclaimer": "Search Console metrics evaluate past organic performance; they do not predict rankings.",
            }

        if not token:
            return {
                "status": "NEEDS_AUTHENTICATION",
                "connected": False,
                "verified": False,
                "site_url": self.site_url,
                "auth_method": "SERVICE_ACCOUNT" if has_sa else "OAUTH",
                "message": "Google credentials configured, but no active account is connected. Authorize Search Console to begin.",
                "scope_required": GSC_READONLY_SCOPE,
                "disclaimer": "Search Console metrics evaluate past organic performance; they do not predict rankings.",
            }

        # Check property verification against Google API
        verification = self.verify_site_property(self.site_url, token=token)
        if not verification.get("verified"):
            return {
                "status": "PROPERTY_UNVERIFIED",
                "connected": True,
                "verified": False,
                "site_url": self.site_url,
                "auth_method": "SERVICE_ACCOUNT" if has_sa else "OAUTH",
                "permission_level": verification.get("permission_level"),
                "message": verification.get(
                    "message",
                    f"Connected to Google account, but property '{self.site_url}' is not verified."
                ),
                "disclaimer": "Search Console requires verified site ownership before performance metrics can be retrieved.",
            }

        return {
            "status": "CONNECTED",
            "connected": True,
            "verified": True,
            "site_url": self.site_url,
            "auth_method": "SERVICE_ACCOUNT" if has_sa else "OAUTH",
            "permission_level": verification.get("permission_level", "siteOwner"),
            "message": f"Connected to verified Google Search Console property '{self.site_url}' with read-only access.",
            "disclaimer": "Rankings and impressions are determined by search engine algorithms.",
        }

    # ==========================================================================
    # 3. Search Analytics Data Retrieval
    # ==========================================================================

    def fetch_search_analytics(
        self,
        start_date: str,
        end_date: str,
        dimensions: Optional[List[str]] = None,
        row_limit: int = 250,
        start_row: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetches clicks, impressions, CTR, and average position from Google Search Console API.
        Handles token refresh, rate limits (429), missing permissions (403), and pagination.
        """
        token = self.get_valid_access_token()
        if not token:
            status = self.get_service_status()
            return {
                "success": False,
                "status": status.get("status"),
                "site_url": self.site_url,
                "total_rows": 0,
                "rows": [],
                "error": status.get("message"),
                "disclaimer": "Search Console metrics require verified Google property ownership.",
            }

        dimensions = dimensions or ["page", "query"]

        encoded_site = urllib.parse.quote(self.site_url, safe="")
        endpoint = f"{GSC_API_BASE_URL}/sites/{encoded_site}/searchAnalytics/query"

        request_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": min(row_limit, 5000),
            "startRow": start_row,
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=25.0) as client:
                res = client.post(endpoint, json=request_body, headers=headers)

                # If token expired mid-session, attempt single refresh
                if res.status_code == 401:
                    logger.info("GSC API returned 401. Attempting refresh token...")
                    refreshed = self.refresh_access_token()
                    if refreshed:
                        headers["Authorization"] = f"Bearer {refreshed}"
                        res = client.post(endpoint, json=request_body, headers=headers)

                if res.status_code == 403:
                    logger.warning("GSC Permission Denied (403): %s", res.text)
                    return {
                        "success": False,
                        "status": "PERMISSION_DENIED",
                        "error": (
                            f"Access denied for property '{self.site_url}'. Ensure the authenticated "
                            f"Google account is a verified owner or user of '{self.site_url}' in Google Search Console."
                        ),
                        "details": res.text,
                    }

                if res.status_code == 429:
                    logger.warning("GSC rate limit exceeded (429)")
                    return {
                        "success": False,
                        "status": "RATE_LIMITED",
                        "error": "Google Search Console API rate limit exceeded. Please retry in a few minutes.",
                    }

                if res.status_code != 200:
                    logger.error("GSC query error (%d): %s", res.status_code, res.text)
                    return {
                        "success": False,
                        "status": "ERROR",
                        "error": f"Search Console API returned error {res.status_code}: {res.text}",
                    }

                data = res.json()
                raw_rows = data.get("rows", [])

                # Calculate aggregates
                total_clicks = sum(r.get("clicks", 0) for r in raw_rows)
                total_impressions = sum(r.get("impressions", 0) for r in raw_rows)
                avg_ctr = (
                    round((total_clicks / total_impressions) * 100, 2)
                    if total_impressions > 0
                    else 0.0
                )
                weighted_pos = (
                    sum(r.get("position", 0) * r.get("impressions", 0) for r in raw_rows)
                    / total_impressions
                    if total_impressions > 0
                    else 0.0
                )

                # Aggregate top search queries across all rows
                query_aggregates: Dict[str, Dict[str, Any]] = {}
                for r in raw_rows:
                    keys = r.get("keys", [])
                    # If query is in keys (e.g. ["page", "query"] -> keys[1])
                    q_text = None
                    if len(keys) >= 2:
                        q_text = keys[1]
                    elif len(keys) == 1 and "query" in dimensions:
                        q_text = keys[0]

                    if q_text:
                        if q_text not in query_aggregates:
                            query_aggregates[q_text] = {
                                "query": q_text,
                                "clicks": 0,
                                "impressions": 0,
                                "positions": [],
                            }
                        query_aggregates[q_text]["clicks"] += r.get("clicks", 0)
                        query_aggregates[q_text]["impressions"] += r.get("impressions", 0)
                        query_aggregates[q_text]["positions"].append(r.get("position", 0))

                top_queries = []
                for q, item in query_aggregates.items():
                    impr = item["impressions"]
                    clicks = item["clicks"]
                    positions = item["positions"]
                    avg_p = round(sum(positions) / len(positions), 1) if positions else 0.0
                    ctr = round((clicks / impr) * 100, 2) if impr > 0 else 0.0
                    top_queries.append({
                        "query": q,
                        "clicks": clicks,
                        "impressions": impr,
                        "ctr": ctr,
                        "average_position": avg_p,
                    })

                top_queries.sort(key=lambda x: (x["clicks"], x["impressions"]), reverse=True)

                return {
                    "success": True,
                    "status": "CONNECTED",
                    "site_url": self.site_url,
                    "date_range": {"start": start_date, "end": end_date},
                    "total_rows": len(raw_rows),
                    "summary": {
                        "total_clicks": total_clicks,
                        "total_impressions": total_impressions,
                        "average_ctr": avg_ctr,
                        "average_position": round(weighted_pos, 1),
                    },
                    "top_queries": top_queries[:30],
                    "rows": raw_rows,
                    "disclaimer": "Performance measurements reflect organic Google Search appearances over the selected date range.",
                }

        except httpx.RequestError as exc:
            logger.error("Network error querying Google Search Console: %s", exc)
            return {
                "success": False,
                "status": "NETWORK_ERROR",
                "error": f"Network request to Google Search Console failed: {exc}",
            }
        except Exception as exc:
            logger.exception("Unexpected exception in fetch_search_analytics: %s", exc)
            return {
                "success": False,
                "status": "ERROR",
                "error": str(exc),
            }

    # ==========================================================================
    # 4. Shopify URL Mapping & Performance Categorization
    # ==========================================================================

    @staticmethod
    def map_search_console_to_shopify(
        gsc_rows: List[Dict[str, Any]],
        shopify_products: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Maps Search Console performance data (page URLs) to Shopify product handles.

        Returns:
        - matched_products: Shopify products matched to GSC metrics
        - top_performing_products: Matched products sorted by organic traffic
        - low_visibility_products: Products appearing in search with low impressions (<50) or 0 clicks
        - unranked_products: Shopify products with 0 impressions / no GSC data
        - unmatched_pages: Search Console URLs that don't match any active Shopify product
        """
        # Build lookup table of Shopify products by handle and relative path
        product_by_handle: Dict[str, Dict[str, Any]] = {}
        for p in shopify_products:
            handle = str(p.get("handle") or "").strip().lower()
            if handle:
                product_by_handle[handle] = p

        matched_data: Dict[str, Dict[str, Any]] = {}
        unmatched_pages: List[Dict[str, Any]] = []

        for row in gsc_rows:
            keys = row.get("keys", [])
            page_url = keys[0] if keys else row.get("page", "")

            # Extract handle from URL path (e.g. https://domain.com/products/my-handle -> my-handle)
            parsed = urllib.parse.urlparse(page_url)
            path = parsed.path.strip("/")
            parts = path.split("/")

            handle = None
            if len(parts) >= 2 and parts[-2] == "products":
                handle = parts[-1].lower()
            elif len(parts) == 1 and parts[0] in product_by_handle:
                handle = parts[0].lower()

            if handle and handle in product_by_handle:
                prod = product_by_handle[handle]
                pid = str(prod.get("id"))
                if pid not in matched_data:
                    matched_data[pid] = {
                        "product_id": pid,
                        "title": prod.get("title"),
                        "handle": handle,
                        "page_url": page_url,
                        "clicks": 0,
                        "impressions": 0,
                        "ctr": 0.0,
                        "positions": [],
                        "queries": [],
                    }

                matched_data[pid]["clicks"] += row.get("clicks", 0)
                matched_data[pid]["impressions"] += row.get("impressions", 0)
                matched_data[pid]["positions"].append(row.get("position", 0))

                # If query dimension exists in keys
                if len(keys) > 1:
                    query_text = keys[1]
                    matched_data[pid]["queries"].append({
                        "query": query_text,
                        "clicks": row.get("clicks", 0),
                        "impressions": row.get("impressions", 0),
                        "position": row.get("position", 0),
                    })
            else:
                unmatched_pages.append({
                    "page_url": page_url,
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0),
                    "position": row.get("position", 0),
                })

        # Calculate weighted averages for matched products
        matched_products: List[Dict[str, Any]] = []
        matched_ids = set()
        for pid, item in matched_data.items():
            matched_ids.add(pid)
            impr = item["impressions"]
            clicks = item["clicks"]
            positions = item["positions"]
            avg_pos = round(sum(positions) / len(positions), 1) if positions else 0.0
            ctr = round((clicks / impr) * 100, 2) if impr > 0 else 0.0
            item["ctr"] = ctr
            item["average_position"] = avg_pos
            item["positions"] = None  # drop raw array
            # Sort queries by clicks/impressions
            item["queries"].sort(key=lambda q: (q["clicks"], q["impressions"]), reverse=True)
            matched_products.append(item)

        # Sort matched products by clicks descending
        matched_products.sort(key=lambda m: (m["clicks"], m["impressions"]), reverse=True)

        # Categorize top-performing products (top 10 by clicks/impressions)
        top_performing_products = [p for p in matched_products if p["clicks"] > 0][:10]
        if not top_performing_products and matched_products:
            top_performing_products = matched_products[:5]

        # Categorize low-visibility products (impressions > 0 but clicks == 0 or impressions < 50)
        low_visibility_products = [
            p for p in matched_products if p["clicks"] == 0 or p["impressions"] < 50
        ]

        # Unranked products (0 impressions recorded in Search Console)
        unranked_products: List[Dict[str, Any]] = []
        for p in shopify_products:
            pid = str(p.get("id"))
            if pid not in matched_ids:
                unranked_products.append({
                    "product_id": pid,
                    "title": p.get("title"),
                    "handle": p.get("handle"),
                    "status": "UNRANKED / NO_IMPRESSIONS",
                    "clicks": 0,
                    "impressions": 0,
                })

        return {
            "total_shopify_products": len(shopify_products),
            "matched_count": len(matched_products),
            "top_performing_count": len(top_performing_products),
            "low_visibility_count": len(low_visibility_products),
            "unranked_count": len(unranked_products),
            "unmatched_pages_count": len(unmatched_pages),
            "matched_products": matched_products,
            "top_performing_products": top_performing_products,
            "low_visibility_products": low_visibility_products,
            "unranked_products": unranked_products,
            "unmatched_pages": unmatched_pages[:50],  # top 50 non-product URLs
        }
