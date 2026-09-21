# data-generator/ — datos sintéticos para Dynatrace

Genera telemetría OTel (traces distribuidos + métricas + logs) de una tienda web
simulada y la envía a Dynatrace. Inyecta **errores y latencia en
`payment-service`** para que haya fallas/problems reales que el SRE Copilot
investigue.

## Requisitos

En el `.env` de la raíz:
- `DT_ENVIRONMENT` — tu ambiente sprint.
- `DT_INGEST_TOKEN` — **platform token** (`dt0s16`, header `Bearer`) con scopes de
  **OpenPipeline**: `openpipeline:traces:ingest`, `openpipeline:metrics:ingest`,
  `openpipeline:logs:ingest`. (En Gen3 los tokens clásicos `dt0c01` están deprecados.)
  Puede ser el mismo platform token del MCP si le agregas estos scopes, o uno aparte.

## Correr

```bash
cd ~/Documents/Dynatrace-MVP
source .venv/bin/activate
pip install -r data-generator/requirements.txt
python data-generator/generate_telemetry.py     # Ctrl+C para parar
```

Ajustes opcionales por `.env`: `GEN_RATE` (tx/seg, def. 3), `GEN_ERROR_RATE`
(def. 0.2), `DT_OTLP_ENDPOINT` (si el host difiere).

## Validar en Dynatrace (DQL)

Tras 1–3 min:

```dql
fetch spans | filter service.name == "payment-service" | limit 20
fetch spans | filter request.is_failed == true | summarize count(), by:{service.name}
fetch logs  | filter loglevel == "ERROR" | limit 20
```

Servicios que verás: `frontend`, `checkout-service`, `payment-service`,
`inventory-service`. Deja correr unos minutos para que Davis pueda levantar
problems por tasa de error / latencia.
