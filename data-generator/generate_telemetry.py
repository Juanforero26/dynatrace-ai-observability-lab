"""
Generador de datos sintéticos — envía telemetría OTel a Dynatrace.

Simula una tienda web con varios servicios (frontend → checkout → inventory /
payment) que producen traces distribuidos, métricas y logs. Inyecta errores y
picos de latencia en 'payment-service' para que Dynatrace tenga fallas/problems
reales que el SRE Copilot pueda investigar por DQL.

Envía OTLP/HTTP (protobuf) directo a Dynatrace:
  {DT_ENVIRONMENT}/api/v2/otlp/v1/{traces,metrics,logs}   con Api-Token.

Requisitos (.env en la raíz del repo):
  DT_ENVIRONMENT   = https://<env>.sprint.apps.dynatracelabs.com
  DT_INGEST_TOKEN  = dt0s16....  (platform token, header Bearer, scopes OpenPipeline:
                     openpipeline:traces:ingest, openpipeline:metrics:ingest, openpipeline:logs:ingest)
                     (se acepta DT_API_TOKEN como alias)
  # opcionales:
  DT_OTLP_ENDPOINT = (por defecto = DT_ENVIRONMENT + /api/v2/otlp)
  GEN_RATE         = transacciones por segundo (def. 3)
  GEN_ERROR_RATE   = prob. de fallo en payment (def. 0.2)

Correr:  python data-generator/generate_telemetry.py    (Ctrl+C para parar)
"""
import logging
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from opentelemetry import metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.trace import Status, StatusCode
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

# --- Config ------------------------------------------------------------------
DT_ENV = os.environ["DT_ENVIRONMENT"].rstrip("/")
# Gen3: platform token (dt0s16) con header Bearer. DT_API_TOKEN se acepta como alias.
DT_TOKEN = os.getenv("DT_INGEST_TOKEN") or os.environ["DT_API_TOKEN"]
BASE = os.getenv("DT_OTLP_ENDPOINT", f"{DT_ENV}/api/v2/otlp").rstrip("/")
HEADERS = {"Authorization": f"Bearer {DT_TOKEN}"}
RATE = float(os.getenv("GEN_RATE", "3"))
ERROR_RATE = float(os.getenv("GEN_ERROR_RATE", "0.2"))

# Dynatrace exige temporalidad DELTA en métricas OTLP (cumulative -> 400 Bad Request).
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")

span_exporter = OTLPSpanExporter(endpoint=f"{BASE}/v1/traces", headers=HEADERS)
metric_exporter = OTLPMetricExporter(endpoint=f"{BASE}/v1/metrics", headers=HEADERS)

# --- Un TracerProvider por servicio (cada uno con su service.name) -----------
_providers = []


def tracer_for(service_name: str):
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(span_exporter))
    _providers.append(provider)
    return provider.get_tracer(service_name)


fe = tracer_for("frontend")
co = tracer_for("checkout-service")
pay = tracer_for("payment-service")
inv = tracer_for("inventory-service")

# --- Métricas ----------------------------------------------------------------
meter_provider = MeterProvider(
    resource=Resource.create({"service.name": "webshop"}),
    metric_readers=[
        PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10000)
    ],
)
metrics.set_meter_provider(meter_provider)
meter = meter_provider.get_meter("webshop")
req_counter = meter.create_counter("webshop.requests", unit="1", description="Requests")
latency_hist = meter.create_histogram("webshop.latency", unit="ms", description="Latency")

# --- Logs (best-effort; traces/métricas son el core) -------------------------
log = logging.getLogger("webshop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log_provider = None
try:
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

    _log_provider = LoggerProvider(resource=Resource.create({"service.name": "webshop"}))
    _log_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{BASE}/v1/logs", headers=HEADERS))
    )
    log.addHandler(LoggingHandler(level=logging.INFO, logger_provider=_log_provider))
    print("[gen] logs OTLP habilitados")
except Exception as e:  # noqa: BLE001
    print(f"[gen] logs OTLP no disponibles ({e}); sigo con traces+métricas")

PRODUCTS = ["SKU-100", "SKU-205", "SKU-317", "SKU-420", "SKU-501"]


def one_transaction() -> None:
    product = random.choice(PRODUCTS)
    with fe.start_as_current_span("GET /checkout") as s_fe:
        s_fe.set_attribute("http.route", "/checkout")
        s_fe.set_attribute("product.id", product)
        time.sleep(random.uniform(0.01, 0.05))

        with co.start_as_current_span("POST /checkout/submit") as s_co:
            s_co.set_attribute("cart.items", random.randint(1, 5))

            with inv.start_as_current_span("check-stock") as s_inv:
                slow = random.random() < 0.05
                time.sleep(random.uniform(0.2, 0.6) if slow else random.uniform(0.01, 0.04))
                s_inv.set_attribute("stock.available", True)

            amount = round(random.uniform(10, 500), 2)
            with pay.start_as_current_span("charge") as s_pay:
                s_pay.set_attribute("payment.amount", amount)
                fail = random.random() < ERROR_RATE
                spike = random.random() < 0.15
                dur_ms = random.uniform(400, 1500) if (fail or spike) else random.uniform(30, 120)
                time.sleep(dur_ms / 1000.0)
                latency_hist.record(dur_ms, {"service": "payment-service"})

                if fail:
                    s_pay.set_status(Status(StatusCode.ERROR, "payment gateway timeout"))
                    s_pay.record_exception(TimeoutError("payment gateway timeout"))
                    s_co.set_status(Status(StatusCode.ERROR, "checkout failed"))
                    req_counter.add(1, {"service": "payment-service", "status": "error"})
                    log.error("Payment failed for %s (amount=%.2f): gateway timeout", product, amount)
                else:
                    req_counter.add(1, {"service": "payment-service", "status": "ok"})
                    log.info("Payment OK for %s (amount=%.2f)", product, amount)


def main() -> None:
    print(f"[gen] enviando OTLP a {BASE}  | rate={RATE}/s  error_rate={ERROR_RATE}")
    print("[gen] Ctrl+C para detener. La data tarda ~1-3 min en verse en Dynatrace.")
    interval = 1.0 / RATE if RATE > 0 else 0.3
    n = 0
    try:
        while True:
            one_transaction()
            n += 1
            if n % 20 == 0:
                print(f"[gen] {n} transacciones enviadas")
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n[gen] detenido tras {n} transacciones. Vaciando buffers...")
    finally:
        for p in _providers:
            try:
                p.force_flush(); p.shutdown()
            except Exception:  # noqa: BLE001
                pass
        try:
            meter_provider.force_flush(); meter_provider.shutdown()
        except Exception:  # noqa: BLE001
            pass
        if _log_provider is not None:
            try:
                _log_provider.force_flush(); _log_provider.shutdown()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    main()
