"""YouTube Data source — tested via the cache layer (no live API needed).

Strategy: pre-seed the cache directory with fixture JSON that matches
what the API would return. The source's cached_call() reads from disk
before falling through to a live call. With the fixture present, the
source operates entirely offline.
"""

import json
import time
from pathlib import Path

import pytest

from youtube_research_agent.models import Channel, Video
from youtube_research_agent.sources.base import _cache_path
from youtube_research_agent.sources.youtube_data import (
    YouTubeDataSource, _parse_iso8601_duration,
)


def _seed_cache(tmp_path: Path, source: str, method: str,
                params: dict, response: dict) -> None:
    """Drop a fixture into the cache so the source never hits the network."""
    path = _cache_path(source, method, params, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"__stored_at__": time.time(), "data": response}, f)


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("YTR_CACHE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def source(cache_dir):
    # No API key needed — every call hits the cache.
    return YouTubeDataSource(api_key="")


# ---------------------------------------------------------------------------
# Duration parser
# ---------------------------------------------------------------------------


class TestDurationParser:
    @pytest.mark.parametrize("iso,expected", [
        ("PT0S", 0),
        ("PT45S", 45),
        ("PT1M30S", 90),
        ("PT1H", 3600),
        ("PT1H2M3S", 3723),
        ("not-iso", 0),
    ])
    def test_parses_durations(self, iso, expected):
        assert _parse_iso8601_duration(iso) == expected


# ---------------------------------------------------------------------------
# get_channels
# ---------------------------------------------------------------------------


class TestGetChannels:
    def test_parses_cached_response(self, source, cache_dir):
        _seed_cache(cache_dir, "youtube_data", "channels.list",
                    {"ids": ["UC123"]}, {
            "items": [{
                "id": "UC123",
                "snippet": {"title": "QuantPy"},
                "statistics": {
                    "subscriberCount": "42000",
                    "videoCount": "120",
                    "viewCount": "1500000",
                },
            }],
        })
        result = source.get_channels(["UC123"])
        assert len(result) == 1
        assert isinstance(result[0], Channel)
        assert result[0].id == "UC123"
        assert result[0].title == "QuantPy"
        assert result[0].subscriber_count == 42_000
        assert result[0].video_count == 120
        assert result[0].view_count == 1_500_000

    def test_empty_input_returns_empty(self, source):
        assert source.get_channels([]) == []

    def test_missing_stats_treated_as_zero(self, source, cache_dir):
        _seed_cache(cache_dir, "youtube_data", "channels.list",
                    {"ids": ["UCX"]}, {
            "items": [{"id": "UCX", "snippet": {"title": "New"},
                       "statistics": {}}],
        })
        ch = source.get_channels(["UCX"])[0]
        assert ch.subscriber_count == 0
        assert ch.view_count == 0


# ---------------------------------------------------------------------------
# get_videos
# ---------------------------------------------------------------------------


class TestGetVideos:
    def test_parses_full_video(self, source, cache_dir):
        _seed_cache(cache_dir, "youtube_data", "videos.list",
                    {"ids": ["vid42"]}, {
            "items": [{
                "id": "vid42",
                "snippet": {
                    "title": "How To Build an Algo Trading Bot",
                    "channelId": "UC123",
                    "channelTitle": "QuantPy",
                    "publishedAt": "2026-03-15T10:00:00Z",
                    "description": "Step-by-step guide",
                    "tags": ["algo", "trading"],
                },
                "statistics": {
                    "viewCount": "245000", "likeCount": "12000",
                    "commentCount": "890",
                },
                "contentDetails": {"duration": "PT12M34S"},
            }],
        })
        v = source.get_videos(["vid42"])[0]
        assert isinstance(v, Video)
        assert v.id == "vid42"
        assert v.view_count == 245_000
        assert v.like_count == 12_000
        assert v.comment_count == 890
        assert v.duration_seconds == 754
        assert v.tags == ["algo", "trading"]
        assert v.is_short is False

    def test_detects_short(self, source, cache_dir):
        _seed_cache(cache_dir, "youtube_data", "videos.list",
                    {"ids": ["short1"]}, {
            "items": [{
                "id": "short1",
                "snippet": {"title": "60-sec teaser", "channelId": "UC123",
                            "channelTitle": "C", "publishedAt": "2026-04-01T0:00:00Z"},
                "statistics": {"viewCount": "5000", "likeCount": "100",
                               "commentCount": "10"},
                "contentDetails": {"duration": "PT45S"},
            }],
        })
        v = source.get_videos(["short1"])[0]
        assert v.is_short is True


# ---------------------------------------------------------------------------
# recent_videos_by_channel + search_videos return id lists
# ---------------------------------------------------------------------------


class TestSearch:
    def test_recent_videos_by_channel_returns_ids(self, source, cache_dir):
        # The source rounds the cutoff to day precision so the cache key is
        # stable across a 24h window — recompute it the same way here.
        from datetime import datetime, timezone, timedelta
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=180)).date()
        cutoff = datetime.combine(cutoff_date, datetime.min.time(),
                                  tzinfo=timezone.utc).isoformat()
        _seed_cache(cache_dir, "youtube_data", "search.list.by_channel",
                    {"channel_id": "UC1", "max_results": 25, "published_after": cutoff},
                    {"items": [
                        {"id": {"videoId": "v1"}},
                        {"id": {"videoId": "v2"}},
                    ]})
        ids = source.recent_videos_by_channel("UC1")
        assert ids == ["v1", "v2"]

    def test_search_videos_returns_ids(self, source, cache_dir):
        _seed_cache(cache_dir, "youtube_data", "search.list.by_query",
                    {"query": "algorithmic trading", "max_results": 25},
                    {"items": [
                        {"id": {"videoId": "x1"}},
                        {"id": {"videoId": "x2"}},
                        {"id": {"kind": "youtube#playlist"}},   # skipped — no videoId
                    ]})
        assert source.search_videos("algorithmic trading") == ["x1", "x2"]


# ---------------------------------------------------------------------------
# hydrate_baselines
# ---------------------------------------------------------------------------


class TestHydrateBaselines:
    def test_fills_median(self, source):
        from youtube_research_agent.models import Channel, Video

        ch = Channel(id="UC1", title="C", subscriber_count=1000,
                     video_count=10, view_count=100_000)
        sample = [Video(id=f"v{i}", title="x", channel_id="UC1", channel_title="C",
                        published_at="2026-04-01T00:00:00Z",
                        view_count=v, like_count=0, comment_count=0)
                  for i, v in enumerate([1000, 2000, 4000, 8000, 16000])]
        source.hydrate_baselines([ch], {"UC1": sample})
        assert ch.median_views_per_video == 4000

    def test_no_sample_leaves_baseline_zero(self, source):
        from youtube_research_agent.models import Channel

        ch = Channel(id="UC1", title="C", subscriber_count=1000,
                     video_count=10, view_count=100_000)
        source.hydrate_baselines([ch], {})
        assert ch.median_views_per_video == 0.0


# ---------------------------------------------------------------------------
# API key gating — only triggered when nothing's cached
# ---------------------------------------------------------------------------


class TestApiKeyGate:
    def test_missing_key_raises_only_on_cache_miss(self, cache_dir, monkeypatch):
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        source = YouTubeDataSource(api_key="")
        with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY"):
            source.get_channels(["UC_missing"])

    def test_cached_response_works_without_key(self, cache_dir):
        _seed_cache(cache_dir, "youtube_data", "channels.list",
                    {"ids": ["UC_cached"]}, {"items": [{
                        "id": "UC_cached",
                        "snippet": {"title": "Cached"},
                        "statistics": {"subscriberCount": "5",
                                        "videoCount": "1", "viewCount": "10"},
                    }]})
        source = YouTubeDataSource(api_key="")  # empty key OK because cache hits
        ch = source.get_channels(["UC_cached"])[0]
        assert ch.title == "Cached"
