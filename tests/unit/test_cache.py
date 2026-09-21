import time
import pytest
from app.adapters.cache import TTLCache
from app.config import Settings

@pytest.fixture
def settings():
    return Settings(
        cache_ttl_seconds=10,
        cache_max_entries=3,
    )

class MockClock:
    def __init__(self):
        self.current = 100.0

    def __call__(self):
        return self.current

    def tick(self, seconds: float):
        self.current += seconds

def test_cache_set_get(settings):
    clock = MockClock()
    cache = TTLCache(settings, clock=clock)
    
    cache.set("v1", "gemini", "task1", "text", {"out": "ok"})
    res = cache.get("v1", "gemini", "task1", "text")
    assert res == {"out": "ok"}
    
    res_none = cache.get("v1", "gemini", "task2", "text")
    assert res_none is None

def test_cache_ttl_expiry(settings):
    clock = MockClock()
    cache = TTLCache(settings, clock=clock)
    
    cache.set("v1", "gemini", "task1", "text", "val1")
    clock.tick(5.0)
    assert cache.get("v1", "gemini", "task1", "text") == "val1"
    
    clock.tick(6.0) # total 11 seconds elapsed
    assert cache.get("v1", "gemini", "task1", "text") is None

def test_cache_max_entries_eviction(settings):
    clock = MockClock()
    cache = TTLCache(settings, clock=clock)
    
    cache.set("v1", "gemini", "t1", "txt", "val1")
    cache.set("v1", "gemini", "t2", "txt", "val2")
    cache.set("v1", "gemini", "t3", "txt", "val3")
    
    # 3 entries in cache now
    assert cache.get("v1", "gemini", "t1", "txt") == "val1"
    
    # Add a 4th entry. Because we just accessed t1, t2 should be the oldest and evicted
    cache.set("v1", "gemini", "t4", "txt", "val4")
    
    assert cache.get("v1", "gemini", "t2", "txt") is None
    assert cache.get("v1", "gemini", "t1", "txt") == "val1"
    assert cache.get("v1", "gemini", "t3", "txt") == "val3"
    assert cache.get("v1", "gemini", "t4", "txt") == "val4"

def test_cache_options_ordering(settings):
    clock = MockClock()
    cache = TTLCache(settings, clock=clock)
    
    # Dicts with different key order should produce the same cache key
    cache.set("v1", "gemini", "t", "txt", "val", options={"a": 1, "b": 2})
    res = cache.get("v1", "gemini", "t", "txt", options={"b": 2, "a": 1})
    assert res == "val"
