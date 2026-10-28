from pymongo import UpdateOne
from pymongo.database import Database

from ..seed_data import MATERIALS, QUESTIONS

_seed_checked = False


def run_seed(db: Database) -> dict:
    """Idempotente: faz upsert por (disciplina, título) e por enunciado."""
    material_ops = [
        UpdateOne({"subject": m["subject"], "title": m["title"]}, {"$set": m}, upsert=True) for m in MATERIALS
    ]
    question_ops = [UpdateOne({"statement": q["statement"]}, {"$set": q}, upsert=True) for q in QUESTIONS]
    mat = db.materials.bulk_write(material_ops, ordered=False)
    qst = db.questions.bulk_write(question_ops, ordered=False)
    return {
        "materials": {"inserted": mat.upserted_count, "updated": mat.modified_count, "total": db.materials.count_documents({})},
        "questions": {"inserted": qst.upserted_count, "updated": qst.modified_count, "total": db.questions.count_documents({})},
    }


def ensure_seeded(db: Database) -> None:
    """Popula o banco automaticamente na primeira consulta se as coleções estiverem vazias."""
    global _seed_checked
    if _seed_checked:
        return
    if db.materials.estimated_document_count() == 0 or db.questions.estimated_document_count() == 0:
        run_seed(db)
    _seed_checked = True
