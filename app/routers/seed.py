import secrets

from fastapi import APIRouter, HTTPException, status

from ..config import settings
from ..database import get_db
from ..services.seeder import run_seed

router = APIRouter(prefix="/api", tags=["Seed"])


def _seed(key: str | None):
    if settings.SEED_KEY and not secrets.compare_digest(key or "", settings.SEED_KEY):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chave de seed inválida.")
    return {"ok": True, **run_seed(get_db())}


@router.post("/seed")
def seed_post(key: str | None = None):
    return _seed(key)


@router.get("/seed")
def seed_get(key: str | None = None):
    """Atalho para popular o banco pelo navegador: abra /api/seed."""
    return _seed(key)
