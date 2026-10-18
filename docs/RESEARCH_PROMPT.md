# The deep research prompt

This is the prompt that birthed this repo. Run it against a strong research agent (ChatGPT with web search, Claude with research mode, or Perplexity Deep Research) and you'll get a decision-grade report on the YouTube content-research landscape. This codebase is the operationalisation of section 5 + 6 of that report.

---

## RESEARCH MISSION — How serious YouTube operators decide what to make before they make it

You are conducting a research report for a media operator who wants to build (or buy) a content-research pipeline. The deliverable is a decision-grade document — not a tool catalog. By the end the reader should know:

1. What top-1% YouTube creators and channels actually DO (not what they say they do) for pre-production ideation, with cited case studies from 2024–2026.
2. Which tools are genuinely useful versus repackaged keyword research with marketing polish — and how to tell them apart.
3. The smallest viable in-house pipeline that replicates ~80% of what the best paid tools do.
4. Where the leading edge is moving next.

## HARD CONSTRAINTS

- Every claim cites a specific source (creator name, channel, tool docs, founder essay, podcast transcript, post URL). No "studies show" without a link.
- Prefer 2025–2026 sources. Anything older needs an explicit reason for inclusion.
- Distinguish what creators SAY (interviews, marketing copy) from what they DO (workflow walkthroughs, API behaviors, public dashboards, leaked SOPs). Flag the gap when it appears.
- When a tool claims "AI," answer: what signal does the AI actually act on? Vague answers = de-rank that tool.
- Two-source minimum on any "this works" claim. One source = anecdote.

## INVESTIGATE IN THIS ORDER

1. **Pre-production workflows of top operators** — concrete workflows from at least 5 named operators (MrBeast, Jenny Hoyos, Paddy Galloway, Veritasium, Spotter Studio clients, Colin & Samir, ViewStats power users). The exact steps they take from "blank slate" to "approved brief," in order, sourced.

2. **The serious-tool landscape** — vidIQ, TubeBuddy, ViewStats, 1of10, Spotter Studio, CreatorML, Glimpse, Morningfame, Tubular Labs, YouTube Studio Research tab, Google Trends. For each: what it does, what signal it uses, pricing, API access, honest edge assessment. Distinguish "keyword research with charts" from "predictive of growth."

3. **Trend detection signals, ranked by leading-indicator quality** — search autocomplete velocity, Google Trends rising queries, TikTok-to-YouTube migration, Reddit/X acceleration, comment-section pain mining, outlier video detection (>10× channel baseline), new-channel breakouts, thumbnail/title format spread, retention-curve shape changes. Rank by lead-time × reliability.

4. **Idea vetting before production** — Shorts as MVP, title testing via paid traffic, thumbnail tournaments, community polls, newsletter validation, comment-prompt asking, search-volume gating, outlier-similarity scoring. For each: a named creator who reports it works, with their result.

5. **Programmatic / API workflows** — what's possible with YouTube Data API + Google Trends + Reddit/X APIs + LLM scoring. GitHub repos, open-source projects, operator-published pipelines. What's solo-in-a-weekend vs needs-real-infra. Include rate limits and quota gotchas.

6. **An honest scoring model** — derive a 0–100 scoring rubric with cited category weights. Mark inferences explicitly. Map to the signals in §3.

7. **Build-vs-buy criteria** — given a team with engineering capacity but limited time, when is a SaaS tool worth it and when does in-house win? Specific criteria, not hedged "it depends."

8. **The leading edge (mid–late 2026)** — what credible operators are experimenting with right now. AI agents that draft briefs from competitor scrape? Retention prediction from script? Thumbnail nearest-neighbor against winners? Flag promising vs marketing.

## OUTPUT FORMAT

- **Executive verdict** (1 page): the three things to change about your research process this quarter, with reasoning.
- **Workflow case studies**: 5 named operators, half-page each, sourced.
- **Tool decision matrix**: tools × (signal type, pricing, API y/n, recommend y/n, replaceable-by-DIY y/n).
- **Trend signal ranking**: single ranked table — lead-time × reliability scoring.
- **Programmatic pipeline blueprint**: an architecture you could actually build.
- **Scoring rubric**: 0–100 with category weights, citation per weight.
- **What would change the conclusions**: 3 things that, if observed in the next 6 months, would invalidate the recommendations.
- **Open questions**: what you couldn't resolve.

## WHAT MAKES THIS REPORT VALUABLE

A reader should finish knowing exactly which 3 tools (if any) to pay for, which 3 things to build, and the smallest weekly research ritual that beats most channels. If it reads like a feature comparison from a SaaS landing page, it failed. If it reads like "here's the truth, here's the proof, here's the call" — it worked.

---

## How this repo relates

| Research-prompt deliverable | Where it lives in the repo |
|---|---|
| Executive verdict | The README sets the philosophy; per-niche verdicts land in `output/` |
| Workflow case studies | (Not in this repo — a research artifact, not code) |
| Tool decision matrix | [`docs/BUILD_VS_BUY.md`](BUILD_VS_BUY.md) |
| Trend signal ranking | Implemented in `src/youtube_research_agent/analysis/trend_signals.py` |
| Programmatic pipeline blueprint | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) + the actual code |
| Scoring rubric | [`docs/SCORING_RUBRIC.md`](SCORING_RUBRIC.md) + `src/youtube_research_agent/scoring/` |
| What would change conclusions | Bottom of [`docs/SCORING_RUBRIC.md`](SCORING_RUBRIC.md) (calibration section) |
| Open questions | The "out of scope" section of [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |

The research output is the **what to build**; this repo is the **how**.
