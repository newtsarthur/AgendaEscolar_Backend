"""Conexão com o MongoDB Atlas.

Usa o driver síncrono do PyMongo com rotas `def` (o FastAPI as executa num threadpool).
Isso é mais robusto em ambiente serverless do que clientes assíncronos presos a um event loop.
O cliente é cacheado no módulo e reaproveitado entre invocações "quentes" da função.
"""
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from .config import settings

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is not None:
        return _db
    if not settings.MONGODB_URI:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MONGODB_URI não configurada no servidor.",
        )
    _client = MongoClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=8000,
        connectTimeoutMS=8000,
        maxPoolSize=10,
        tz_aware=False,
    )
    db = _client[settings.MONGODB_DB]
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.tasks.create_index([("user_id", ASCENDING), ("due_date", ASCENDING)])
    db.materials.create_index([("subject", ASCENDING), ("title", ASCENDING)], unique=True)
    db.questions.create_index([("subject", ASCENDING), ("topic", ASCENDING)])
    db.questions.create_index([("statement", ASCENDING)], unique=True)
    db.question_attempts.create_index([("user_id", ASCENDING), ("question_id", ASCENDING)])
    db.essays.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    _db = db
    return _db


def to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID inválido.")


def serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Converte ObjectId -> str e datetime -> ISO 8601, renomeando _id para id."""
    if doc is None:
        return None
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if key == "_id":
            out["id"] = str(value)
        elif key == "password_hash":
            continue
        elif isinstance(value, ObjectId):
            out[key] = str(value)
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, list):
            out[key] = [serialize(v) if isinstance(v, dict) else (str(v) if isinstance(v, ObjectId) else v) for v in value]
        elif isinstance(value, dict):
            out[key] = serialize(value)
        else:
            out[key] = value
    return out
