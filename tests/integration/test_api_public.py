"""The endpoints anyone can read: health, rules and the page itself."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.version import VERSION
from tests.paths import WEB_ROOT


def test_health_reports_the_running_version(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    assert body == {"status": "ok", "version": VERSION}


def test_the_rules_endpoint_publishes_every_rule(client: TestClient) -> None:
    rules = client.get("/api/v1/rules").json()["rules"]
    assert [rule["id"] for rule in rules] == [
        "in.ni_act.s138_demand",
        "in.sarfaesi.s13_2_demand",
        "in.tpa.s106_termination",
    ]


def test_each_published_rule_carries_its_source_and_review_date(client: TestClient) -> None:
    for rule in client.get("/api/v1/rules").json()["rules"]:
        assert rule["sources"]
        assert rule["sources"][0]["url"].startswith("https://")
        assert rule["last_reviewed"]
        assert rule["period_days"] > 0


def test_the_rules_can_be_read_in_hindi(client: TestClient) -> None:
    english = client.get("/api/v1/rules", params={"language": "en"}).json()["rules"]
    hindi = client.get("/api/v1/rules", params={"language": "hi"}).json()["rules"]
    assert english[0]["title"] != hindi[0]["title"]
    assert any("ऀ" <= ch <= "ॿ" for ch in hindi[0]["title"])


def test_an_unknown_language_is_refused(client: TestClient) -> None:
    assert client.get("/api/v1/rules", params={"language": "fr"}).status_code == 422


def test_the_page_is_served_at_the_root(client: TestClient) -> None:
    if not (WEB_ROOT / "index.html").exists():
        return
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["Cache-Control"] == "no-cache"


def test_the_samples_are_served(client: TestClient) -> None:
    response = client.get("/samples/cheque-demand-notice.txt")
    assert response.status_code == 200
    assert "SECTION 138" in response.text
