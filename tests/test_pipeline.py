"""Pipeline orchestrator — end-to-end with fixture-seeded sources."""

import json
import time
from pathlib import Path

import pytest

from youtube_research_agent.pipeline import (
    PipelineResult, render_report, research_niche, synthesize_ideas,
    collect_signals,
)
from youtube_research_agent.sources.base import _cache_path
from youtube_research_agent.sources.youtube_data import YouTubeDataSource
from youtube_research_agent.sources.google_trends import GoogleTrendsSource
from youtube_research_agent.sources.reddit import RedditSource
from youtube_research_agent.llm.provider import HeuristicProvider


def _seed(tmp_path: Path, source: str, method: str,
          params: dict, response: dict) -> None:
    p = _cache_path(source, method, params, tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"__stored_at__": time.time(), "data": response}, f)


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("YTR_CACHE_DIR", str(tmp_path))
    # Force HeuristicProvider so we don't try to use LLM keys
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return tmp_path


def _seed_full_run(cache_dir: Path) -> None:
    """Seed every source so the pipeline runs offline end-to-end."""
    # Channels
    _seed(cache_dir, "youtube_data", "channels.list",
          {"ids": ["UC_quantpy"]},
          {"items": [{
              "id": "UC_quantpy",
              "snippet": {"title": "QuantPy"},
              "statistics": {"subscriberCount": "120000",
                             "videoCount": "80", "viewCount": "20000000"},
          }]})
    # Recent videos by channel (search.list)
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.combine(
        (datetime.now(timezone.utc) - timedelta(days=180)).date(),
        datetime.min.time(), tzinfo=timezone.utc,
    ).isoformat()
    _seed(cache_dir, "youtube_data", "search.list.by_channel",
          {"channel_id": "UC_quantpy", "max_results": 20,
           "published_after": cutoff},
          {"items": [
              {"id": {"videoId": "v_outlier"}},
              {"id": {"videoId": "v_normal"}},
          ]})
    # search.list by query (broad niche search)
    _seed(cache_dir, "youtube_data", "search.list.by_query",
          {"query": "algorithmic trading", "max_results": 20},
          {"items": [{"id": {"videoId": "v_outlier"}}]})
    # videos.list — note ordering is sorted(ids)
    _seed(cache_dir, "youtube_data", "videos.list",
          {"ids": sorted(["v_outlier", "v_normal"])},
          {"items": [
              {
                  "id": "v_outlier",
                  "snippet": {
                      "title": "I built a $1m algo trading bot",
                      "channelId": "UC_quantpy", "channelTitle": "QuantPy",
                      "publishedAt": "2026-03-15T10:00:00Z",
                      "description": "...", "tags": ["algo"],
                  },
                  "statistics": {"viewCount": "850000",
                                  "likeCount": "42000", "commentCount": "3500"},
                  "contentDetails": {"duration": "PT15M30S"},
              },
              {
                  "id": "v_normal",
                  "snippet": {"title": "Normal video", "channelId": "UC_quantpy",
                              "channelTitle": "QuantPy",
                              "publishedAt": "2026-04-01T10:00:00Z"},
                  "statistics": {"viewCount": "25000",
                                  "likeCount": "1000", "commentCount": "100"},
                  "contentDetails": {"duration": "PT10M00S"},
              },
          ]})
    # Trends
    _seed(cache_dir, "google_trends", "rising_queries",
          {"seed": "algorithmic trading", "geo": "US"},
          {"rising": [{"query": "ai trading bot", "value": 90}]})
    _seed(cache_dir, "google_trends", "interest_over_time",
          {"seed": "algorithmic trading", "geo": "US", "timeframe": "today 3-m"},
          {"points": [{"date": "2026-02-01", "value": v} for v in
                       [40, 45, 50, 55, 60, 65, 68, 72, 75, 78, 80, 82, 85]]})
    # Reddit
    recent_ts = time.time() - 3 * 3600
    _seed(cache_dir, "reddit", "rising",
          {"subreddit": "algotrading", "limit": 15},
          {"posts": [{"title": "I built a trading bot that makes money",
                      "subreddit": "algotrading", "upvotes": 300,
                      "comment_count": 50, "created_utc": recent_ts,
                      "permalink": "/r/algotrading/comments/abc/"}]})
    _seed(cache_dir, "reddit", "hot",
          {"subreddit": "algotrading", "limit": 10},
          {"posts": [{"title": "How do you backtest your bot",
                      "subreddit": "algotrading", "upvotes": 80,
                      "comment_count": 22,
                      "created_utc": time.time() - 8 * 3600,
                      "permalink": "/r/algotrading/comments/xyz/"}]})


class TestEndToEnd:
    def test_runs_offline_with_seeded_cache(self, cache_dir):
        _seed_full_run(cache_dir)
        result = research_niche(
            niche="algorithmic trading",
            seed_channels=["UC_quantpy"],
            subreddits=["algotrading"],
            top_n=3,
            provider=HeuristicProvider(),
        )
        assert isinstance(result, PipelineResult)
        assert result.niche == "algorithmic trading"
        assert len(result.raw.videos) == 2
        assert "UC_quantpy" in result.raw.channels
        assert result.raw.channels["UC_quantpy"].median_views_per_video > 0
        # 850k vs 25k baseline (median 437.5k) — only 850k qualifies if we used mean
        # but with the median(2 items) = midpoint, 850k / 437500 ≈ 1.94x → below 10x
        # The outlier here only triggers when the threshold's adjusted, so check that:
        # the test exercises the SIGNAL FLOW, not the threshold tuning.
        # We do assert ideas were synthesized and briefs generated.
        assert len(result.scored_ideas) > 0
        assert len(result.briefs) == len(result.scored_ideas)
        for brief in result.briefs:
            assert brief.hook
            assert len(brief.title_candidates) >= 1
            assert brief.scored_idea.total > 0

    def test_pipeline_handles_no_seed_channels(self, cache_dir):
        # Trends-only run still produces briefs from rising queries
        _seed(cache_dir, "google_trends", "rising_queries",
              {"seed": "algo trading", "geo": "US"},
              {"rising": [{"query": "trading bot tutorial", "value": 75}]})
        _seed(cache_dir, "google_trends", "interest_over_time",
              {"seed": "algo trading", "geo": "US",
               "timeframe": "today 3-m"}, {"points": []})

        result = research_niche(
            niche="algo trading", seed_channels=[],
            subreddits=[], top_n=2,
            provider=HeuristicProvider(),
        )
        # No outliers (no videos), but trend-first ideas should fire
        assert len(result.scored_ideas) > 0

    def test_pipeline_handles_no_sources_available(self, cache_dir, monkeypatch):
        # Nothing seeded; no live API keys. Pipeline should degrade gracefully.
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        result = research_niche(
            niche="esoteric niche", seed_channels=["UC_unknown"],
            subreddits=["unknown_sub"], top_n=3,
            provider=HeuristicProvider(),
        )
        # No raw signals collected, but the pipeline ran to completion.
        assert isinstance(result, PipelineResult)
        assert result.raw.videos == []
        assert result.scored_ideas == []
        assert result.briefs == []


class TestRenderReport:
    def test_includes_section_headers(self, cache_dir):
        _seed_full_run(cache_dir)
        result = research_niche(
            niche="algo trading", seed_channels=["UC_quantpy"],
            subreddits=["algotrading"], top_n=2,
            provider=HeuristicProvider(),
        )
        md = render_report(result)
        assert "# YouTube content research" in md
        assert "## Signal summary" in md
        assert "Briefs" in md
        # The first brief's topic should appear
        if result.briefs:
            assert result.briefs[0].scored_idea.idea.topic[:30] in md
