import os

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "sim"}


class Settings:
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "agenda_escolar")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-troque-em-producao")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

    CORS_ORIGINS: list[str] = [
        o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
    ]
    ALLOW_VERCEL_PREVIEWS: bool = _bool(os.getenv("ALLOW_VERCEL_PREVIEWS"), True)

    SEED_KEY: str = os.getenv("SEED_KEY", "")

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    HF_MODEL: str = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

    POLLINATIONS_ENABLED: bool = _bool(os.getenv("POLLINATIONS_ENABLED"), True)
    POLLINATIONS_URL: str = os.getenv("POLLINATIONS_URL", "https://text.pollinations.ai/openai")
    POLLINATIONS_MODEL: str = os.getenv("POLLINATIONS_MODEL", "openai")


settings = Settings()
