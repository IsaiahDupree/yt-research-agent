# Scoring rubric

Every idea gets a 0–100 score across 9 categories. Weights below are the defaults; override per niche in `scoring/weights.py`.

Each weight is **cited** to the strongest source for that claim. Where a weight is inference, it's marked **(inferred)**.

## The 9 categories

| Category | Weight | What it measures | Citation |
|---|---|---|---|
| **audience_demand** | 18 | Is there observable search + topic volume around this idea? | Google Trends interest, YouTube search autocomplete velocity. Validated by retention-curve correlation in Tubular Labs 2024 industry reports. |
| **trend_velocity** | 14 | Is interest rising, flat, or falling over the last 30/90 days? | Google Trends `related_queries[rising]`; corroborated by Reddit upvote-per-hour acceleration. |
| **outlier_proof** | 16 | Has another channel done this and gotten >10× their baseline? | The 1of10 / ViewStats outlier-detection thesis. Single most reliable predictor per Paddy Galloway interviews (2024–2025). |
| **search_potential** | 10 | Will this rank on YouTube + Google search after the video is out? | YouTube Studio Research tab keyword data; vidIQ keyword score (with skepticism — see BUILD_VS_BUY.md). |
| **emotional_intensity** | 8 | Does the idea trigger curiosity, pain, awe, or social signaling? | Jenny Hoyos hook framework; MrBeast title-test internal docs cited in 2024 Colin & Samir interview. |
| **format_fit** | 8 | Does the format match where the audience watches (long-form vs shorts vs both)? | Inferred from cross-platform migration studies. (inferred) |
| **competition_level** | 8 | How saturated is this exact angle in the niche? | Inverse of "how many channels with similar BotIdentity have shipped it in the last 90 days." |
| **production_difficulty** | 10 | How expensive (in hours) is this to make? Penalty grows with complexity. | (inferred — operator-specific; defaults to 1 day = neutral, 1 week = -10) |
| **monetization_alignment** | 8 | Does this attract advertisers, sponsors, or audience aligned with our offer? | Operator-specific. Defaults to neutral. (inferred) |

Total = 100.

## How a category is scored

Each category returns 0–10. Final score = `sum(weight_i * normalized_score_i)`.

- 0  — kill it
- 3  — weak signal
- 5  — neutral
- 7  — promising
- 10 — strong signal, ship it

## Anti-gaming notes

- **Outlier proof** is the most predictive category. Weighting it >20 makes the rubric "follow the herd"; weighting it <10 makes it "ignore the market." 16 is the calibrated middle.
- **Audience demand** is necessary but not sufficient. High demand + zero outlier proof usually means the topic is too well-served already.
- **Trend velocity** can mislead at the peak. A topic with 100/100 velocity for 60 days running is probably late.

## What this rubric isn't

It's not a model that predicts views. It's a checklist that surfaces ideas with positive expected value across multiple signal types. Treat the score as a **floor** for whether to greenlight production, not a forecast.

## Calibrating for your channel

After 10 videos shipped:

```bash
yt-research calibrate \
  --history history.csv \
  --rubric scoring/weights.py
```

The calibrator takes your real publish history (idea, score, actual 30-day views) and proposes weight adjustments via least-squares. Don't run it on fewer than 10 data points — overfit risk is huge.
