from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..database import get_db, serialize, to_object_id
from ..schemas import TaskIn, TaskStatus, TaskUpdate
from ..security import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["Agenda"])


def _validate_material(material_id: str | None):
    if material_id and not get_db().materials.find_one({"_id": to_object_id(material_id)}, {"_id": 1}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Material relacionado não encontrado.")


def _get_owned(task_id: str, user: dict) -> dict:
    task = get_db().tasks.find_one({"_id": to_object_id(task_id), "user_id": user["_id"]})
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarefa não encontrada.")
    return task


@router.get("")
def list_tasks(
    start: datetime | None = Query(None, description="Início do intervalo (inclusivo), horário local"),
    end: datetime | None = Query(None, description="Fim do intervalo (exclusivo), horário local"),
    status_filter: TaskStatus | None = Query(None, alias="status"),
    subject: str | None = None,
    user: dict = Depends(get_current_user),
):
    query: dict = {"user_id": user["_id"]}
    date_range: dict = {}
    if start:
        date_range["$gte"] = start.replace(tzinfo=None)
    if end:
        date_range["$lt"] = end.replace(tzinfo=None)
    if date_range:
        query["due_date"] = date_range
    if status_filter:
        query["status"] = status_filter
    if subject:
        query["subject"] = subject
    tasks = get_db().tasks.find(query).sort("due_date", 1).limit(500)
    return [serialize(t) for t in tasks]


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)):
    db = get_db()
    counts = {s: 0 for s in ["Pendente", "Em Andamento", "Concluída"]}
    for row in db.tasks.aggregate([{"$match": {"user_id": user["_id"]}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        counts[row["_id"]] = row["n"]
    now = datetime.now()
    upcoming = db.tasks.find(
        {"user_id": user["_id"], "status": {"$ne": "Concluída"}, "due_date": {"$gte": now}}
    ).sort("due_date", 1).limit(5)
    overdue = db.tasks.count_documents({"user_id": user["_id"], "status": {"$ne": "Concluída"}, "due_date": {"$lt": now}})
    return {"counts": counts, "overdue": overdue, "upcoming": [serialize(t) for t in upcoming]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(data: TaskIn, user: dict = Depends(get_current_user)):
    _validate_material(data.related_material_id)
    doc = data.model_dump()
    doc["user_id"] = user["_id"]
    doc["created_at"] = datetime.now()
    result = get_db().tasks.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.get("/{task_id}")
def get_task(task_id: str, user: dict = Depends(get_current_user)):
    return serialize(_get_owned(task_id, user))


@router.put("/{task_id}")
def update_task(task_id: str, data: TaskUpdate, user: dict = Depends(get_current_user)):
    task = _get_owned(task_id, user)
    changes = data.model_dump(exclude_unset=True)
    if "related_material_id" in changes:
        _validate_material(changes["related_material_id"])
    if changes:
        changes["updated_at"] = datetime.now()
        get_db().tasks.update_one({"_id": task["_id"]}, {"$set": changes})
        task.update(changes)
    return serialize(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    task = _get_owned(task_id, user)
    get_db().tasks.delete_one({"_id": task["_id"]})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
