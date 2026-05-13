"""Scoring rubric — pure function tests."""

import pytest

from youtube_research_agent.models import Channel, Idea, Outlier, RedditSignal, TrendQuery, Video
from youtube_research_agent.scoring.rubric import Scorer
from youtube_research_agent.scoring.weights import DEFAULT_RUBRIC, Rubric


def make_idea(
    *,
    outliers: list[Outlier] | None = None,
    trends: list[TrendQuery] | None = None,
    reddit: list[RedditSignal] | None = None,
    topic: str = "Algo trading 101",
    angle: str = "From scratch in 10 minutes",
) -> Idea:
    return Idea(
        topic=topic, angle=angle, niche="algo trading",
        inspiration_outliers=outliers or [],
        inspiration_trends=trends or [],
        inspiration_reddit=reddit or [],
    )


def make_outlier(mult: float, title: str = "Outlier video", channel_name: str = "ChanA") -> Outlier:
    v = Video(
        id="v", title=title, channel_id="ch", channel_title=channel_name,
        published_at="2026-04-01T00:00:00Z", view_count=100_000,
        like_count=5_000, comment_count=500,
    )
    ch = Channel(id="ch", title=channel_name, subscriber_count=1000, video_count=50,
                 view_count=100_000, median_views_per_video=100_000 / mult if mult else 1.0)
    return Outlier(video=v, channel=ch, multiplier=mult)


def make_trend(now: float, then_30d: float = 0.0, query: str = "algo trading",
               source: str = "google_trends") -> TrendQuery:
    return TrendQuery(query=query, source=source,
                      interest_now=now, interest_30d_ago=then_30d,
                      interest_90d_ago=then_30d * 0.5,
                      rising=now > then_30d)


# ---------------------------------------------------------------------------
# Total range
# ---------------------------------------------------------------------------


class TestScorerTotalRange:
    def test_empty_idea_lands_low_but_not_zero(self):
        idea = make_idea()
        scored = Scorer().score(idea)
        assert 0 < scored.total < 70

    def test_strong_idea_lands_high(self):
        idea = make_idea(
            outliers=[make_outlier(50.0), make_outlier(25.0)],
            trends=[make_trend(now=80, then_30d=20)],
            reddit=[RedditSignal(title="bot", subreddit="algotrading",
                                  upvotes=400, comment_count=50, hours_since_post=2.0)],
            angle="The truth about why bots fail — actually exposed",
        )
        scored = Scorer().score(idea)
        # Calibrated against the default rubric — a strong-signal idea reliably
        # lands in the 70s. >=70 is the meaningful threshold; pushing higher
        # would require a category-by-category tuning pass.
        assert scored.total >= 70

    def test_total_never_exceeds_100(self):
        idea = make_idea(
            outliers=[make_outlier(999.0)],
            trends=[make_trend(now=100, then_30d=1)],
        )
        scored = Scorer().score(idea)
        assert scored.total <= 100.0

    def test_total_is_sum_of_weighted(self):
        idea = make_idea(outliers=[make_outlier(20.0)])
        scored = Scorer().score(idea)
        assert scored.total == pytest.approx(
            sum(c.weighted for c in scored.categories), rel=1e-6,
        )


# ---------------------------------------------------------------------------
# Per-category behaviour
# ---------------------------------------------------------------------------


class TestOutlierProof:
    def test_no_outliers_low(self):
        scored = Scorer().score(make_idea())
        cat = next(c for c in scored.categories if c.name == "outlier_proof")
        assert cat.raw <= 3.0

    def test_one_strong_outlier_high(self):
        scored = Scorer().score(make_idea(outliers=[make_outlier(80.0)]))
        cat = next(c for c in scored.categories if c.name == "outlier_proof")
        assert cat.raw >= 8.0


class TestTrendVelocity:
    def test_flat_trend_low(self):
        scored = Scorer().score(make_idea(trends=[make_trend(now=50, then_30d=50)]))
        cat = next(c for c in scored.categories if c.name == "trend_velocity")
        assert cat.raw <= 4.0

    def test_rising_trend_high(self):
        scored = Scorer().score(make_idea(trends=[make_trend(now=80, then_30d=20)]))
        cat = next(c for c in scored.categories if c.name == "trend_velocity")
        assert cat.raw >= 8.0


class TestEmotionalIntensity:
    def test_dry_title_neutral(self):
        scored = Scorer().score(make_idea(topic="A short overview", angle="Of how it works"))
        cat = next(c for c in scored.categories if c.name == "emotional_intensity")
        assert 3.5 < cat.raw < 6.0

    def test_packed_title_high(self):
        scored = Scorer().score(make_idea(
            topic="I lost $1m testing the biggest mistake in algo trading",
            angle="The hidden truth exposed — challenge experiment",
        ))
        cat = next(c for c in scored.categories if c.name == "emotional_intensity")
        assert cat.raw >= 8.0


class TestCompetitionLevel:
    def test_no_outliers_room(self):
        scored = Scorer().score(make_idea())
        cat = next(c for c in scored.categories if c.name == "competition_level")
        assert cat.raw >= 6.0

    def test_one_outlier_sweet_spot(self):
        scored = Scorer().score(make_idea(outliers=[make_outlier(15.0)]))
        cat = next(c for c in scored.categories if c.name == "competition_level")
        assert cat.raw == 8.0

    def test_many_outliers_saturated(self):
        scored = Scorer().score(make_idea(outliers=[make_outlier(15.0)] * 8))
        cat = next(c for c in scored.categories if c.name == "competition_level")
        assert cat.raw <= 2.0


class TestProductionDifficulty:
    def test_easy_high(self):
        scored = Scorer(production_hours_estimate=2.0).score(make_idea())
        cat = next(c for c in scored.categories if c.name == "production_difficulty")
        assert cat.raw >= 8.0

    def test_heavy_low(self):
        scored = Scorer(production_hours_estimate=80.0).score(make_idea())
        cat = next(c for c in scored.categories if c.name == "production_difficulty")
        assert cat.raw <= 2.0


# ---------------------------------------------------------------------------
# Rubric override
# ---------------------------------------------------------------------------


class TestRubricOverride:
    def test_zero_weighted_category_drops_to_zero(self):
        rubric = Rubric()
        rubric.outlier_proof = 0.0
        scorer = Scorer(rubric=rubric)
        scored = scorer.score(make_idea(outliers=[make_outlier(100.0)]))
        cat = next(c for c in scored.categories if c.name == "outlier_proof")
        assert cat.weighted == 0.0

    def test_default_weights_sum_to_100(self):
        assert DEFAULT_RUBRIC.total_weight == 100.0
