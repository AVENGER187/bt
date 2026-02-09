from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from database.initialization import get_db
from database.schemas import (
    ProjectModel, ProjectMemberModel, ProjectRoleModel, ProjectStatusEnum, 
    MemberRoleEnum, UserProfileModel
)
from utils.auth import get_current_user
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, timezone

router = APIRouter(prefix="/management", tags=["Project Management"])

class UpdateStatusRequest(BaseModel):
    status: ProjectStatusEnum

class PromoteMemberRequest(BaseModel):
    member_role: MemberRoleEnum

class MemberResponse(BaseModel):
    user_id: str
    name: str
    profession: str | None
    profile_photo_url: str | None
    member_role: str
    role_title: str | None
    joined_at: str

# Helper function for authorization check (DRY)
async def check_admin_authorization(project_id: UUID, user_id: UUID, db: AsyncSession):
    """Check if user is admin of the project"""
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id,
                ProjectMemberModel.member_role == MemberRoleEnum.ADMIN
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only admins can perform this action")

async def check_parent_or_admin_authorization(project_id: UUID, user_id: UUID, db: AsyncSession):
    """Check if user is parent or admin of the project"""
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id,
                ProjectMemberModel.member_role.in_([MemberRoleEnum.PARENT, MemberRoleEnum.ADMIN])
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only parents and admins can perform this action")

@router.put("/project/{project_id}/status")
async def update_project_status(
    project_id: UUID,
    request: UpdateStatusRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update project status. Only PARENT or ADMIN can do this."""
    
    # OPTIMIZATION: Get project and check authorization in one query
    result = await db.execute(
        select(ProjectModel, ProjectMemberModel)
        .outerjoin(
            ProjectMemberModel,
            and_(
                ProjectMemberModel.project_id == ProjectModel.id,
                ProjectMemberModel.user_id == current_user.id
            )
        )
        .where(ProjectModel.id == project_id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(404, "Project not found")
    
    project, member = row
    
    # Check authorization
    if not member or member.member_role not in [MemberRoleEnum.PARENT, MemberRoleEnum.ADMIN]:
        # Check if creator
        if project.creator_id != current_user.id:
            raise HTTPException(403, "Only parents and admins can update status")
    
    old_status = project.status
    
    # Update status
    project.status = request.status
    project.last_status_update = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {
        "message": f"Project status updated from {old_status.value} to {request.status.value}",
        "old_status": old_status.value,
        "new_status": request.status.value
    }

@router.put("/project/{project_id}/member/{user_id}/promote")
async def promote_member(
    project_id: UUID,
    user_id: UUID,
    request: PromoteMemberRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Promote/demote a member. Only ADMIN can do this."""
    
    # Can't promote to ADMIN role
    if request.member_role == MemberRoleEnum.ADMIN:
        raise HTTPException(400, "Cannot promote to admin role")
    
    # Can't modify yourself
    if user_id == current_user.id:
        raise HTTPException(400, "Cannot change your own role")
    
    # Check authorization
    await check_admin_authorization(project_id, current_user.id, db)
    
    # Get target member
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id
            )
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Member not found in project")
    
    # Can't change admin role
    if member.member_role == MemberRoleEnum.ADMIN:
        raise HTTPException(400, "Cannot change admin role")
    
    old_role = member.member_role
    
    # Update role
    member.member_role = request.member_role
    await db.commit()
    
    return {
        "message": f"Member role updated from {old_role.value} to {request.member_role.value}",
        "user_id": str(user_id),
        "old_role": old_role.value,
        "new_role": request.member_role.value
    }

@router.get("/project/{project_id}/members", response_model=list[MemberResponse])
async def get_project_members(
    project_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all members of a project. Must be a member to view."""
    
    # Check if user is member
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == current_user.id
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Not a member of this project")
    
    # OPTIMIZATION: Get all members with profiles and roles in one query
    result = await db.execute(
        select(ProjectMemberModel, UserProfileModel, ProjectRoleModel)
        .join(UserProfileModel, ProjectMemberModel.user_id == UserProfileModel.user_id)
        .outerjoin(ProjectRoleModel, ProjectMemberModel.role_id == ProjectRoleModel.id)
        .where(ProjectMemberModel.project_id == project_id)
        .order_by(
            # Order: ADMIN first, then PARENT, then CHILD
            ProjectMemberModel.member_role.desc(),
            ProjectMemberModel.joined_at.asc()
        )
    )
    rows = result.all()
    
    response = []
    for member, profile, role in rows:
        response.append(MemberResponse(
            user_id=str(member.user_id),
            name=profile.name,
            profession=profile.profession,
            profile_photo_url=profile.profile_photo_url,
            member_role=member.member_role.value,
            role_title=role.role_title if role else None,
            joined_at=member.joined_at.isoformat()
        ))
    
    return response

@router.delete("/project/{project_id}/member/{user_id}")
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a member from project. Only ADMIN can do this."""
    
    # Can't remove yourself
    if user_id == current_user.id:
        raise HTTPException(400, "Cannot remove yourself from the project")
    
    # Check authorization
    await check_admin_authorization(project_id, current_user.id, db)
    
    # OPTIMIZATION: Get member and their role in one query
    result = await db.execute(
        select(ProjectMemberModel, ProjectRoleModel)
        .outerjoin(ProjectRoleModel, ProjectMemberModel.role_id == ProjectRoleModel.id)
        .where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id
            )
        )
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(404, "Member not found")
    
    member, role = row
    
    # Can't remove admin
    if member.member_role == MemberRoleEnum.ADMIN:
        raise HTTPException(400, "Cannot remove admin from project")
    
    # Update role slots if they had a role
    if role:
        role.slots_filled = max(0, role.slots_filled - 1)  # Prevent negative
        role.is_filled = role.slots_filled >= role.slots_available
        
        # Check if project should be marked as not fully staffed
        result = await db.execute(
            select(func.count(ProjectRoleModel.id))
            .where(
                and_(
                    ProjectRoleModel.project_id == project_id,
                    ProjectRoleModel.is_filled == False
                )
            )
        )
        unfilled_count = result.scalar()
        
        if unfilled_count > 0:
            result = await db.execute(
                select(ProjectModel).where(ProjectModel.id == project_id)
            )
            project = result.scalar_one()
            project.is_fully_staffed = False
    
    # Delete member
    await db.delete(member)
    await db.commit()
    
    return {
        "message": "Member removed successfully",
        "user_id": str(user_id),
        "role_freed": role.role_title if role else None
    }

@router.post("/project/{project_id}/leave")
async def leave_project(
    project_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Leave a project. Can't leave if you're the admin."""
    
    # Get member and role in one query
    result = await db.execute(
        select(ProjectMemberModel, ProjectRoleModel, ProjectModel)
        .outerjoin(ProjectRoleModel, ProjectMemberModel.role_id == ProjectRoleModel.id)
        .join(ProjectModel, ProjectMemberModel.project_id == ProjectModel.id)
        .where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == current_user.id
            )
        )
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(404, "You are not a member of this project")
    
    member, role, project = row
    
    # Can't leave if you're the admin/creator
    if member.member_role == MemberRoleEnum.ADMIN or project.creator_id == current_user.id:
        raise HTTPException(400, "Admins and creators cannot leave the project. Transfer ownership or delete the project instead.")
    
    # Update role slots if they had a role
    if role:
        role.slots_filled = max(0, role.slots_filled - 1)
        role.is_filled = role.slots_filled >= role.slots_available
        
        # Update project fully_staffed status
        result = await db.execute(
            select(func.count(ProjectRoleModel.id))
            .where(
                and_(
                    ProjectRoleModel.project_id == project_id,
                    ProjectRoleModel.is_filled == False
                )
            )
        )
        unfilled_count = result.scalar()
        
        if unfilled_count > 0:
            project.is_fully_staffed = False
    
    # Delete member
    await db.delete(member)
    await db.commit()
    
    return {
        "message": "Successfully left the project",
        "project_id": str(project_id)
    }

@router.get("/project/{project_id}/stats")
async def get_project_stats(
    project_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get project statistics. Must be a member."""
    
    # Check if user is member
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == current_user.id
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Not a member of this project")
    
    # Get stats in optimized queries
    # Total members
    result = await db.execute(
        select(func.count(ProjectMemberModel.id))
        .where(ProjectMemberModel.project_id == project_id)
    )
    total_members = result.scalar()
    
    # Role stats
    result = await db.execute(
        select(
            func.count(ProjectRoleModel.id).label('total_roles'),
            func.sum(ProjectRoleModel.slots_available).label('total_slots'),
            func.sum(ProjectRoleModel.slots_filled).label('filled_slots')
        )
        .where(ProjectRoleModel.project_id == project_id)
    )
    role_stats = result.one()
    
    # Message count
    from database.schemas import MessageModel
    result = await db.execute(
        select(func.count(MessageModel.id))
        .where(
            and_(
                MessageModel.project_id == project_id,
                MessageModel.is_deleted == False
            )
        )
    )
    message_count = result.scalar()
    
    # Pending applications
    from database.schemas import ApplicationModel, ApplicationStatusEnum
    result = await db.execute(
        select(func.count(ApplicationModel.id))
        .where(
            and_(
                ApplicationModel.project_id == project_id,
                ApplicationModel.status == ApplicationStatusEnum.PENDING
            )
        )
    )
    pending_applications = result.scalar()
    
    return {
        "project_id": str(project_id),
        "total_members": total_members,
        "total_roles": role_stats.total_roles or 0,
        "total_slots": int(role_stats.total_slots or 0),
        "filled_slots": int(role_stats.filled_slots or 0),
        "completion_percentage": round((role_stats.filled_slots / role_stats.total_slots * 100) if role_stats.total_slots else 0, 1),
        "message_count": message_count,
        "pending_applications": pending_applications
    }