.PHONY: install ingest eval run lint typecheck test check fmt

install:
	uv pip install -e ".[dev]"

ingest:
	python -m ragbot.ingest.run

eval:
	python -m ragbot.eval.run

run:
	uvicorn ragbot.api.app:app --reload --port 8000

lint:
	ruff check src tests

fmt:
	ruff format src tests
	ruff check --fix src tests

typecheck:
	mypy src

test:
	pytest

check: lint typecheck test
