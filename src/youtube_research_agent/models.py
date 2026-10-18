"""Data models for the YouTube research agent.

Every model is a plain dataclass — no business logic. Analysis lives in
its own module. Models are JSON-serialisable via `to_dict()` so any of
them can be cached on disk.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------


@dataclass
class Channel:
    id: str
    title: str
    subscriber_count: int
    video_count: int
    view_count: int                            # lifetime
    median_views_per_video: float = 0.0        # the "baseline" outliers exceed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Video:
    id: str
    title: str
    channel_id: str
    channel_title: str
    published_at: str                          # ISO 8601
    view_count: int
    like_count: int
    comment_count: int
    duration_seconds: int = 0
    description: str = ""
    tags: list[str] = field(default_factory=list)
    # derived
    days_since_publish: float = 0.0
    views_per_day: float = 0.0
    like_ratio: float = 0.0                    # likes / views, capped
    comment_ratio: float = 0.0                 # comments / views, capped
    is_short: bool = False                     # duration < 60s

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Trend signals
# ---------------------------------------------------------------------------


@dataclass
class TrendQuery:
    """A query whose search interest is moving — from Google Trends, YT
    autocomplete velocity, or similar source."""
    query: str
    source: str                                # "google_trends" | "yt_autocomplete" | ...
    interest_now: float                        # 0-100 normalised
    interest_30d_ago: float
    interest_90d_ago: float
    rising: bool = False                       # source flagged as "rising"

    @property
    def velocity_30d(self) -> float:
        """Percent change in interest over the last 30 days."""
        if self.interest_30d_ago <= 0:
            return float("inf") if self.interest_now > 0 else 0.0
        return (self.interest_now - self.interest_30d_ago) / self.interest_30d_ago

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RedditSignal:
    """A subreddit post / topic showing acceleration."""
    title: str
    subreddit: str
    upvotes: int
    comment_count: int
    hours_since_post: float
    url: str = ""

    @property
    def upvote_velocity(self) -> float:
        """Upvotes per hour — the headline acceleration metric."""
        if self.hours_since_post <= 0:
            return float(self.upvotes)
        return self.upvotes / self.hours_since_post

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Outlier + scored idea
# ---------------------------------------------------------------------------


@dataclass
class Outlier:
    """A video whose views materially exceed its channel's baseline.

    multiplier = view_count / channel.median_views_per_video. >=10 is the
    standard 1-of-10 threshold (see Jenny Hoyos framework).
    """
    video: Video
    channel: Channel
    multiplier: float
    rank_in_niche: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "video": self.video.to_dict(),
            "channel": self.channel.to_dict(),
            "multiplier": self.multiplier,
            "rank_in_niche": self.rank_in_niche,
        }


@dataclass
class Idea:
    """A content idea before scoring or brief generation.

    The pipeline synthesises an Idea from the strongest available signal
    (an outlier video, a rising trend query, a hot Reddit thread, or a
    combination). The Idea carries everything the scorer + brief
    generator need.
    """
    topic: str                                 # human-readable handle for the idea
    angle: str                                 # the specific take / framing
    inspiration_outliers: list[Outlier] = field(default_factory=list)
    inspiration_trends: list[TrendQuery] = field(default_factory=list)
    inspiration_reddit: list[RedditSignal] = field(default_factory=list)
    niche: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "angle": self.angle,
            "niche": self.niche,
            "inspiration_outliers": [o.to_dict() for o in self.inspiration_outliers],
            "inspiration_trends": [t.to_dict() for t in self.inspiration_trends],
            "inspiration_reddit": [r.to_dict() for r in self.inspiration_reddit],
        }


# ---------------------------------------------------------------------------
# Scored idea + content brief
# ---------------------------------------------------------------------------


@dataclass
class CategoryScore:
    name: str
    raw: float                                 # 0-10
    weight: float                              # category weight from rubric
    rationale: str = ""

    @property
    def weighted(self) -> float:
        return self.raw * self.weight / 10.0   # contribution to total (max = weight)


@dataclass
class ScoredIdea:
    idea: Idea
    total: float                               # 0-100
    categories: list[CategoryScore] = field(default_factory=list)

    def __lt__(self, other: "ScoredIdea") -> bool:
        return self.total < other.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "idea": self.idea.to_dict(),
            "total": self.total,
            "categories": [
                {"name": c.name, "raw": c.raw, "weight": c.weight,
                 "weighted": c.weighted, "rationale": c.rationale}
                for c in self.categories
            ],
        }


@dataclass
class ContentBrief:
    """The final deliverable — what a producer needs to greenlight a video."""
    scored_idea: ScoredIdea
    hook: str                                  # 1-line cold-open promise
    title_candidates: list[str] = field(default_factory=list)
    thumbnail_concept: str = ""
    outline: list[str] = field(default_factory=list)
    retention_anchors: list[str] = field(default_factory=list)
    predicted_audience: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "scored_idea": self.scored_idea.to_dict(),
            "hook": self.hook,
            "title_candidates": self.title_candidates,
            "thumbnail_concept": self.thumbnail_concept,
            "outline": self.outline,
            "retention_anchors": self.retention_anchors,
            "predicted_audience": self.predicted_audience,
            "generated_at": self.generated_at,
        }

    def to_markdown(self) -> str:
        """Render as a single markdown brief — what gets written to output/."""
        s = self.scored_idea
        lines: list[str] = [
            f"## {s.idea.topic}",
            "",
            f"**Angle:** {s.idea.angle}",
            f"**Score:** {s.total:.1f} / 100",
            "",
            f"**Hook:** {self.hook}",
            "",
            "### Title candidates",
        ]
        for t in self.title_candidates:
            lines.append(f"- {t}")
        lines += ["", "### Thumbnail concept", self.thumbnail_concept, ""]
        lines.append("### Outline")
        for i, beat in enumerate(self.outline, 1):
            lines.append(f"{i}. {beat}")
        lines += ["", "### Retention anchors"]
        for a in self.retention_anchors:
            lines.append(f"- {a}")
        lines += ["", f"**Predicted audience:** {self.predicted_audience}", ""]
        lines.append("### Score breakdown")
        lines.append("")
        lines.append("| Category | Raw | Weight | Contribution | Why |")
        lines.append("|---|---|---|---|---|")
        for c in s.categories:
            lines.append(
                f"| {c.name} | {c.raw:.1f} | {c.weight:.0f} | "
                f"{c.weighted:.1f} | {c.rationale} |"
            )
        lines.append("")
        if s.idea.inspiration_outliers:
            lines.append("### Outlier inspiration")
            for o in s.idea.inspiration_outliers[:3]:
                lines.append(
                    f"- *{o.video.title}* by **{o.video.channel_title}** — "
                    f"{o.video.view_count:,} views ({o.multiplier:.1f}× channel baseline)"
                )
            lines.append("")
        return "\n".join(lines)
