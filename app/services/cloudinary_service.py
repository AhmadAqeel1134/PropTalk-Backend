import cloudinary
import cloudinary.uploader
from app.config import settings
from typing import Optional
import uuid

_cloudinary_configured = False

def _ensure_cloudinary_configured():
    """Ensure Cloudinary is configured"""
    global _cloudinary_configured
    if not _cloudinary_configured:
        if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
            raise ValueError("Cloudinary credentials not configured. Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in .env")
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET
        )
        _cloudinary_configured = True


def upload_file_to_cloudinary(file_content: bytes, file_name: str, folder: str = "documents") -> dict:
    """
    Upload file to Cloudinary
    Returns: {"cloudinary_public_id": "folder/unique_id", "cloudinary_url": "https://..."}
    """
    _ensure_cloudinary_configured()
    try:
        file_extension = file_name.split('.')[-1] if '.' in file_name else ''
        unique_file_name = f"{uuid.uuid4()}.{file_extension}"
        public_id = f"{folder}/{unique_file_name}"
        
        result = cloudinary.uploader.upload(
            file_content,
            public_id=public_id,
            resource_type="auto",
            folder=folder
        )
        
        return {
            "cloudinary_public_id": result["public_id"],
            "cloudinary_url": result["secure_url"]
        }
    except Exception as e:
        raise ValueError(f"Failed to upload file to Cloudinary: {str(e)}")


def delete_file_from_cloudinary(cloudinary_public_id: str) -> bool:
    """Delete file from Cloudinary"""
    _ensure_cloudinary_configured()
    try:
        result = cloudinary.uploader.destroy(
            cloudinary_public_id,
            resource_type="auto"
        )
        return result.get("result") == "ok"
    except Exception as e:
        print(f"Error deleting file from Cloudinary: {str(e)}")
        return False

