# Fase 1 — Dynatrace: tokens + MCP

Objetivo: que un agente pueda **consultar** tu tenant (problems, logs, DQL) a
través del MCP, y que el colector pueda **ingerir** OTLP hacia Dynatrace.
Son dos credenciales distintas con propósitos distintos.

```
  Agente  ──(lee)──►  MCP  ──►  Dynatrace     ← usa DT_PLATFORM_TOKEN
  Agente  ──(emite OTLP)──►  Colector  ──►  Dynatrace   ← usa DT_API_TOKEN (ingesta)
```

---

## 1.1 Platform token (para el MCP — lectura)

1. Andá a **https://myaccount.dynatrace.com/platformTokens** ("My platform tokens").
2. **Create platform token** → nombre (ej. `mcp-lab-sre-copilot`), expiración,
   account y el **environment** (tu sprint).
3. Marcá los scopes:
   - **Crítico:** `app-engine:apps:run` (sin este casi nada funciona)
   - **Lectura de datos (Grail/DQL):** `storage:buckets:read`, `storage:logs:read`,
     `storage:metrics:read`, `storage:spans:read`, `storage:entities:read`,
     `storage:events:read`, `storage:bizevents:read`, `storage:system:read`
   - **Davis / IA:** `davis-copilot:conversations:execute`,
     `davis-copilot:nl2dql:execute`, `davis-copilot:dql2nl:execute`,
     `davis:analyzers:read`, `davis:analyzers:execute`
   - **Opcionales (fases posteriores):** `app-settings:objects:read`,
     `storage:events:write`, `email:emails:send`, `document:documents:read`,
     `document:documents:write`
4. Generá → **el valor se muestra una sola vez**. Copialo a `.env` en
   `DT_PLATFORM_TOKEN`.

> Alternativa: el MCP también soporta **OAuth por navegador** (solo
> `DT_ENVIRONMENT`, sin token). El platform token es más estable para un lab.

> **Costo de Grail:** cada consulta DQL consume presupuesto. En `.env` ya está
> `DT_GRAIL_QUERY_BUDGET_GB=1` para acotarlo. Subilo solo si lo necesitás.

## 1.2 API token de ingesta (para OTLP — escritura)

1. En tu tenant: **Access Tokens → Generate new token**.
2. Prefijo `dt0c01.`. Scopes:
   - `openTelemetryTrace.ingest`
   - `logs.ingest`
   - `metrics.ingest`
3. Copialo a `.env` en `DT_API_TOKEN`.
4. Confirmá el endpoint OTLP de tu tenant y ponelo en `DT_OTLP_ENDPOINT`:
   `https://<env-id>.live.dynatrace.com/api/v2/otlp`
   (algunos tenants Gen3 usan un host distinto; verificá en la doc de tu tenant
   en *Settings → OpenTelemetry* si la ingesta no aparece en Fase 3).

## 1.3 Levantar el MCP de Dynatrace

> ⚠️ **Importante:** el repo original `dynatrace-oss/dynatrace-mcp` quedó
> **deprecado** (último release 2.1.2). Usá el **Dynatrace MCP Server actual**
> (a través del Dynatrace Hub / "Dynatrace for AI" o el Remote MCP Server).
> El comando de abajo sirve como referencia; reemplazá el paquete por el vigente
> que indique el Hub de tu tenant.

Prueba rápida por línea de comandos (modo stdio):

```bash
export DT_ENVIRONMENT="https://<env-id>.apps.dynatrace.com"
export DT_PLATFORM_TOKEN="dt0s16...."
export DT_GRAIL_QUERY_BUDGET_GB=1

npx -y @dynatrace-oss/dynatrace-mcp-server   # ← reemplazar por el server vigente
```

Si arranca sin errores de autenticación, el MCP puede hablar con tu tenant.
En **Fase 4** el agente Python se conecta a este mismo comando como herramienta.

### Validar que hay datos para investigar

Para que el SRE Copilot tenga algo que investigar, tu tenant necesita al menos
un *problem* o algo de telemetría. Dos opciones:
- Dejá el trial unos minutos monitoreando algo (aunque sea el propio host).
- O más simple: en Fase 3/4 los propios agentes generan traces que aparecen en
  Dynatrace, y podemos disparar un problem de prueba desde ahí.

## Checklist de salida de la Fase 1

- [ ] `DT_PLATFORM_TOKEN` en `.env` (prefijo `dt0s16.`)
- [ ] `DT_API_TOKEN` en `.env` (prefijo `dt0c01.`, scopes de ingesta)
- [ ] `DT_OTLP_ENDPOINT` confirmado
- [ ] El MCP arranca por `npx` sin error de auth
- [ ] `DT_GRAIL_QUERY_BUDGET_GB` acotado

Siguiente: **Fase 2** — levantar BindPlane OP (te la escribo cuando llegues aquí,
para no saturarte de una vez). Arquitectura completa en
[`architecture.md`](architecture.md).
