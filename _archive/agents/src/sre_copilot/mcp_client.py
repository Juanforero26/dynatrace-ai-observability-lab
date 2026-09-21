"""Conexión al MCP de Dynatrace como conjunto de herramientas del agente.

⚠️ El paquete `@dynatrace-oss/dynatrace-mcp-server` quedó DEPRECADO.
Reemplazá `args` por el server MCP vigente que indique el Dynatrace Hub de tu
tenant (Dynatrace for AI / Remote MCP Server). Ver docs/01-dynatrace-mcp.md.
"""
from langchain_mcp_adapters.client import MultiServerMCPClient

from . import config


async def get_dynatrace_tools():
    """Devuelve las tools del MCP de Dynatrace listas para el agente LangGraph."""
    client = MultiServerMCPClient(
        {
            "dynatrace": {
                "command": "npx",
                "args": ["-y", "@dynatrace-oss/dynatrace-mcp-server"],  # TODO: server vigente
                "transport": "stdio",
                "env": {
                    "DT_ENVIRONMENT": config.DT_ENVIRONMENT,
                    "DT_PLATFORM_TOKEN": config.DT_PLATFORM_TOKEN,
                    "DT_GRAIL_QUERY_BUDGET_GB": config.DT_GRAIL_QUERY_BUDGET_GB,
                },
            }
        }
    )
    return await client.get_tools()
