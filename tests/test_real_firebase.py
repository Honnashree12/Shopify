import os
import pytest
import uuid

os.environ["ALLOW_REAL_FIREBASE"] = "True"

# Check if real Firebase credentials are set
has_firebase_credentials = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY") is not None and os.path.exists(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", ""))


@pytest.mark.skipif(not has_firebase_credentials, reason="Real Firebase credentials not configured in environment.")
def test_real_firebase_firestore_crud():
    from services.firebase_service import initialize_firebase, save_product, get_product
    
    db = initialize_firebase()
    assert db is not None, "Real Firebase client initialization returned None"
    
    test_id = f"prod_integration_test_{uuid.uuid4().hex[:6]}"
    test_payload = {
        "title": "Real Integration Product Test",
        "price": 129.99,
        "sku": "REAL-INTEG-TEST-01",
        "workflow": {
            "shopify": "pending",
            "verification": "pending"
        }
    }
    
    try:
        # 1. Firestore Write
        save_product(test_id, test_payload)
        
        # 2. Firestore Read
        retrieved = get_product(test_id)
        assert retrieved is not None
        assert retrieved["title"] == "Real Integration Product Test"
        assert float(retrieved["price"]) == 129.99
        
        # 3. Firestore Update
        from services.firebase_service import update_workflow_status
        update_workflow_status(test_id, "shopify", "completed")
        
        retrieved_updated = get_product(test_id)
        assert retrieved_updated["workflow"]["shopify"] == "completed"
        
    finally:
        # 4. Firestore Delete
        db.collection("products").document(test_id).delete()
        
        # Confirm deletion
        assert db.collection("products").document(test_id).get().exists is False
