from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..database import get_db, serialize, to_object_id
from ..schemas import EssayIn
from ..security import get_current_user
from ..services.ai import active_providers, evaluate_essay

router = APIRouter(prefix="/api/essays", tags=["Redação"])


@router.get("/providers")
def providers(_: dict = Depends(get_current_user)):
    return {"providers": [name for name, _fn in active_providers()] + ["heuristica-local"]}


@router.post("/correct", status_code=status.HTTP_201_CREATED)
def correct_essay(data: EssayIn, user: dict = Depends(get_current_user)):
    text = data.text.strip()
    evaluation = evaluate_essay(data.theme.strip(), text)
    doc = {
        "user_id": user["_id"],
        "theme": data.theme.strip(),
        "transcribed_text": text,
        "total_score": evaluation["total_score"],
        "competencies": evaluation["competencies"],
        "strengths": evaluation["strengths"],
        "improvements": evaluation["improvements"],
        "summary": evaluation.get("summary", ""),
        "provider": evaluation.get("provider"),
        "created_at": datetime.now(),
    }
    result = get_db().essays.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.get("")
def list_essays(user: dict = Depends(get_current_user)):
    cursor = get_db().essays.find(
        {"user_id": user["_id"]}, {"transcribed_text": 0}
    ).sort("created_at", -1).limit(100)
    return [serialize(e) for e in cursor]


@router.get("/{essay_id}")
def get_essay(essay_id: str, user: dict = Depends(get_current_user)):
    essay = get_db().essays.find_one({"_id": to_object_id(essay_id), "user_id": user["_id"]})
    if not essay:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Redação não encontrada.")
    return serialize(essay)


@router.delete("/{essay_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_essay(essay_id: str, user: dict = Depends(get_current_user)):
    result = get_db().essays.delete_one({"_id": to_object_id(essay_id), "user_id": user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Redação não encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
