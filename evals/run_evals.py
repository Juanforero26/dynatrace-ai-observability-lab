"""
Evals de Phoenix — juez LLM (Claude) de "groundedness" para el SRE Copilot.

Para cada corrida del agente (trace) toma:
  - input     = la pregunta/tarea
  - reference = datos recuperados por execute_dql (contexto de Dynatrace)
  - output    = el informe de causa raíz del agente
y Claude juzga si está grounded o si alucina. El resultado se registra en Phoenix
como anotación del trace (visible en la UI).

Cliente: phoenix.client.Client (Phoenix 20.x). Juez: SDK de Anthropic directo.

Correr en el venv de Phoenix:
  ~/phoenix-venv/bin/pip install anthropic python-dotenv
  ~/phoenix-venv/bin/python evals/run_evals.py
"""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import pandas as pd
from phoenix.client import Client
from anthropic import Anthropic

PHOENIX_URL = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
MAX_TRACES = int(os.getenv("EVAL_MAX_TRACES", "15"))
PROJECT = os.getenv("PHOENIX_PROJECT", "default")  # los traces del agente caen en 'default'

anthropic = Anthropic()  # ANTHROPIC_API_KEY del entorno

PROMPT = """Eres un evaluador estricto. Un asistente SRE analizó un entorno Dynatrace y \
entregó una hipótesis de causa raíz. Juzga si esa respuesta está SUSTENTADA en los datos \
que recuperó (no inventada).

[Pregunta]
{q}

[Datos recuperados de Dynatrace]
{ctx}

[Respuesta del asistente]
{ans}

Si no hubo datos recuperados pero el asistente afirmó causas concretas, es "hallucinated".
Responde SOLO con JSON: {{"label": "grounded" | "hallucinated", "explanation": "<breve>"}}"""


def judge(q, ctx, ans):
    msg = anthropic.messages.create(
        model=MODEL, max_tokens=300,
        messages=[{"role": "user", "content": PROMPT.format(q=q, ctx=ctx, ans=ans)}],
    )
    text = "".join(getattr(b, "text", "") for b in msg.content)
    label, expl = "hallucinated", text.strip()[:600]
    try:
        j = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        label = str(j.get("label", "")).strip().lower()
        expl = str(j.get("explanation", expl))
    except Exception:  # noqa: BLE001
        low = text.lower()
        label = "grounded" if ("grounded" in low and "halluc" not in low) else "hallucinated"
    return ("grounded" if label == "grounded" else "hallucinated"), expl


def cell(row, name, default=""):
    try:
        v = row.get(name, default)
        return default if v is None or (isinstance(v, float) and pd.isna(v)) else v
    except Exception:  # noqa: BLE001
        return default


def main():
    client = Client(base_url=PHOENIX_URL)
    try:
        df = client.spans.get_spans_dataframe(project_identifier=PROJECT, limit=2000)
    except TypeError:
        df = client.spans.get_spans_dataframe(project_identifier=PROJECT)

    if df is None or len(df) == 0:
        print(f"[evals] No hay spans en el proyecto '{PROJECT}'. Corre el agente primero.")
        return

    # El span_id suele venir como índice; lo pasamos a columna.
    if df.index.name and df.index.name not in df.columns:
        df = df.reset_index()

    cols = list(df.columns)
    span_col = next((c for c in ("context.span_id", "span_id") if c in cols), None)
    trace_col = next((c for c in ("context.trace_id", "trace_id") if c in cols), None)
    if not span_col or not trace_col:
        print("[evals] No encuentro columnas de span/trace id. Columnas disponibles:")
        print(cols)
        return

    records = []
    for _, g in df.groupby(trace_col):
        roots = g[g["name"] == "LangGraph"]
        if roots.empty:
            continue
        root = roots.iloc[0]
        tools = g[g["name"] == "execute_dql"]
        ctx_parts = [str(x) for x in tools.get("attributes.output.value", pd.Series(dtype=str)).dropna().tolist()]
        records.append({
            "span_id": root[span_col],
            "q": str(cell(root, "attributes.input.value"))[:4000],
            "ctx": ("\n\n".join(ctx_parts) if ctx_parts else "(el agente no recuperó datos)")[:8000],
            "ans": str(cell(root, "attributes.output.value"))[:4000],
        })

    if not records:
        print("[evals] No hallé traces con span raíz 'LangGraph'. ¿Corriste el agente?")
        return

    records = records[:MAX_TRACES]
    print(f"[evals] Evaluando {len(records)} corridas con {MODEL}...")

    rows = []
    for r in records:
        label, expl = judge(r["q"], r["ctx"], r["ans"])
        rows.append({"span_id": r["span_id"], "label": label,
                     "score": 1.0 if label == "grounded" else 0.0, "explanation": expl})
        print(f"  - {str(r['span_id'])[:14]}… -> {label}")

    results = pd.DataFrame(rows)  # columnas: span_id, label, score, explanation
    client.spans.log_span_annotations_dataframe(
        dataframe=results, annotation_name="Groundedness", annotator_kind="LLM",
    )

    print("\n[evals] Resumen:")
    print(results["label"].value_counts().to_string())
    print(f"\n[evals] Listo. Phoenix ({PHOENIX_URL}) → proyecto '{PROJECT}' → "
          "anotación 'Groundedness' en los traces.")


if __name__ == "__main__":
    main()
