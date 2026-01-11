from datetime import datetime, timedelta, timezone
from database.schemas import ProjectModel, ProjectStatusEnum
from sqlalchemy import select, update

async def mark_stale_projects_dead(db):
    """Mark projects as DEAD if not updated in 30 days"""
    threshold = datetime.now(timezone.utc) - timedelta(days=30)
    
    await db.execute(
        update(ProjectModel)
        .where(
            ProjectModel.status == ProjectStatusEnum.ACTIVE,
            ProjectModel.last_status_update < threshold
        )
        .values(status=ProjectStatusEnum.DEAD)
    )
    await db.commit()