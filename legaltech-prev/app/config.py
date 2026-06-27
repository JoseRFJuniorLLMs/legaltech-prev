"""Configuração central do backend (lida de variáveis de ambiente / .env)."""
import os
from pathlib import Path


def _load_dotenv() -> None:
    """Carrega um .env simples (sem dependência externa) da raiz do projeto."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


class Settings:
    # HeraclitusDB — banco do projeto (regra: projeto novo usa HeraclitusDB)
    HERA_ADDR = os.environ.get("HERACLITUS_ADDR", "127.0.0.1:7474")
    HERA_STUBS_PATH = os.environ.get("HERA_STUBS_PATH", r"D:\DEV\scripts\hera_mem")
    APP_AGENT_ID = "legaltech-prev"
    GENERATED_BY = "legaltech_app"

    # URL pública do app (compõe o link enviado ao cliente)
    BASE_URL = os.environ.get("LEGALTECH_BASE_URL", "http://localhost:3000")

    # Destino final da petição gerada
    CAROLINA_EMAIL = os.environ.get("CAROLINA_EMAIL", "carolina0606.campos@gmail.com")

    # SMTP (opcional). Sem SMTP_HOST o Notifier roda em modo dev (loga em vez de enviar).
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASS = os.environ.get("SMTP_PASS")
    SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@legaltech-prev.local")

    # Motor LLM — Gemini (substitui o LM Studio). Dois modos:
    #   API key:  GEMINI_API_KEY
    #   Vertex AI (VM GCP, sem key): GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_USE_VERTEX = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes")
    GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
    GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")


settings = Settings()
