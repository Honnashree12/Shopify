import os
import pytest
import uuid

os.environ["ALLOW_REAL_FIREBASE"] = "True"

# Check if real Firebase credentials and storage bucket are set
has_storage_credentials = (
    os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY") is not None 
    and os.path.exists(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", ""))
    and os.getenv("FIREBASE_STORAGE_BUCKET") is not None
)


@pytest.mark.skipif(not has_storage_credentials, reason="Real Firebase Storage credentials/bucket not configured in environment.")
def test_real_firebase_storage_upload_delete(tmp_path):
    from services.firebase_service import initialize_firebase
    from services.firebase_storage_service import upload_file
    
    db = initialize_firebase()
    assert db is not None, "Real Firebase client initialization returned None"
    
    try:
        from firebase_admin import storage
        bucket = storage.bucket()
        if not bucket.exists():
            pytest.skip("Real Firebase Storage bucket is not enabled or does not exist on this project.")
    except Exception as e:
        pytest.skip(f"Failed to contact Firebase Storage bucket: {e}")
    
    # Create a temporary file
    test_file = tmp_path / "test_image.jpg"
    test_file.write_text("dummy-image-data-bytes")
    
    product_id = f"test_prod_{uuid.uuid4().hex[:6]}"
    
    try:
        # 1. Upload temporary file
        meta = upload_file(product_id, "images", str(test_file))
        assert meta is not None
        assert meta["filename"] == "test_image.jpg"
        assert meta["content_type"] == "image/jpeg"
        assert "public_url" in meta
        assert "storage_path" in meta
        
        # 2. Verify it exists using bucket APIs
        from firebase_admin import storage
        bucket = storage.bucket()
        blob = bucket.blob(meta["storage_path"])
        assert blob.exists() is True
        
    finally:
        # 3. Delete temporary file from Cloud Storage
        from firebase_admin import storage
        bucket = storage.bucket()
        blob = bucket.blob(f"products/{product_id}/images/test_image.jpg")
        if blob.exists():
            blob.delete()
            
        # Confirm deletion
        assert blob.exists() is False
