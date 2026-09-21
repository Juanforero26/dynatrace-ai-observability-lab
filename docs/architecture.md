# Arquitectura del laboratorio

## La historia en una frase

Bindplane **controla** la telemetría que entra, Dynatrace **observa** app/infra,
y Arize **evalúa** el cerebro de IA. Este lab reproduce esa cadena de punta a
punta, que es exactamente la tesis de las dos adquisiciones de Dynatrace
(Bindplane, abr-2026; Arize, ~sep-2026, US$915M).

## Diagrama

```
   Sistema multiagente (Python + LangGraph + Claude)
    ├── usa como herramientas → MCP de Dynatrace   (DQL, problems, logs)
    └── instrumentado con OpenInference → emite spans OTLP (LLM + tool calls)
                     │
                     ▼
      Colector OTel gestionado por BINDPLANE OP   (pipeline con fan-out)
           │                                   │
           ▼ (señales de IA)                   ▼ (traces / logs / métricas)
      ARIZE PHOENIX                       DYNATRACE (trial)
      evals, alucinación,                 traces del propio agente,
      calidad, tokens, drift              Grail, problems
           ▲                                   │
           └──── los agentes CONSULTAN ────────┘
                 Dynatrace vía el MCP
```

El detalle que lo hace redondo: Dynatrace termina **observando al agente que
consulta a Dynatrace**, y Phoenix **evalúa la calidad** de ese mismo agente. Un
solo stream de OTel, y BindPlane es quien lo abre en abanico hacia ambos lados.

## Caso de uso: "SRE / Observability Copilot"

Tres roles orquestados en LangGraph:

1. **Triage** — consulta vía MCP los `problems` abiertos.
2. **Investigador** — ejecuta DQL sobre Grail para traer logs/métricas de la
   entidad afectada.
3. **Reporter** — redacta hipótesis de causa raíz + recomendación.

Es autorreferencial, genera tráfico rico de tokens/tool-calls (buen material
para los evals de Phoenix) y es justo el tipo de agente que un cliente querría
construir. La lógica de investigación y los prompts se inspiran en el repo
`managed-agent-demo` (solo como referencia).

## Componentes y puertos

| Componente | Imagen | Puerto | Rol |
|------------|--------|--------|-----|
| Arize Phoenix | `arizephoenix/phoenix` | 6006 (UI+OTLP HTTP), 4317 (gRPC) | AI observability / evals |
| OTel Collector | `otel/opentelemetry-collector-contrib` | 4318 (HTTP), 14317 (gRPC) | ingesta + fan-out |
| BindPlane OP | `ghcr.io/observiq/bindplane-ee` | 3001 (UI) | control plane de telemetría |
| PostgreSQL | `postgres:16` | interno | store de BindPlane |
| Dynatrace | SaaS (trial) | — | full-stack + Grail + MCP |

## Fases

| Fase | Qué se hace | Estado |
|------|-------------|--------|
| 0 | Prerrequisitos (Docker, trial, keys) | `docs/00-prerequisites.md` |
| 1 | Dynatrace: tokens + MCP | `docs/01-dynatrace-mcp.md` |
| 2 | BindPlane OP (control plane) | pendiente |
| 3 | Phoenix + colector (pipeline base) | compose listo |
| 4 | Sistema multiagente (LangGraph) | esqueleto en `agents/` |
| 5 | Bucle completo + evals | pendiente |
| 6 | Narrativa / demo | pendiente |
| 7 (opcional) | Auto-remediación (PRs) | fuera de alcance por ahora |

## Decisiones de diseño

- **Python + LangGraph** (no Node/Managed Agent) porque el objetivo es
  *instrumentar* la IA con OpenInference, y eso exige controlar el loop del
  agente localmente. OpenInference es Python-first.
- **Los agentes exportan al colector, no directo a Phoenix.** Así BindPlane
  gobierna de verdad el pipeline (ese es el punto de la pieza).
- **Todo self-hosted** para costo ~0; el único gasto variable son las llamadas
  a Claude.
