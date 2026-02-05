from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from database.initialization import get_db
from database.schemas import (
    ProjectModel, ProjectRoleModel, UserProfileModel, SkillModel,
    ProjectStatusEnum, user_skills, ProjectTypeEnum
)
from pydantic import BaseModel, Field
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

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)

@router.get("/projects", response_model=list[ProjectSearchResult])
async def search_projects(
    skill_id: int | None = Query(None),
    project_type: str | None = Query(None),
    city: str | None = Query(None),
    query: str | None = Query(None, description="Search in name/description"),
    latitude: float | None = Query(None),
    longitude: float | None = Query(None),
    max_distance_km: float | None = Query(None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Search for projects. Filter by skill, type, location, and text query."""
    
    # Base query - only show ACTIVE projects that aren't fully staffed
    stmt = select(ProjectModel).where(
        and_(
            ProjectModel.status == ProjectStatusEnum.ACTIVE,
            ProjectModel.is_fully_staffed == False
        )
    )
    
    # Text search filter
    if query:
        stmt = stmt.where(
            or_(
                ProjectModel.name.ilike(f"%{query}%"),
                ProjectModel.description.ilike(f"%{query}%")
            )
        )
    
    # City filter (exact match, case-insensitive)
    if city:
        stmt = stmt.where(ProjectModel.city.ilike(city))
    
    # Project type filter
    if project_type:
        try:
            stmt = stmt.where(ProjectModel.project_type == ProjectTypeEnum(project_type))
        except ValueError:
            # Invalid project type, return empty
            return []
    
    # If filtering by skill, join with roles
    if skill_id:
        stmt = stmt.join(ProjectRoleModel).where(
            and_(
                ProjectRoleModel.skill_id == skill_id,
                ProjectRoleModel.is_filled == False
            )
        ).distinct()
    
    result = await db.execute(stmt)
    projects = result.scalars().all()
    
    # OPTIMIZATION: Fetch all roles in one query instead of N queries
    project_ids = [p.id for p in projects]
    if project_ids:
        roles_result = await db.execute(
            select(ProjectRoleModel)
            .where(
                and_(
                    ProjectRoleModel.project_id.in_(project_ids),
                    ProjectRoleModel.is_filled == False
                )
            )
        )
        all_roles = roles_result.scalars().all()
        
        # Group roles by project_id
        roles_by_project = {}
        for role in all_roles:
            if role.project_id not in roles_by_project:
                roles_by_project[role.project_id] = []
            roles_by_project[role.project_id].append(role)
    else:
        roles_by_project = {}
    
    # Build results with distance calculation
    results = []
    for project in projects:
        roles = roles_by_project.get(project.id, [])
        
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
        } for r in roles]
        
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
    
    # Pagination
    offset = (page - 1) * limit
    return results[offset:offset + limit]


@router.get("/users", response_model=list[UserSearchResult])
async def search_users(
    name: str | None = Query(None),
    profession: str | None = Query(None),
    skill_id: int | None = Query(None),
    city: str | None = Query(None),
    is_actor: bool | None = Query(None),
    latitude: float | None = Query(None),
    longitude: float | None = Query(None),
    max_distance_km: float | None = Query(None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Search for users. Filter by name, profession, skill, and location."""
    
    stmt = select(UserProfileModel)
    
    # Filter by name (partial match)
    if name:
        stmt = stmt.where(UserProfileModel.name.ilike(f"%{name}%"))
    
    # Filter by profession (partial match)
    if profession:
        stmt = stmt.where(UserProfileModel.profession.ilike(f"%{profession}%"))
    
    # Filter by city
    if city:
        stmt = stmt.where(UserProfileModel.city.ilike(city))
    
    # Filter by actor status
    if is_actor is not None:
        stmt = stmt.where(UserProfileModel.is_actor == is_actor)
    
    # If filtering by skill, join with user_skills
    if skill_id:
        stmt = stmt.join(user_skills).where(user_skills.c.skill_id == skill_id).distinct()
    
    result = await db.execute(stmt)
    profiles = result.scalars().all()
    
    # OPTIMIZATION: Fetch all skills in one query instead of N queries
    profile_ids = [p.id for p in profiles]
    if profile_ids:
        skills_result = await db.execute(
            select(SkillModel, user_skills.c.user_profile_id)
            .join(user_skills)
            .where(user_skills.c.user_profile_id.in_(profile_ids))
        )
        all_skills = skills_result.all()
        
        # Group skills by user_profile_id
        skills_by_profile = {}
        for skill, profile_id in all_skills:
            if profile_id not in skills_by_profile:
                skills_by_profile[profile_id] = []
            skills_by_profile[profile_id].append(skill)
    else:
        skills_by_profile = {}
    
    # Build results with distance calculation
    results = []
    for profile in profiles:
        skills = skills_by_profile.get(profile.id, [])
        
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
    
    # Pagination
    offset = (page - 1) * limit
    return results[offset:offset + limit]