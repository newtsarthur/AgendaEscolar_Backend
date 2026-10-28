import re

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import get_db, serialize, to_object_id
from ..security import get_current_user
from ..seed_data import SUBJECTS
from ..services.seeder import ensure_seeded

router = APIRouter(prefix="/api/materials", tags=["Biblioteca"])


@router.get("/subjects")
def list_subjects(_: dict = Depends(get_current_user)):
    db = get_db()
    ensure_seeded(db)
    counts = {row["_id"]: row["n"] for row in db.materials.aggregate([{"$group": {"_id": "$subject", "n": {"$sum": 1}}}])}
    extra = sorted(s for s in counts if s not in SUBJECTS)
    return [{"name": s, "count": counts.get(s, 0)} for s in SUBJECTS + extra]


@router.get("")
def list_materials(subject: str | None = None, q: str | None = None, _: dict = Depends(get_current_user)):
    db = get_db()
    ensure_seeded(db)
    query: dict = {}
    if subject:
        query["subject"] = subject
    if q:
        pattern = re.compile(re.escape(q.strip()), re.IGNORECASE)
        query["$or"] = [{"title": pattern}, {"topic": pattern}, {"description": pattern}]
    return [serialize(m) for m in db.materials.find(query).sort([("subject", 1), ("title", 1)])]


@router.get("/{material_id}")
def get_material(material_id: str, _: dict = Depends(get_current_user)):
    material = get_db().materials.find_one({"_id": to_object_id(material_id)})
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material não encontrado.")
    return serialize(material)
