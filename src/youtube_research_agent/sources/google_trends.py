"""Google Trends source via pytrends.

Lazy import — pytrends is unstable across pytrends/google-trends API
changes and we don't want test-runs to fail when it's not installed.

What we actually use from pytrends:
  - related_queries (rising) — for trend-velocity signals
  - interest_over_time     — for absolute interest snapshots
"""

from __future__ import annotations

from ..models import TrendQuery
from .base import Source, cached_call


class GoogleTrendsSource(Source):
    name = "google_trends"

    def __init__(self, cache_max_age_seconds: int | None = None) -> None:
        self.cache_max_age = cache_max_age_seconds
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from pytrends.request import TrendReq   # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "pytrends not installed. `pip install pytrends`. "
                "(Tests should hit the cache directly via seeded fixtures.)"
            ) from e
        self._client = TrendReq(hl="en-US", tz=0)
        return self._client

    def _kwargs(self) -> dict:
        return {} if self.cache_max_age is None else {"max_age_seconds": self.cache_max_age}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rising_queries(self, seed: str, *, geo: str = "US") -> list[TrendQuery]:
        """Return rising queries related to `seed` from Google Trends.

        Caches the raw pytrends response. Returns a list of TrendQuery
        objects where `rising=True` and `interest_now` is the
        pytrends-reported "value" (0-100ish).
        """
        raw = cached_call(
            source=self.name,
            method="rising_queries",
            params={"seed": seed, "geo": geo},
            compute=lambda: self._raw_rising_queries(seed, geo),
            **self._kwargs(),
        )
        return [self._parse_rising_row(row, seed) for row in raw.get("rising", [])]

    def interest_snapshot(self, seed: str, *, geo: str = "US",
                          timeframe: str = "today 3-m") -> TrendQuery | None:
        """Return a snapshot of `seed` itself — interest now vs 30d ago vs 90d ago.

        Uses pytrends `interest_over_time` and reads 3 datapoints
        (latest, latest-30d, latest-90d). Returns None if pytrends
        returned no data for the seed.
        """
        raw = cached_call(
            source=self.name,
            method="interest_over_time",
            params={"seed": seed, "geo": geo, "timeframe": timeframe},
            compute=lambda: self._raw_interest_over_time(seed, geo, timeframe),
            **self._kwargs(),
        )
        points = raw.get("points", [])
        if not points:
            return None
        # points = list[{date, value}], sorted oldest->newest
        latest = points[-1]["value"]
        # ~30 days back = 30 datapoints if daily, fewer if weekly
        idx_30 = max(0, len(points) - 1 - 4)    # weekly bucket → ~4 weeks
        idx_90 = max(0, len(points) - 1 - 12)
        return TrendQuery(
            query=seed,
            source=self.name,
            interest_now=float(latest),
            interest_30d_ago=float(points[idx_30]["value"]),
            interest_90d_ago=float(points[idx_90]["value"]),
            rising=False,
        )

    # ------------------------------------------------------------------
    # Raw API calls
    # ------------------------------------------------------------------

    def _raw_rising_queries(self, seed: str, geo: str) -> dict:
        c = self._get_client()
        c.build_payload([seed], geo=geo, timeframe="today 3-m")
        rq = c.related_queries() or {}
        seed_rq = rq.get(seed, {}) if isinstance(rq, dict) else {}
        rising_df = seed_rq.get("rising") if isinstance(seed_rq, dict) else None
        if rising_df is None or getattr(rising_df, "empty", True):
            return {"rising": []}
        rows = [
            {"query": str(r["query"]), "value": int(r["value"])}
            for _, r in rising_df.iterrows()
        ]
        return {"rising": rows}

    def _raw_interest_over_time(self, seed: str, geo: str, timeframe: str) -> dict:
        c = self._get_client()
        c.build_payload([seed], geo=geo, timeframe=timeframe)
        df = c.interest_over_time()
        if df is None or getattr(df, "empty", True):
            return {"points": []}
        points = [
            {"date": str(idx.date()), "value": int(row[seed])}
            for idx, row in df.iterrows() if seed in df.columns
        ]
        return {"points": points}

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_rising_row(row: dict, seed: str) -> TrendQuery:
        v = float(row.get("value", 0))
        # Pytrends "rising" values can be >100 ("breakout"). Cap at 100
        # for downstream sanity; the rising flag captures the bullishness.
        v = min(v, 100.0)
        return TrendQuery(
            query=row["query"], source="google_trends",
            interest_now=v, interest_30d_ago=v * 0.4,
            interest_90d_ago=v * 0.1, rising=True,
        )
