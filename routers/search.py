from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from database.initialization import get_db
from database.schemas import (
    ProjectModel, ProjectRoleModel, UserProfileModel, SkillModel,
    ProjectStatusEnum, user_skills
)
from pydantic import BaseModel
from math import radians, cos, sin, asin, sqrt

router = APIRouter(prefix="/search", tags=["Search"])

def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance between two points in km"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

class ProjectSearchResult(BaseModel):
    id: str
    name: str
    description: str | None
    project_type: str
    city: str | None
    state: str | None
    country: str | None
    distance_km: float | None
    roles: list[dict]

class UserSearchResult(BaseModel):
    id: str
    user_id: str
    name: str
    profession: str | None
    city: str | None
    state: str | None
    country: str | None
    distance_km: float | None
    profile_photo_url: str | None
    skills: list[dict]

@router.get("/projects", response_model=list[ProjectSearchResult])
async def search_projects(
    skill_id: int | None = Query(None),
    project_type: str | None = Query(None),
    latitude: float | None = Query(None),
    longitude: float | None = Query(None),
    max_distance_km: float | None = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Search for projects. Filter by skill, type, and location."""
    
    # Base query - only show ACTIVE projects that aren't fully staffed
    query = select(ProjectModel).where(
        and_(
            ProjectModel.status == ProjectStatusEnum.ACTIVE,
            ProjectModel.is_fully_staffed == False
        )
    )
    
    result = await db.execute(query)
    projects = result.scalars().all()
    
    results = []
    for project in projects:
        # Get roles
        result = await db.execute(
            select(ProjectRoleModel).where(ProjectRoleModel.project_id == project.id)
        )
        roles = result.scalars().all()
        
        # Filter by skill if specified
        if skill_id:
            if not any(r.skill_id == skill_id and not r.is_filled for r in roles):
                continue
        
        # Filter by project type
        if project_type and project.project_type.value != project_type:
            continue
        
        # Calculate distance
        distance = None
        if latitude and longitude and project.latitude and project.longitude:
            distance = haversine(longitude, latitude, project.longitude, project.latitude)
            if max_distance_km and distance > max_distance_km:
                continue
        
        roles_data = [{
            "id": str(r.id),
            "skill_id": r.skill_id,
            "role_title": r.role_title,
            "slots_available": r.slots_available,
            "slots_filled": r.slots_filled,
            "is_filled": r.is_filled,
            "payment_type": r.payment_type.value,
            "payment_amount": r.payment_amount
        } for r in roles if not r.is_filled]
        
        results.append(ProjectSearchResult(
            id=str(project.id),
            name=project.name,
            description=project.description,
            project_type=project.project_type.value,
            city=project.city,
            state=project.state,
            country=project.country,
            distance_km=round(distance, 2) if distance else None,
            roles=roles_data
        ))
    
    # Sort by distance if location provided
    if latitude and longitude:
        results.sort(key=lambda x: x.distance_km if x.distance_km else float('inf'))
    
    return results

@router.get("/users", response_model=list[UserSearchResult])
async def search_users(
    name: str | None = Query(None),
    profession: str | None = Query(None),
    skill_id: int | None = Query(None),
    latitude: float | None = Query(None),
    longitude: float | None = Query(None),
    max_distance_km: float | None = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Search for users. Filter by name, profession, skill, and location."""
    
    query = select(UserProfileModel)
    
    # Filter by name (partial match)
    if name:
        query = query.where(UserProfileModel.name.ilike(f"%{name}%"))
    
    # Filter by profession (partial match)
    if profession:
        query = query.where(UserProfileModel.profession.ilike(f"%{profession}%"))
    
    result = await db.execute(query)
    profiles = result.scalars().all()
    
    results = []
    for profile in profiles:
        # Get skills
        result = await db.execute(
            select(SkillModel).join(user_skills).where(user_skills.c.user_id == profile.user_id)
        )
        skills = result.scalars().all()
        
        # Filter by skill if specified
        if skill_id:
            if not any(s.id == skill_id for s in skills):
                continue
        
        # Calculate distance
        distance = None
        if latitude and longitude and profile.latitude and profile.longitude:
            distance = haversine(longitude, latitude, profile.longitude, profile.latitude)
            if max_distance_km and distance > max_distance_km:
                continue
        
        skills_data = [{"id": s.id, "name": s.name, "category": s.category} for s in skills]
        
        results.append(UserSearchResult(
            id=str(profile.id),
            user_id=str(profile.user_id),
            name=profile.name,
            profession=profile.profession,
            city=profile.city,
            state=profile.state,
            country=profile.country,
            distance_km=round(distance, 2) if distance else None,
            profile_photo_url=profile.profile_photo_url,
            skills=skills_data
        ))
    
    # Sort by distance if location provided
    if latitude and longitude:
        results.sort(key=lambda x: x.distance_km if x.distance_km else float('inf'))
    
    return results