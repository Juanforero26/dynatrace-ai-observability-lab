# evals/ — evaluación de calidad del agente (Arize/Phoenix)

Corre un **juez LLM (Claude)** sobre los traces del SRE Copilot y evalúa
**groundedness**: ¿el informe de causa raíz está sustentado en los datos que el
agente recuperó por DQL, o alucina? El resultado se escribe en Phoenix como
evaluación sobre cada trace.

Es el "así se ve la calidad de la IA" de Arize — lo que le mostrarías a un cliente.

## Correr

Usa el **venv de Phoenix** (tiene `arize-phoenix`):

```bash
~/phoenix-venv/bin/pip install anthropic python-dotenv
~/phoenix-venv/bin/python evals/run_evals.py
```

Requisitos:
- Phoenix corriendo (localhost:6006).
- El agente ya ejecutado al menos una vez **con data real en Dynatrace** (para que
  el `execute_dql` traiga contexto y el eval tenga sustancia).
- `ANTHROPIC_API_KEY` en el `.env` de la raíz.

## Ver el resultado

En Phoenix (localhost:6006) → proyecto **`sre-copilot`** → verás la columna
**`Groundedness`** (grounded / hallucinated) con la explicación del juez en cada
trace.

## Nota

La API de `phoenix.evals` cambia entre versiones; si algún import o nombre de
columna no coincide, el script imprime las columnas disponibles para ajustarlo
rápido.
