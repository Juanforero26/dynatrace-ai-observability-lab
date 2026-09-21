"""Instrumentación OpenTelemetry + OpenInference.

Pieza CLAVE del laboratorio: aquí se convierte la actividad de los agentes
(llamadas al LLM, tokens, tool calls) en spans OTLP.

Los spans se exportan al COLECTOR (gestionado por BindPlane), NO directo a
Phoenix. BindPlane luego los reparte hacia Phoenix (señales de IA) y Dynatrace
(traces full-stack). Ese fan-out es lo que demuestra el rol de BindPlane.
"""
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from openinference.instrumentation.langchain import LangChainInstrumentor

from . import config


def setup_telemetry() -> None:
    endpoint = config.OTEL_COLLECTOR_HTTP.rstrip("/") + "/v1/traces"
    resource = Resource.create(
        {
            "service.name": config.SERVICE_NAME,
            "deployment.environment": "lab",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)

    # Auto-instrumenta LangChain/LangGraph -> spans OpenInference (GenAI).
    LangChainInstrumentor().instrument(tracer_provider=provider)
    print(f"[telemetry] exportando spans a {endpoint}")
