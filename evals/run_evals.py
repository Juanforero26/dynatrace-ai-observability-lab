"""
Evals de Phoenix — juez LLM (Claude) de "groundedness" para el SRE Copilot.

Para cada corrida del agente (trace) toma:
  - input     = la pregunta/tarea
  - reference = los datos recuperados por execute_dql (contexto de Dynatrace)
  - output    = el informe de causa raíz del agente
y le pide a Claude que juzgue si el informe está grounded en esos datos o si
alucina. Escribe el resultado en Phoenix como evaluación del trace.

Diseño robusto: usa el SDK de Anthropic directo como juez (no depende de la API
de phoenix.evals, que cambia entre versiones). Phoenix solo se usa para leer los
spans y registrar las evaluaciones.

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
import phoenix as px
from phoenix.trace import SpanEvaluations
from anthropic import Anthropic

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
MAX_TRACES = int(os.getenv("EVAL_MAX_TRACES", "15"))
anthropic = Anthropic()  # usa ANTHROPIC_API_KEY del entorno

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


def judge(q: str, ctx: str, ans: str):
    msg = anthropic.messages.create(
        model=MODEL,
        max_tokens=300,
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
    if label not in ("grounded", "hallucinated"):
        label = "hallucinated"
    return label, expl


def cell(row, name, default=""):
    try:
        v = row.get(name, default)
        return default if v is None or (isinstance(v, float) and pd.isna(v)) else v
    except Exception:  # noqa: BLE001
        return default


def main() -> None:
    client = px.Client()
    try:
        df = client.get_spans_dataframe(project_name="sre-copilot")
    except TypeError:
        df = client.get_spans_dataframe()
    if df is None or df.empty:
        print("[evals] No hay spans en 'sre-copilot'. Corre el agente primero.")
        return

    trace_col = "context.trace_id" if "context.trace_id" in df.columns else "trace_id"
    span_col = "context.span_id" if "context.span_id" in df.columns else "span_id"

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
        print(f"  - {r['span_id'][:12]}… -> {label}")

    results = pd.DataFrame(rows).set_index("span_id")
    client.log_evaluations(SpanEvaluations(eval_name="Groundedness", dataframe=results))

    print("\n[evals] Resumen:")
    print(results["label"].value_counts().to_string())
    print("\n[evals] Listo. Phoenix (localhost:6006) → proyecto 'sre-copilot' → "
          "columna 'Groundedness' en los traces.")


if __name__ == "__main__":
    main()
