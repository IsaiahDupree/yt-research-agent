"""Content brief generator.

Given a ScoredIdea, generate a ContentBrief (hook + titles + thumbnail
concept + outline + retention anchors + audience).

Two paths:
  1. With an LLM provider — high-quality narrative copy.
  2. Without (HeuristicProvider) — structurally-valid fallback derived
     from the idea's own data. Lower quality but always works.

The function is deterministic given the inputs + provider.
"""

from __future__ import annotations

import json

from ..models import ContentBrief, Idea, ScoredIdea
from .provider import HeuristicProvider, LLMProvider, get_provider


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

BRIEF_PROMPT = """\
You are a YouTube content strategist. Given a content idea with outlier
proof and trend signals, write a production brief.

Return STRICT JSON only (no commentary, no markdown fences). Schema:

{{
  "hook": "<1 sentence cold-open promise>",
  "title_candidates": ["<title1>", "<title2>", "<title3>"],
  "thumbnail_concept": "<2-3 sentences: what's in frame, face expression, text overlay>",
  "outline": ["<beat1>", "<beat2>", "<beat3>", "<beat4>", "<beat5>"],
  "retention_anchors": [
    "<re-engagement trigger near 30s>",
    "<re-engagement trigger at midpoint>",
    "<closing trigger that earns the CTA>"
  ],
  "predicted_audience": "<1 sentence on who this hits hardest>"
}}

Context:

NICHE: {niche}
IDEA TOPIC: {topic}
SPECIFIC ANGLE: {angle}

OUTLIER PROOF (videos in this niche that broke baseline):
{outliers}

TREND SIGNALS:
{trends}

REDDIT SIGNALS:
{reddit}

SCORE BREAKDOWN (operator's rubric):
{score_breakdown}

Style notes:
- Hook should be a *concrete promise*, not "in this video we'll explore"
- Titles should be ≤60 chars; vary length (one short, one medium, one long)
- Thumbnail concept must specify: subject placement, facial expression,
  any on-frame text. Avoid stock-photo descriptions.
- Outline beats are chapter markers a producer can shoot against.
- Retention anchors are *specific moments*, not "stay tuned!"
- Predicted audience names a persona, not a demographic. "Devs who hate
  Excel" beats "developers aged 25-40".
"""


def _fmt_outliers(idea: Idea) -> str:
    if not idea.inspiration_outliers:
        return "(none — this idea isn't outlier-proven; consider it experimental.)"
    lines = []
    for o in idea.inspiration_outliers[:5]:
        lines.append(
            f"- '{o.video.title}' by {o.video.channel_title}: "
            f"{o.video.view_count:,} views ({o.multiplier:.1f}x channel baseline)"
        )
    return "\n".join(lines)


def _fmt_trends(idea: Idea) -> str:
    if not idea.inspiration_trends:
        return "(none)"
    lines = []
    for t in idea.inspiration_trends[:5]:
        lines.append(
            f"- '{t.query}' ({t.source}): interest now={t.interest_now:.0f}, "
            f"30d ago={t.interest_30d_ago:.0f}, rising={t.rising}"
        )
    return "\n".join(lines)


def _fmt_reddit(idea: Idea) -> str:
    if not idea.inspiration_reddit:
        return "(none)"
    lines = []
    for r in idea.inspiration_reddit[:5]:
        lines.append(
            f"- '{r.title}' on r/{r.subreddit}: "
            f"{r.upvotes} upvotes / {r.hours_since_post:.1f}h "
            f"= {r.upvote_velocity:.0f}/hr"
        )
    return "\n".join(lines)


def _fmt_score(scored: ScoredIdea) -> str:
    return "\n".join(
        f"- {c.name}: {c.raw:.1f}/10 (weight {c.weight:.0f}) — {c.rationale}"
        for c in scored.categories
    )


def _parse_llm_json(text: str) -> dict | None:
    """Tolerant JSON parse — strips markdown fences and trailing junk."""
    text = text.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fence
        text = text.split("```")[1] if len(text.split("```")) >= 3 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract the first {...} block
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _heuristic_brief(scored: ScoredIdea) -> dict:
    """Structured fallback when no LLM is available.

    Output is grammatical and useful but obviously template-driven.
    A producer reading it will recognise the placeholders. Good enough
    to ship a runnable pipeline; not good enough for content as-is.
    """
    idea = scored.idea
    top_outlier = (idea.inspiration_outliers[0].video.title
                   if idea.inspiration_outliers else None)
    top_trend = (idea.inspiration_trends[0].query
                 if idea.inspiration_trends else None)

    if top_outlier and top_trend:
        hook = (f"There is a way to do {idea.angle.lower()} that almost "
                f"nobody talks about — and it is showing up in {top_trend}.")
    elif top_outlier:
        hook = (f"Here is exactly how to do {idea.angle.lower()} — and "
                f"why one channel just got {idea.inspiration_outliers[0].multiplier:.0f}× "
                f"their normal views doing it.")
    else:
        hook = f"Here is what {idea.topic} actually looks like — start to finish."

    titles = [
        idea.topic,
        f"How to {idea.angle}",
        f"{idea.topic} — what nobody tells you",
    ]

    thumbnail = (
        f"Subject left of frame, face shows controlled surprise. "
        f"Right side shows a single screen artifact related to '{idea.topic}'. "
        f"Bold 3-word overlay top-right that contradicts the obvious framing."
    )

    outline = [
        f"Cold open: state the promise about '{idea.topic}' in one sentence",
        "Context: why this matters now (cite the trend signal or outlier)",
        f"Demonstration: show {idea.angle} happening, step by step",
        "Result: the unexpected detail that justifies the hook",
        "Close: one-sentence CTA + the next-logical-question",
    ]

    retention_anchors = [
        "30s: pattern-interrupt — change subject or location to reset attention",
        "Midpoint: surface the result a beat before they expect it",
        "End: tease the next-question the audience already wants answered",
    ]

    predicted_audience = (
        f"People searching for '{top_trend}' who already know basics "
        f"and want to see it done concretely."
        if top_trend
        else f"Operators in {idea.niche} who have read about this but never seen it executed."
    )

    return {
        "hook": hook,
        "title_candidates": titles,
        "thumbnail_concept": thumbnail,
        "outline": outline,
        "retention_anchors": retention_anchors,
        "predicted_audience": predicted_audience,
    }


def generate_brief(scored: ScoredIdea,
                   provider: LLMProvider | None = None) -> ContentBrief:
    """Generate a ContentBrief from a ScoredIdea.

    With an LLM provider: prompts the model and parses JSON.
    Without (or on parse failure): falls back to a heuristic brief.
    """
    provider = provider or get_provider()
    payload: dict | None = None

    if not isinstance(provider, HeuristicProvider):
        prompt = BRIEF_PROMPT.format(
            niche=scored.idea.niche or "(unspecified)",
            topic=scored.idea.topic,
            angle=scored.idea.angle,
            outliers=_fmt_outliers(scored.idea),
            trends=_fmt_trends(scored.idea),
            reddit=_fmt_reddit(scored.idea),
            score_breakdown=_fmt_score(scored),
        )
        try:
            text = provider.complete(prompt)
            payload = _parse_llm_json(text)
        except Exception:
            payload = None

    if payload is None:
        payload = _heuristic_brief(scored)

    return ContentBrief(
        scored_idea=scored,
        hook=payload.get("hook", ""),
        title_candidates=list(payload.get("title_candidates", [])),
        thumbnail_concept=payload.get("thumbnail_concept", ""),
        outline=list(payload.get("outline", [])),
        retention_anchors=list(payload.get("retention_anchors", [])),
        predicted_audience=payload.get("predicted_audience", ""),
    )
