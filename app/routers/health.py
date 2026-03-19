"""Health check endpoint."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Returns a simple health status."""
    return {"status": "ok"}
