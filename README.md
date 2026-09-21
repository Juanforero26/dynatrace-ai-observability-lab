# Dynatrace AI Observability Lab — BindPlane + Arize

Laboratorio personal que integra las dos adquisiciones de Dynatrace
—**BindPlane** (pipelines de telemetría) y **Arize** (AI observability)— en un
escenario real: un **agente** que consulta Dynatrace vía MCP/DQL, cuya telemetría
**la gobierna BindPlane**, y que es **observado por Arize/Phoenix**.

## Estado — ✅ POC de las 3 integradas FUNCIONANDO (18-sep-2026)

```
Agente SRE Copilot  →  BindPlane (enruta + tagea)  →  Arize / Phoenix
        │
        └─ consulta Dynatrace vía MCP / DQL (execute_dql)
```

- **Fase 1 ✅** — Dynatrace (ambiente sprint) + platform token + MCP validado (VS Code + curl).
- **Fase 4 ✅** — agente `agents/sre_copilot_direct.py` observado por Phoenix.
- **Fase 2/3 ✅** — BindPlane Free (consola cloud) + colector local (BDOT 1.x) enrutando la telemetría del agente hacia Phoenix.

**Prueba del path:** un processor "Add Fields" en BindPlane inyecta el atributo
`routed.by = bindplane`. Ese atributo aparece en el trace en Phoenix → prueba
irrefutable de que la telemetría pasó por BindPlane (el agente nunca lo envía).

## Arquitectura efectiva

| Pieza | Cómo quedó |
|-------|-----------|
| **Dynatrace** | Ambiente sprint (dynatracelabs). El agente lo consulta con DQL directo (`execute_dql`, httpx). MCP validado aparte en VS Code. |
| **Agente** | Python 3.12, LangGraph + Claude, instrumentado con OpenInference. Exporta OTLP a `localhost:4318`. |
| **BindPlane** | Plan Free (consola cloud) + colector local BDOT 1.x. Pipeline Traces: Source OTLP (HTTP 4318 / gRPC 4319) → processor `routed.by` → destino `phoenix-local`. |
| **Arize** | Phoenix self-hosted en venv aislado (`python -m phoenix.server.main serve`), UI en :6006. |

## Puertos (para no chocar)

- Phoenix: **6006** (UI + OTLP HTTP), **4317** (gRPC).
- Colector BindPlane (Source OTLP): **4318** (HTTP, aquí exporta el agente), **4319** (gRPC, movido para no chocar con el 4317 de Phoenix).

## Estructura

```
.
├── README.md                     ← estás acá
├── COMANDOS.md                   ← cómo levantar todo, paso a paso
├── docs/                         ← runbooks (00 prereqs, 01 Dynatrace/MCP, architecture)
├── agents/
│   ├── sre_copilot_direct.py     ← agente activo (DQL directo + Phoenix)
│   └── requirements-direct.txt
├── data-generator/               ← app OTel que emite data real a Dynatrace
│   ├── generate_telemetry.py
│   └── requirements.txt
├── .env / .env.example / .gitignore
└── _archive/                     ← intentos previos (referencia; no se usan)
```

## Siguientes pasos

1. **App generadora de datos** → ✅ **funcionando**: emite traces/logs/métricas reales a Dynatrace (webshop con fallas en payment). Ver `data-generator/`.
2. **Evals en Phoenix** (groundedness/alucinación) → "así se ve la calidad de la IA" para clientes. ← en curso.
3. **Destino Dynatrace en BindPlane** → fan-out real (que la data del generador pase por BindPlane, no directa).
