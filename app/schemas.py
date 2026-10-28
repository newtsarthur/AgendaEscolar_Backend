from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

GradeYear = Literal["1º ano", "2º ano", "3º ano", "Cursinho"]
Focus = Literal["ENEM", "Vestibular", "ENEM e Vestibular", "Concurso", "Reforço escolar"]
TaskType = Literal["Compromisso", "Trabalho", "Prova", "Revisão"]
TaskStatus = Literal["Pendente", "Em Andamento", "Concluída"]
Option = Literal["A", "B", "C", "D", "E"]


def _naive(value: datetime | None) -> datetime | None:
    """Datas são armazenadas como horário local de parede (sem fuso), como digitado pelo aluno."""
    if value is None:
        return None
    return value.replace(tzinfo=None, microsecond=0)


# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    grade_year: GradeYear = "3º ano"
    focus: Focus = "ENEM"


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    grade_year: GradeYear | None = None
    focus: Focus | None = None


# ---------- Tasks ----------
class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    subject: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=2000)
    due_date: datetime
    task_type: TaskType = "Revisão"
    status: TaskStatus = "Pendente"
    related_material_id: str | None = None

    @field_validator("due_date")
    @classmethod
    def normalize_date(cls, v: datetime) -> datetime:
        return _naive(v)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    subject: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=2000)
    due_date: datetime | None = None
    task_type: TaskType | None = None
    status: TaskStatus | None = None
    related_material_id: str | None = None

    @field_validator("due_date")
    @classmethod
    def normalize_date(cls, v: datetime | None) -> datetime | None:
        return _naive(v)


# ---------- Questions ----------
class AnswerIn(BaseModel):
    selected_option: Option


# ---------- Essays ----------
class EssayIn(BaseModel):
    theme: str = Field(min_length=3, max_length=300)
    text: str = Field(min_length=50, max_length=12000)
