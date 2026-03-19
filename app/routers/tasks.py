"""
Tasks router — scheduled / cron endpoints.

POST /tasks/timeout-check:
  - Validates X-Cron-Secret header against settings.webhook_secret.
  - Returns 403 if missing or invalid.
  - Runs the timeout check logic.
  - Returns {"status": "ok", "checked": N}.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.tasks.timeout_check import run_timeout_check

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/timeout-check")
def timeout_check(request: Request, db: Session = Depends(get_db)):
    """Run the shopping trip timeout check."""
    secret = request.headers.get("X-Cron-Secret")
    if secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    count = run_timeout_check(db)
    logger.info("Timeout check completed: %d list(s) timed out.", count)
    return {"status": "ok", "checked": count}
