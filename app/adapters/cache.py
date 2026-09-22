"""A small in-memory cache with expiry, keyed on the whole request shape.

Keys are the SHA-256 of a canonical JSON array of the prompt version, the
model id, the task, the masked document text and the request options, so a
different language, reading level or prompt version can never read another
entry. Values are validated model output built from masked text only.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any

from app.config import Settings

CacheValue = Mapping[str, Any]


class TTLCache:
    """A least-recently-used cache whose entries expire."""

    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic) -> None:
        """Build a cache sized and timed from *settings*.

        Args:
            settings: Supplies ``cache_max_entries`` and ``cache_ttl_seconds``.
            clock: Monotonic time source, injected so tests can move time.
        """
        self._max_entries = settings.cache_max_entries
        self._ttl = settings.cache_ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, CacheValue]] = OrderedDict()

    @staticmethod
    def key(
        *,
        prompt_version: str,
        model: str,
        task: str,
        texts: tuple[str, ...],
        options: Mapping[str, str | int | None],
    ) -> str:
        """Build the cache key for one request.

        Args:
            prompt_version: The current prompt version.
            model: The model id the answer would come from.
            task: The pipeline task name, such as ``decode``.
            texts: The masked document texts, in the order they are sent.
            options: Request options such as language and reading level.

        Returns:
            A hex SHA-256 digest of the canonical form of those inputs.
        """
        canonical = json.dumps(
            [prompt_version, model, task, list(texts), dict(sorted(options.items()))],
            separators=(",", ":"),
            ensure_ascii=False,
            sort_keys=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get(self, key: str) -> CacheValue | None:
        """Return the value for *key*, or None if it is absent or expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def set(self, key: str, value: CacheValue) -> None:
        """Store *value* under *key*, evicting the least recently used entry."""
        self._entries[key] = (self._clock() + self._ttl, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def __len__(self) -> int:
        """Return the number of entries currently held, expired or not."""
        return len(self._entries)
