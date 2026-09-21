# agents/ — SRE Copilot

Agente (LangGraph + Claude) que consulta Dynatrace y queda observado en Arize
Phoenix.

## Archivo activo

- **`sre_copilot_direct.py`** — el agente. Llama al API DQL/Grail de Dynatrace
  directamente con `httpx` (sin librerías MCP, para evitar conflictos de
  versiones) y exporta su telemetría OpenInference a Phoenix.
- **`requirements-direct.txt`** — dependencias del agente.

> El MCP de Dynatrace ya quedó validado aparte (VS Code + curl). Para el agente
> usamos DQL directo, que es estable y llega al mismo dato.

## Cómo correr

Ver **`../COMANDOS.md`**. Resumen: Phoenix en un venv aislado + el agente en el
venv del repo.

## Nota

Los intentos anteriores (versión con `langchain-mcp-adapters` y el paquete
skeleton en `src/`) quedaron en **`../_archive/`** por si se necesitan de
referencia. No se usan.
