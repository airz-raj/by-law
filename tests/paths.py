"""Repository paths, so tests do not depend on the working directory."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = REPO_ROOT / "app"
WEB_ROOT = REPO_ROOT / "web"
RULES_PATH = APP_ROOT / "data" / "rules_in.json"
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
LLM_FIXTURES = FIXTURES_ROOT / "llm"
SAMPLES_ROOT = WEB_ROOT / "samples"
