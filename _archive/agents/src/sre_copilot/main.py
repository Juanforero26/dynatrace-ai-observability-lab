"""Punto de entrada del SRE Copilot (Fase 4).

Ejecuta:  python -m sre_copilot.main
Requisitos: el colector + Phoenix arriba (make up) y el .env completo.
"""
import asyncio

from langchain_core.messages import HumanMessage

from .graph import build_graph
from .mcp_client import get_dynatrace_tools
from .telemetry import setup_telemetry


async def run() -> None:
    setup_telemetry()  # instrumentación ANTES de crear los agentes

    tools = await get_dynatrace_tools()
    app = build_graph(tools)

    kickoff = HumanMessage(
        content="Revisá el estado del entorno, investigá el problem más crítico "
        "y entregá una hipótesis de causa raíz con recomendación."
    )
    result = await app.ainvoke({"messages": [kickoff]})

    print("\n=== Informe del SRE Copilot ===\n")
    print(result["messages"][-1].content)
    print(
        "\nAbrí Phoenix en http://localhost:6006 para ver los spans y evals, "
        "y tu tenant de Dynatrace para ver los traces del agente."
    )


if __name__ == "__main__":
    asyncio.run(run())
