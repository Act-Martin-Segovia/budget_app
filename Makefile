PYTHON := python3
VENV := .venv
UV := $(HOME)/.local/bin/uv

.PHONY: help
help:
	@echo "make setup        Install uv, create venv, install deps"
	@echo "make lint         Run ruff and sqlfluff"
	@echo "make run          Run the app"

.PHONY: install-uv
install-uv:
	@if [ ! -x "$(UV)" ]; then \
		curl -LsSf https://astral.sh/uv/install.sh | sh ; \
	fi

.PHONY: setup
setup: install-uv
	$(UV) venv $(VENV)
	$(UV) pip install -e . --group dev

.PHONY: lint
lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format .
	$(VENV)/bin/sqlfluff lint sql || true

.PHONY: run
run:
	$(VENV)/bin/python -m streamlit run src/budget_app/app/main.py

