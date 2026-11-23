from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DBSession
from app.core.config import settings

router = APIRouter(tags=["运维"])


@router.get("/health", summary="健康检查（含数据库连通性）")
async def health(db: DBSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "app": settings.app_name}


@router.get("/", include_in_schema=False)
async def index() -> dict[str, str]:
    return {"message": "FastAPI Starter", "docs": "/docs"}
