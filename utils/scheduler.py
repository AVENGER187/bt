# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database.initialization import AsyncSessionLocal
from utils.cleanup import run_all_cleanup_tasks
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def scheduled_cleanup():
    """Run cleanup tasks"""
    logger.info("Starting scheduled cleanup job...")
    async with AsyncSessionLocal() as db:
        try:
            results = await run_all_cleanup_tasks(db)
            logger.info(f"Cleanup completed: {results}")
        except Exception as e:
            logger.error(f"Scheduled cleanup failed: {e}", exc_info=True)

def start_scheduler():
    """Start the background scheduler"""
    # Run cleanup every day at 2 AM UTC
    scheduler.add_job(
        scheduled_cleanup,
        trigger=CronTrigger(hour=2, minute=0),  # Better syntax
        id='daily_cleanup',
        replace_existing=True,
        name='Daily cleanup tasks'
    )
    
    scheduler.start()
    logger.info("Cleanup scheduler started (runs daily at 2:00 AM UTC)")

def stop_scheduler():
    """Stop the scheduler gracefully"""
    if scheduler.running:
        scheduler.shutdown(wait=True)  # Wait for running jobs to finish
        logger.info("Cleanup scheduler stopped")
    else:
        logger.info("Scheduler was not running")