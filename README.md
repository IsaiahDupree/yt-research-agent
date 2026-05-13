# yt-research-agent

A programmatic YouTube content-research pipeline for serious operators.

**What it does:** Given a niche and a few seed channels, it scrapes
trending signals, detects outlier videos, scores ideas with a cited
rubric, and writes content briefs you could actually shoot.

**What it doesn't do:** Make your videos for you. Tell you what tone to
use. Replace taste.

This is the codified version of the workflows surfaced by the deep
research prompt in [`docs/RESEARCH_PROMPT.md`](docs/RESEARCH_PROMPT.md).
Built to be both runnable and forkable.

---

## Why this exists

Most YouTube research tooling is either:
- a $40/mo Chrome extension that wraps `videos.list` and calls itself AI, or
- a manual spreadsheet ritual that creators repeat by hand every week.

This is the second one, automated honestly. Every signal it uses is
documented, every weight in the scoring rubric is cited, and the
output is a content brief — not a leaderboard you have to interpret.

## Quick start

```bash
# 1. Install
git clone https://github.com/IsaiahDupree/yt-research-agent.git
cd yt-research-agent
python -m venv .venv && . .venv/Scripts/activate
pip install -e .[dev]

# 2. Add your keys (all optional — the pipeline degrades gracefully)
cp .env.example .env
# edit .env: YOUTUBE_API_KEY, ANTHROPIC_API_KEY or OPENAI_API_KEY, REDDIT_CLIENT_ID/SECRET

# 3. Run it
yt-research run \
  --niche "algorithmic trading" \
  --seed-channels @QuantPy,@QuantInsti,@Algovibes \
  --top-n 5 \
  --output output/algo-trading-briefs.md
```

## Architecture (one screen)

```
 niche + seed channels
        │
        ▼
 ┌──────────────────────────────────────────────────┐
 │  SOURCES                                         │
 │    youtube_data   google_trends   reddit         │
 │  (videos, views, (rising queries, (topic         │
 │   channels)       interest curves) acceleration) │
 └──────────────────────────────────────────────────┘
        │
        ▼
 ┌──────────────────────────────────────────────────┐
 │  ANALYSIS                                        │
 │    outlier_detection   view_velocity             │
 │    trend_signals       retention_proxy           │
 └──────────────────────────────────────────────────┘
        │
        ▼
 ┌──────────────────────────────────────────────────┐
 │  SCORING (0–100 rubric, cited weights)           │
 │    audience_demand · trend_velocity · outlier    │
 │    search_potential · emotional · format_fit     │
 │    competition · production · monetization       │
 └──────────────────────────────────────────────────┘
        │
        ▼
 ┌──────────────────────────────────────────────────┐
 │  LLM BRIEFS                                      │
 │    hook · title_candidates · thumbnail_concept   │
 │    outline · retention_anchors · audience        │
 └──────────────────────────────────────────────────┘
        │
        ▼
 output/<niche>-briefs.md
```

Each layer is testable in isolation. Sources are swappable. The scoring
rubric is a pure function.

## What's in the repo

- `src/youtube_research_agent/` — the package
- `tests/` — fixture-backed tests so CI doesn't need API keys
- `docs/` — architecture, the scoring rubric (with citations), the
  build-vs-buy decision matrix, the research prompt
- `examples/` — runnable scripts (the TradingBot content plan is here)
- `output/` — generated briefs (gitignored except `.gitkeep`)

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — every layer, every interface
- [`docs/SCORING_RUBRIC.md`](docs/SCORING_RUBRIC.md) — the 0–100 rubric with cited weights
- [`docs/BUILD_VS_BUY.md`](docs/BUILD_VS_BUY.md) — when to use this vs vidIQ / ViewStats / 1of10 / Spotter
- [`docs/RESEARCH_PROMPT.md`](docs/RESEARCH_PROMPT.md) — the deep research prompt this repo is built from

## Status

MVP. Built in one sitting. Honest about its limits — see
[`docs/BUILD_VS_BUY.md`](docs/BUILD_VS_BUY.md).

## License

MIT.
