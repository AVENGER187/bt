from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from utils.auth import get_current_user
import httpx
from config import SUPABASE_URL, SUPABASE_KEY
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["File Upload"])

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@router.post("/profile-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload profile photo to Supabase Storage."""
    
    # Validate file type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Only images allowed (JPEG, PNG, WebP)")
    
    # Validate filename exists
    if not file.filename:
        raise HTTPException(400, "No filename provided")
    
    # Read file
    try:
        contents = await file.read()
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(400, "Error reading file")
    
    # Validate size
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large (max {MAX_FILE_SIZE / 1024 / 1024:.0f}MB)")
    
    # Validate not empty
    if len(contents) == 0:
        raise HTTPException(400, "Empty file")
    
    # Generate unique filename with safe extension
    ext = file.filename.split(".")[-1].lower()
    if ext not in ["jpg", "jpeg", "png", "webp"]:
        ext = "jpg"  # default
    filename = f"profiles/{current_user.id}/{uuid.uuid4()}.{ext}"
    
    # Upload to Supabase Storage
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/profile-photos/{filename}",
                headers={
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": file.content_type
                },
                content=contents
            )
        
        if response.status_code not in [200, 201]:
            logger.error(f"Supabase upload failed: {response.status_code} - {response.text}")
            raise HTTPException(500, "Upload failed")
    
    except httpx.TimeoutException:
        logger.error("Upload timeout")
        raise HTTPException(504, "Upload timeout")
    except httpx.RequestError as e:
        logger.error(f"Upload request error: {e}")
        raise HTTPException(500, "Upload failed")
    
    # Return public URL
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/profile-photos/{filename}"
    
    return {
        "url": public_url,
        "filename": filename
    }

@router.post("/portfolio")
async def upload_portfolio_file(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload portfolio files (images/videos/PDFs) to Supabase Storage."""
    
    ALLOWED_TYPES = ALLOWED_IMAGE_TYPES + ["video/mp4", "video/quicktime", "application/pdf"]
    MAX_SIZE = 50 * 1024 * 1024  # 50MB for videos
    
    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Invalid file type (allowed: images, videos, PDFs)")
    
    # Validate filename exists
    if not file.filename:
        raise HTTPException(400, "No filename provided")
    
    # Read file
    try:
        contents = await file.read()
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(400, "Error reading file")
    
    # Validate size
    if len(contents) > MAX_SIZE:
        raise HTTPException(400, f"File too large (max {MAX_SIZE / 1024 / 1024:.0f}MB)")
    
    # Validate not empty
    if len(contents) == 0:
        raise HTTPException(400, "Empty file")
    
    # Generate unique filename with safe extension
    ext = file.filename.split(".")[-1].lower()
    allowed_exts = ["jpg", "jpeg", "png", "webp", "mp4", "mov", "pdf"]
    if ext not in allowed_exts:
        # Map content type to extension
        ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "video/mp4": "mp4",
            "video/quicktime": "mov",
            "application/pdf": "pdf"
        }
        ext = ext_map.get(file.content_type, "bin")
    
    filename = f"portfolio/{current_user.id}/{uuid.uuid4()}.{ext}"
    
    # Upload to Supabase Storage
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for videos
            response = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/portfolio-files/{filename}",
                headers={
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": file.content_type
                },
                content=contents
            )
        
        if response.status_code not in [200, 201]:
            logger.error(f"Supabase upload failed: {response.status_code} - {response.text}")
            raise HTTPException(500, "Upload failed")
    
    except httpx.TimeoutException:
        logger.error("Upload timeout")
        raise HTTPException(504, "Upload timeout - file may be too large")
    except httpx.RequestError as e:
        logger.error(f"Upload request error: {e}")
        raise HTTPException(500, "Upload failed")
    
    # Return public URL
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/portfolio-files/{filename}"
    
    return {
        "url": public_url,
        "filename": filename,
        "file_type": file.content_type,
        "size_bytes": len(contents)
    }

@router.delete("/profile-photo")
async def delete_profile_photo(
    filename: str,
    current_user = Depends(get_current_user)
):
    """Delete a profile photo from Supabase Storage."""
    
    # Verify filename belongs to current user
    if not filename.startswith(f"profiles/{current_user.id}/"):
        raise HTTPException(403, "Unauthorized")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{SUPABASE_URL}/storage/v1/object/profile-photos/{filename}",
                headers={
                    "Authorization": f"Bearer {SUPABASE_KEY}"
                }
            )
        
        if response.status_code not in [200, 204]:
            logger.error(f"Delete failed: {response.status_code} - {response.text}")
            raise HTTPException(500, "Delete failed")
    
    except httpx.RequestError as e:
        logger.error(f"Delete request error: {e}")
        raise HTTPException(500, "Delete failed")
    
    return {"message": "Photo deleted successfully"}