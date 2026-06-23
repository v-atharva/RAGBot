.PHONY: install ingest index build-all eval serve run web web-install lint typecheck test check fmt

VENV := .venv
PY := $(VENV)/bin/python

install:
	uv venv --python 3.12 $(VENV)
	uv pip install --python $(PY) -e ".[dev]" httpx

ingest:
	$(PY) -m ragbot.ingest.run

index:
	$(PY) -m ragbot.retrieve.build_index

build-all: ingest index

eval:
	$(PY) -m ragbot.eval.run

serve:
	$(VENV)/bin/uvicorn ragbot.api.app:app --reload --port 8000

run: serve

web-install:
	cd web && npm install

web:
	cd web && npm run dev

lint:
	$(VENV)/bin/ruff check src tests

fmt:
	$(VENV)/bin/ruff format src tests
	$(VENV)/bin/ruff check --fix src tests

typecheck:
	$(VENV)/bin/mypy src

test:
	$(VENV)/bin/pytest

check: lint typecheck test
