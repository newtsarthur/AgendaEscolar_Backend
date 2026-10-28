from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from ..database import get_db, serialize
from ..schemas import LoginIn, ProfileUpdate, RegisterIn
from ..security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])


def _auth_response(user: dict) -> dict:
    return {"access_token": create_access_token(str(user["_id"])), "token_type": "bearer", "user": serialize(user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn):
    db = get_db()
    user = {
        "name": data.name.strip(),
        "email": data.email.lower(),
        "password_hash": hash_password(data.password),
        "grade_year": data.grade_year,
        "focus": data.focus,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    try:
        result = db.users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este e-mail já está cadastrado.")
    user["_id"] = result.inserted_id
    return _auth_response(user)


@router.post("/login")
def login(data: LoginIn):
    user = get_db().users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos.")
    return _auth_response(user)


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return serialize(user)


@router.put("/me")
def update_me(data: ProfileUpdate, user: dict = Depends(get_current_user)):
    changes = data.model_dump(exclude_none=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if changes:
        get_db().users.update_one({"_id": user["_id"]}, {"$set": changes})
        user.update(changes)
    return serialize(user)
