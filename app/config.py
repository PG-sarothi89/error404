"""Application configuration and environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# Provider keys
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Provider selection: "gemini", "openai", "groq", or "fallback"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "").lower()
if not LLM_PROVIDER:
    if GEMINI_API_KEY:
        LLM_PROVIDER = "gemini"
    elif GROQ_API_KEY:
        LLM_PROVIDER = "groq"
    elif OPENAI_API_KEY:
        LLM_PROVIDER = "openai"
    else:
        LLM_PROVIDER = "fallback"

# Timeouts in seconds
LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "12.0"))
SOLVER_TIMEOUT_SECONDS: float = float(os.getenv("SOLVER_TIMEOUT_SECONDS", "5.0"))
TOTAL_TIMEOUT_SECONDS: float = float(os.getenv("TOTAL_TIMEOUT_SECONDS", "28.0"))

# Logging & Environment
ENV: str = os.getenv("ENV", "production")
DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
