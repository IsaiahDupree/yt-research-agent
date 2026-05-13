"""Outlier detection — pure helpers."""

import pytest

from youtube_research_agent.analysis.outlier_detection import (
    channel_baseline, derive_engagement_ratios, derive_view_velocity, detect_outliers,
)
from youtube_research_agent.models import Channel, Video


def make_video(views: int, vid_id: str = "v", channel_id: str = "ch1",
               published_at: str = "2026-04-01T00:00:00Z") -> Video:
    return Video(
        id=vid_id, title=f"Video {vid_id}", channel_id=channel_id,
        channel_title="Channel", published_at=published_at, view_count=views,
        like_count=views // 50, comment_count=views // 500,
    )


def make_channel(baseline: float, ch_id: str = "ch1") -> Channel:
    return Channel(id=ch_id, title="Channel", subscriber_count=10_000,
                   video_count=50, view_count=1_000_000,
                   median_views_per_video=baseline)


class TestChannelBaseline:
    def test_median_of_views(self):
        videos = [make_video(1000), make_video(5000), make_video(10_000)]
        assert channel_baseline(videos) == 5000

    def test_empty(self):
        assert channel_baseline([]) == 0.0


class TestDetectOutliers:
    def test_threshold_default_is_10x(self):
        ch = make_channel(baseline=1000)
        videos = [
            make_video(2_000, "low"),
            make_video(10_001, "outlier"),
            make_video(50_000, "big-outlier"),
        ]
        out = detect_outliers(videos, {"ch1": ch})
        ids = [o.video.id for o in out]
        assert ids == ["big-outlier", "outlier"]
        assert out[0].multiplier == 50.0
        assert out[1].multiplier == pytest.approx(10.001)
        assert out[0].rank_in_niche == 1
        assert out[1].rank_in_niche == 2

    def test_threshold_custom(self):
        ch = make_channel(baseline=1000)
        videos = [make_video(3_000, "modest"), make_video(20_000, "loud")]
        out = detect_outliers(videos, {"ch1": ch}, threshold=2.0)
        assert {o.video.id for o in out} == {"modest", "loud"}

    def test_zero_baseline_treats_views_as_infinite_multiplier(self):
        ch = make_channel(baseline=0)
        videos = [make_video(100, "new")]
        out = detect_outliers(videos, {"ch1": ch})
        assert len(out) == 1
        assert out[0].multiplier == float("inf")

    def test_missing_channel_skipped(self):
        ch = make_channel(baseline=1000, ch_id="ch1")
        # Video references ch99 which isn't in the channels dict
        videos = [make_video(50_000, "orphan", channel_id="ch99")]
        out = detect_outliers(videos, {"ch1": ch})
        assert out == []


class TestDeriveViewVelocity:
    def test_basic(self):
        v = make_video(100_000, published_at="2026-04-01T00:00:00Z")
        derive_view_velocity([v], now_iso="2026-04-11T00:00:00Z")
        assert v.days_since_publish == pytest.approx(10.0)
        assert v.views_per_day == pytest.approx(10_000.0)

    def test_invalid_iso_falls_back_safely(self):
        v = make_video(100, published_at="garbage")
        derive_view_velocity([v], now_iso="2026-04-11T00:00:00Z")
        assert v.days_since_publish == 0.0
        assert v.views_per_day == 100.0


class TestDeriveEngagement:
    def test_ratios(self):
        v = make_video(10_000)
        v.like_count = 500
        v.comment_count = 100
        derive_engagement_ratios([v])
        assert v.like_ratio == pytest.approx(0.05)
        assert v.comment_ratio == pytest.approx(0.01)

    def test_zero_views_safe(self):
        v = make_video(0)
        derive_engagement_ratios([v])
        assert v.like_ratio == 0.0
        assert v.comment_ratio == 0.0
