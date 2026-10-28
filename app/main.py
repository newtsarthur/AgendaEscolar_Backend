import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .config import settings
from .database import get_db
from .routers import auth, essays, materials, questions, seed, tasks

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Agenda Escolar Inteligente API",
    version="1.0.0",
    description="API do MVP: autenticação, agenda, biblioteca, banco de questões e correção de redação com IA.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_ORIGINS + settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app" if settings.ALLOW_VERCEL_PREVIEWS else None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PyMongoError)
async def mongo_error_handler(_: Request, exc: PyMongoError):
    logging.getLogger("agenda").exception("Erro no MongoDB: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Não foi possível acessar o banco de dados. Verifique a MONGODB_URI e o Network Access do Atlas."},
    )


@app.get("/", include_in_schema=False)
@app.get("/api", include_in_schema=False)
def root():
    return {"name": "Agenda Escolar Inteligente API", "docs": "/api/docs", "health": "/api/health"}


@app.get("/api/health", tags=["Sistema"])
def health():
    db_ok = False
    try:
        get_db().command("ping")
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok", "database": "connected" if db_ok else "unavailable"}


app.include_router(auth.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(materials.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(essays.router, prefix="/api")
app.include_router(seed.router, prefix="/api")