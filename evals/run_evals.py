"""
Evals de Phoenix — juez LLM (Claude) de "groundedness" para el SRE Copilot.

Para cada corrida del agente (trace), toma:
  - input     = la pregunta/tarea
  - reference = los datos recuperados por execute_dql (contexto de Dynatrace)
  - output    = el informe de causa raíz del agente
y le pide a Claude que juzgue si el informe está **grounded** en esos datos o si
**alucina**. Luego escribe el resultado en Phoenix como una evaluación sobre el
trace (se ve en la UI, columna de evals / anotaciones).

Correr en el venv que tiene Phoenix (el de ~/phoenix-venv):
  ~/phoenix-venv/bin/pip install anthropic python-dotenv
  ~/phoenix-venv/bin/python evals/run_evals.py

Requisitos: Phoenix corriendo (localhost:6006), agente ya ejecutado (que haya
traces del proyecto 'sre-copilot'), y ANTHROPIC_API_KEY en el .env de la raíz.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import pandas as pd
import phoenix as px
from phoenix.trace import SpanEvaluations
from phoenix.evals import llm_classify, AnthropicModel

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

GROUNDEDNESS_TEMPLATE = """
Eres un evaluador. Un asistente SRE analizó un entorno Dynatrace y entregó una
hipótesis de causa raíz. Debes juzgar si esa respuesta está SUSTENTADA en los
datos que el asistente recuperó (no inventada).

[Pregunta]
{input}

[Datos recuperados de Dynatrace (contexto)]
{reference}

[Respuesta del asistente]
{output}

¿La respuesta está sustentada en los datos recuperados, sin inventar hechos?
Si no hubo datos recuperados y el asistente igual afirmó causas concretas,
eso es "hallucinated". Responde SOLO una palabra: grounded o hallucinated.
"""
RAILS = ["grounded", "hallucinated"]


def col(row, name, default=""):
    try:
        v = row.get(name, default)
        return default if v is None or (isinstance(v, float) and pd.isna(v)) else v
    except Exception:  # noqa: BLE001
        return default


def main() -> None:
    client = px.Client()  # usa PHOENIX_COLLECTOR_ENDPOINT o localhost:6006
    df = client.get_spans_dataframe(project_name="sre-copilot")
    if df is None or df.empty:
        print("[evals] No hay spans en el proyecto 'sre-copilot'. Corre el agente primero.")
        return
    print(f"[evals] {len(df)} spans leídos. Columnas de interés: "
          f"{[c for c in df.columns if 'input' in c or 'output' in c][:6]}")

    trace_col = "context.trace_id" if "context.trace_id" in df.columns else "trace_id"
    span_col = "context.span_id" if "context.span_id" in df.columns else "span_id"

    records = []
    for trace_id, g in df.groupby(trace_col):
        roots = g[g["name"] == "LangGraph"]
        if roots.empty:
            continue
        root = roots.iloc[0]
        question = col(root, "attributes.input.value")
        answer = col(root, "attributes.output.value")
        tools = g[g["name"] == "execute_dql"]
        ctx_parts = [str(x) for x in tools.get("attributes.output.value", pd.Series(dtype=str)).dropna().tolist()]
        reference = "\n\n".join(ctx_parts) if ctx_parts else "(el agente no recuperó datos)"
        records.append({
            span_col: root[span_col],
            "input": str(question)[:4000],
            "reference": str(reference)[:8000],
            "output": str(answer)[:4000],
        })

    if not records:
        print("[evals] No encontré traces con span raíz 'LangGraph'. ¿Corriste el agente?")
        return

    eval_df = pd.DataFrame(records).set_index(span_col)
    print(f"[evals] Evaluando {len(eval_df)} corridas del agente con {MODEL}...")

    results = llm_classify(
        dataframe=eval_df,
        template=GROUNDEDNESS_TEMPLATE,
        model=AnthropicModel(model=MODEL),
        rails=RAILS,
        provide_explanation=True,
    )
    results.index = eval_df.index  # alinear al span_id

    client.log_evaluations(SpanEvaluations(eval_name="Groundedness", dataframe=results))
    print("\n[evals] Resultados:")
    print(results[["label"]].value_counts())
    print("\n[evals] Listo. Míralo en Phoenix (localhost:6006) → proyecto 'sre-copilot' → "
          "columna 'Groundedness' en los traces.")


if __name__ == "__main__":
    main()
