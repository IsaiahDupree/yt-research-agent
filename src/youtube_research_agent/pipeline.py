"""Pipeline orchestrator.

`research_niche()` is the top-level entry point. Given a niche and seed
channels, it pulls signals from the configured sources, detects
outliers, ranks trends, synthesizes ideas, scores them, generates
briefs for the top N, and returns the briefs.

Every step is a function call; the orchestrator just glues them. If a
source is unavailable (missing key, missing dep, rate-limited), the
pipeline drops that signal and keeps going — degradation is graceful.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .analysis.outlier_detection import (
    derive_engagement_ratios, derive_view_velocity, detect_outliers,
)
from .analysis.trend_signals import RankedSignal, rank_trends
from .llm.briefs import generate_brief
from .llm.provider import LLMProvider, get_provider
from .models import (
    Channel, ContentBrief, Idea, Outlier, RedditSignal, ScoredIdea,
    TrendQuery, Video,
)
from .scoring.rubric import Scorer
from .scoring.weights import Rubric
from .sources.google_trends import GoogleTrendsSource
from .sources.reddit import RedditSource
from .sources.youtube_data import YouTubeDataSource


log = logging.getLogger(__name__)


@dataclass
class RawSignals:
    videos: list[Video] = field(default_factory=list)
    channels: dict[str, Channel] = field(default_factory=dict)
    trends: list[TrendQuery] = field(default_factory=list)
    reddit: list[RedditSignal] = field(default_factory=list)


@dataclass
class PipelineResult:
    niche: str
    raw: RawSignals
    outliers: list[Outlier]
    ranked_trends: list[RankedSignal]
    scored_ideas: list[ScoredIdea]
    briefs: list[ContentBrief]


# ---------------------------------------------------------------------------
# Source collection
# ---------------------------------------------------------------------------


def collect_signals(
    niche: str,
    seed_channels: list[str],
    *,
    subreddits: list[str] | None = None,
    youtube: YouTubeDataSource | None = None,
    trends: GoogleTrendsSource | None = None,
    reddit: RedditSource | None = None,
    max_videos_per_channel: int = 20,
) -> RawSignals:
    """Pull raw signals from every available source. Degrades gracefully."""
    out = RawSignals()

    # ---- YouTube ----
    yt = youtube or YouTubeDataSource()
    try:
        channels = yt.get_channels(seed_channels) if seed_channels else []
        out.channels = {c.id: c for c in channels}
        all_video_ids: list[str] = []
        for ch_id in out.channels:
            ids = yt.recent_videos_by_channel(ch_id,
                                              max_results=max_videos_per_channel)
            all_video_ids.extend(ids)
        # Free-text search adds breadth beyond the seed channels
        all_video_ids.extend(yt.search_videos(niche, max_results=20))
        # Dedupe while preserving order
        seen: set[str] = set()
        dedup = [v for v in all_video_ids if not (v in seen or seen.add(v))]
        if dedup:
            out.videos = yt.get_videos(dedup)
        # Hydrate channel baselines from the recent-video sample
        videos_by_channel: dict[str, list[Video]] = {}
        for v in out.videos:
            videos_by_channel.setdefault(v.channel_id, []).append(v)
        yt.hydrate_baselines(channels, videos_by_channel)
    except RuntimeError as e:
        log.warning("YouTube source unavailable: %s", e)

    # ---- Trends ----
    gt = trends or GoogleTrendsSource()
    try:
        out.trends.extend(gt.rising_queries(niche))
        snap = gt.interest_snapshot(niche)
        if snap:
            out.trends.append(snap)
    except RuntimeError as e:
        log.warning("Trends source unavailable: %s", e)
    except Exception as e:    # pytrends is famously flaky
        log.warning("Trends source error: %s", e)

    # ---- Reddit ----
    rd = reddit or RedditSource()
    for sub in (subreddits or []):
        try:
            out.reddit.extend(rd.rising_posts(sub, limit=15))
            out.reddit.extend(rd.hot_posts(sub, limit=10))
        except RuntimeError as e:
            log.warning("Reddit source unavailable for r/%s: %s", sub, e)
        except Exception as e:
            log.warning("Reddit error for r/%s: %s", sub, e)

    # Derive velocity + engagement ratios in-place
    derive_view_velocity(out.videos)
    derive_engagement_ratios(out.videos)
    return out


# ---------------------------------------------------------------------------
# Idea synthesis
# ---------------------------------------------------------------------------


def synthesize_ideas(
    niche: str,
    raw: RawSignals,
    outliers: list[Outlier],
    ranked_trends: list[RankedSignal],
) -> list[Idea]:
    """Build candidate ideas by combining the strongest available signals.

    Strategies:
      A. Outlier-first — each top outlier becomes one idea, with the
         strongest matching trend attached.
      B. Trend-first   — each rising trend with no matching outlier still
         becomes an idea (experimental, lower confidence).
      C. Reddit-first  — each high-velocity Reddit thread becomes an idea
         (pain-mining strategy).
    """
    ideas: list[Idea] = []
    used_topics: set[str] = set()

    # Strategy A: outlier-first
    for o in outliers[:10]:
        topic = o.video.title.strip()[:80]
        key = topic.lower()
        if key in used_topics:
            continue
        used_topics.add(key)
        # Match trends + reddit by keyword overlap (heuristic)
        matched_trends = _match_signals(o.video.title, raw.trends)
        matched_reddit = _match_reddit(o.video.title, raw.reddit)
        ideas.append(Idea(
            topic=topic,
            angle=f"How '{o.video.channel_title}' got {o.multiplier:.0f}x baseline",
            niche=niche,
            inspiration_outliers=[o],
            inspiration_trends=matched_trends,
            inspiration_reddit=matched_reddit,
        ))

    # Strategy B: trend-first (only for trends not already used)
    used_queries = {t.query.lower() for idea in ideas for t in idea.inspiration_trends}
    for rs in ranked_trends[:8]:
        if rs.query.lower() in used_queries or rs.query.lower() in used_topics:
            continue
        used_topics.add(rs.query.lower())
        # Find the matching TrendQuery object
        match_t = next((t for t in raw.trends if t.query == rs.query
                        and t.source == rs.source), None)
        if match_t is None:
            continue
        ideas.append(Idea(
            topic=rs.query.title(),
            angle="A first-look explainer on a rising query",
            niche=niche,
            inspiration_outliers=[],
            inspiration_trends=[match_t],
            inspiration_reddit=_match_reddit(rs.query, raw.reddit),
        ))

    # Strategy C: pain-mining from Reddit
    for r in sorted(raw.reddit, key=lambda x: x.upvote_velocity, reverse=True)[:5]:
        if r.title.lower() in used_topics:
            continue
        used_topics.add(r.title.lower())
        ideas.append(Idea(
            topic=r.title[:80],
            angle="Audience-pain explainer answering a hot community thread",
            niche=niche,
            inspiration_outliers=[],
            inspiration_trends=_match_signals(r.title, raw.trends),
            inspiration_reddit=[r],
        ))

    return ideas


def _match_signals(text: str, trends: list[TrendQuery]) -> list[TrendQuery]:
    text_lower = text.lower()
    out = []
    for t in trends:
        if any(w in text_lower for w in t.query.lower().split() if len(w) > 3):
            out.append(t)
    # Sort matches by interest desc and cap
    out.sort(key=lambda x: x.interest_now, reverse=True)
    return out[:3]


def _match_reddit(text: str, reddit: list[RedditSignal]) -> list[RedditSignal]:
    text_lower = text.lower()
    out = []
    for r in reddit:
        # Match if any meaningful (>=4 char) word from either is in the other
        text_words = {w for w in text_lower.split() if len(w) >= 4}
        title_words = {w for w in r.title.lower().split() if len(w) >= 4}
        if text_words & title_words:
            out.append(r)
    out.sort(key=lambda x: x.upvote_velocity, reverse=True)
    return out[:3]


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def research_niche(
    niche: str,
    seed_channels: list[str],
    *,
    subreddits: list[str] | None = None,
    top_n: int = 5,
    rubric: Rubric | None = None,
    provider: LLMProvider | None = None,
    sources: dict | None = None,
) -> PipelineResult:
    """End-to-end: signals → outliers → ranked trends → ideas → scored → briefs."""
    sources = sources or {}
    raw = collect_signals(
        niche, seed_channels, subreddits=subreddits,
        youtube=sources.get("youtube"),
        trends=sources.get("trends"),
        reddit=sources.get("reddit"),
    )
    outliers = detect_outliers(raw.videos, raw.channels)
    ranked = rank_trends(raw.trends, raw.reddit)
    ideas = synthesize_ideas(niche, raw, outliers, ranked)

    scorer = Scorer(rubric=rubric)
    scored = sorted([scorer.score(idea) for idea in ideas], reverse=True)[:top_n]

    llm = provider or get_provider()
    briefs = [generate_brief(s, provider=llm) for s in scored]

    return PipelineResult(
        niche=niche, raw=raw, outliers=outliers, ranked_trends=ranked,
        scored_ideas=scored, briefs=briefs,
    )


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def render_report(result: PipelineResult) -> str:
    """Render the full pipeline output as a single markdown document."""
    lines: list[str] = [
        f"# YouTube content research — {result.niche}",
        "",
        f"*Auto-generated by yt-research-agent. {len(result.briefs)} briefs ranked by composite score.*",
        "",
        f"## Signal summary",
        "",
        f"- **{len(result.raw.videos)}** videos sampled across "
        f"**{len(result.raw.channels)}** seed channels",
        f"- **{len(result.outliers)}** outliers detected (≥10× channel baseline)",
        f"- **{len(result.raw.trends)}** trend signals from Google Trends",
        f"- **{len(result.raw.reddit)}** Reddit signals from community subreddits",
        "",
    ]
    if result.outliers:
        lines.append("### Top outliers")
        lines.append("")
        lines.append("| Multiplier | Title | Channel | Views |")
        lines.append("|---|---|---|---|")
        for o in result.outliers[:5]:
            mult = (f"{o.multiplier:.1f}×"
                    if o.multiplier != float("inf") else "∞")
            lines.append(
                f"| {mult} | {o.video.title[:60]} | "
                f"{o.video.channel_title} | {o.video.view_count:,} |"
            )
        lines.append("")
    if result.ranked_trends:
        lines.append("### Top ranked signals")
        lines.append("")
        lines.append("| Composite | Source | Query | Velocity |")
        lines.append("|---|---|---|---|")
        for rs in result.ranked_trends[:8]:
            lines.append(
                f"| {rs.composite:.3f} | {rs.source} | "
                f"{rs.query[:60]} | {rs.velocity:.2f} |"
            )
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("# Briefs")
    lines.append("")
    for brief in result.briefs:
        lines.append(brief.to_markdown())
        lines.append("---")
        lines.append("")
    return "\n".join(lines)
