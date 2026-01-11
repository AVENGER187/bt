from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from utils.auth import get_current_user
import httpx
from config import SUPABASE_URL, SUPABASE_KEY
import uuid

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
    
    # Read file
    contents = await file.read()
    
    # Validate size
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (max 5MB)")
    
    # Generate unique filename
    ext = file.filename.split(".")[-1]
    filename = f"profiles/{current_user.id}/{uuid.uuid4()}.{ext}"
    
    # Upload to Supabase Storage
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/profile-photos/{filename}",
            headers={
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": file.content_type
            },
            content=contents
        )
    
    if response.status_code not in [200, 201]:
        raise HTTPException(500, "Upload failed")
    
    # Return public URL
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/profile-photos/{filename}"
    
    return {"url": public_url}

@router.post("/portfolio")
async def upload_portfolio_file(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload portfolio files (images/videos) to Supabase Storage."""
    
    ALLOWED_TYPES = ALLOWED_IMAGE_TYPES + ["video/mp4", "video/quicktime", "application/pdf"]
    MAX_SIZE = 50 * 1024 * 1024  # 50MB for videos
    
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Invalid file type")
    
    contents = await file.read()
    
    if len(contents) > MAX_SIZE:
        raise HTTPException(400, "File too large (max 50MB)")
    
    ext = file.filename.split(".")[-1]
    filename = f"portfolio/{current_user.id}/{uuid.uuid4()}.{ext}"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/portfolio-files/{filename}",
            headers={
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": file.content_type
            },
            content=contents
        )
    
    if response.status_code not in [200, 201]:
        raise HTTPException(500, "Upload failed")
    
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/portfolio-files/{filename}"
    
    return {"url": public_url}