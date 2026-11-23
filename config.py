import os
import sys
import logging
import contextvars
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Context variables for request, session, and workflow tracing in logs
request_id_var = contextvars.ContextVar("request_id", default="-")
session_id_var = contextvars.ContextVar("session_id", default="-")
workflow_id_var = contextvars.ContextVar("workflow_id", default="-")


class Settings(BaseSettings):
    # App General Configuration
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")

    # Shopify Configuration
    shopify_store_url: Optional[str] = Field(default=None, validation_alias="SHOPIFY_STORE_URL")
    shopify_access_token: Optional[str] = Field(default=None, validation_alias="SHOPIFY_ACCESS_TOKEN")
    shopify_api_version: str = Field(default="2025-07", validation_alias="SHOPIFY_API_VERSION")
    shopify_api_secret: Optional[str] = Field(default=None, validation_alias="SHOPIFY_API_SECRET")
    shopify_client_id: Optional[str] = Field(default=None, validation_alias="SHOPIFY_CLIENT_ID")
    shopify_client_secret: Optional[str] = Field(default=None, validation_alias="SHOPIFY_CLIENT_SECRET")
    shopify_redirect_uri: Optional[str] = Field(default=None, validation_alias="SHOPIFY_REDIRECT_URI")
    shopify_app_url: Optional[str] = Field(default=None, validation_alias="SHOPIFY_APP_URL")

    # Multi-store Shopify Configuration
    shopify_dev_store: Optional[str] = Field(default=None, validation_alias="SHOPIFY_DEV_STORE")
    shopify_dev_token: Optional[str] = Field(default=None, validation_alias="SHOPIFY_DEV_TOKEN")
    shopify_validation_store: Optional[str] = Field(default=None, validation_alias="SHOPIFY_VALIDATION_STORE")
    shopify_validation_token: Optional[str] = Field(default=None, validation_alias="SHOPIFY_VALIDATION_TOKEN")

    @property
    def dev_store_url(self) -> Optional[str]:
        return self.shopify_dev_store or self.shopify_store_url

    @property
    def dev_access_token(self) -> Optional[str]:
        return self.shopify_dev_token or self.shopify_access_token

    @property
    def validation_store_url(self) -> Optional[str]:
        return self.shopify_validation_store

    @property
    def validation_access_token(self) -> Optional[str]:
        return self.shopify_validation_token


    # Firebase Configuration
    firebase_service_account_key: Optional[str] = Field(default=None, validation_alias="FIREBASE_SERVICE_ACCOUNT_KEY")
    firebase_storage_bucket: Optional[str] = Field(default=None, validation_alias="FIREBASE_STORAGE_BUCKET")

    # Security / Production Hardening (Phase 5)
    # Comma-separated list of allowed browser origins, e.g.
    # "https://cockpit.example.com,https://admin.example.com". Defaults to
    # "*" (all origins) only for local/dev convenience -- validate_startup()
    # below refuses to boot with a wildcard in a non-testing environment
    # when app_env == "production".
    cors_allowed_origins: str = Field(default="*", validation_alias="CORS_ALLOWED_ORIGINS")
    max_upload_file_size_mb: int = Field(default=15, validation_alias="MAX_UPLOAD_FILE_SIZE_MB")
    max_upload_total_files: int = Field(default=300, validation_alias="MAX_UPLOAD_TOTAL_FILES")

    @property
    def cors_origins_list(self) -> list:
        if not self.cors_allowed_origins or self.cors_allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    # Google Cloud / Vertex AI / Gemini API
    google_genai_use_vertexai: bool = Field(default=True, validation_alias="GOOGLE_GENAI_USE_VERTEXAI")
    google_cloud_project: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLOUD_PROJECT")
    google_cloud_location: str = Field(default="us-central1", validation_alias="GOOGLE_CLOUD_LOCATION")
    google_api_key: Optional[str] = Field(default=None, validation_alias="GOOGLE_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")

    # Google Sheets Configuration (Student Registration Automation)
    google_sheets_spreadsheet_id: Optional[str] = Field(default=None, validation_alias="GOOGLE_SHEETS_SPREADSHEET_ID")
    google_sheets_tab_name: str = Field(default="Registrations", validation_alias="GOOGLE_SHEETS_TAB_NAME")
    google_application_credentials: Optional[str] = Field(default=None, validation_alias="GOOGLE_APPLICATION_CREDENTIALS")
    mock_google_sheets: bool = Field(default=False, validation_alias="MOCK_GOOGLE_SHEETS")

    # Google Search Console Configuration (Phase 4)
    search_console_site_url: Optional[str] = Field(default=None, validation_alias="SEARCH_CONSOLE_SITE_URL")
    google_client_id: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLIENT_SECRET")
    google_oauth_redirect_uri: Optional[str] = Field(
        default=None,
        validation_alias="GOOGLE_OAUTH_REDIRECT_URI"
    )
    gsc_service_account_key: Optional[str] = Field(default=None, validation_alias="GSC_SERVICE_ACCOUNT_KEY")

    @property
    def effective_search_console_site_url(self) -> Optional[str]:
        if self.search_console_site_url:
            return self.search_console_site_url
        if self.shopify_store_url:
            return f"https://{self.shopify_store_url}" if not self.shopify_store_url.startswith("http") else self.shopify_store_url
        return None

    @property
    def effective_google_oauth_redirect_uri(self) -> str:
        if self.google_oauth_redirect_uri:
            return self.google_oauth_redirect_uri
        host = self.app_host if self.app_host not in ("0.0.0.0", "::") else "localhost"
        return f"http://{host}:{self.app_port}/api/seo/search-console/oauth/callback"

    # SMTP / Email Configuration
    sender_email: str = Field(default="space-workshops@example.com", validation_alias="SENDER_EMAIL")
    sales_team_email: str = Field(default="sales@example.com", validation_alias="SALES_TEAM_EMAIL")
    smtp_server: Optional[str] = Field(default=None, validation_alias="SMTP_SERVER")
    smtp_port: Optional[int] = Field(default=None, validation_alias="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, validation_alias="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, validation_alias="SMTP_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True
    )

    def validate_startup(self):
        """
        Verify presence of required environment configuration at startup.
        Strict verification is bypassed during unit tests to allow testing.
        """
        is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "True"
        if is_testing:
            return

        missing = []
        if not self.shopify_store_url:
            missing.append("SHOPIFY_STORE_URL")
        # For OAuth flow, the token is fetched dynamically, so we only require SHOPIFY_ACCESS_TOKEN
        # if the client ID or client secret are missing.
        if not self.shopify_access_token and (not self.shopify_client_id or not self.shopify_client_secret):
            missing.append("SHOPIFY_ACCESS_TOKEN (or both SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET for OAuth)")

        if self.app_env == "production":
            if self.cors_origins_list == ["*"]:
                raise ValueError(
                    "\n"
                    "=================================================================\n"
                    "CRITICAL STARTUP ERROR: WILDCARD CORS IN PRODUCTION\n"
                    "=================================================================\n"
                    "APP_ENV=production but CORS_ALLOWED_ORIGINS is unset or '*'. This\n"
                    "would allow any website to make authenticated, credentialed\n"
                    "requests to this API. Set CORS_ALLOWED_ORIGINS to a comma-separated\n"
                    "allowlist of the real cockpit frontend origin(s), e.g.\n"
                    "  CORS_ALLOWED_ORIGINS=https://cockpit.example.com\n"
                    "=================================================================\n"
                )
            if self.mock_google_sheets:
                raise ValueError(
                    "\n"
                    "=================================================================\n"
                    "CRITICAL STARTUP ERROR: MOCK GOOGLE SHEETS IN PRODUCTION\n"
                    "=================================================================\n"
                    "APP_ENV=production but MOCK_GOOGLE_SHEETS=True. Production cannot\n"
                    "use mock mode. Set MOCK_GOOGLE_SHEETS=False and provide valid credentials.\n"
                    "=================================================================\n"
                )

        if missing:
            msg = (
                "\n"
                "=================================================================\n"
                "CRITICAL STARTUP ERROR: MISSING SHOPIFY CONFIGURATION\n"
                "=================================================================\n"
                f"Required Shopify configuration is missing: {', '.join(missing)}\n"
                "Please create a .env file from .env.example and populate your values:\n"
                "  cp .env.example .env\n"
                "=================================================================\n"
            )
            raise ValueError(msg)

    def __repr__(self):
        """Return representation masking sensitive secrets."""
        safe_dict = self.model_dump()
        if safe_dict.get("shopify_access_token"):
            safe_dict["shopify_access_token"] = "********"
        if safe_dict.get("shopify_dev_token"):
            safe_dict["shopify_dev_token"] = "********"
        if safe_dict.get("shopify_validation_token"):
            safe_dict["shopify_validation_token"] = "********"
        if safe_dict.get("shopify_api_secret"):
            safe_dict["shopify_api_secret"] = "********"
        if safe_dict.get("shopify_client_secret"):
            safe_dict["shopify_client_secret"] = "********"
        if safe_dict.get("firebase_service_account_key"):
            safe_dict["firebase_service_account_key"] = "********"
        if safe_dict.get("google_api_key"):
            safe_dict["google_api_key"] = "********"
        if safe_dict.get("google_client_secret"):
            safe_dict["google_client_secret"] = "********"
        if safe_dict.get("gsc_service_account_key"):
            safe_dict["gsc_service_account_key"] = "********"
        if safe_dict.get("gemini_api_key"):
            safe_dict["gemini_api_key"] = "********"
        if safe_dict.get("smtp_password"):
            safe_dict["smtp_password"] = "********"
        if safe_dict.get("google_application_credentials"):
            safe_dict["google_application_credentials"] = "********"
        return f"Settings({safe_dict})"


# Global settings singleton
settings = Settings()


class ContextFilter(logging.Filter):
    """
    Logger filter that dynamically populates log records with
    request_id, session_id, and workflow_id context variables.
    """
    def filter(self, record):
        record.request_id = request_id_var.get("-")
        record.session_id = session_id_var.get("-")
        record.workflow_id = workflow_id_var.get("-")
        return True


def setup_logging(log_level: str = "INFO"):
    """
    Configures context-aware structured-looking log formatting globally.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    
    # Context-aware formatter incorporating request, session, and workflow tracing IDs
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [req=%(request_id)s session=%(session_id)s workflow=%(workflow_id)s] - %(message)s"
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Configure uvicorn to propagate its logs through our root logger
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = True
    logging.getLogger("uvicorn.error").handlers = []
    logging.getLogger("uvicorn.error").propagate = True
