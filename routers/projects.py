from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.initialization import get_db
from database.schemas import (
    ProjectModel, ProjectRoleModel, ProjectMemberModel, 
    ProjectTypeEnum, ProjectStatusEnum, PaymentTypeEnum, MemberRoleEnum,
    UserProfileModel
)
from utils.auth import get_current_user
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import UUID

router = APIRouter(prefix="/projects", tags=["Projects"])

class RoleRequest(BaseModel):
    skill_id: int
    role_title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    slots_available: int = Field(default=1, ge=1)
    payment_type: PaymentTypeEnum
    payment_amount: float | None = None
    payment_details: str | None = None

class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    project_type: ProjectTypeEnum
    release_platform: str | None = None
    estimated_completion: datetime | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    roles: list[RoleRequest]

class ProjectResponse(BaseModel):
    id: str
    creator_id: str
    name: str
    description: str | None
    project_type: str
    release_platform: str | None
    estimated_completion: str | None
    status: str
    is_fully_staffed: bool
    city: str | None
    state: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    created_at: str
    roles: list[dict] = []

@router.post("/create", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user has profile
    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(400, "Create profile first")
    
    # Create project
    project = ProjectModel(
        creator_id=current_user.id,
        name=request.name,
        description=request.description,
        project_type=request.project_type,
        release_platform=request.release_platform,
        estimated_completion=request.estimated_completion,
        city=request.city,
        state=request.state,
        country=request.country,
        latitude=request.latitude,
        longitude=request.longitude,
        last_status_update=datetime.now(timezone.utc)
    )
    
    db.add(project)
    await db.flush()
    
    # Add roles
    roles_data = []
    for role_req in request.roles:
        role = ProjectRoleModel(
            project_id=project.id,
            skill_id=role_req.skill_id,
            role_title=role_req.role_title,
            description=role_req.description,
            slots_available=role_req.slots_available,
            payment_type=role_req.payment_type,
            payment_amount=role_req.payment_amount,
            payment_details=role_req.payment_details
        )
        db.add(role)
        await db.flush()
        roles_data.append({
            "id": str(role.id),
            "skill_id": role.skill_id,
            "role_title": role.role_title,
            "description": role.description,
            "slots_available": role.slots_available,
            "slots_filled": role.slots_filled,
            "is_filled": role.is_filled,
            "payment_type": role.payment_type.value,
            "payment_amount": role.payment_amount,
            "payment_details": role.payment_details
        })
    
    # Add creator as ADMIN member
    member = ProjectMemberModel(
        project_id=project.id,
        user_id=current_user.id,
        member_role=MemberRoleEnum.ADMIN
    )
    db.add(member)
    
    await db.commit()
    await db.refresh(project)
    
    return ProjectResponse(
        id=str(project.id),
        creator_id=str(project.creator_id),
        name=project.name,
        description=project.description,
        project_type=project.project_type.value,
        release_platform=project.release_platform,
        estimated_completion=project.estimated_completion.isoformat() if project.estimated_completion else None,
        status=project.status.value,
        is_fully_staffed=project.is_fully_staffed,
        city=project.city,
        state=project.state,
        country=project.country,
        latitude=project.latitude,
        longitude=project.longitude,
        created_at=project.created_at.isoformat(),
        roles=roles_data
    )

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(404, "Project not found")
    
    # Get roles
    result = await db.execute(
        select(ProjectRoleModel).where(ProjectRoleModel.project_id == project_id)
    )
    roles = result.scalars().all()
    roles_data = [{
        "id": str(r.id),
        "skill_id": r.skill_id,
        "role_title": r.role_title,
        "description": r.description,
        "slots_available": r.slots_available,
        "slots_filled": r.slots_filled,
        "is_filled": r.is_filled,
        "payment_type": r.payment_type.value,
        "payment_amount": r.payment_amount,
        "payment_details": r.payment_details
    } for r in roles]
    
    return ProjectResponse(
        id=str(project.id),
        creator_id=str(project.creator_id),
        name=project.name,
        description=project.description,
        project_type=project.project_type.value,
        release_platform=project.release_platform,
        estimated_completion=project.estimated_completion.isoformat() if project.estimated_completion else None,
        status=project.status.value,
        is_fully_staffed=project.is_fully_staffed,
        city=project.city,
        state=project.state,
        country=project.country,
        latitude=project.latitude,
        longitude=project.longitude,
        created_at=project.created_at.isoformat(),
        roles=roles_data
    )

@router.get("/my/projects", response_model=list[ProjectResponse])
async def get_my_projects(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.creator_id == current_user.id)
    )
    projects = result.scalars().all()
    
    response = []
    for project in projects:
        result = await db.execute(
            select(ProjectRoleModel).where(ProjectRoleModel.project_id == project.id)
        )
        roles = result.scalars().all()
        roles_data = [{
            "id": str(r.id),
            "skill_id": r.skill_id,
            "role_title": r.role_title,
            "description": r.description,
            "slots_available": r.slots_available,
            "slots_filled": r.slots_filled,
            "is_filled": r.is_filled,
            "payment_type": r.payment_type.value,
            "payment_amount": r.payment_amount,
            "payment_details": r.payment_details
        } for r in roles]
        
        response.append(ProjectResponse(
            id=str(project.id),
            creator_id=str(project.creator_id),
            name=project.name,
            description=project.description,
            project_type=project.project_type.value,
            release_platform=project.release_platform,
            estimated_completion=project.estimated_completion.isoformat() if project.estimated_completion else None,
            status=project.status.value,
            is_fully_staffed=project.is_fully_staffed,
            city=project.city,
            state=project.state,
            country=project.country,
            latitude=project.latitude,
            longitude=project.longitude,
            created_at=project.created_at.isoformat(),
            roles=roles_data
        ))
    
    return response