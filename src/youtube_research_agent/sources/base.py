"""Base Source class + shared cache.

Every source caches API responses under .cache/<source>/<hash>.json
keyed on (method, params). Caches live for 24h by default; tunable
per-call via `max_age_seconds`.

The cache layer makes the pipeline cheap to re-run during dev (no
quota burn on the same query) and lets tests load fixtures by simply
seeding the .cache directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable


DEFAULT_CACHE_DIR = ".cache"
DEFAULT_MAX_AGE = 24 * 3600    # 24h


def _cache_path(source: str, method: str, params: dict[str, Any],
                cache_dir: Path) -> Path:
    canonical = json.dumps({"method": method, "params": params},
                           sort_keys=True, default=str)
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return cache_dir / source / f"{method}_{h}.json"


def cached_call(
    source: str,
    method: str,
    params: dict[str, Any],
    compute: Callable[[], Any],
    *,
    cache_dir: Path | str | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE,
) -> Any:
    """Run `compute()` only if the cached result is missing or stale.

    Cache key is the JSON-stringified (method, params).
    """
    cache_root = Path(cache_dir or os.environ.get("YTR_CACHE_DIR", DEFAULT_CACHE_DIR))
    path = _cache_path(source, method, params, cache_root)

    # Hit
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                cached = json.load(f)
            stored_at = cached.get("__stored_at__", 0)
            if max_age_seconds <= 0 or (time.time() - stored_at) < max_age_seconds:
                return cached.get("data")
        except Exception:
            pass  # fall through to recompute

    # Miss
    data = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"__stored_at__": time.time(), "data": data}, f, default=str)
    return data


class Source:
    """Marker base class. Sources may use cached_call() directly; they
    don't have to subclass this. Kept here for type hints and future
    polymorphism (e.g. a unified `Source.fetch()` interface)."""

    name: str = "abstract"
