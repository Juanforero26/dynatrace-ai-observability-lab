"""Grafo LangGraph del SRE Copilot: triage -> investigar -> reportar.

ESQUELETO de Fase 4. La estructura está; los nodos tienen la lógica mínima y
TODOs para conectar las tools reales del MCP. Se apoya en las tools que devuelve
mcp_client.get_dynatrace_tools().
"""
from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from . import config


class CopilotState(TypedDict):
    messages: Annotated[list, add_messages]


PROMPTS = {
    "triage": (
        "Sos el agente de TRIAGE de un SRE Copilot. Usá las herramientas de "
        "Dynatrace para listar los problems abiertos y elegir el más crítico. "
        "Devolvé la entidad afectada y por qué la priorizás."
    ),
    "investigate": (
        "Sos el agente INVESTIGADOR. Para la entidad priorizada, ejecutá DQL "
        "sobre logs y métricas para reunir evidencia de la causa. No inventes "
        "datos: si una query no devuelve nada, decilo."
    ),
    "report": (
        "Sos el agente REPORTER. Con la evidencia recolectada, escribí una "
        "hipótesis de causa raíz y una recomendación accionable, citando los "
        "datos que la respaldan."
    ),
}


def build_graph(dynatrace_tools):
    """Construye el grafo. `dynatrace_tools` viene del MCP (mcp_client)."""
    llm = ChatAnthropic(
        model=config.ANTHROPIC_MODEL,
        api_key=config.ANTHROPIC_API_KEY,
    ).bind_tools(dynatrace_tools)

    def _agent_node(system_prompt: str):
        def node(state: CopilotState):
            from langchain_core.messages import SystemMessage

            msgs = [SystemMessage(content=system_prompt)] + state["messages"]
            return {"messages": [llm.invoke(msgs)]}

        return node

    graph = StateGraph(CopilotState)
    graph.add_node("triage", _agent_node(PROMPTS["triage"]))
    graph.add_node("investigate", _agent_node(PROMPTS["investigate"]))
    graph.add_node("report", _agent_node(PROMPTS["report"]))
    graph.add_node("tools", ToolNode(dynatrace_tools))

    # Flujo lineal simplificado. TODO Fase 4: agregar aristas condicionales
    # (tools_condition) para que cada agente pueda llamar tools y volver.
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "investigate")
    graph.add_edge("investigate", "report")
    graph.add_edge("report", END)

    return graph.compile()
