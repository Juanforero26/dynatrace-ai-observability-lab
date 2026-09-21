"""Configuración centralizada — lee del .env de la raíz del repo."""
import os
from pathlib import Path

from dotenv import load_dotenv

# El .env vive en la raíz del repo (un nivel arriba de agents/).
_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_ROOT / ".env")


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val or val.startswith("<") or "XXXX" in val:
        raise RuntimeError(f"Falta configurar {name} en .env")
    return val


# Dynatrace / MCP
DT_ENVIRONMENT = os.getenv("DT_ENVIRONMENT", "")
DT_PLATFORM_TOKEN = os.getenv("DT_PLATFORM_TOKEN", "")
DT_GRAIL_QUERY_BUDGET_GB = os.getenv("DT_GRAIL_QUERY_BUDGET_GB", "1")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

# Telemetría — los agentes exportan al colector (gestionado por BindPlane)
OTEL_COLLECTOR_HTTP = os.getenv("OTEL_COLLECTOR_HTTP", "http://localhost:4318")

SERVICE_NAME = "sre-copilot"
