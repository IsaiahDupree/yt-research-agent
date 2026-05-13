"""Default scoring weights.

Override per niche by constructing a custom Rubric. See
docs/SCORING_RUBRIC.md for the citation behind each weight.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Rubric:
    audience_demand: float = 18.0
    trend_velocity: float = 14.0
    outlier_proof: float = 16.0
    search_potential: float = 10.0
    emotional_intensity: float = 8.0
    format_fit: float = 8.0
    competition_level: float = 8.0
    production_difficulty: float = 10.0
    monetization_alignment: float = 8.0

    @property
    def total_weight(self) -> float:
        return (
            self.audience_demand + self.trend_velocity + self.outlier_proof
            + self.search_potential + self.emotional_intensity + self.format_fit
            + self.competition_level + self.production_difficulty
            + self.monetization_alignment
        )

    def as_pairs(self) -> list[tuple[str, float]]:
        return [
            ("audience_demand", self.audience_demand),
            ("trend_velocity", self.trend_velocity),
            ("outlier_proof", self.outlier_proof),
            ("search_potential", self.search_potential),
            ("emotional_intensity", self.emotional_intensity),
            ("format_fit", self.format_fit),
            ("competition_level", self.competition_level),
            ("production_difficulty", self.production_difficulty),
            ("monetization_alignment", self.monetization_alignment),
        ]


DEFAULT_RUBRIC = Rubric()
