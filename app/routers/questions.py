from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..database import get_db, serialize, to_object_id
from ..schemas import AnswerIn
from ..security import get_current_user
from ..services.seeder import ensure_seeded

router = APIRouter(prefix="/api/questions", tags=["Banco de Questões"])

PUBLIC_FIELDS = {"correct_option": 0, "explanation": 0}


@router.get("/meta")
def meta(_: dict = Depends(get_current_user)):
    db = get_db()
    ensure_seeded(db)
    rows = db.questions.aggregate(
        [{"$group": {"_id": {"subject": "$subject", "topic": "$topic"}, "n": {"$sum": 1}}}, {"$sort": {"_id.subject": 1, "_id.topic": 1}}]
    )
    subjects: dict[str, dict] = {}
    for row in rows:
        s, t = row["_id"]["subject"], row["_id"]["topic"]
        entry = subjects.setdefault(s, {"name": s, "count": 0, "topics": []})
        entry["count"] += row["n"]
        entry["topics"].append(t)
    return {"subjects": list(subjects.values()), "difficulties": ["Fácil", "Média", "Difícil"]}


@router.get("")
def list_questions(
    subject: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
    only_unanswered: bool = False,
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    ensure_seeded(db)
    query: dict = {}
    if subject:
        query["subject"] = subject
    if topic:
        query["topic"] = topic
    if difficulty:
        query["difficulty"] = difficulty

    # Última tentativa do aluno em cada questão
    last_attempts: dict = {}
    for a in db.question_attempts.find({"user_id": user["_id"]}).sort("created_at", 1):
        last_attempts[a["question_id"]] = a
    if only_unanswered and last_attempts:
        query["_id"] = {"$nin": list(last_attempts.keys())}

    result = []
    for q in db.questions.find(query, PUBLIC_FIELDS).sort([("subject", 1), ("topic", 1)]).limit(limit):
        item = serialize(q)
        attempt = last_attempts.get(q["_id"])
        item["last_attempt"] = (
            {"selected_option": attempt["selected_option"], "is_correct": attempt["is_correct"]} if attempt else None
        )
        result.append(item)
    return result


@router.get("/stats")
def stats(user: dict = Depends(get_current_user)):
    db = get_db()
    pipeline = [
        {"$match": {"user_id": user["_id"]}},
        {"$group": {"_id": "$subject", "total": {"$sum": 1}, "correct": {"$sum": {"$cond": ["$is_correct", 1, 0]}}}},
        {"$sort": {"_id": 1}},
    ]
    by_subject = []
    total = correct = 0
    for row in db.question_attempts.aggregate(pipeline):
        total += row["total"]
        correct += row["correct"]
        by_subject.append(
            {"subject": row["_id"], "total": row["total"], "correct": row["correct"],
             "accuracy": round(row["correct"] * 100 / row["total"], 1) if row["total"] else 0}
        )
    recent = []
    for a in db.question_attempts.find({"user_id": user["_id"]}).sort("created_at", -1).limit(10):
        recent.append(serialize(a))
    return {
        "total": total,
        "correct": correct,
        "wrong": total - correct,
        "accuracy": round(correct * 100 / total, 1) if total else 0,
        "by_subject": by_subject,
        "recent": recent,
    }


@router.post("/{question_id}/answer")
def answer(question_id: str, data: AnswerIn, user: dict = Depends(get_current_user)):
    db = get_db()
    question = db.questions.find_one({"_id": to_object_id(question_id)})
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questão não encontrada.")
    is_correct = data.selected_option == question["correct_option"]
    db.question_attempts.insert_one(
        {
            "user_id": user["_id"],
            "question_id": question["_id"],
            "subject": question["subject"],
            "topic": question["topic"],
            "selected_option": data.selected_option,
            "is_correct": is_correct,
            "created_at": datetime.now(),
        }
    )
    return {
        "is_correct": is_correct,
        "selected_option": data.selected_option,
        "correct_option": question["correct_option"],
        "explanation": question["explanation"],
    }
