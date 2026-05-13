"""Trend-signal ranking.

Combines trend signals (Google Trends rising queries, Reddit topic
acceleration, etc.) into a single ranked list. The ranking uses two
axes:

  - lead_time:  how early does this signal fire (0-1; higher = earlier)
  - reliability: how often does it convert into actual interest (0-1)

See docs/SCORING_RUBRIC.md for sources behind each weight.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import RedditSignal, TrendQuery


# Lead-time × reliability for each source. Cited; tunable.
# These are operator-calibratable — see SCORING_RUBRIC.md.
SOURCE_PROFILE = {
    "google_trends":    {"lead_time": 0.55, "reliability": 0.65},
    "yt_autocomplete":  {"lead_time": 0.70, "reliability": 0.55},
    "reddit":           {"lead_time": 0.80, "reliability": 0.45},
    "tiktok":           {"lead_time": 0.85, "reliability": 0.40},  # not in MVP
    "comment_mining":   {"lead_time": 0.60, "reliability": 0.70},
}


@dataclass
class RankedSignal:
    source: str
    query: str
    velocity: float           # source-specific velocity metric, normalised 0..1
    lead_time: float          # how early this fires
    reliability: float        # how often it converts
    composite: float          # final ranking score 0..1

    def to_dict(self) -> dict:
        return {
            "source": self.source, "query": self.query, "velocity": self.velocity,
            "lead_time": self.lead_time, "reliability": self.reliability,
            "composite": self.composite,
        }


def _normalize_velocity(value: float, soft_cap: float) -> float:
    """Squash a raw velocity into 0..1 using a soft cap.

    Below the cap we scale linearly; above the cap we saturate. Avoids
    one runaway signal dominating the ranking.
    """
    if value <= 0:
        return 0.0
    return min(value / soft_cap, 1.0)


def rank_trends(
    trends: list[TrendQuery],
    reddit: list[RedditSignal],
) -> list[RankedSignal]:
    """Combine trend + reddit signals into a single ranked list.

    Composite score = (lead_time × reliability × velocity). Higher is
    a stronger signal that the topic is worth exploring NOW.
    """
    out: list[RankedSignal] = []

    for t in trends:
        # 100% velocity over 30 days is the soft cap for trends data
        v = _normalize_velocity(t.velocity_30d, soft_cap=1.0)
        profile = SOURCE_PROFILE.get(t.source, SOURCE_PROFILE["google_trends"])
        out.append(RankedSignal(
            source=t.source, query=t.query, velocity=v,
            lead_time=profile["lead_time"], reliability=profile["reliability"],
            composite=v * profile["lead_time"] * profile["reliability"],
        ))

    for r in reddit:
        # 50 upvotes/hour is a strong signal; saturate there
        v = _normalize_velocity(r.upvote_velocity, soft_cap=50.0)
        profile = SOURCE_PROFILE["reddit"]
        out.append(RankedSignal(
            source="reddit", query=r.title, velocity=v,
            lead_time=profile["lead_time"], reliability=profile["reliability"],
            composite=v * profile["lead_time"] * profile["reliability"],
        ))

    out.sort(key=lambda s: s.composite, reverse=True)
    return out
