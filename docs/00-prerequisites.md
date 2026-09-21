# Fase 0 — Prerrequisitos

Objetivo: dejar lista la base para poder ejecutar el resto del laboratorio.
Nada de esto cuesta dinero salvo, más adelante, unas pocas llamadas al LLM.

## 0.1 Herramientas locales

| Herramienta | Versión mínima | Verificar con |
|-------------|----------------|----------------|
| Docker + Docker Compose | Docker 24+, Compose v2 | `docker --version && docker compose version` |
| Python | 3.11+ | `python --version` |
| Node.js | 18+ (para correr el MCP con `npx`) | `node --version` |
| Git | cualquiera reciente | `git --version` |

> Recursos: el stack completo (Phoenix + colector + BindPlane + Postgres) pide
> ~4–6 GB de RAM libre. Si tu máquina va justa, en Fase 2 podés levantar
> BindPlane, mirar y luego bajarlo (`make down`) mientras trabajás las demás fases.

## 0.2 Tenant trial de Dynatrace

1. Andá a **https://www.dynatrace.com/trial/** y creá una cuenta de prueba.
   Vas a obtener un tenant de plataforma (Gen3, con Grail) del tipo
   `https://<env-id>.apps.dynatrace.com`.
2. Anotá el `<env-id>` — lo vas a usar en `DT_ENVIRONMENT` y en el endpoint OTLP.
3. Este tenant es **solo para el lab**. No conectes datos de trabajo. -- check

## 0.3 API key de Anthropic

1. En **https://console.anthropic.com/** creá una API key.
2. Guardala; irá en `ANTHROPIC_API_KEY` dentro de `.env`.
3. Costo esperado del lab: bajísimo. El SRE Copilot hace pocas llamadas por
   corrida; con un modelo pequeño/medio el gasto es de centavos. -- 
   
   ***REDACTED***

## 0.4 Preparar el repo

```bash
cd dynatrace-ai-observability-lab
make env          # crea .env desde .env.example
```

Abrí `.env` y, por ahora, completá al menos:
- `DT_ENVIRONMENT`
- `ANTHROPIC_API_KEY`

El resto de tokens los generamos en la **Fase 1**.

## Checklist de salida de la Fase 0

- [x] `docker compose version` funciona
- [x] `python --version` ≥ 3.11 y `node --version` ≥ 18
- [x] Tenant trial de Dynatrace creado; `<env-id>` anotado
- [x] API key de Anthropic creada
- [x] `.env` creado con `DT_ENVIRONMENT` y `ANTHROPIC_API_KEY`

Siguiente: [`01-dynatrace-mcp.md`](01-dynatrace-mcp.md)
