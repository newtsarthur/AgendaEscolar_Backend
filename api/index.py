"""Entrypoint da Vercel (runtime Python). A Vercel procura a variável `app` (ASGI)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.main import app  # noqa: E402,F401
