from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.initialization import get_db
from database.schemas import UserProfileModel, SkillModel, user_skills
from utils.auth import get_current_user
from utils.validators import CreateProfileRequest
from pydantic import BaseModel
from database.schemas import GenderEnum
from pydantic import BaseModel, Field, model_validator

router = APIRouter(prefix="/profile", tags=["Profile"])

class CreateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    age: int | None = None
    gender: GenderEnum | None = None
    profession: str | None = None
    bio: str | None = None
    is_actor: bool = False
    profile_photo_url: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    years_of_experience: int | None = None
    previous_projects: str | None = None
    portfolio_url: str | None = None
    skill_ids: list[int] = []
    
    @model_validator(mode='after')
    def check_actor_requirements(self):
        if self.is_actor:
            if not self.age:
                raise ValueError("Age is required for actors")
            if not self.gender:
                raise ValueError("Gender is required for actors")
            if not self.profile_photo_url:
                raise ValueError("Profile photo is required for actors")
        return self

class ProfileResponse(BaseModel):
    id: str
    user_id: str
    name: str
    age: int | None = None
    gender: str | None = None
    profession: str | None = None
    bio: str | None = None
    is_actor: bool
    profile_photo_url: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    years_of_experience: int | None = None
    previous_projects: str | None = None
    portfolio_url: str | None = None
    skills: list[dict] = []
    created_at: str
    
    class Config:
        from_attributes = True

@router.post("/create", status_code=status.HTTP_201_CREATED, response_model=ProfileResponse)
async def create_profile(
    request: CreateProfileRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if profile exists
    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Profile already exists")
    
    # Create profile
    profile = UserProfileModel(
        user_id=current_user.id,
        name=request.name,
        age=request.age,
        gender=request.gender,
        profession=request.profession,
        bio=request.bio,
        is_actor=request.is_actor,
        profile_photo_url=request.profile_photo_url,
        city=request.city,
        state=request.state,
        country=request.country,
        latitude=request.latitude,
        longitude=request.longitude,
        years_of_experience=request.years_of_experience,
        previous_projects=request.previous_projects,
        portfolio_url=request.portfolio_url
    )
    
    db.add(profile)
    await db.flush()
    
    # Add skills
    if request.skill_ids:
        for skill_id in request.skill_ids:
            await db.execute(
                user_skills.insert().values(user_id=current_user.id, skill_id=skill_id)
            )
    
    await db.commit()
    await db.refresh(profile)
    
    # Get skills
    result = await db.execute(
        select(SkillModel).join(user_skills).where(user_skills.c.user_id == current_user.id)
    )
    skills = [{"id": s.id, "name": s.name, "category": s.category} for s in result.scalars().all()]
    
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        name=profile.name,
        age=profile.age,
        gender=profile.gender.value if profile.gender else None,
        profession=profile.profession,
        bio=profile.bio,
        is_actor=profile.is_actor,
        profile_photo_url=profile.profile_photo_url,
        city=profile.city,
        state=profile.state,
        country=profile.country,
        latitude=profile.latitude,
        longitude=profile.longitude,
        years_of_experience=profile.years_of_experience,
        previous_projects=profile.previous_projects,
        portfolio_url=profile.portfolio_url,
        skills=skills,
        created_at=profile.created_at.isoformat()
    )

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(404, "Profile not found")
    
    # Get skills
    result = await db.execute(
        select(SkillModel).join(user_skills).where(user_skills.c.user_id == current_user.id)
    )
    skills = [{"id": s.id, "name": s.name, "category": s.category} for s in result.scalars().all()]
    
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        name=profile.name,
        age=profile.age,
        gender=profile.gender.value if profile.gender else None,
        profession=profile.profession,
        bio=profile.bio,
        is_actor=profile.is_actor,
        profile_photo_url=profile.profile_photo_url,
        city=profile.city,
        state=profile.state,
        country=profile.country,
        latitude=profile.latitude,
        longitude=profile.longitude,
        years_of_experience=profile.years_of_experience,
        previous_projects=profile.previous_projects,
        portfolio_url=profile.portfolio_url,
        skills=skills,
        created_at=profile.created_at.isoformat()
    )

@router.put("/update", response_model=ProfileResponse)
async def update_profile(
    request: CreateProfileRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(404, "Profile not found")
    
    # Update fields
    profile.name = request.name
    profile.age = request.age
    profile.gender = request.gender
    profile.profession = request.profession
    profile.bio = request.bio
    profile.is_actor = request.is_actor
    profile.profile_photo_url = request.profile_photo_url
    profile.city = request.city
    profile.state = request.state
    profile.country = request.country
    profile.latitude = request.latitude
    profile.longitude = request.longitude
    profile.years_of_experience = request.years_of_experience
    profile.previous_projects = request.previous_projects
    profile.portfolio_url = request.portfolio_url
    
    # Update skills
    await db.execute(user_skills.delete().where(user_skills.c.user_id == current_user.id))
    if request.skill_ids:
        for skill_id in request.skill_ids:
            await db.execute(
                user_skills.insert().values(user_id=current_user.id, skill_id=skill_id)
            )
    
    await db.commit()
    await db.refresh(profile)
    
    # Get skills
    result = await db.execute(
        select(SkillModel).join(user_skills).where(user_skills.c.user_id == current_user.id)
    )
    skills = [{"id": s.id, "name": s.name, "category": s.category} for s in result.scalars().all()]
    
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        name=profile.name,
        age=profile.age,
        gender=profile.gender.value if profile.gender else None,
        profession=profile.profession,
        bio=profile.bio,
        is_actor=profile.is_actor,
        profile_photo_url=profile.profile_photo_url,
        city=profile.city,
        state=profile.state,
        country=profile.country,
        latitude=profile.latitude,
        longitude=profile.longitude,
        years_of_experience=profile.years_of_experience,
        previous_projects=profile.previous_projects,
        portfolio_url=profile.portfolio_url,
        skills=skills,
        created_at=profile.created_at.isoformat()
    )