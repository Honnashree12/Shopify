"""
Google Sheets Integration Service for Workshop Student Registrations.

Provides both real Google Sheets API v4 client and high-fidelity Mock client
for offline / permission-blocked development and testing.
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from config import settings

logger = logging.getLogger(__name__)

# Expected 12 columns in exact order
SHEET_COLUMNS = [
    "Registration ID",
    "Shopify Order ID",
    "Workshop Name",
    "Parent Name",
    "Parent Phone",
    "Parent Email",
    "Area",
    "Child Name",
    "Child Age",
    "Payment Status",
    "Registration Date",
    "Sync Status"
]


class GoogleSheetsError(Exception):
    """Base exception for Google Sheets operations."""
    pass


class MockGoogleSheetsClient:
    """
    In-memory simulation of Google Sheets API v4.
    Used for local development and testing when Google Cloud permissions are pending.
    """

    def __init__(self, spreadsheet_id: Optional[str] = None, tab_name: str = "Registrations"):
        self.spreadsheet_id = spreadsheet_id or "mock_spreadsheet_id"
        self.tab_name = tab_name
        self.headers = list(SHEET_COLUMNS)
        self.rows: List[List[Any]] = []
        self._should_fail: bool = False
        self._failure_error: str = "Simulated Google Sheets API 503 Unavailable"
        self._failure_count: int = 0
        self._fail_operations = {"append_row", "update_sync_status"}
        self.call_history: List[str] = []

    def simulate_failure(
        self,
        should_fail: bool = True,
        error_message: str = "Simulated Google Sheets API Error",
        fail_operations: Optional[List[str]] = None
    ):
        """Enable or disable simulated API failures for testing retry handling."""
        self._should_fail = should_fail
        self._failure_error = error_message
        if fail_operations:
            self._fail_operations = set(fail_operations)
        else:
            self._fail_operations = {"append_row", "update_sync_status"}

    def _check_failure(self, operation: str):
        self.call_history.append(operation)
        if self._should_fail and operation in self._fail_operations:
            self._failure_count += 1
            logger.warning("[MOCK SHEETS] Simulated failure triggered during %s: %s", operation, self._failure_error)
            raise GoogleSheetsError(self._failure_error)

    def ensure_headers(self) -> bool:
        """Ensure the sheet headers match the required 12 columns."""
        self._check_failure("ensure_headers")
        return True

    def get_all_rows(self) -> List[List[Any]]:
        """Return all rows excluding headers."""
        self._check_failure("get_all_rows")
        return [list(r) for r in self.rows]

    def find_row_index_by_reg_id(self, registration_id: str) -> Optional[int]:
        """Find 0-indexed row position of a registration ID, or None if not found."""
        self._check_failure("find_row_by_reg_id")
        for idx, row in enumerate(self.rows):
            if row and str(row[0]).strip() == str(registration_id).strip():
                return idx
        return None

    def append_row(self, row_values: List[Any]) -> bool:
        """
        Append a row of 12 values to the sheet.
        If row with registration_id already exists, updates it idempotently.
        """
        self._check_failure("append_row")
        if len(row_values) != len(SHEET_COLUMNS):
            raise GoogleSheetsError(
                f"Row column mismatch: expected {len(SHEET_COLUMNS)} columns, got {len(row_values)}"
            )

        reg_id = str(row_values[0]).strip()
        existing_idx = None
        for idx, r in enumerate(self.rows):
            if r and str(r[0]).strip() == reg_id:
                existing_idx = idx
                break

        if existing_idx is not None:
            # Idempotent update
            self.rows[existing_idx] = list(row_values)
            logger.info("[MOCK SHEETS] Updated existing row for registration ID %s", reg_id)
        else:
            self.rows.append(list(row_values))
            logger.info("[MOCK SHEETS] Appended new row for registration ID %s (Total rows: %d)", reg_id, len(self.rows))
        return True

    def update_sync_status(self, registration_id: str, new_status: str) -> bool:
        """Update the Sync Status (column 12) of an existing row."""
        self._check_failure("update_sync_status")
        for idx, row in enumerate(self.rows):
            if row and str(row[0]).strip() == str(registration_id).strip():
                row[11] = new_status
                return True
        return False

    def clear(self):
        """Clear all stored rows in mock."""
        self.rows.clear()
        self.call_history.clear()
        self._should_fail = False
        self._failure_count = 0


class RealGoogleSheetsClient:
    """
    Production Google Sheets client using Google API Client library and Service Account credentials.
    """

    def __init__(
        self,
        spreadsheet_id: str,
        tab_name: str = "Registrations",
        credentials_path: Optional[str] = None
    ):
        self.spreadsheet_id = spreadsheet_id
        self.tab_name = tab_name
        self.credentials_path = credentials_path or settings.google_application_credentials
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service

        if not self.spreadsheet_id:
            raise GoogleSheetsError("GOOGLE_SHEETS_SPREADSHEET_ID is not configured.")

        if not self.credentials_path or not os.path.exists(self.credentials_path):
            raise GoogleSheetsError(
                f"Google application credentials file not found at: {self.credentials_path}. "
                "Ensure GOOGLE_APPLICATION_CREDENTIALS is set to a valid service account JSON key."
            )

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            self._service = build("sheets", "v4", credentials=creds)
            return self._service
        except Exception as e:
            logger.exception("Failed to initialize Google Sheets API client")
            raise GoogleSheetsError(f"Could not initialize Google Sheets client: {e}")

    def _validate_tab_name(self, service) -> None:
        """Verify the configured tab exists in the spreadsheet."""
        try:
            metadata = service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = metadata.get("sheets", [])
            tab_names = [s.get("properties", {}).get("title") for s in sheets]
            if self.tab_name not in tab_names:
                raise GoogleSheetsError(
                    f"Configured tab name '{self.tab_name}' not found in spreadsheet {self.spreadsheet_id}. "
                    f"Available tabs in this spreadsheet: {tab_names}. Please create tab '{self.tab_name}' "
                    f"or update GOOGLE_SHEETS_TAB_NAME in .env."
                )
        except GoogleSheetsError:
            raise
        except Exception as e:
            logger.warning("Could not verify spreadsheet metadata for tab '%s': %s", self.tab_name, e)

    def ensure_headers(self) -> bool:
        """Check if header row exists, if not initialize it."""
        service = self._get_service()
        self._validate_tab_name(service)
        range_name = f"{self.tab_name}!A1:L1"
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=range_name
            ).execute()
            values = result.get("values", [])
            if not values:
                # Append headers
                body = {"values": [SHEET_COLUMNS]}
                service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body
                ).execute()
                logger.info("Initialized Google Sheet headers.")
            return True
        except Exception as e:
            logger.exception("Failed to ensure headers in Google Sheets")
            raise GoogleSheetsError(f"Header validation failed: {e}")

    def get_all_rows(self) -> List[List[Any]]:
        """Fetch all rows from sheet."""
        service = self._get_service()
        range_name = f"{self.tab_name}!A2:L"
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=range_name
            ).execute()
            return result.get("values", [])
        except Exception as e:
            raise GoogleSheetsError(f"Failed to fetch rows: {e}")

    def find_row_index_by_reg_id(self, registration_id: str) -> Optional[int]:
        """Find row position of a registration ID in column A."""
        rows = self.get_all_rows()
        for idx, row in enumerate(rows):
            if row and str(row[0]).strip() == str(registration_id).strip():
                return idx + 2  # 1-indexed and accounting for header row at row 1
        return None

    def append_row(self, row_values: List[Any]) -> bool:
        """Append a row to the spreadsheet, updating if already present."""
        if len(row_values) != len(SHEET_COLUMNS):
            raise GoogleSheetsError(f"Row column mismatch: expected {len(SHEET_COLUMNS)}, got {len(row_values)}")

        reg_id = str(row_values[0]).strip()
        existing_row = self.find_row_index_by_reg_id(reg_id)
        service = self._get_service()

        try:
            if existing_row is not None:
                # Update existing row
                range_name = f"{self.tab_name}!A{existing_row}:L{existing_row}"
                body = {"values": [row_values]}
                service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    body=body
                ).execute()
                logger.info("Updated existing registration ID %s at row %d", reg_id, existing_row)
            else:
                range_name = f"{self.tab_name}!A:L"
                body = {"values": [row_values]}
                service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=body
                ).execute()
                logger.info("Appended new registration ID %s", reg_id)
            return True
        except Exception as e:
            raise GoogleSheetsError(f"Failed to append/update row: {e}")

    def update_sync_status(self, registration_id: str, new_status: str) -> bool:
        """Update Sync Status column for a registration ID."""
        row_idx = self.find_row_index_by_reg_id(registration_id)
        if not row_idx:
            return False
        service = self._get_service()
        range_name = f"{self.tab_name}!L{row_idx}"
        body = {"values": [[new_status]]}
        try:
            service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            return True
        except Exception as e:
            raise GoogleSheetsError(f"Failed to update sync status: {e}")


# Singleton mock instance for test sharing
_mock_instance: Optional[MockGoogleSheetsClient] = None


def get_mock_sheets_client() -> MockGoogleSheetsClient:
    """Return shared mock client instance."""
    global _mock_instance
    if _mock_instance is None:
        _mock_instance = MockGoogleSheetsClient(
            spreadsheet_id=settings.google_sheets_spreadsheet_id,
            tab_name=settings.google_sheets_tab_name
        )
    return _mock_instance


def reset_mock_sheets_client() -> MockGoogleSheetsClient:
    """Reset shared mock client for test isolation."""
    global _mock_instance
    _mock_instance = MockGoogleSheetsClient(
        spreadsheet_id=settings.google_sheets_spreadsheet_id,
        tab_name=settings.google_sheets_tab_name
    )
    return _mock_instance


def get_sheets_client():
    """
    Factory to retrieve appropriate Google Sheets client.
    Enforces that production environments NEVER silently use mock mode.
    """
    is_testing = "pytest" in os.sys.modules or os.getenv("TESTING") == "True"
    is_production = settings.app_env.lower() == "production"

    if is_production:
        if settings.mock_google_sheets:
            raise GoogleSheetsError(
                "CRITICAL ERROR: MOCK_GOOGLE_SHEETS is enabled, but mock mode is strictly forbidden in production."
            )
        if not settings.google_sheets_spreadsheet_id:
            raise GoogleSheetsError("CRITICAL ERROR: GOOGLE_SHEETS_SPREADSHEET_ID is missing in production.")
        if not settings.google_application_credentials or not os.path.exists(settings.google_application_credentials):
            raise GoogleSheetsError(
                f"CRITICAL ERROR: Google application credentials file missing in production: {settings.google_application_credentials}"
            )
        return RealGoogleSheetsClient(
            spreadsheet_id=settings.google_sheets_spreadsheet_id,
            tab_name=settings.google_sheets_tab_name,
            credentials_path=settings.google_application_credentials
        )

    # In development / testing:
    if settings.mock_google_sheets or is_testing:
        return get_mock_sheets_client()

    creds_exist = bool(settings.google_application_credentials and os.path.exists(settings.google_application_credentials))
    if creds_exist and settings.google_sheets_spreadsheet_id:
        return RealGoogleSheetsClient(
            spreadsheet_id=settings.google_sheets_spreadsheet_id,
            tab_name=settings.google_sheets_tab_name,
            credentials_path=settings.google_application_credentials
        )

    # In local development if credentials are not present and mock was not explicitly enabled:
    raise GoogleSheetsError(
        "Google Sheets credentials not configured. Explicitly set MOCK_GOOGLE_SHEETS=True in .env for local testing."
    )


def sync_registration_to_sheets_with_retry(
    row_values: List[Any],
    max_retries: int = 3,
    base_delay_seconds: float = 0.5,
    client = None
) -> Tuple[bool, Optional[str]]:
    """
    Append or update registration row with exponential backoff retry.
    Returns (success: bool, error_message: Optional[str]).
    """
    if client is None:
        client = get_sheets_client()

    attempt = 0
    last_error = None

    while attempt < max_retries:
        attempt += 1
        try:
            client.append_row(row_values)
            return True, None
        except Exception as e:
            last_error = str(e)
            logger.warning(
                "Google Sheets sync attempt %d/%d failed for registration ID %s: %s",
                attempt, max_retries, row_values[0] if row_values else "unknown", last_error
            )
            if attempt < max_retries:
                # Exponential backoff
                sleep_time = base_delay_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_time)

    return False, f"Exhausted {max_retries} attempts: {last_error}"
