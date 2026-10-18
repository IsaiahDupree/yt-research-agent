"""Outlier detection.

A video is an "outlier" when its view count materially exceeds its
channel's baseline. The classic threshold is 10x (Jenny Hoyos's
"1 of 10" framework) but the function is parameterisable.

The function is pure: given a list of videos + their channels, it
returns the outliers ranked by multiplier.
"""

from __future__ import annotations

from statistics import median

from ..models import Channel, Outlier, Video


DEFAULT_THRESHOLD = 10.0


def channel_baseline(videos: list[Video]) -> float:
    """Median views across a channel's recent uploads. The median is
    more robust than the mean against viral spikes."""
    if not videos:
        return 0.0
    return float(median(v.view_count for v in videos))


def detect_outliers(
    videos: list[Video],
    channels: dict[str, Channel],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[Outlier]:
    """Return videos whose views exceed `threshold × channel_baseline`.

    `channels` is keyed by `channel_id`. If a channel's
    `median_views_per_video` is zero (new channel, no history), the
    video is included with `multiplier=inf` — a brand-new channel
    putting up real numbers is itself a signal.

    Outliers are returned sorted by multiplier desc, with
    `rank_in_niche` filled in.
    """
    out: list[Outlier] = []
    for v in videos:
        ch = channels.get(v.channel_id)
        if ch is None:
            continue
        baseline = ch.median_views_per_video
        if baseline <= 0:
            multiplier = float("inf") if v.view_count > 0 else 0.0
        else:
            multiplier = v.view_count / baseline
        if multiplier >= threshold:
            out.append(Outlier(video=v, channel=ch, multiplier=multiplier))
    out.sort(key=lambda o: o.multiplier, reverse=True)
    for i, o in enumerate(out, 1):
        o.rank_in_niche = i
    return out


def derive_view_velocity(videos: list[Video], now_iso: str | None = None) -> None:
    """Mutates the video list in place: fills `days_since_publish` and
    `views_per_day` from `published_at`. Idempotent."""
    from datetime import datetime, timezone

    if now_iso is None:
        now = datetime.now(timezone.utc)
    else:
        now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))

    for v in videos:
        try:
            published = datetime.fromisoformat(v.published_at.replace("Z", "+00:00"))
        except ValueError:
            v.days_since_publish = 0.0
            v.views_per_day = float(v.view_count)
            continue
        delta = now - published
        days = max(delta.total_seconds() / 86400.0, 0.0001)
        v.days_since_publish = days
        v.views_per_day = v.view_count / days


def derive_engagement_ratios(videos: list[Video]) -> None:
    """Mutates the video list in place: fills `like_ratio` and
    `comment_ratio`. Caps both at 1.0 to handle edge cases."""
    for v in videos:
        if v.view_count <= 0:
            v.like_ratio = 0.0
            v.comment_ratio = 0.0
            continue
        v.like_ratio = min(v.like_count / v.view_count, 1.0)
        v.comment_ratio = min(v.comment_count / v.view_count, 1.0)
