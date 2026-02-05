from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from database.initialization import get_db
from database.schemas import (
    ApplicationModel, ProjectRoleModel, ProjectMemberModel, ProjectModel,
    ApplicationStatusEnum, MemberRoleEnum, UserProfileModel
)
from utils.auth import get_current_user
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, timezone

router = APIRouter(prefix="/applications", tags=["Applications"])

class ApplyRequest(BaseModel):
    role_id: UUID
    cover_letter: str | None = Field(None, max_length=2000)

class ApplicationResponse(BaseModel):
    id: str
    project_id: str
    project_name: str
    role_id: str
    role_title: str
    applicant_id: str
    applicant_name: str
    cover_letter: str | None
    status: str
    applied_at: str
    reviewed_at: str | None

# Helper function to check authorization (DRY principle)
async def check_project_authorization(project_id: UUID, user_id: UUID, db: AsyncSession) -> ProjectModel:
    """Check if user can manage applications for this project"""
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    
    # Creator has automatic access
    if project.creator_id == user_id:
        return project
    
    # Check if admin/parent member
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id,
                ProjectMemberModel.member_role.in_([MemberRoleEnum.ADMIN, MemberRoleEnum.PARENT])
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Not authorized to manage this project")
    
    return project

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
    
    # Get role and project in one query with join
    result = await db.execute(
        select(ProjectRoleModel, ProjectModel)
        .join(ProjectModel, ProjectRoleModel.project_id == ProjectModel.id)
        .where(ProjectRoleModel.id == request.role_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Role not found")
    
    role, project = row
    
    if role.is_filled:
        raise HTTPException(400, "Role is already filled")
    
    # Check if user is creator (can't apply to own project)
    if project.creator_id == current_user.id:
        raise HTTPException(400, "Cannot apply to your own project")
    
    # Check if already a member of this project
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == role.project_id,
                ProjectMemberModel.user_id == current_user.id
            )
        )
    )
    existing_member = result.scalar_one_or_none()
    if existing_member:
        # If they're already assigned to THIS specific role, extra protection
        if existing_member.role_id == request.role_id:
            raise HTTPException(400, "You are already assigned to this role")
        else:
            raise HTTPException(400, "You are already a member of this project")
    
    # Check if already applied to this role
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
        project_name=project.name,
        role_id=str(application.role_id),
        role_title=role.role_title,
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
    # Check authorization using helper function
    await check_project_authorization(project_id, current_user.id, db)
    
    # OPTIMIZED: Get applications with role and profile data in one query
    result = await db.execute(
        select(ApplicationModel, ProjectRoleModel, UserProfileModel, ProjectModel)
        .join(ProjectRoleModel, ApplicationModel.role_id == ProjectRoleModel.id)
        .join(UserProfileModel, ApplicationModel.applicant_id == UserProfileModel.user_id)
        .join(ProjectModel, ApplicationModel.project_id == ProjectModel.id)
        .where(ApplicationModel.project_id == project_id)
        .order_by(ApplicationModel.applied_at.desc())
    )
    rows = result.all()
    
    response = []
    for app, role, profile, project in rows:
        response.append(ApplicationResponse(
            id=str(app.id),
            project_id=str(app.project_id),
            project_name=project.name,
            role_id=str(app.role_id),
            role_title=role.role_title,
            applicant_id=str(app.applicant_id),
            applicant_name=profile.name,
            cover_letter=app.cover_letter,
            status=app.status.value,
            applied_at=app.applied_at.isoformat(),
            reviewed_at=app.reviewed_at.isoformat() if app.reviewed_at else None
        ))
    
    return response

@router.get("/my-applications", response_model=list[ApplicationResponse])
async def get_my_applications(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all applications submitted by the current user"""
    
    # OPTIMIZED: Get all data in one query
    result = await db.execute(
        select(ApplicationModel, ProjectRoleModel, UserProfileModel, ProjectModel)
        .join(ProjectRoleModel, ApplicationModel.role_id == ProjectRoleModel.id)
        .join(UserProfileModel, ApplicationModel.applicant_id == UserProfileModel.user_id)
        .join(ProjectModel, ApplicationModel.project_id == ProjectModel.id)
        .where(ApplicationModel.applicant_id == current_user.id)
        .order_by(ApplicationModel.applied_at.desc())
    )
    rows = result.all()
    
    response = []
    for app, role, profile, project in rows:
        response.append(ApplicationResponse(
            id=str(app.id),
            project_id=str(app.project_id),
            project_name=project.name,
            role_id=str(app.role_id),
            role_title=role.role_title,
            applicant_id=str(app.applicant_id),
            applicant_name=profile.name,
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
    try:
        async with db.begin_nested():  # Use savepoint for transaction
            # Get application with role in one query
            result = await db.execute(
                select(ApplicationModel, ProjectRoleModel)
                .join(ProjectRoleModel, ApplicationModel.role_id == ProjectRoleModel.id)
                .where(ApplicationModel.id == application_id)
            )
            row = result.one_or_none()
            if not row:
                raise HTTPException(404, "Application not found")
            
            application, role = row
            
            # Check authorization
            await check_project_authorization(application.project_id, current_user.id, db)
            
            if application.status != ApplicationStatusEnum.PENDING:
                raise HTTPException(400, f"Application already {application.status.value}")
            
            # Check slots available (prevent race condition)
            if role.slots_filled >= role.slots_available:
                raise HTTPException(400, "No slots available for this role")
            
            # Check if applicant is already a member (shouldn't happen, but safety check)
            result = await db.execute(
                select(ProjectMemberModel).where(
                    and_(
                        ProjectMemberModel.project_id == application.project_id,
                        ProjectMemberModel.user_id == application.applicant_id
                    )
                )
            )
            if result.scalar_one_or_none():
                raise HTTPException(400, "Applicant is already a project member")
            
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
                select(func.count(ProjectRoleModel.id))
                .where(
                    and_(
                        ProjectRoleModel.project_id == application.project_id,
                        ProjectRoleModel.is_filled == False
                    )
                )
            )
            unfilled_count = result.scalar()
            
            if unfilled_count == 0:
                result = await db.execute(
                    select(ProjectModel).where(ProjectModel.id == application.project_id)
                )
                project = result.scalar_one()
                project.is_fully_staffed = True
        
        await db.commit()
        
        return {
            "message": "Application accepted",
            "application_id": str(application_id),
            "member_id": str(member.id)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Failed to accept application: {str(e)}")

@router.post("/reject/{application_id}")
async def reject_application(
    application_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        async with db.begin_nested():  # Use savepoint for transaction
            # Get application
            result = await db.execute(
                select(ApplicationModel).where(ApplicationModel.id == application_id)
            )
            application = result.scalar_one_or_none()
            if not application:
                raise HTTPException(404, "Application not found")
            
            # Check authorization
            await check_project_authorization(application.project_id, current_user.id, db)
            
            if application.status != ApplicationStatusEnum.PENDING:
                raise HTTPException(400, f"Application already {application.status.value}")
            
            # Reject application
            application.status = ApplicationStatusEnum.REJECTED
            application.reviewed_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        return {
            "message": "Application rejected",
            "application_id": str(application_id)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Failed to reject application: {str(e)}")