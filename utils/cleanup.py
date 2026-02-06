from datetime import datetime, timedelta, timezone
from database.schemas import (
    ProjectModel, ProjectStatusEnum, OTPVerificationModel, RefreshTokenModel
)
from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

async def mark_stale_projects_dead(db: AsyncSession, days_threshold: int = 30) -> int:
    """
    Mark projects as DEAD if not updated in X days.
    
    Args:
        db: Database session
        days_threshold: Number of days of inactivity before marking as DEAD
    
    Returns:
        Number of projects marked as DEAD
    """
    try:
        threshold = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        
        # First, count how many will be affected
        count_result = await db.execute(
            select(func.count(ProjectModel.id))
            .where(
                ProjectModel.status == ProjectStatusEnum.ACTIVE,
                ProjectModel.last_status_update < threshold
            )
        )
        count = count_result.scalar()
        
        if count == 0:
            logger.info("No stale projects to mark as DEAD")
            return 0
        
        # Update projects
        await db.execute(
            update(ProjectModel)
            .where(
                ProjectModel.status == ProjectStatusEnum.ACTIVE,
                ProjectModel.last_status_update < threshold
            )
            .values(
                status=ProjectStatusEnum.DEAD,
                last_status_update=datetime.now(timezone.utc)
            )
        )
        
        await db.commit()
        
        logger.info(f"Marked {count} stale projects as DEAD (inactive for {days_threshold}+ days)")
        return count
        
    except Exception as e:
        logger.error(f"Error marking stale projects: {e}", exc_info=True)
        await db.rollback()
        return 0

async def cleanup_expired_otps(db: AsyncSession) -> int:
    """
    Delete expired OTP records from database.
    
    Returns:
        Number of OTPs deleted
    """
    try:
        # Delete OTPs that expired more than 1 day ago
        threshold = datetime.now(timezone.utc) - timedelta(days=1)
        
        count_result = await db.execute(
            select(func.count(OTPVerificationModel.id))
            .where(OTPVerificationModel.expires_at < threshold)
        )
        count = count_result.scalar()
        
        if count == 0:
            logger.info("No expired OTPs to delete")
            return 0
        
        # Delete expired OTPs
        await db.execute(
            delete(OTPVerificationModel)
            .where(OTPVerificationModel.expires_at < threshold)
        )
        
        await db.commit()
        
        logger.info(f"Deleted {count} expired OTP records")
        return count
        
    except Exception as e:
        logger.error(f"Error cleaning up OTPs: {e}", exc_info=True)
        await db.rollback()
        return 0

async def cleanup_revoked_refresh_tokens(db: AsyncSession) -> int:
    """
    Delete old revoked refresh tokens (keep for 30 days for audit).

    Returns:
        Number of tokens deleted
    """
    try:
        # Delete revoked tokens older than 30 days
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        
        count_result = await db.execute(
            select(func.count(RefreshTokenModel.id))
            .where(
                RefreshTokenModel.is_revoked == True,
                RefreshTokenModel.created_at < threshold
            )
        )
        count = count_result.scalar()
        
        if count == 0:
            logger.info("No old revoked tokens to delete")
            return 0
        
        await db.execute(
            delete(RefreshTokenModel)
            .where(
                RefreshTokenModel.is_revoked == True,
                RefreshTokenModel.created_at < threshold
            )
        )
        
        await db.commit()
        
        logger.info(f"Deleted {count} old revoked refresh tokens")
        return count
        
    except Exception as e:
        logger.error(f"Error cleaning up tokens: {e}", exc_info=True)
        await db.rollback()
        return 0

async def run_all_cleanup_tasks(db: AsyncSession) -> dict:
    """
    Run all cleanup tasks and return summary.
    
    Returns:
        Dict with counts of items cleaned up
    """
    logger.info("Starting scheduled cleanup tasks...")
    
    results = {
        "stale_projects": await mark_stale_projects_dead(db),
        "expired_otps": await cleanup_expired_otps(db),
        "revoked_tokens": await cleanup_revoked_refresh_tokens(db),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    logger.info(f"Cleanup tasks completed: {results}")
    return results