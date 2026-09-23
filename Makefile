# Prefer the project's own virtualenv, so every target works whether or not
# it has been activated. Falls back to an active venv, then to python3.
# macOS ships no bare `python`, so hard-coding one fails outside a venv with
# "No such file or directory" rather than anything useful.
PYTHON ?= $(shell \
  [ -x .venv/bin/python ] && echo .venv/bin/python \
  || command -v python 2>/dev/null \
  || command -v python3)

.PHONY: install dev lint format typecheck security test webtest smoke check

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

dev:
	$(PYTHON) -m uvicorn app.main:create_app --factory --reload --port 8080

lint:
	$(PYTHON) -m ruff check app tests scripts
	$(PYTHON) -m ruff format --check app tests scripts

format:
	$(PYTHON) -m ruff check --fix app tests scripts
	$(PYTHON) -m ruff format app tests scripts

typecheck:
	$(PYTHON) -m mypy app scripts

security:
	$(PYTHON) -m bandit -r app -c pyproject.toml -q
	$(PYTHON) -m pip_audit -r requirements.txt

test:
	$(PYTHON) -m pytest tests/unit tests/integration -q

webtest:
	npx vitest run --reporter=verbose
	npx tsc --noEmit

smoke:
	$(PYTHON) -m scripts.smoke

check: lint typecheck security test webtest
