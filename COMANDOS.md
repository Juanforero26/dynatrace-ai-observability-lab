# Comandos del laboratorio (copiá y pegá)

Parado en la carpeta del repo:

```bash
cd ~/Documents/Dynatrace-MVP
```

## Estado del checkpoint (18-sep-2026)

✅ **POC de las 3 integradas funcionando:** Agente → BindPlane → Phoenix, con el
agente consultando Dynatrace vía DQL. Validado con el atributo `routed.by=bindplane`.

---

## Cómo levantar todo (3 terminales)

### 1) Phoenix (venv aislado — dejar corriendo)

```bash
python3.12 -m venv ~/phoenix-venv          # solo la 1a vez
~/phoenix-venv/bin/pip install -U pip arize-phoenix
~/phoenix-venv/bin/python -m phoenix.server.main serve
```
UI: http://localhost:6006

### 2) Colector de BindPlane (local)

- Consola: **https://app.bindplane.com** (plan Free).
- El colector BDOT 1.x se instaló con el comando que da la consola (**Agents → Install**).
- Debe estar **Connected** y con la config **rolled out** (Source OTLP 4318/4319 → processor `routed.by` → destino `phoenix-local` a localhost:6006).
- Verificar que escucha:
  ```bash
  lsof -i :4318
  ```

### 3) Agente (venv del repo)

```bash
cd ~/Documents/Dynatrace-MVP
python3.12 -m venv .venv                    # si no existe
source .venv/bin/activate
pip install -U pip
pip install -r agents/requirements-direct.txt
python agents/sre_copilot_direct.py
```
El print de arranque debe decir `...http://localhost:4318/v1/traces` (va por BindPlane).

---

## Validar el path (agente → BindPlane → Phoenix)

En Phoenix, abre un trace nuevo → pestaña **Attributes** → debe aparecer:

```
routed.by = bindplane
```

Ese atributo lo inyecta BindPlane con el processor "Add Fields"; el agente nunca
lo envía. Si está → la telemetría pasó por BindPlane. ✅

(Prueba alterna: detén el colector y re-corre; en Phoenix dejan de llegar traces.)

---

## Prueba directa del token de Dynatrace

```bash
export $(grep -E '^(DT_ENVIRONMENT|DT_PLATFORM_TOKEN)=' .env | xargs)
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST "$DT_ENVIRONMENT/platform/storage/query/v1/query:execute" \
  -H "Authorization: Bearer $DT_PLATFORM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"data record(hello=\"world\")"}'
# 200/202 = OK
```

---

## Notas / gotchas aprendidos

- Usar **Python 3.12** (3.14 rompe el stack de agentes).
- Phoenix corre en **venv aparte** del agente (sus dependencias chocan: `mcp<2` vs `mcp>=2`).
- Endpoint del agente = **4318** (el colector), NO 6006 (eso es Phoenix directo, se salta BindPlane).
- gRPC del Source de BindPlane movido a **4319** para no chocar con el 4317 de Phoenix.

### Ingesta OTLP a Dynatrace Gen3 (aprendido con el data-generator)
- Auth = **platform token (`dt0s16`) con header `Bearer`**. Los tokens clásicos `dt0c01` están **deprecados** en Gen3.
- El token **hereda permisos del usuario**: además del scope, el usuario necesita una **policy IAM de OpenPipeline** (`ALLOW openpipeline:traces:ingest;` + metrics + logs). Sin ella → `403 Forbidden`.
- Métricas OTLP exigen **temporalidad DELTA** (`OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`); cumulative → `400 Bad Request`.
- Endpoint: `{DT_ENVIRONMENT}/api/v2/otlp/v1/{traces,metrics,logs}`, `http/protobuf` (no gRPC, no JSON).
