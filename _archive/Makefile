.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help
help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: env
env: ## Crea .env a partir de .env.example (si no existe)
	@test -f .env || (cp .env.example .env && echo "Creado .env — completá los valores")

# ----------------------- Fase 3: pipeline base ------------------------------
.PHONY: up
up: ## Levanta Phoenix + OTel collector (Fase 3)
	$(COMPOSE) up -d phoenix otelcol

.PHONY: logs
logs: ## Sigue los logs de Phoenix y del colector
	$(COMPOSE) logs -f phoenix otelcol

.PHONY: down
down: ## Baja todos los contenedores
	$(COMPOSE) down

.PHONY: nuke
nuke: ## Baja TODO y borra volúmenes (datos de Phoenix/BindPlane)
	$(COMPOSE) down -v

# ----------------------- Fase 2: BindPlane ----------------------------------
.PHONY: bindplane-up
bindplane-up: ## Levanta BindPlane OP + Postgres + Prometheus (Fase 2)
	$(COMPOSE) --profile bindplane up -d

# ----------------------- Fase 4: agentes ------------------------------------
.PHONY: agents-install
agents-install: ## Instala dependencias Python de los agentes
	cd agents && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

.PHONY: agents-run
agents-run: ## Corre el SRE Copilot (Fase 4)
	cd agents && . .venv/bin/activate && python -m sre_copilot.main

# ----------------------- Utilidades -----------------------------------------
.PHONY: smoke
smoke: ## Envía un span de prueba al colector para validar el fan-out
	@curl -sS -X POST http://localhost:4318/v1/traces \
		-H 'Content-Type: application/json' \
		-d @otel-collector/smoke-trace.json && echo "\nSpan de prueba enviado."
