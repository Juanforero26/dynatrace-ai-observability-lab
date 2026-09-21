"""
SRE Copilot — Plan B "a prueba de balas" (Fase 4).

Sin librerías MCP (evita el conflicto mcp<2 vs mcp>=2). El agente llama al
API DQL/Grail de Dynatrace directamente con httpx — el mismo request que ya
validaste con curl (HTTP 202) — y queda observado en Arize Phoenix.

Requisitos:
  1) Phoenix corriendo en su venv aislado (ver instrucciones).
  2) .env con DT_ENVIRONMENT, DT_PLATFORM_TOKEN, ANTHROPIC_API_KEY.

Correr (desde la raíz del repo):  python agents/sre_copilot_direct.py
"""
import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

# --- 1) Telemetría -> Phoenix (OTel puro, sin el paquete servidor de phoenix) -
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from openinference.instrumentation.langchain import LangChainInstrumentor

# Endpoint OTLP de salida.
#   - Para enrutar por BindPlane: OTEL_COLLECTOR_HTTP=http://localhost:4318 (fuente del colector)
#   - Para ir directo a Phoenix:  OTEL_COLLECTOR_HTTP=http://localhost:6006
# Se aceptan también OTEL_EXPORT_ENDPOINT / PHOENIX_COLLECTOR_ENDPOINT como alias.
OTEL_ENDPOINT = (
    os.getenv("OTEL_COLLECTOR_HTTP")
    or os.getenv("OTEL_EXPORT_ENDPOINT")
    or os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
    or "http://localhost:6006"
).rstrip("/")
_provider = TracerProvider(resource=Resource.create({"service.name": "sre-copilot"}))
_provider.add_span_processor(
    SimpleSpanProcessor(OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces"))
)
print(f"[otel] exportando spans a {OTEL_ENDPOINT}/v1/traces")
trace.set_tracer_provider(_provider)
LangChainInstrumentor().instrument(tracer_provider=_provider)

# --- 2) Herramienta: DQL directo contra Grail --------------------------------
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

DT_ENV = os.environ["DT_ENVIRONMENT"].rstrip("/")
DT_TOKEN = os.environ["DT_PLATFORM_TOKEN"]
BUDGET = os.getenv("DT_GRAIL_QUERY_BUDGET_GB", "1")
HEADERS = {"Authorization": f"Bearer {DT_TOKEN}", "Content-Type": "application/json"}


def _trim(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= 6000 else s[:6000] + " …(recortado)"


@tool
def execute_dql(query: str) -> str:
    """Ejecuta una consulta DQL en Grail de Dynatrace y devuelve los registros.

    Ejemplos de query:
      - 'fetch logs | limit 5'
      - 'fetch dt.davis.problems | limit 20'
      - 'fetch events | filter event.kind == "DAVIS_PROBLEM" | limit 20'
    """
    try:
        with httpx.Client(timeout=40) as c:
            r = c.post(
                f"{DT_ENV}/platform/storage/query/v1/query:execute",
                headers=HEADERS,
                json={"query": query, "requestTimeoutMilliseconds": 30000},
            )
            r.raise_for_status()
            data = r.json()

            # Resultado inmediato
            if data.get("result") is not None:
                return _trim(data["result"])

            token = data.get("requestToken")
            if not token:
                return _trim(data)

            # Polling hasta que termine
            for _ in range(30):
                p = c.get(
                    f"{DT_ENV}/platform/storage/query/v1/query:poll",
                    headers=HEADERS,
                    params={"request-token": token},
                )
                p.raise_for_status()
                pd = p.json()
                state = pd.get("state")
                if state == "SUCCEEDED":
                    return _trim(pd.get("result", pd))
                if state in ("FAILED", "CANCELLED", "NOT_STARTED"):
                    return f"Query {state}: {_trim(pd)}"
                time.sleep(1)
            return "Timeout esperando el resultado de la query."
    except httpx.HTTPStatusError as e:
        return f"Error HTTP {e.response.status_code}: {e.response.text[:500]}"
    except Exception as e:  # noqa: BLE001
        return f"Error ejecutando DQL: {e}"


SYSTEM_PROMPT = (
    "Eres un SRE / Observability Copilot para Dynatrace. Tienes una herramienta "
    "execute_dql para consultar Grail con DQL. Flujo: (1) triage — busca "
    "problems abiertos (p.ej. 'fetch dt.davis.problems | limit 20'); (2) "
    "investiga — usa DQL sobre logs/eventos relevantes; (3) reporta — hipótesis "
    "de causa raíz y recomendación citando los datos. Si una query no devuelve "
    "nada, dilo; no inventes datos. Usa 'limit' bajo para cuidar el presupuesto."
)

TASK = (
    "Revisa el estado del entorno, investiga el problem más crítico (o, si no "
    "hay, resume la salud general con un par de queries simples) y entrega una "
    "hipótesis de causa raíz con recomendación."
)


def main() -> None:
    llm = ChatAnthropic(
        model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=4096,
    )
    agent = create_react_agent(llm, [execute_dql], prompt=SYSTEM_PROMPT)

    result = agent.invoke({"messages": [{"role": "user", "content": TASK}]})

    print("\n=== Informe del SRE Copilot ===\n")
    print(result["messages"][-1].content)
    print(
        "\nAbre Phoenix en http://localhost:6006 -> proyecto 'sre-copilot' "
        "para ver spans, tokens y las tool-calls."
    )
    _provider.force_flush()


if __name__ == "__main__":
    main()
