import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "launch_platform.db"))

def get_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def parse_json_field(val: Any, default: Any = None) -> Any:
    if default is None:
        default = {}
    if not val:
        return default
    if isinstance(val, (dict, list)):
        return val
    try:
        parsed = json.loads(val)
        if isinstance(parsed, str):
            return json.loads(parsed)
        return parsed
    except Exception:
        return default

def init_db(clear: bool = False):
    """Initialize database schemas for workshops and registrations."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with get_connection() as conn:
        if clear:
            conn.execute("DROP TABLE IF EXISTS workshops")
            conn.execute("DROP TABLE IF EXISTS registrations")
            conn.execute("DROP TABLE IF EXISTS webhook_events")
            conn.execute("DROP TABLE IF EXISTS student_registrations")
        # Create workshops table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workshops (
                id TEXT PRIMARY KEY,
                shopify_product_id INTEGER,
                shopify_variant_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                date TEXT,
                time TEXT,
                duration TEXT,
                venue TEXT,
                age_group TEXT,
                price REAL,
                topics TEXT,
                poster_path TEXT,
                video_url TEXT,
                sales_team_email TEXT,
                generated_description TEXT,
                seo_metadata TEXT,
                marketing TEXT,
                image_prompts TEXT,
                image_paths TEXT,
                shopify_media TEXT,
                media TEXT,
                content TEXT,
                instructor TEXT,
                registration TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        # Ensure new columns exist (migration helpers)
        for new_col in ["shopify_variant_id", "media", "content", "instructor", "registration"]:
            try:
                conn.execute(f"ALTER TABLE workshops ADD COLUMN {new_col} TEXT")
            except sqlite3.OperationalError:
                # Column already exists
                pass

        # Create registrations/orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                order_id TEXT PRIMARY KEY,
                shopify_order_id INTEGER,
                shopify_order_number TEXT,
                workshop_id TEXT,
                customer_name TEXT,
                customer_email TEXT,
                customer_phone TEXT,
                amount REAL,
                payment_status TEXT,
                child_name TEXT,
                child_age INTEGER,
                parent_name TEXT,
                school TEXT,
                emergency_contact TEXT,
                created_at TEXT
            )
        """)
        
        # Webhook Events table for reliability & persistence before acknowledgement
        conn.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_id TEXT PRIMARY KEY,
                topic TEXT,
                order_id TEXT,
                raw_payload TEXT,
                status TEXT DEFAULT 'received',
                sync_status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT,
                processed_at TEXT
            )
        """)

        # Student registrations table for Google Sheets synchronization
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_registrations (
                registration_id TEXT PRIMARY KEY,
                shopify_order_id TEXT,
                workshop_name TEXT,
                parent_name TEXT,
                parent_phone TEXT,
                parent_email TEXT,
                area TEXT,
                child_name TEXT,
                child_age TEXT,
                payment_status TEXT,
                registration_date TEXT,
                sync_status TEXT DEFAULT 'Pending',
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                raw_properties TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Ensure school & emergency_contact columns exist in registrations (migration helper)
        try:
            conn.execute("ALTER TABLE registrations ADD COLUMN school TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE registrations ADD COLUMN emergency_contact TEXT")
        except sqlite3.OperationalError:
            pass
            
        conn.commit()

def create_workshop(workshop_data: Dict[str, Any]) -> str:
    """Create a new workshop draft entry."""
    workshop_id = workshop_data.get("id") or f"workshop_{int(datetime.utcnow().timestamp())}"
    now = datetime.utcnow().isoformat()
    
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO workshops (
                id, name, description, date, time, duration, venue, age_group, price, 
                topics, poster_path, video_url, sales_team_email, media, content, instructor, registration, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workshop_id,
                workshop_data["name"],
                workshop_data.get("description", ""),
                workshop_data.get("date", ""),
                workshop_data.get("time", ""),
                workshop_data.get("duration", ""),
                workshop_data.get("venue", ""),
                workshop_data.get("age_group", ""),
                workshop_data.get("price", 0.0),
                json.dumps(workshop_data.get("topics", [])),
                workshop_data.get("poster_path", ""),
                workshop_data.get("video_url", ""),
                workshop_data.get("sales_team_email", ""),
                json.dumps(workshop_data.get("media", {})),
                json.dumps(workshop_data.get("content", {})),
                json.dumps(workshop_data.get("instructor", {})),
                json.dumps(workshop_data.get("registration", {})),
                workshop_data.get("status", "draft"),
                now,
                now
            )
        )
        conn.commit()
    return workshop_id

def update_workshop_status(workshop_id: str, status: str):
    """Update status of a workshop in the database."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE workshops SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, workshop_id)
        )
        conn.commit()

def update_workshop_ai_content(workshop_id: str, updates: Dict[str, Any]):
    """Update AI-generated content for a workshop."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE workshops
            SET generated_description = ?,
                seo_metadata = ?,
                marketing = ?,
                image_prompts = ?,
                image_paths = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                updates.get("generated_description"),
                json.dumps(updates.get("seo_metadata", {})),
                json.dumps(updates.get("marketing", {})),
                json.dumps(updates.get("image_prompts", {})),
                json.dumps(updates.get("image_paths", [])),
                updates.get("status", "generated"),
                now,
                workshop_id
            )
        )
        conn.commit()

def publish_workshop(workshop_id: str, shopify_product_id: int, shopify_url: str,
                      shopify_media: List[Dict[str, Any]] = None, shopify_variant_id: int = None):
    """Mark a workshop as published and bind it to a Shopify product.

    shopify_variant_id is the ID of the product's first variant, required by the
    landing page to build a valid Shopify Cart Permalink checkout URL. Without it,
    the landing page has no way to know the product was actually published and
    will keep showing its "preview draft mode" fallback message.
    """
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE workshops
            SET shopify_product_id = ?,
                shopify_variant_id = ?,
                shopify_media = ?,
                status = 'published',
                updated_at = ?
            WHERE id = ?
            """,
            (
                shopify_product_id,
                shopify_variant_id,
                json.dumps(shopify_media or []),
                now,
                workshop_id
            )
        )
        conn.commit()

def update_workshop_shopify_ids(workshop_id: str, shopify_product_id: int, shopify_variant_id: Optional[int] = None, status: Optional[str] = None):
    """Update shopify_product_id, shopify_variant_id, and optional status of a workshop in the database."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        if status:
            conn.execute(
                "UPDATE workshops SET shopify_product_id = ?, shopify_variant_id = ?, status = ?, updated_at = ? WHERE id = ?",
                (shopify_product_id, shopify_variant_id, status, now, workshop_id)
            )
        else:
            conn.execute(
                "UPDATE workshops SET shopify_product_id = ?, shopify_variant_id = ?, updated_at = ? WHERE id = ?",
                (shopify_product_id, shopify_variant_id, now, workshop_id)
            )
        conn.commit()


def _decode_workshop_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    data["topics"] = parse_json_field(data.get("topics"), [])
    data["seo_metadata"] = parse_json_field(data.get("seo_metadata"), {})
    data["marketing"] = parse_json_field(data.get("marketing"), {})
    data["image_prompts"] = parse_json_field(data.get("image_prompts"), {})
    data["image_paths"] = parse_json_field(data.get("image_paths"), [])
    data["shopify_media"] = parse_json_field(data.get("shopify_media"), [])
    data["media"] = parse_json_field(data.get("media"), {})
    data["content"] = parse_json_field(data.get("content"), {})
    data["instructor"] = parse_json_field(data.get("instructor"), {})
    data["registration"] = parse_json_field(data.get("registration"), {})
    return data


def get_workshop(workshop_id: str) -> Optional[Dict[str, Any]]:
    """Fetch details of a single workshop."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM workshops WHERE id = ?", (workshop_id,)).fetchone()
        if not row:
            return None
        return _decode_workshop_dict(dict(row))

def get_workshop_by_shopify_id(shopify_product_id: int) -> Optional[Dict[str, Any]]:
    """Fetch details of a workshop by Shopify Product ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM workshops WHERE shopify_product_id = ?", (shopify_product_id,)).fetchone()
        if not row:
            return None
        return _decode_workshop_dict(dict(row))

def get_all_workshops() -> List[Dict[str, Any]]:
    """Fetch all workshops in the system."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM workshops ORDER BY created_at DESC").fetchall()
        return [_decode_workshop_dict(dict(r)) for r in rows]

def add_registration(reg_data: Dict[str, Any]):
    """Insert a new order/registration."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO registrations (
                order_id, shopify_order_id, shopify_order_number, workshop_id, customer_name,
                customer_email, customer_phone, amount, payment_status, child_name, child_age, parent_name, 
                school, emergency_contact, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reg_data["order_id"],
                reg_data.get("shopify_order_id"),
                reg_data.get("shopify_order_number"),
                reg_data.get("workshop_id"),
                reg_data["customer_name"],
                reg_data["customer_email"],
                reg_data.get("customer_phone"),
                reg_data.get("amount", 0.0),
                reg_data.get("payment_status", "pending"),
                reg_data.get("child_name"),
                reg_data.get("child_age"),
                reg_data.get("parent_name"),
                reg_data.get("school"),
                reg_data.get("emergency_contact"),
                reg_data.get("created_at") or datetime.utcnow().isoformat()
            )
        )
        conn.commit()

def get_all_registrations() -> List[Dict[str, Any]]:
    """Fetch all registrations."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM registrations ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

def get_registration(order_id: str) -> Optional[Dict[str, Any]]:
    """Fetch details of a single registration by order_id (registration_id)."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM registrations WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return None
        return dict(row)

def get_dashboard_metrics() -> Dict[str, Any]:
    """Calculate dashboard summary statistics."""
    with get_connection() as conn:
        total_workshops = conn.execute("SELECT COUNT(*) FROM workshops").fetchone()[0]
        published_workshops = conn.execute("SELECT COUNT(*) FROM workshops WHERE status = 'published'").fetchone()[0]
        upcoming_workshops = conn.execute("SELECT COUNT(*) FROM workshops WHERE date >= ?", (datetime.utcnow().strftime("%Y-%m-%d"),)).fetchone()[0]
        
        total_registrations = conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
        revenue = conn.execute("SELECT SUM(amount) FROM registrations WHERE payment_status = 'paid' OR payment_status = 'authorized'").fetchone()[0] or 0.0
        
        recent_orders = conn.execute("SELECT * FROM registrations ORDER BY created_at DESC LIMIT 5").fetchall()
        
        return {
            "total_workshops": total_workshops,
            "published_workshops": published_workshops,
            "upcoming_workshops": upcoming_workshops,
            "total_registrations": total_registrations,
            "total_revenue": revenue,
            "recent_orders": [dict(r) for r in recent_orders]
        }


# =====================================================================
# Student Registration and Webhook Event Persistence
# =====================================================================

def save_webhook_event(
    event_id: str,
    topic: str,
    order_id: Optional[str],
    raw_payload: str,
    status: str = "received",
    sync_status: str = "pending"
) -> str:
    """Persist raw webhook event before processing."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO webhook_events (
                event_id, topic, order_id, raw_payload, status, sync_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, topic, str(order_id) if order_id else None, raw_payload, status, sync_status, now)
        )
        conn.commit()
    return event_id


def update_webhook_event(
    event_id: str,
    status: str,
    sync_status: str,
    error_message: Optional[str] = None
):
    """Update status of a webhook event."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE webhook_events
            SET status = ?, sync_status = ?, error_message = ?, processed_at = ?
            WHERE event_id = ?
            """,
            (status, sync_status, error_message, now, event_id)
        )
        conn.commit()


def get_webhook_event(event_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve webhook event by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM webhook_events WHERE event_id = ?", (event_id,)).fetchone()
        if not row:
            return None
        return dict(row)


def scrub_webhook_event_payload(event_id: str):
    """
    Scrub sensitive customer and child PII from a processed webhook payload
    to avoid indefinite retention of personal data (GDPR / DPDP compliance).
    """
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        row = conn.execute("SELECT raw_payload FROM webhook_events WHERE event_id = ?", (event_id,)).fetchone()
        if not row or not row["raw_payload"]:
            return
        try:
            data = json.loads(row["raw_payload"])
            if "customer" in data and isinstance(data["customer"], dict):
                cust = data["customer"]
                data["customer"] = {
                    "id": cust.get("id"),
                    "email_scrubbed": bool(cust.get("email")),
                    "phone_scrubbed": bool(cust.get("phone"))
                }
            if "billing_address" in data and isinstance(data["billing_address"], dict):
                data["billing_address"] = {"country": data["billing_address"].get("country", "")}
            if "shipping_address" in data and isinstance(data["shipping_address"], dict):
                data["shipping_address"] = {"country": data["shipping_address"].get("country", "")}
            if "email" in data:
                data["email"] = "[SCRUBBED]"
            if "phone" in data:
                data["phone"] = "[SCRUBBED]"
            if "note_attributes" in data and isinstance(data["note_attributes"], list):
                data["note_attributes"] = [
                    {"name": a.get("name"), "value": "[SCRUBBED]"} for a in data.get("note_attributes", [])
                    if isinstance(a, dict)
                ]
            for item in data.get("line_items", []):
                if isinstance(item, dict) and "properties" in item and isinstance(item["properties"], list):
                    item["properties"] = [
                        {"name": p.get("name"), "value": "[SCRUBBED]"} for p in item.get("properties", [])
                        if isinstance(p, dict)
                    ]
            data["_sanitized"] = True
            data["_sanitized_at"] = now
            scrubbed_payload = json.dumps(data)
            conn.execute(
                "UPDATE webhook_events SET raw_payload = ? WHERE event_id = ?",
                (scrubbed_payload, event_id)
            )
            conn.commit()
        except Exception:
            pass


def prune_old_webhook_events(retention_days: int = 30) -> int:
    """Delete processed/ignored webhook events older than retention_days."""
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM webhook_events WHERE status IN ('processed', 'ignored') AND created_at < ?",
            (cutoff,)
        )
        conn.commit()
        return cursor.rowcount


def save_student_registration(reg_dict: Dict[str, Any]) -> str:
    """Save or update student registration record."""
    now = datetime.utcnow().isoformat()
    raw_props = json.dumps(reg_dict.get("raw_properties", {})) if isinstance(reg_dict.get("raw_properties"), (dict, list)) else str(reg_dict.get("raw_properties", ""))
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO student_registrations (
                registration_id, shopify_order_id, workshop_name,
                parent_name, parent_phone, parent_email, area,
                child_name, child_age, payment_status, registration_date,
                sync_status, retry_count, error_message, raw_properties,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reg_dict["registration_id"],
                str(reg_dict.get("shopify_order_id", "")),
                reg_dict.get("workshop_name", ""),
                reg_dict.get("parent_name", ""),
                reg_dict.get("parent_phone", ""),
                reg_dict.get("parent_email", ""),
                reg_dict.get("area", ""),
                reg_dict.get("child_name", ""),
                str(reg_dict.get("child_age", "")),
                reg_dict.get("payment_status", "paid"),
                reg_dict.get("registration_date", now),
                reg_dict.get("sync_status", "Pending"),
                reg_dict.get("retry_count", 0),
                reg_dict.get("error_message"),
                raw_props,
                reg_dict.get("created_at") or now,
                now
            )
        )
        conn.commit()
    return reg_dict["registration_id"]


def get_student_registration(registration_id: str) -> Optional[Dict[str, Any]]:
    """Fetch details of a single student registration."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM student_registrations WHERE registration_id = ?", (registration_id,)).fetchone()
        if not row:
            return None
        return dict(row)


def get_all_student_registrations() -> List[Dict[str, Any]]:
    """Fetch all student registrations."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM student_registrations ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def update_student_registration_sync(
    registration_id: str,
    sync_status: str,
    error_message: Optional[str] = None,
    increment_retry: bool = False
):
    """Update synchronization status of a student registration."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        if increment_retry:
            conn.execute(
                """
                UPDATE student_registrations
                SET sync_status = ?, error_message = ?, retry_count = retry_count + 1, updated_at = ?
                WHERE registration_id = ?
                """,
                (sync_status, error_message, now, registration_id)
            )
        else:
            conn.execute(
                """
                UPDATE student_registrations
                SET sync_status = ?, error_message = ?, updated_at = ?
                WHERE registration_id = ?
                """,
                (sync_status, error_message, now, registration_id)
            )
        conn.commit()


def get_failed_student_registrations() -> List[Dict[str, Any]]:
    """Fetch all student registrations that failed to sync."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM student_registrations WHERE sync_status IN ('Failed', 'Pending') ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]