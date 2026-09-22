"""Tests for the content-hash TTL cache."""

from __future__ import annotations

from app.adapters.cache import TTLCache
from app.config import Settings

BASE_KEY_ARGS = {
    "prompt_version": "2026-09-b",
    "model": "gemini-flash",
    "task": "decode",
    "texts": ("a notice about a cheque",),
}


def make_cache(clock: list[float], *, max_entries: int = 3, ttl: int = 900) -> TTLCache:
    """Build a cache whose clock the test controls."""
    settings = Settings(cache_max_entries=max_entries, cache_ttl_seconds=ttl)
    return TTLCache(settings, clock=lambda: clock[0])


def key(**overrides: object) -> str:
    """Build a cache key, overriding any of the base arguments."""
    args: dict[str, object] = {**BASE_KEY_ARGS, "options": {}}
    args.update(overrides)
    return TTLCache.key(**args)  # type: ignore[arg-type]


def test_hit_returns_the_stored_value() -> None:
    clock = [0.0]
    cache = make_cache(clock)
    cache.set(key(), {"summary": "kept"})
    assert cache.get(key()) == {"summary": "kept"}


def test_miss_returns_none() -> None:
    clock = [0.0]
    cache = make_cache(clock)
    assert cache.get(key()) is None


def test_entry_expires_after_the_ttl() -> None:
    clock = [0.0]
    cache = make_cache(clock, ttl=900)
    cache.set(key(), {"summary": "kept"})
    clock[0] = 899.0
    assert cache.get(key()) is not None
    clock[0] = 900.0
    assert cache.get(key()) is None


def test_expired_entry_is_dropped() -> None:
    clock = [0.0]
    cache = make_cache(clock, ttl=10)
    cache.set(key(), {"summary": "kept"})
    clock[0] = 20.0
    cache.get(key())
    assert len(cache) == 0


def test_least_recently_used_entry_is_evicted() -> None:
    clock = [0.0]
    cache = make_cache(clock, max_entries=2)
    first, second, third = key(task="a"), key(task="b"), key(task="c")
    cache.set(first, {"n": 1})
    cache.set(second, {"n": 2})
    cache.get(first)
    cache.set(third, {"n": 3})
    assert cache.get(second) is None
    assert cache.get(first) == {"n": 1}
    assert cache.get(third) == {"n": 3}


def test_a_different_language_is_a_different_key() -> None:
    assert key(options={"language": "en"}) != key(options={"language": "hi"})


def test_a_different_reading_level_is_a_different_key() -> None:
    assert key(options={"reading_level": "simple"}) != key(options={"reading_level": "detailed"})


def test_a_different_prompt_version_is_a_different_key() -> None:
    assert key(prompt_version="2026-09-a") != key(prompt_version="2026-09-b")


def test_a_different_model_is_a_different_key() -> None:
    assert key(model="flash-a") != key(model="flash-b")


def test_a_different_document_is_a_different_key() -> None:
    assert key(texts=("one",)) != key(texts=("two",))


def test_option_order_does_not_change_the_key() -> None:
    forwards = key(options={"language": "en", "reading_level": "simple"})
    backwards = key(options={"reading_level": "simple", "language": "en"})
    assert forwards == backwards


def test_two_documents_key_on_their_order() -> None:
    assert key(texts=("notice", "agreement")) != key(texts=("agreement", "notice"))
