"""
SRE Copilot — versión mínima "al grano" (Fase 4, iteración 1).

Un agente (LangGraph ReAct) que:
  - usa tu MCP de Dynatrace como herramientas (DQL, problems, logs)
  - queda instrumentado con OpenInference -> se observa en Arize Phoenix

Usa el Dynatrace Remote MCP Server (hosted, no deprecado) por HTTP — sin npx/Node.

Requisitos previos:
  1) Phoenix corriendo:            phoenix serve      (en otra pestaña de terminal)
  2) .env completo (DT_ENVIRONMENT, DT_PLATFORM_TOKEN, ANTHROPIC_API_KEY)
  3) Python 3.12 (el stack de agentes aún no soporta 3.14)

Correr:   python sre_copilot_min.py
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()  # lee el .env de la carpeta actual

# --- 1) Telemetría hacia Phoenix (OpenInference) -----------------------------
from phoenix.otel import register

# Los spans van directo a Phoenix en esta iteración. Más adelante los
# apuntaremos al colector (BindPlane) cambiando solo el endpoint.
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")

tracer_provider = register(
    project_name="sre-copilot",
    auto_instrument=False,  # instrumentamos LangChain explícitamente abajo
)

from openinference.instrumentation.langchain import LangChainInstrumentor

LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

# --- 2) LLM + herramientas del MCP -------------------------------------------
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

SYSTEM_PROMPT = (
    "Eres un SRE / Observability Copilot para Dynatrace. Tienes herramientas "
    "del MCP de Dynatrace. Flujo: (1) triage — lista los problems abiertos y "
    "elige el más crítico; (2) investiga — usa DQL sobre logs/métricas de la "
    "entidad afectada; (3) reporta — da una hipótesis de causa raíz y una "
    "recomendación, citando los datos. Si una consulta no devuelve nada, dilo; "
    "no inventes datos."
)

TASK = (
    "Revisa el estado del entorno, investiga el problem más crítico (o, si no "
    "hay problems, resume la salud general con un par de queries DQL simples) y "
    "entrega una hipótesis de causa raíz con recomendación."
)


def build_mcp_client() -> MultiServerMCPClient:
    # Dynatrace Remote MCP Server (hosted). Sin npx/Node.
    base = os.environ["DT_ENVIRONMENT"].rstrip("/")
    mcp_url = f"{base}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
    return MultiServerMCPClient(
        {
            "dynatrace": {
                "url": mcp_url,
                "transport": "streamable_http",
                "headers": {
                    "Authorization": f"Bearer {os.environ['DT_PLATFORM_TOKEN']}",
                },
            }
        }
    )


async def main() -> None:
    client = build_mcp_client()
    tools = await client.get_tools()
    print(f"[mcp] {len(tools)} herramientas cargadas desde Dynatrace")

    llm = ChatAnthropic(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=4096,
    )

    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": TASK}]}
    )

    print("\n=== Informe del SRE Copilot ===\n")
    print(result["messages"][-1].content)
    print(
        "\nAbre Phoenix en http://localhost:6006 -> proyecto 'sre-copilot' "
        "para ver los spans, tokens y tool-calls."
    )

    # Asegura que los spans se envíen antes de salir.
    tracer_provider.force_flush()


if __name__ == "__main__":
    asyncio.run(main())