.PHONY: install dev lint format typecheck security test webtest check

install:
	pip install -r requirements-dev.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

lint:
	ruff check app tests
	ruff format --check app tests

format:
	ruff check --fix app tests
	ruff format app tests

typecheck:
	mypy app

security:
	bandit -r app -c pyproject.toml -q
	pip-audit -r requirements.txt

test:
	pytest tests/unit tests/integration -q

webtest:
	npx vitest run --reporter=verbose
	npx tsc --noEmit

check: lint typecheck security test webtest
