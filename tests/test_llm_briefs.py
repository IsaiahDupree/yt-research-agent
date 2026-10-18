"""Brief generator — pure tests using FakeProvider + HeuristicProvider."""

import pytest

from youtube_research_agent.llm.briefs import (
    _heuristic_brief, _parse_llm_json, generate_brief,
)
from youtube_research_agent.llm.provider import HeuristicProvider
from youtube_research_agent.models import (
    Channel, Idea, Outlier, RedditSignal, ScoredIdea, TrendQuery, Video, CategoryScore,
)


def make_scored() -> ScoredIdea:
    v = Video(id="v1", title="I built a $1m algo bot", channel_id="ch1",
              channel_title="QuantPy", published_at="2026-04-01T0:00:00Z",
              view_count=850_000, like_count=42_000, comment_count=3_500)
    ch = Channel(id="ch1", title="QuantPy", subscriber_count=120_000,
                 video_count=80, view_count=20_000_000, median_views_per_video=30_000)
    o = Outlier(video=v, channel=ch, multiplier=28.3)
    t = TrendQuery(query="ai trading bot", source="google_trends",
                   interest_now=82.0, interest_30d_ago=45.0,
                   interest_90d_ago=20.0, rising=True)
    r = RedditSignal(title="I lost $5k to a bot", subreddit="algotrading",
                     upvotes=620, comment_count=200, hours_since_post=3.0)
    idea = Idea(topic="Why algo bots actually lose",
                angle="Three failure modes nobody documents",
                niche="algorithmic trading",
                inspiration_outliers=[o], inspiration_trends=[t],
                inspiration_reddit=[r])
    return ScoredIdea(
        idea=idea, total=78.4,
        categories=[
            CategoryScore("audience_demand", 8.0, 18.0, "high"),
            CategoryScore("outlier_proof", 8.5, 16.0, "28x"),
        ],
    )


class FakeJSONProvider:
    name = "fake-json"

    def __init__(self, text: str) -> None:
        self._text = text

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        return self._text


# ---------------------------------------------------------------------------
# JSON parser tolerance
# ---------------------------------------------------------------------------


class TestParseLLMJson:
    def test_plain_json(self):
        assert _parse_llm_json('{"a": 1}') == {"a": 1}

    def test_markdown_fenced(self):
        assert _parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_with_preamble_garbage(self):
        text = 'Sure! Here is the JSON:\n\n{"hook": "h"}\n\nLet me know!'
        assert _parse_llm_json(text) == {"hook": "h"}

    def test_unrecoverable_returns_none(self):
        assert _parse_llm_json("not json at all") is None


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------


class TestHeuristicBrief:
    def test_produces_structurally_valid_brief(self):
        out = _heuristic_brief(make_scored())
        assert isinstance(out["hook"], str) and len(out["hook"]) > 20
        assert len(out["title_candidates"]) == 3
        assert len(out["outline"]) == 5
        assert len(out["retention_anchors"]) == 3
        assert "thumbnail_concept" in out
        assert "predicted_audience" in out


# ---------------------------------------------------------------------------
# generate_brief with each provider type
# ---------------------------------------------------------------------------


class TestGenerateBrief:
    def test_heuristic_provider_uses_fallback(self):
        brief = generate_brief(make_scored(), provider=HeuristicProvider())
        assert brief.hook
        assert len(brief.title_candidates) == 3
        assert len(brief.outline) == 5

    def test_llm_provider_with_valid_json(self):
        provider = FakeJSONProvider('''
        {
          "hook": "Watch this bot make $100",
          "title_candidates": ["A", "B", "C"],
          "thumbnail_concept": "Face, screen, text",
          "outline": ["1", "2", "3", "4", "5"],
          "retention_anchors": ["x", "y", "z"],
          "predicted_audience": "Devs"
        }
        ''')
        brief = generate_brief(make_scored(), provider=provider)
        assert brief.hook == "Watch this bot make $100"
        assert brief.title_candidates == ["A", "B", "C"]
        assert brief.outline == ["1", "2", "3", "4", "5"]
        assert brief.predicted_audience == "Devs"

    def test_llm_provider_with_garbage_falls_back_to_heuristic(self):
        provider = FakeJSONProvider("I'm sorry, I can't help with that.")
        brief = generate_brief(make_scored(), provider=provider)
        # heuristic kicks in — brief is still complete
        assert brief.hook
        assert len(brief.title_candidates) == 3

    def test_llm_provider_that_raises_falls_back(self):
        class Raising:
            name = "raising"
            def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
                raise RuntimeError("api down")
        brief = generate_brief(make_scored(), provider=Raising())
        assert brief.hook  # heuristic kicked in

    def test_brief_to_markdown_renders(self):
        brief = generate_brief(make_scored(), provider=HeuristicProvider())
        md = brief.to_markdown()
        assert "Why algo bots actually lose" in md
        assert "78.4" in md   # total score
        assert "Outlier inspiration" in md
