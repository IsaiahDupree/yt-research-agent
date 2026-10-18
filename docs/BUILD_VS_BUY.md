# Build vs Buy

An honest answer to "should I use this repo or pay $40/mo for vidIQ?"

## TL;DR

| Situation | Recommendation |
|---|---|
| You publish < 1 video/week, no engineering capacity | **Buy** — vidIQ Pro or ViewStats. Repeatable manual rituals win. |
| You publish 1–4 videos/week, some engineering | **Both** — buy a $40/mo tool for the polish, use this repo for outlier scans and brief generation. |
| You publish 5+ videos/week with a team | **Build / fork this repo** — your API spend will pay back the build time within 60 days. |
| You're a research / media / agency operator | **Fork** — the in-house pipeline is the moat. |

## What SaaS tools actually do for you

| Tool | What it's actually good at | What it claims that's overstated |
|---|---|---|
| **vidIQ** | Keyword research, daily ideas feed, AI Coach for "what should I title this" | "AI strategy" is GPT calls on top of basic stats |
| **TubeBuddy** | Keyword research, A/B title testing, in-Studio chrome extension | Bulk-edit features are the real win, not "AI insights" |
| **ViewStats** | Outlier scanning, channel comparison, dashboard polish | Most signals are derivable from YouTube Data API + 50 lines of Python |
| **1of10** | Outlier detection with a slick UI, "1 of 10" framing forces you to compare | The framework is more valuable than the software — read [Jenny Hoyos](https://www.youtube.com/@jennyhoyos) explain it, build it yourself |
| **Spotter Studio** | AI-driven ideation tuned to your channel + creator coaching | The coaching is the actual product; the AI is competent but not magical |
| **CreatorML** | Thumbnail / title testing via CLIP-style similarity scoring | Genuinely good niche tool; building this from scratch is a week of work |
| **Tubular Labs** | Enterprise-grade cross-platform data | $$$$, not for solo creators |

## What you give up by going DIY

- **A team that updates it for you** when YouTube changes its API or hides a metric
- **An interface designed for non-engineers** (your editor / thumbnail designer / sponsor lead can use vidIQ; they probably can't run `yt-research run --niche ...`)
- **Outlier libraries with full historical context** (ViewStats has years of cached data; you don't)
- **A11y / UX polish**

## What you get by building

- **No quota games.** Run as many scans as your API quota allows; no $40/mo gate.
- **Custom signals.** Add TikTok migration detection. Add Discord topic acceleration. Add anything.
- **Inspectable scoring.** When vidIQ's "AI Coach" tells you a title will perform well, you can't see why. With this rubric, every weight is in `scoring/weights.py`.
- **Repeatable in CI.** Schedule a weekly scan via GitHub Actions; commit the briefs to a content-ops repo.
- **A product, not a subscription.** Fork it, modify it, sell it.

## The honest middle path

Most operators don't need to choose. Buy ViewStats for the polish and the outlier library. Use this repo for:

1. Scheduled weekly scans of competitor channels (outlier scanner)
2. LLM brief generation from a shortlist your team manually picked
3. Custom signal experiments (TikTok migration, Discord acceleration, etc.)

The two tools live next to each other; one's a daily dashboard, one's an opinionated batch pipeline.

## When you've outgrown this repo

If you find yourself:

- Maintaining > 5 forks for different niches
- Wanting per-thumbnail similarity scoring against a winners corpus
- Wanting per-second retention prediction from script alone
- Needing sponsor / brand-fit scoring against a CRM

You probably want a real product, not a script. Either invest in building that, or pay Spotter / Tubular and stop trying to recreate them.

## The principle

This repo exists because the **techniques** behind these tools are not secret. They're: outlier detection, view velocity, trend acceleration, LLM scoring. Anyone who has read this doc and can write Python can build 80% of the value of any tool on this page. The remaining 20% — the polish, the team, the cache, the partnerships — is what you pay $40/mo for.
