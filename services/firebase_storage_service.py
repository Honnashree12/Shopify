import os
import shutil
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Fallback local mock storage directory
MOCK_STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", "mock_storage"))
os.makedirs(MOCK_STORAGE_DIR, exist_ok=True)


def upload_file(product_id: str, folder_name: str, file_path: str) -> dict:
    """
    Uploads a file to Firebase Storage under products/{product_id}/{folder_name}/{filename}.
    Falls back to copying the file into the local mock storage folder if Firebase is unconfigured.
    Returns metadata including filename, storage_path, content_type, size, and uploaded_at.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File to upload not found: {file_path}")
        
    filename = os.path.basename(file_path)
    size = os.path.getsize(file_path)
    
    # Content-Type mapper
    _, ext = os.path.splitext(filename.lower())
    if ext in (".jpg", ".jpeg"):
        content_type = "image/jpeg"
    elif ext == ".png":
        content_type = "image/png"
    elif ext == ".webp":
        content_type = "image/webp"
    elif ext == ".gif":
        content_type = "image/gif"
    elif ext == ".mp4":
        content_type = "video/mp4"
    elif ext == ".avi":
        content_type = "video/x-msvideo"
    elif ext == ".pdf":
        content_type = "application/pdf"
    elif ext == ".docx":
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext == ".xlsx":
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content_type = "application/octet-stream"

    storage_path = f"products/{product_id}/{folder_name}/{filename}"
    
    # Try uploading to real Firebase Storage first
    from services.firebase_service import initialize_firebase
    db = initialize_firebase()
    if db:
        try:
            import firebase_admin
            from firebase_admin import storage
            
            bucket = storage.bucket()
            blob = bucket.blob(storage_path)
            blob.upload_from_filename(file_path, content_type=content_type)
            
            # Make public to retrieve the public url
            try:
                blob.make_public()
                public_url = blob.public_url
            except Exception:
                public_url = blob.generate_signed_url(expiration=3600)
                
            logger.info("Successfully uploaded %s to Firebase Storage: %s", filename, public_url)
            
            return {
                "filename": filename,
                "storage_path": storage_path,
                "public_url": public_url,
                "content_type": content_type,
                "size": size,
                "uploaded_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error("Failed to upload to real Firebase Storage: %s. Falling back to local mock.", e)
            
    # Mock Storage Fallback: copy file to local directory
    mock_dest_dir = os.path.join(MOCK_STORAGE_DIR, "products", product_id, folder_name)
    os.makedirs(mock_dest_dir, exist_ok=True)
    mock_dest_path = os.path.join(mock_dest_dir, filename)
    shutil.copy2(file_path, mock_dest_path)
    
    # Generate relative URL served by FastAPI for frontend visibility
    public_url = f"/outputs/mock_storage/products/{product_id}/{folder_name}/{filename}"
    logger.info("Saved %s to Mock Storage: %s", filename, mock_dest_path)
    
    return {
        "filename": filename,
        "storage_path": storage_path,
        "public_url": public_url,
        "content_type": content_type,
        "size": size,
        "uploaded_at": datetime.utcnow().isoformat()
    }
