from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.initialization import get_db
from database.schemas import SkillModel
from utils.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/skills", tags=["Skills"])

class CreateSkillRequest(BaseModel):
    name: str
    category: str | None = None

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
    
    # Check if skill already exists
    result = await db.execute(
        select(SkillModel).where(SkillModel.name == request.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Skill already exists")
    
    skill = SkillModel(
        name=request.name,
        category=request.category
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
    category: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """List all skills, optionally filtered by category."""
    
    query = select(SkillModel)
    
    if category:
        query = query.where(SkillModel.category == category)
    
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