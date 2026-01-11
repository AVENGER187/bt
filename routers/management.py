from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.initialization import get_db
from database.schemas import (
    ProjectModel, ProjectMemberModel, ProjectStatusEnum, MemberRoleEnum
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

@router.put("/project/{project_id}/status")
async def update_project_status(
    project_id: UUID,
    request: UpdateStatusRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update project status. Only PARENT or ADMIN can do this."""
    
    # Get project
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    
    # Check if user is parent or admin
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == current_user.id,
                ProjectMemberModel.member_role.in_([MemberRoleEnum.PARENT, MemberRoleEnum.ADMIN])
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only parents and admins can update status")
    
    # Update status
    project.status = request.status
    project.last_status_update = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {"message": f"Project status updated to {request.status.value}"}

@router.put("/project/{project_id}/member/{user_id}/promote")
async def promote_member(
    project_id: UUID,
    user_id: UUID,
    request: PromoteMemberRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Promote/demote a member. Only ADMIN can do this."""
    
    # Check if current user is admin
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == current_user.id,
                ProjectMemberModel.member_role == MemberRoleEnum.ADMIN
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only admins can change member roles")
    
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
    
    # Update role
    member.member_role = request.member_role
    await db.commit()
    
    return {"message": f"Member role updated to {request.member_role.value}"}

@router.get("/project/{project_id}/members")
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
    
    # Get all members
    result = await db.execute(
        select(ProjectMemberModel).where(ProjectMemberModel.project_id == project_id)
    )
    members = result.scalars().all()
    
    from database.schemas import UserProfileModel
    response = []
    for member in members:
        result = await db.execute(
            select(UserProfileModel).where(UserProfileModel.user_id == member.user_id)
        )
        profile = result.scalar_one_or_none()
        
        response.append({
            "user_id": str(member.user_id),
            "name": profile.name if profile else "Unknown",
            "member_role": member.member_role.value,
            "joined_at": member.joined_at.isoformat()
        })
    
    return response

@router.delete("/project/{project_id}/member/{user_id}")
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a member from project. Only ADMIN can do this."""
    
    # Check if current user is admin
    result = await db.execute(
        select(ProjectMemberModel).where(
            and_(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == current_user.id,
                ProjectMemberModel.member_role == MemberRoleEnum.ADMIN
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only admins can remove members")
    
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
        raise HTTPException(404, "Member not found")
    
    # Can't remove admin
    if member.member_role == MemberRoleEnum.ADMIN:
        raise HTTPException(400, "Cannot remove admin")
    
    # Remove member and update role slots if they had a role
    if member.role_id:
        from database.schemas import ProjectRoleModel
        result = await db.execute(
            select(ProjectRoleModel).where(ProjectRoleModel.id == member.role_id)
        )
        role = result.scalar_one_or_none()
        if role:
            role.slots_filled -= 1
            role.is_filled = False
    
    await db.delete(member)
    await db.commit()
    
    return {"message": "Member removed"}