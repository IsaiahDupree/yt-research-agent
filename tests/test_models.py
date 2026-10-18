"""Models — dataclass shape + serialisation."""

from youtube_research_agent.models import (
    CategoryScore, Channel, ContentBrief, Idea, Outlier, RedditSignal,
    ScoredIdea, TrendQuery, Video,
)


def make_video(**overrides) -> Video:
    base = dict(
        id="v1", title="A great video", channel_id="ch1", channel_title="Channel",
        published_at="2026-04-01T00:00:00Z", view_count=100_000,
        like_count=5_000, comment_count=500,
    )
    base.update(overrides)
    return Video(**base)


def make_channel(**overrides) -> Channel:
    base = dict(id="ch1", title="Channel", subscriber_count=10_000,
                video_count=50, view_count=1_000_000, median_views_per_video=5_000)
    base.update(overrides)
    return Channel(**base)


def make_idea() -> Idea:
    v = make_video()
    ch = make_channel()
    o = Outlier(video=v, channel=ch, multiplier=20.0)
    t = TrendQuery(query="algo trading bot", source="google_trends",
                   interest_now=80.0, interest_30d_ago=40.0, interest_90d_ago=20.0,
                   rising=True)
    r = RedditSignal(title="I built a bot",
                     subreddit="algotrading", upvotes=200, comment_count=50,
                     hours_since_post=4.0)
    return Idea(topic="Algo trading bot tutorial", angle="From scratch in 10 minutes",
                inspiration_outliers=[o], inspiration_trends=[t],
                inspiration_reddit=[r], niche="algorithmic trading")


class TestVideoModel:
    def test_to_dict_round_trip(self):
        v = make_video()
        d = v.to_dict()
        assert d["id"] == "v1"
        assert d["view_count"] == 100_000

    def test_is_short_defaults_false(self):
        assert make_video().is_short is False


class TestTrendQuery:
    def test_velocity_normal(self):
        t = TrendQuery(query="x", source="google_trends",
                       interest_now=80.0, interest_30d_ago=40.0, interest_90d_ago=20.0)
        assert t.velocity_30d == 1.0

    def test_velocity_zero_baseline(self):
        t = TrendQuery(query="x", source="google_trends",
                       interest_now=50.0, interest_30d_ago=0.0, interest_90d_ago=0.0)
        assert t.velocity_30d == float("inf")

    def test_velocity_flat(self):
        t = TrendQuery(query="x", source="google_trends",
                       interest_now=50.0, interest_30d_ago=50.0, interest_90d_ago=50.0)
        assert t.velocity_30d == 0.0


class TestRedditSignal:
    def test_upvote_velocity(self):
        r = RedditSignal(title="x", subreddit="y", upvotes=100,
                         comment_count=10, hours_since_post=2.0)
        assert r.upvote_velocity == 50.0

    def test_upvote_velocity_zero_hours_falls_back_to_upvotes(self):
        r = RedditSignal(title="x", subreddit="y", upvotes=100,
                         comment_count=10, hours_since_post=0)
        assert r.upvote_velocity == 100.0


class TestContentBriefMarkdown:
    def test_markdown_includes_score_breakdown(self):
        idea = make_idea()
        scored = ScoredIdea(idea=idea, total=72.5, categories=[
            CategoryScore(name="audience_demand", raw=8.0, weight=18.0, rationale="solid"),
            CategoryScore(name="outlier_proof", raw=9.0, weight=16.0, rationale="20x"),
        ])
        brief = ContentBrief(
            scored_idea=scored,
            hook="Watch a bot make $100 in 10 minutes",
            title_candidates=["I Built a Trading Bot", "AI Trades While I Sleep"],
            thumbnail_concept="Face on left, terminal on right",
            outline=["Cold open", "Background", "Demo", "Result", "CTA"],
            retention_anchors=["30s pattern interrupt", "midpoint reveal", "end CTA"],
            predicted_audience="Developers curious about trading",
        )
        md = brief.to_markdown()
        assert "## " in md and "Algo trading bot tutorial" in md
        assert "Score:** 72.5" in md
        assert "audience_demand" in md
        assert "20x" in md   # rationale propagates
        assert "Outlier inspiration" in md
