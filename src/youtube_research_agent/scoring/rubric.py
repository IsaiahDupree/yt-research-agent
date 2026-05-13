"""Idea scoring.

Pure function: Idea -> ScoredIdea. Each category returns 0-10; final
score = sum(weight_i × raw_i / 10).

The scorers are deliberately simple and inspectable. Override per
niche by subclassing and replacing any of the `_score_*` methods.
"""

from __future__ import annotations

from ..models import CategoryScore, Idea, ScoredIdea
from .weights import DEFAULT_RUBRIC, Rubric


class Scorer:
    """Default scorer. Each `_score_<category>` returns (raw_score, rationale)."""

    def __init__(self, rubric: Rubric | None = None,
                 production_hours_estimate: float = 8.0) -> None:
        self.rubric = rubric or DEFAULT_RUBRIC
        self.production_hours_estimate = production_hours_estimate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, idea: Idea) -> ScoredIdea:
        categories = [
            self._make("audience_demand", *self._score_audience_demand(idea)),
            self._make("trend_velocity", *self._score_trend_velocity(idea)),
            self._make("outlier_proof", *self._score_outlier_proof(idea)),
            self._make("search_potential", *self._score_search_potential(idea)),
            self._make("emotional_intensity", *self._score_emotional_intensity(idea)),
            self._make("format_fit", *self._score_format_fit(idea)),
            self._make("competition_level", *self._score_competition_level(idea)),
            self._make("production_difficulty", *self._score_production_difficulty(idea)),
            self._make("monetization_alignment", *self._score_monetization_alignment(idea)),
        ]
        total = sum(c.weighted for c in categories)
        return ScoredIdea(idea=idea, total=total, categories=categories)

    def _make(self, name: str, raw: float, rationale: str) -> CategoryScore:
        raw = max(0.0, min(raw, 10.0))
        weight = getattr(self.rubric, name)
        return CategoryScore(name=name, raw=raw, weight=weight, rationale=rationale)

    # ------------------------------------------------------------------
    # Category scorers — override these to specialise per niche
    # ------------------------------------------------------------------

    def _score_audience_demand(self, idea: Idea) -> tuple[float, str]:
        """Strongest trend signal × number of corroborating sources."""
        if not idea.inspiration_trends:
            return 4.0, "No trend signal; demand unknown."
        top = max(idea.inspiration_trends, key=lambda t: t.interest_now)
        raw = top.interest_now / 10.0   # Google Trends 0-100 → 0-10
        n_sources = (
            (1 if idea.inspiration_trends else 0)
            + (1 if idea.inspiration_reddit else 0)
            + (1 if idea.inspiration_outliers else 0)
        )
        bonus = (n_sources - 1) * 0.5   # +0.5 per extra corroborating source
        raw = min(raw + bonus, 10.0)
        return raw, f"Top trend `{top.query}` at interest={top.interest_now:.0f}; {n_sources} sources."

    def _score_trend_velocity(self, idea: Idea) -> tuple[float, str]:
        if not idea.inspiration_trends:
            return 4.0, "No trend signal; velocity unknown."
        velocities = [max(0.0, t.velocity_30d) for t in idea.inspiration_trends]
        if not velocities or max(velocities) == 0:
            return 3.0, "Flat or declining."
        top_v = max(velocities)
        # 100% growth in 30 days = strong; 200%+ saturates at 10
        raw = min(top_v * 5.0, 10.0)
        return raw, f"Top 30d velocity: {top_v * 100:.0f}%."

    def _score_outlier_proof(self, idea: Idea) -> tuple[float, str]:
        if not idea.inspiration_outliers:
            return 2.0, "No outlier proof — no other channel has done this in this niche."
        top = max(idea.inspiration_outliers, key=lambda o: o.multiplier)
        # 10x = neutral-positive, 50x = strong, 100x+ = exceptional
        raw = min((top.multiplier / 10.0), 10.0) if top.multiplier != float("inf") else 9.0
        return raw, (f"Outlier proof: *{top.video.title[:60]}…* by "
                     f"{top.video.channel_title} ({top.multiplier:.1f}× baseline).")

    def _score_search_potential(self, idea: Idea) -> tuple[float, str]:
        if not idea.inspiration_trends:
            return 5.0, "Neutral — no search data."
        # Use the absolute interest level as a proxy for search potential
        top = max(idea.inspiration_trends, key=lambda t: t.interest_now)
        raw = top.interest_now / 10.0
        return raw, f"Search interest proxy: {top.interest_now:.0f}/100 for `{top.query}`."

    def _score_emotional_intensity(self, idea: Idea) -> tuple[float, str]:
        """Heuristic on the angle text — the LLM brief generator does
        the heavier lift on this one, but we score it crudely up front."""
        text = (idea.topic + " " + idea.angle).lower()
        emotional_markers = [
            # curiosity / surprise
            "actually", "real reason", "truth", "exposed", "hidden", "secret",
            # pain / fear
            "lost", "failed", "broke", "warning", "mistake",
            # awe / scale
            "$1m", "millions", "world", "biggest", "fastest", "first ever",
            # social
            "won", "vs", "challenge", "experiment", "tested",
        ]
        hits = sum(1 for m in emotional_markers if m in text)
        raw = min(4.0 + hits * 1.2, 10.0)
        return raw, f"{hits} emotional markers in angle text."

    def _score_format_fit(self, idea: Idea) -> tuple[float, str]:
        # In MVP we assume long-form; format_fit becomes important when
        # we add Shorts MVPing.
        return 6.0, "Neutral — long-form format assumed."

    def _score_competition_level(self, idea: Idea) -> tuple[float, str]:
        """Inverse-ish of outlier count. Many outliers in this niche on
        this exact angle = saturated."""
        n = len(idea.inspiration_outliers)
        if n == 0:
            return 7.0, "No proof, but also no saturation."
        if n == 1:
            return 8.0, "One outlier — sweet spot."
        if n <= 3:
            return 6.0, f"{n} outliers — proven but room remains."
        if n <= 6:
            return 4.0, f"{n} outliers — crowded; need a sharper angle."
        return 2.0, f"{n} outliers — saturated."

    def _score_production_difficulty(self, idea: Idea) -> tuple[float, str]:
        """Penalty for high estimated production cost. Default estimate
        is 8 hours (= neutral, raw=6). 16h ~= 4. 40h ~= 2.

        Override `production_hours_estimate` per idea if you know better.
        """
        hours = self.production_hours_estimate
        if hours <= 4:
            return 9.0, f"~{hours}h — easy."
        if hours <= 8:
            return 7.0, f"~{hours}h — manageable."
        if hours <= 16:
            return 5.0, f"~{hours}h — significant."
        if hours <= 40:
            return 3.0, f"~{hours}h — heavy."
        return 1.0, f"~{hours}h — production-monster."

    def _score_monetization_alignment(self, idea: Idea) -> tuple[float, str]:
        # MVP returns neutral. Override per channel/sponsor profile.
        return 6.0, "Neutral — operator override recommended."
