"""Google Trends + Reddit sources — fixture-backed tests."""

import json
import time
from pathlib import Path

import pytest

from youtube_research_agent.sources.base import _cache_path
from youtube_research_agent.sources.google_trends import GoogleTrendsSource
from youtube_research_agent.sources.reddit import RedditSource


def _seed_cache(tmp_path: Path, source: str, method: str,
                params: dict, response: dict) -> None:
    path = _cache_path(source, method, params, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"__stored_at__": time.time(), "data": response}, f)


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("YTR_CACHE_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Google Trends
# ---------------------------------------------------------------------------


class TestGoogleTrendsRisingQueries:
    def test_parses_rising_rows(self, cache_dir):
        _seed_cache(cache_dir, "google_trends", "rising_queries",
                    {"seed": "algo trading", "geo": "US"},
                    {"rising": [
                        {"query": "ai trading bot 2026", "value": 250},
                        {"query": "quant trading youtube", "value": 80},
                    ]})
        src = GoogleTrendsSource()
        out = src.rising_queries("algo trading")
        assert len(out) == 2
        # "breakout" capped at 100
        assert out[0].interest_now == 100.0
        assert out[1].interest_now == 80.0
        assert all(t.rising for t in out)

    def test_empty_rising_returns_empty(self, cache_dir):
        _seed_cache(cache_dir, "google_trends", "rising_queries",
                    {"seed": "x", "geo": "US"}, {"rising": []})
        assert GoogleTrendsSource().rising_queries("x") == []


class TestGoogleTrendsInterestSnapshot:
    def test_returns_three_datapoints(self, cache_dir):
        _seed_cache(cache_dir, "google_trends", "interest_over_time",
                    {"seed": "trading bot", "geo": "US", "timeframe": "today 3-m"},
                    {"points": [
                        {"date": "2026-02-01", "value": 30},
                        {"date": "2026-02-08", "value": 35},
                        {"date": "2026-02-15", "value": 40},
                        {"date": "2026-02-22", "value": 45},
                        {"date": "2026-03-01", "value": 50},
                        {"date": "2026-03-08", "value": 55},
                        {"date": "2026-03-15", "value": 60},
                        {"date": "2026-03-22", "value": 65},
                        {"date": "2026-04-01", "value": 70},
                        {"date": "2026-04-08", "value": 75},
                        {"date": "2026-04-15", "value": 78},
                        {"date": "2026-04-22", "value": 82},
                        {"date": "2026-04-29", "value": 85},
                    ]})
        snap = GoogleTrendsSource().interest_snapshot("trading bot")
        assert snap is not None
        assert snap.interest_now == 85
        # ~30 days back = 4-weeks earlier in the weekly bucket
        assert snap.interest_30d_ago > 0
        assert snap.interest_90d_ago > 0
        assert snap.interest_now > snap.interest_30d_ago > snap.interest_90d_ago

    def test_no_data_returns_none(self, cache_dir):
        _seed_cache(cache_dir, "google_trends", "interest_over_time",
                    {"seed": "nonsense xyz", "geo": "US",
                     "timeframe": "today 3-m"}, {"points": []})
        assert GoogleTrendsSource().interest_snapshot("nonsense xyz") is None


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------


class TestRedditSource:
    def test_parses_hot_posts(self, cache_dir):
        # 4 hours ago — for "2 hours ago" we'd use a delta from now,
        # but the parser just computes velocity from `created_utc`.
        recent_ts = time.time() - 4 * 3600
        _seed_cache(cache_dir, "reddit", "hot",
                    {"subreddit": "algotrading", "limit": 25},
                    {"posts": [{
                        "title": "I built a trading bot",
                        "subreddit": "algotrading",
                        "upvotes": 400, "comment_count": 50,
                        "created_utc": recent_ts,
                        "permalink": "/r/algotrading/comments/abc/",
                    }]})
        out = RedditSource(client_id="x", client_secret="y").hot_posts("algotrading")
        assert len(out) == 1
        assert out[0].upvotes == 400
        # ~100 upvotes/hour
        assert 90 < out[0].upvote_velocity < 110
        assert out[0].url == "/r/algotrading/comments/abc/"

    def test_rising_posts_uses_rising_method(self, cache_dir):
        _seed_cache(cache_dir, "reddit", "rising",
                    {"subreddit": "algotrading", "limit": 10},
                    {"posts": [{
                        "title": "what's the best broker for paper trading",
                        "subreddit": "algotrading",
                        "upvotes": 50, "comment_count": 12,
                        "created_utc": time.time() - 1800,    # 30min ago
                        "permalink": "/r/algotrading/comments/xyz/",
                    }]})
        out = RedditSource(client_id="x", client_secret="y").rising_posts(
            "algotrading", limit=10)
        assert len(out) == 1
        # 30 minutes ≈ 0.5h, 50 upvotes => 100 upvotes/hour
        assert out[0].upvote_velocity > 50

    def test_missing_creds_raises_on_cache_miss(self, cache_dir, monkeypatch):
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="REDDIT_CLIENT_ID"):
            RedditSource().hot_posts("uncached_subreddit")
