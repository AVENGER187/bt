from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.initialization import get_db
from database.schemas import SkillModel
from utils.auth import get_current_user
from pydantic import BaseModel, Field

router = APIRouter(prefix="/skills", tags=["Skills"])

class CreateSkillRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: str | None = Field(None, max_length=255)

class SkillResponse(BaseModel):
    id: int
    name: str
    category: str | None
    created_at: str

@router.post("/create", status_code=status.HTTP_201_CREATED, response_model=SkillResponse)
async def create_skill(
    request: CreateSkillRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new skill. Any authenticated user can add skills."""
    
    # Check if skill already exists (case-insensitive)
    result = await db.execute(
        select(SkillModel).where(func.lower(SkillModel.name) == request.name.lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Skill already exists")
    
    skill = SkillModel(
        name=request.name.strip(),
        category=request.category.strip() if request.category else None
    )
    
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        category=skill.category,
        created_at=skill.created_at.isoformat()
    )

@router.get("/list", response_model=list[SkillResponse])
async def list_skills(
    category: str | None = Query(None),
    search: str | None = Query(None, description="Search skills by name"),
    db: AsyncSession = Depends(get_db)
):
    """List all skills, optionally filtered by category or search term."""
    
    query = select(SkillModel)
    
    if category:
        query = query.where(SkillModel.category == category)
    
    if search:
        query = query.where(SkillModel.name.ilike(f"%{search}%"))
    
    result = await db.execute(query.order_by(SkillModel.name))
    skills = result.scalars().all()
    
    return [
        SkillResponse(
            id=skill.id,
            name=skill.name,
            category=skill.category,
            created_at=skill.created_at.isoformat()
        )
        for skill in skills
    ]

@router.get("/categories", response_model=list[str])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Get all unique skill categories."""
    
    result = await db.execute(
        select(SkillModel.category)
        .distinct()
        .where(SkillModel.category.isnot(None))
        .order_by(SkillModel.category)
    )
    categories = result.scalars().all()
    
    return categories

@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific skill by ID."""
    
    result = await db.execute(
        select(SkillModel).where(SkillModel.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    
    if not skill:
        raise HTTPException(404, "Skill not found")
    
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        category=skill.category,
        created_at=skill.created_at.isoformat()
    )