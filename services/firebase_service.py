import os
import sys
import json
import logging
from datetime import datetime
from typing import Optional, Any, Dict

from config import settings

logger = logging.getLogger(__name__)

# Local directory where files will be stored in mock mode
MOCK_FIRESTORE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", "mock_firestore"))
os.makedirs(MOCK_FIRESTORE_DIR, exist_ok=True)

_firebase_initialized = False
db = None

def initialize_firebase():
    global _firebase_initialized, db
    if _firebase_initialized:
        return db
        
    is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "True"
    allow_real_firebase = os.getenv("ALLOW_REAL_FIREBASE") == "True"
    if is_testing and not allow_real_firebase:
        logger.warning("Bypassing real Firebase initialization under testing. Falling back to local Mock Firestore.")
        return None
        
    service_account_path = settings.firebase_service_account_key
    if not service_account_path or not os.path.exists(service_account_path):
        logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY is not set or file not found. Falling back to local Mock Firestore.")
        return None
        
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            bucket_name = settings.firebase_storage_bucket
            if bucket_name:
                firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
            else:
                firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        _firebase_initialized = True
        logger.info("Firebase Admin Firestore client initialized successfully.")
        return db
    except Exception as e:
        logger.exception("Failed to initialize real Firebase Admin: %s. Falling back to Mock Firestore.", e)
        return None


def _save_mock_doc(collection: str, doc_id: str, data: dict):
    col_dir = os.path.join(MOCK_FIRESTORE_DIR, collection)
    os.makedirs(col_dir, exist_ok=True)
    doc_path = os.path.join(col_dir, f"{doc_id}.json")
    serializable_data = json.loads(json.dumps(data, default=str))
    with open(doc_path, "w", encoding="utf-8") as f:
        json.dump(serializable_data, f, indent=2)


def _get_mock_doc(collection: str, doc_id: str) -> Optional[dict]:
    doc_path = os.path.join(MOCK_FIRESTORE_DIR, collection, f"{doc_id}.json")
    if not os.path.exists(doc_path):
        return None
    try:
        with open(doc_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_design_system(store_id: str, design_system: dict):
    client = initialize_firebase()
    design_system["updated_at"] = datetime.utcnow()
    
    if client:
        try:
            doc_ref = client.collection("stores").document(store_id).collection("design_system").document("current")
            doc_ref.set(design_system)
            logger.info("Saved design system to Firestore for store %s", store_id)
        except Exception as e:
            logger.error("Failed to write design system to Firestore: %s. Writing to local mock.", e)
            _save_mock_doc(f"stores_{store_id}_design_system", "current", design_system)
    else:
        _save_mock_doc(f"stores_{store_id}_design_system", "current", design_system)


def get_design_system(store_id: str) -> Optional[dict]:
    client = initialize_firebase()
    if client:
        try:
            doc_ref = client.collection("stores").document(store_id).collection("design_system").document("current")
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            logger.error("Failed to read design system from Firestore: %s. Checking local mock.", e)
            
    return _get_mock_doc(f"stores_{store_id}_design_system", "current")


def save_product(product_id: str, data: dict):
    client = initialize_firebase()
    data["updated_at"] = datetime.utcnow()
    if "created_at" not in data:
        data["created_at"] = datetime.utcnow()
        
    if client:
        try:
            doc_ref = client.collection("products").document(product_id)
            doc_ref.set(data)
            logger.info("Saved product %s to Firestore", product_id)
        except Exception as e:
            logger.error("Failed to write product %s to Firestore: %s. Writing to local mock.", product_id, e)
            _save_mock_doc("products", product_id, data)
    else:
        _save_mock_doc("products", product_id, data)


def get_product(product_id: str) -> Optional[dict]:
    client = initialize_firebase()
    if client:
        try:
            doc_ref = client.collection("products").document(product_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            logger.error("Failed to read product %s from Firestore: %s. Checking local mock.", product_id, e)
            
    return _get_mock_doc("products", product_id)


def update_workflow_status(product_id: str, stage: str, status: str):
    client = initialize_firebase()
    if client:
        try:
            doc_ref = client.collection("products").document(product_id)
            doc_ref.update({
                f"workflow.{stage}": status,
                "updated_at": datetime.utcnow()
            })
            logger.info("Updated workflow stage '%s' to '%s' for product %s", stage, status, product_id)
            return
        except Exception as e:
            logger.error("Failed to update Firestore workflow for product %s: %s. Updating local mock.", product_id, e)
            
    prod = get_product(product_id)
    if prod:
        if "workflow" not in prod:
            prod["workflow"] = {}
        prod["workflow"][stage] = status
        save_product(product_id, prod)


def save_audit_log(log_id: str, data: dict):
    client = initialize_firebase()
    if "timestamp" not in data:
        data["timestamp"] = datetime.utcnow().isoformat() + "Z"
    
    if client:
        try:
            doc_ref = client.collection("audit_logs").document(log_id)
            doc_ref.set(data)
            logger.info("Saved audit log %s to Firestore", log_id)
        except Exception as e:
            logger.error("Failed to write audit log %s to Firestore: %s. Writing to local mock.", log_id, e)
            _save_mock_doc("audit_logs", log_id, data)
    else:
        _save_mock_doc("audit_logs", log_id, data)


def get_audit_logs() -> list:
    client = initialize_firebase()
    results = []
    if client:
        try:
            docs = client.collection("audit_logs").stream()
            for doc in docs:
                results.append(doc.to_dict())
            # Sort descending by timestamp
            results.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
            return results
        except Exception as e:
            logger.error("Failed to read audit logs from Firestore: %s. Checking local mock.", e)
            
    # Local mock directory listing
    col_dir = os.path.join(MOCK_FIRESTORE_DIR, "audit_logs")
    if os.path.exists(col_dir):
        for fname in os.listdir(col_dir):
            if fname.endswith(".json"):
                p = os.path.join(col_dir, fname)
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        results.append(json.load(f))
                except Exception:
                    pass
    try:
        results.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    except Exception:
        pass
    return results


def save_shopify_token(store_url: str, token: str):
    """
    Saves the Shopify access token for a store to Firestore (or local mock).
    """
    client = initialize_firebase()
    # Normalize store_url to extract store ID (e.g. kinq5t-q5)
    store_id = store_url.strip().replace("https://", "").replace("http://", "").split(".")[0]
    data = {
        "access_token": token,
        "store_url": store_url,
        "updated_at": datetime.utcnow()
    }
    if client:
        try:
            doc_ref = client.collection("stores").document(store_id).collection("shopify_config").document("oauth")
            doc_ref.set(data)
            logger.info("Saved Shopify OAuth token to Firestore for store %s", store_id)
        except Exception as e:
            logger.error("Failed to write Shopify OAuth token to Firestore: %s. Writing to local mock.", e)
            _save_mock_doc(f"stores_{store_id}_shopify_config", "oauth", data)
    else:
        _save_mock_doc(f"stores_{store_id}_shopify_config", "oauth", data)


def get_shopify_token(store_url: str) -> Optional[str]:
    """
    Retrieves the Shopify access token for a store from Firestore (or local mock).
    """
    client = initialize_firebase()
    store_id = store_url.strip().replace("https://", "").replace("http://", "").split(".")[0]
    if client:
        try:
            doc_ref = client.collection("stores").document(store_id).collection("shopify_config").document("oauth")
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict().get("access_token")
        except Exception as e:
            logger.error("Failed to read Shopify OAuth token from Firestore: %s. Checking local mock.", e)
            
    doc = _get_mock_doc(f"stores_{store_id}_shopify_config", "oauth")
    if doc:
        return doc.get("access_token")
    return None


