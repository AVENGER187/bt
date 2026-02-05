from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from database.initialization import get_db
from database.schemas import (
    ApplicationModel, ProjectRoleModel, ProjectMemberModel, ProjectModel,
    ApplicationStatusEnum, MemberRoleEnum, UserProfileModel
)
from utils.auth import get_current_user
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, timezone

router = APIRouter(prefix="/applications", tags=["Applications"])

class ApplyRequest(BaseModel):
    role_id: UUID
    cover_letter: str | None = None

class ApplicationResponse(BaseModel):
    id: str
    project_id: str
    role_id: str
    applicant_id: str
    applicant_name: str
    cover_letter: str | None
    status: str
    applied_at: str
    reviewed_at: str | None

@router.post("/apply", status_code=status.HTTP_201_CREATED, response_model=ApplicationResponse)
async def apply_to_role(
    request: ApplyRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user has profile
    result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(400, "Create profile first")
    
    # Check if role exists and not filled
    result = await db.execute(
        select(ProjectRoleModel).where(ProjectRoleModel.id == request.role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(404, "Role not found")
    if role.is_filled:
        raise HTTPException(400, "Role is already filled")
    
    # Check if already applied
    result = await db.execute(
        select(ApplicationModel).where(
            and_(
                ApplicationModel.role_id == request.role_id,
                ApplicationModel.applicant_id == current_user.id
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Already applied to this role")
    
    # Check if user is creator
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == role.project_id)
    )
    
    project = result.scalar_one_or_none()
    if project.creator_id == current_user.id:
        raise HTTPException(400, "Cannot apply to your own project")
    
    # Create application
    application = ApplicationModel(
        project_id=role.project_id,
        role_id=request.role_id,
        applicant_id=current_user.id,
        cover_letter=request.cover_letter
    )
    
    db.add(application)
    await db.commit()
    await db.refresh(application)
    
    return ApplicationResponse(
        id=str(application.id),
        project_id=str(application.project_id),
        role_id=str(application.role_id),
        applicant_id=str(application.applicant_id),
        applicant_name=profile.name,
        cover_letter=application.cover_letter,
        status=application.status.value,
        applied_at=application.applied_at.isoformat(),
        reviewed_at=None
    )

@router.get("/project/{project_id}", response_model=list[ApplicationResponse])
async def get_project_applications(
    project_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user is project creator or parent/admin
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    
    if project.creator_id != current_user.id:
        result = await db.execute(
            select(ProjectMemberModel).where(
                and_(
                    ProjectMemberModel.project_id == project_id,
                    ProjectMemberModel.user_id == current_user.id,
                    ProjectMemberModel.member_role.in_([MemberRoleEnum.ADMIN, MemberRoleEnum.PARENT])
                )
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(403, "Not authorized")
    
    # Get applications
    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.project_id == project_id)
    )
    applications = result.scalars().all()
    
    response = []
    for app in applications:
        result = await db.execute(
            select(UserProfileModel).where(UserProfileModel.user_id == app.applicant_id)
        )
        profile = result.scalar_one_or_none()
        
        response.append(ApplicationResponse(
            id=str(app.id),
            project_id=str(app.project_id),
            role_id=str(app.role_id),
            applicant_id=str(app.applicant_id),
            applicant_name=profile.name if profile else "Unknown",
            cover_letter=app.cover_letter,
            status=app.status.value,
            applied_at=app.applied_at.isoformat(),
            reviewed_at=app.reviewed_at.isoformat() if app.reviewed_at else None
        ))
    
    return response

@router.post("/accept/{application_id}")
async def accept_application(
    application_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get application
    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(404, "Application not found")
    
    # Check authorization
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == application.project_id)
    )
    project = result.scalar_one_or_none()
    if project.creator_id != current_user.id:
        result = await db.execute(
            select(ProjectMemberModel).where(
                and_(
                    ProjectMemberModel.project_id == application.project_id,
                    ProjectMemberModel.user_id == current_user.id,
                    ProjectMemberModel.member_role.in_([MemberRoleEnum.ADMIN, MemberRoleEnum.PARENT])
                )
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(403, "Not authorized")
    
    if application.status != ApplicationStatusEnum.PENDING:
        raise HTTPException(400, "Application already processed")
    
    # Get role
    result = await db.execute(
        select(ProjectRoleModel).where(ProjectRoleModel.id == application.role_id)
    )
    role = result.scalar_one_or_none()
    
    if role.slots_filled >= role.slots_available:
        raise HTTPException(400, "No slots available")
    
    # Accept application
    application.status = ApplicationStatusEnum.ACCEPTED
    application.reviewed_at = datetime.now(timezone.utc)
    
    # Add as project member
    member = ProjectMemberModel(
        project_id=application.project_id,
        user_id=application.applicant_id,
        role_id=application.role_id,
        member_role=MemberRoleEnum.CHILD
    )
    db.add(member)
    
    # Update role slots
    role.slots_filled += 1
    if role.slots_filled >= role.slots_available:
        role.is_filled = True
    
    # Check if all roles filled
    result = await db.execute(
        select(ProjectRoleModel).where(ProjectRoleModel.project_id == application.project_id)
    )
    all_roles = result.scalars().all()
    if all(r.is_filled for r in all_roles):
        project.is_fully_staffed = True
    
    await db.commit()
    
    return {"message": "Application accepted"}

@router.post("/reject/{application_id}")
async def reject_application(
    application_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get application
    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(404, "Application not found")
    
    # Check authorization
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == application.project_id)
    )
    project = result.scalar_one_or_none()
    if project.creator_id != current_user.id:
        result = await db.execute(
            select(ProjectMemberModel).where(
                and_(
                    ProjectMemberModel.project_id == application.project_id,
                    ProjectMemberModel.user_id == current_user.id,
                    ProjectMemberModel.member_role.in_([MemberRoleEnum.ADMIN, MemberRoleEnum.PARENT])
                )
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(403, "Not authorized")
    
    if application.status != ApplicationStatusEnum.PENDING:
        raise HTTPException(400, "Application already processed")
    
    application.status = ApplicationStatusEnum.REJECTED
    application.reviewed_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {"message": "Application rejected"}