# Architecture

Every layer is a pure function over the previous one. Sources are swappable. The scoring rubric is data. The LLM is a renderer, not a decider.

## Layers

### 1. Sources

Each source is a class implementing `Source.fetch(query) -> list[Signal]`.

| Source | Signal type | What it actually pulls |
|---|---|---|
| `YouTubeDataSource` | `Video`, `Channel` | search.list + videos.list + channel.list. Includes view count, like count, comment count, published_at, channel statistics. |
| `GoogleTrendsSource` | `TrendQuery` | pytrends `related_queries` (rising) + `interest_over_time` for the niche keyword. |
| `RedditSource` | `RedditPost` | PRAW: hot/rising posts from relevant subreddits, sorted by upvote velocity (upvotes / hours_since_post). |

Each source caches responses under `.cache/<source>/<hash>.json` keyed on (method, params). Caches live for 24h by default; tunable per-call.

### 2. Analysis

Stateless functions that transform raw signals into derived metrics.

| Module | Function | What it returns |
|---|---|---|
| `outlier_detection` | `detect_outliers(videos, baseline)` | Videos whose view count exceeds `N × channel_baseline` (default N=10). |
| `view_velocity` | `compute_velocity(videos)` | views per day since publish — surfaces fresh fast-movers. |
| `trend_signals` | `rank_signals(signals)` | Combines raw signals into a single ranked list with lead-time × reliability weights. |
| `retention_proxy` | `estimate_engagement(video)` | Like ratio, comment ratio, comment-per-view — proxies for retention since real retention is private. |

### 3. Scoring

A pure rubric (`Idea -> Score`) with cited weights. See [SCORING_RUBRIC.md](SCORING_RUBRIC.md).

Output: every idea gets a 0–100 score across 9 categories. Ties broken by audience demand.

### 4. LLM briefs

Given a scored `Idea`, generate a `ContentBrief`:

- 1-line `hook` (the cold-open promise)
- 3 `title_candidates` (varied in length and structure)
- `thumbnail_concept` (what's in frame, what the face does, what text overlays say)
- 5-section `outline` (chapter beats with retention anchors)
- 3 `retention_anchors` (re-engagement triggers at 30s / midpoint / end)
- `predicted_audience` (who this hits hardest)

The LLM is replaceable: Anthropic preferred for narrative quality, OpenAI as fallback. Fixture-based prompts so tests don't need a key.

## Pipeline orchestrator

```python
def research_niche(
    niche: str,
    seed_channels: list[str],
    top_n: int = 5,
    sources: list[Source] | None = None,
) -> list[ContentBrief]:
    raw = collect_signals(niche, seed_channels, sources)
    outliers = detect_outliers(raw.videos)
    trends = rank_signals(raw.trends + raw.reddit)
    ideas = synthesize_ideas(outliers, trends)
    scored = [score(idea) for idea in ideas]
    top = sorted(scored, reverse=True)[:top_n]
    return [generate_brief(idea) for idea in top]
```

Each step is pure (collect_signals is the only IO call). Easy to test, easy to replay, easy to swap.

## Why this shape

- **Sources as classes** — adding TikTok or Twitter later is one file.
- **Analysis as functions** — easy to unit-test, easy to ablate.
- **Scoring as data** — change weights in `scoring/weights.py` without touching code; A/B-test rubrics.
- **LLM as renderer** — model swaps don't touch business logic.
- **Cache everywhere** — API quotas are real; ten reruns of the same query shouldn't cost ten quota hits.

## Out of scope (for this MVP)

- Continuous monitoring / scheduled re-runs (CRON / GitHub Actions would be 30 LOC if you want it)
- Multi-channel orchestration (this generates briefs for ONE channel at a time)
- Performance feedback loop (you publish, we observe view counts, we adjust scoring weights) — designed but not built yet
- TikTok / Shorts cross-platform signals
- Thumbnail similarity scoring against a winners corpus (a CLIP embedding + nearest-neighbor would do it; not in MVP)
