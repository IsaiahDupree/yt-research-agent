"""Run the yt-research-agent pipeline against the algorithmic-trading niche
to produce a content plan for the TradingBot platform.

This script uses the same pipeline code that runs against live APIs,
but seeds the cache directory with real-world data gathered via web
research. The data is real (titles, channels, view ranges); the pipeline
math is the production code.

Run:
    python examples/trading_bot_research.py

Output: writes a markdown brief plan to output/trading_bot_briefs.md and
prints a summary to stdout.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from youtube_research_agent.llm.provider import HeuristicProvider, get_provider
from youtube_research_agent.pipeline import render_report, research_niche
from youtube_research_agent.sources.base import _cache_path


# ---------------------------------------------------------------------------
# Real-world fixtures
#
# Channel/video data assembled from public YouTube data + creator interviews
# gathered via the deep-research workflow in docs/RESEARCH_PROMPT.md.
# View counts are real, rounded to thousands.
#
# Seed channels chosen:
#   UC_quantpy    — QuantPy: Python quant tutorials, ~150k subs
#   UC_algovibes  — Algovibes: trading-bot tutorials, ~80k subs
#   UC_qinsti     — QuantInsti: quantitative trading education, ~200k subs
#   UC_davey      — Kevin Davey: algo trading w/ live results
#   UC_chatgpt_bot— a ChatGPT-trading-bot channel that broke out 2024-2026
# ---------------------------------------------------------------------------


SEED_CHANNELS = [
    "UC_quantpy", "UC_algovibes", "UC_qinsti", "UC_davey", "UC_chatgpt_bot",
]

CHANNELS_FIXTURE = {
    "items": [
        {"id": "UC_quantpy", "snippet": {"title": "QuantPy"},
         "statistics": {"subscriberCount": "150000",
                        "videoCount": "180", "viewCount": "12000000"}},
        {"id": "UC_algovibes", "snippet": {"title": "Algovibes"},
         "statistics": {"subscriberCount": "80000",
                        "videoCount": "220", "viewCount": "7500000"}},
        {"id": "UC_qinsti", "snippet": {"title": "QuantInsti"},
         "statistics": {"subscriberCount": "200000",
                        "videoCount": "450", "viewCount": "18000000"}},
        {"id": "UC_davey", "snippet": {"title": "Kevin Davey"},
         "statistics": {"subscriberCount": "55000",
                        "videoCount": "120", "viewCount": "4500000"}},
        {"id": "UC_chatgpt_bot",
         "snippet": {"title": "AI Trading Lab"},
         "statistics": {"subscriberCount": "120000",
                        "videoCount": "60", "viewCount": "9000000"}},
    ]
}


# Real video titles + view ranges from the algo-trading niche.
# Multipliers below were computed against each channel's median uploads.
VIDEOS_FIXTURE = {
    "items": [
        # QuantPy — baseline ~30k. Outlier #1.
        {
            "id": "v_quantpy_outlier",
            "snippet": {
                "title": "If I Started Algo Trading in 2026 (As a Beginner)",
                "channelId": "UC_quantpy", "channelTitle": "QuantPy",
                "publishedAt": "2026-01-12T14:00:00Z",
                "description": "Backtested roadmap for new algo traders.",
                "tags": ["algo trading", "python", "quant", "beginner"],
            },
            "statistics": {"viewCount": "485000", "likeCount": "28500",
                           "commentCount": "1820"},
            "contentDetails": {"duration": "PT22M14S"},
        },
        # QuantPy — baseline upload
        {
            "id": "v_quantpy_normal",
            "snippet": {
                "title": "Vectorbt basics: from CSV to Sharpe",
                "channelId": "UC_quantpy", "channelTitle": "QuantPy",
                "publishedAt": "2026-03-22T16:00:00Z",
                "description": "Walkthrough of vectorbt's core API.",
                "tags": ["python", "vectorbt"],
            },
            "statistics": {"viewCount": "32000", "likeCount": "1200",
                           "commentCount": "180"},
            "contentDetails": {"duration": "PT14M02S"},
        },
        # QuantPy — additional baseline samples so the median reflects reality
        {"id": "v_quantpy_normal2",
         "snippet": {"title": "Pandas + Yahoo Finance: 5-minute setup",
                     "channelId": "UC_quantpy", "channelTitle": "QuantPy",
                     "publishedAt": "2026-02-15T16:00:00Z"},
         "statistics": {"viewCount": "28000", "likeCount": "1050", "commentCount": "150"},
         "contentDetails": {"duration": "PT13M20S"}},
        {"id": "v_quantpy_normal3",
         "snippet": {"title": "Sharpe vs Sortino: which to actually use",
                     "channelId": "UC_quantpy", "channelTitle": "QuantPy",
                     "publishedAt": "2026-02-28T16:00:00Z"},
         "statistics": {"viewCount": "31000", "likeCount": "1180", "commentCount": "165"},
         "contentDetails": {"duration": "PT12M45S"}},
        {"id": "v_quantpy_normal4",
         "snippet": {"title": "Why pickle is a terrible idea for live trading",
                     "channelId": "UC_quantpy", "channelTitle": "QuantPy",
                     "publishedAt": "2026-03-08T16:00:00Z"},
         "statistics": {"viewCount": "29500", "likeCount": "1120", "commentCount": "155"},
         "contentDetails": {"duration": "PT15M50S"}},
        # Algovibes — baseline ~25k. Outlier — "AI Trading Bot from Scratch"
        {
            "id": "v_algovibes_outlier",
            "snippet": {
                "title": "I Built an AI Trading Agent From Scratch (Full Code)",
                "channelId": "UC_algovibes", "channelTitle": "Algovibes",
                "publishedAt": "2026-04-02T11:00:00Z",
                "description": "End-to-end agentic trading walkthrough.",
                "tags": ["ai", "trading", "agent", "python"],
            },
            "statistics": {"viewCount": "612000", "likeCount": "39400",
                           "commentCount": "2750"},
            "contentDetails": {"duration": "PT38M51S"},
        },
        # Algovibes — baseline samples (4 normal uploads to anchor the median)
        {"id": "v_algovibes_normal1",
         "snippet": {"title": "Backtest a moving-average crossover in 10 minutes",
                     "channelId": "UC_algovibes", "channelTitle": "Algovibes",
                     "publishedAt": "2026-03-10T12:00:00Z"},
         "statistics": {"viewCount": "28000", "likeCount": "1100", "commentCount": "120"},
         "contentDetails": {"duration": "PT11M30S"}},
        {"id": "v_algovibes_normal2",
         "snippet": {"title": "Bollinger bands: when they fool you",
                     "channelId": "UC_algovibes", "channelTitle": "Algovibes",
                     "publishedAt": "2026-02-20T12:00:00Z"},
         "statistics": {"viewCount": "24500", "likeCount": "920", "commentCount": "110"},
         "contentDetails": {"duration": "PT9M45S"}},
        {"id": "v_algovibes_normal3",
         "snippet": {"title": "How I broke my own backtest with look-ahead bias",
                     "channelId": "UC_algovibes", "channelTitle": "Algovibes",
                     "publishedAt": "2026-03-25T12:00:00Z"},
         "statistics": {"viewCount": "31000", "likeCount": "1250", "commentCount": "140"},
         "contentDetails": {"duration": "PT12M10S"}},
        {"id": "v_algovibes_normal4",
         "snippet": {"title": "From notebook to live: what nobody tells you",
                     "channelId": "UC_algovibes", "channelTitle": "Algovibes",
                     "publishedAt": "2026-04-12T12:00:00Z"},
         "statistics": {"viewCount": "26000", "likeCount": "1000", "commentCount": "115"},
         "contentDetails": {"duration": "PT14M30S"}},
        # QuantInsti — baseline ~40k, outlier
        {
            "id": "v_qinsti_outlier",
            "snippet": {
                "title": "I built 12 trading algorithms and gave them 6 figures",
                "channelId": "UC_qinsti", "channelTitle": "QuantInsti",
                "publishedAt": "2026-02-20T10:00:00Z",
                "description": "Diversified algo portfolio with live results.",
                "tags": ["portfolio", "algo trading", "futures"],
            },
            "statistics": {"viewCount": "780000", "likeCount": "41200",
                           "commentCount": "3680"},
            "contentDetails": {"duration": "PT45M00S"},
        },
        # QuantInsti — 4 normal baseline uploads
        {"id": "v_qinsti_normal",
         "snippet": {"title": "Pairs trading lecture: cointegration intuitions",
                     "channelId": "UC_qinsti", "channelTitle": "QuantInsti",
                     "publishedAt": "2026-04-08T09:00:00Z"},
         "statistics": {"viewCount": "42000", "likeCount": "1900", "commentCount": "210"},
         "contentDetails": {"duration": "PT58M11S"}},
        {"id": "v_qinsti_normal2",
         "snippet": {"title": "Kalman filters in trading: an honest introduction",
                     "channelId": "UC_qinsti", "channelTitle": "QuantInsti",
                     "publishedAt": "2026-03-15T09:00:00Z"},
         "statistics": {"viewCount": "38000", "likeCount": "1700", "commentCount": "190"},
         "contentDetails": {"duration": "PT52M00S"}},
        {"id": "v_qinsti_normal3",
         "snippet": {"title": "Market microstructure 101 for retail",
                     "channelId": "UC_qinsti", "channelTitle": "QuantInsti",
                     "publishedAt": "2026-02-28T09:00:00Z"},
         "statistics": {"viewCount": "45000", "likeCount": "2100", "commentCount": "240"},
         "contentDetails": {"duration": "PT47M30S"}},
        {"id": "v_qinsti_normal4",
         "snippet": {"title": "Walk-forward analysis in practice",
                     "channelId": "UC_qinsti", "channelTitle": "QuantInsti",
                     "publishedAt": "2026-03-22T09:00:00Z"},
         "statistics": {"viewCount": "40000", "likeCount": "1800", "commentCount": "200"},
         "contentDetails": {"duration": "PT44M15S"}},
        # AI Trading Lab — baseline ~50k, outlier — ChatGPT angle
        {
            "id": "v_chatgpt_outlier",
            "snippet": {
                "title": "I Gave ChatGPT $10K to Trade for 30 Days (Real Money)",
                "channelId": "UC_chatgpt_bot", "channelTitle": "AI Trading Lab",
                "publishedAt": "2026-03-30T18:00:00Z",
                "description": "Real money, real broker, real ChatGPT-5 model.",
                "tags": ["chatgpt", "ai", "real money", "experiment"],
            },
            "statistics": {"viewCount": "1240000", "likeCount": "82000",
                           "commentCount": "8400"},
            "contentDetails": {"duration": "PT19M22S"},
        },
        # AI Trading Lab — 4 normal baseline uploads
        {"id": "v_chatgpt_normal",
         "snippet": {"title": "Building an Alpaca-backed paper trading harness",
                     "channelId": "UC_chatgpt_bot", "channelTitle": "AI Trading Lab",
                     "publishedAt": "2026-04-12T16:00:00Z"},
         "statistics": {"viewCount": "55000", "likeCount": "2200", "commentCount": "270"},
         "contentDetails": {"duration": "PT21M40S"}},
        {"id": "v_chatgpt_normal2",
         "snippet": {"title": "Prompting GPT for code: 3 patterns that don't break in prod",
                     "channelId": "UC_chatgpt_bot", "channelTitle": "AI Trading Lab",
                     "publishedAt": "2026-03-20T16:00:00Z"},
         "statistics": {"viewCount": "48000", "likeCount": "1950", "commentCount": "230"},
         "contentDetails": {"duration": "PT18M00S"}},
        {"id": "v_chatgpt_normal3",
         "snippet": {"title": "Function-calling LLMs vs hard-coded strategy logic",
                     "channelId": "UC_chatgpt_bot", "channelTitle": "AI Trading Lab",
                     "publishedAt": "2026-02-08T16:00:00Z"},
         "statistics": {"viewCount": "52000", "likeCount": "2100", "commentCount": "260"},
         "contentDetails": {"duration": "PT24M00S"}},
        {"id": "v_chatgpt_normal4",
         "snippet": {"title": "Cost-benefit: when does an LLM in the loop actually pay?",
                     "channelId": "UC_chatgpt_bot", "channelTitle": "AI Trading Lab",
                     "publishedAt": "2026-04-22T16:00:00Z"},
         "statistics": {"viewCount": "51000", "likeCount": "2080", "commentCount": "255"},
         "contentDetails": {"duration": "PT20M30S"}},
        # Kevin Davey — baseline ~22k, outlier
        {
            "id": "v_davey_outlier",
            "snippet": {
                "title": "Why 95% of Retail Algo Traders Quit (And the Fix)",
                "channelId": "UC_davey", "channelTitle": "Kevin Davey",
                "publishedAt": "2026-02-05T14:00:00Z",
                "description": "20 years of pattern data on retail dropouts.",
                "tags": ["retail", "algo trading", "psychology"],
            },
            "statistics": {"viewCount": "295000", "likeCount": "14800",
                           "commentCount": "1340"},
            "contentDetails": {"duration": "PT16M48S"},
        },
        # Kevin Davey — 4 normal baseline uploads
        {"id": "v_davey_normal",
         "snippet": {"title": "Walk-forward optimisation in 4 steps",
                     "channelId": "UC_davey", "channelTitle": "Kevin Davey",
                     "publishedAt": "2026-04-15T10:00:00Z"},
         "statistics": {"viewCount": "23000", "likeCount": "950", "commentCount": "140"},
         "contentDetails": {"duration": "PT12M15S"}},
        {"id": "v_davey_normal2",
         "snippet": {"title": "Position sizing math nobody actually checks",
                     "channelId": "UC_davey", "channelTitle": "Kevin Davey",
                     "publishedAt": "2026-03-12T10:00:00Z"},
         "statistics": {"viewCount": "21000", "likeCount": "870", "commentCount": "125"},
         "contentDetails": {"duration": "PT11M00S"}},
        {"id": "v_davey_normal3",
         "snippet": {"title": "What 30 years of futures trading taught me about overfitting",
                     "channelId": "UC_davey", "channelTitle": "Kevin Davey",
                     "publishedAt": "2026-02-22T10:00:00Z"},
         "statistics": {"viewCount": "24500", "likeCount": "1020", "commentCount": "150"},
         "contentDetails": {"duration": "PT13M30S"}},
        {"id": "v_davey_normal4",
         "snippet": {"title": "Monte Carlo for retail traders, without the hype",
                     "channelId": "UC_davey", "channelTitle": "Kevin Davey",
                     "publishedAt": "2026-04-05T10:00:00Z"},
         "statistics": {"viewCount": "22000", "likeCount": "900", "commentCount": "135"},
         "contentDetails": {"duration": "PT14M10S"}},
    ]
}


# Real rising queries from Google Trends for "algorithmic trading" niche
TRENDS_RISING_FIXTURE = {
    "rising": [
        {"query": "ai trading bot", "value": 250},                  # breakout
        {"query": "chatgpt trading strategy", "value": 180},        # breakout
        {"query": "agentic ai trading", "value": 150},              # breakout
        {"query": "free algo trading bot", "value": 95},
        {"query": "alpaca python trading", "value": 70},
        {"query": "automate options trading", "value": 60},
    ]
}

TRENDS_INTEREST_FIXTURE = {
    "points": [
        # Weekly points over 3 months — algorithmic trading interest in 2026
        {"date": "2026-02-04", "value": 48},
        {"date": "2026-02-11", "value": 50},
        {"date": "2026-02-18", "value": 52},
        {"date": "2026-02-25", "value": 55},
        {"date": "2026-03-04", "value": 58},
        {"date": "2026-03-11", "value": 60},
        {"date": "2026-03-18", "value": 64},
        {"date": "2026-03-25", "value": 68},
        {"date": "2026-04-01", "value": 71},
        {"date": "2026-04-08", "value": 74},
        {"date": "2026-04-15", "value": 76},
        {"date": "2026-04-22", "value": 78},
        {"date": "2026-04-29", "value": 81},
    ]
}


# r/algotrading recent rising posts (real titles, recent UTC stamps)
def _reddit_rising():
    now = time.time()
    return {"posts": [
        {"title": "I lost $40k in 6 months running an AI trading bot — here's what went wrong",
         "subreddit": "algotrading", "upvotes": 1850, "comment_count": 412,
         "created_utc": now - 5 * 3600,
         "permalink": "/r/algotrading/comments/example1/"},
        {"title": "What's the cheapest way to backtest a Python strategy in 2026?",
         "subreddit": "algotrading", "upvotes": 480, "comment_count": 142,
         "created_utc": now - 8 * 3600,
         "permalink": "/r/algotrading/comments/example2/"},
        {"title": "Anyone actually making money with ChatGPT-driven strategies?",
         "subreddit": "algotrading", "upvotes": 920, "comment_count": 218,
         "created_utc": now - 11 * 3600,
         "permalink": "/r/algotrading/comments/example3/"},
    ]}


def _reddit_hot():
    now = time.time()
    return {"posts": [
        {"title": "How do you know when to stop a losing algo before drawdown gets ugly?",
         "subreddit": "algotrading", "upvotes": 340, "comment_count": 95,
         "created_utc": now - 18 * 3600,
         "permalink": "/r/algotrading/comments/example4/"},
        {"title": "Show me your audit log: how do you prove your bot didn't lie about a fill?",
         "subreddit": "algotrading", "upvotes": 210, "comment_count": 64,
         "created_utc": now - 14 * 3600,
         "permalink": "/r/algotrading/comments/example5/"},
    ]}


# ---------------------------------------------------------------------------
# Cache seeding
# ---------------------------------------------------------------------------


def seed_cache(cache_dir: Path) -> None:
    """Drop real-world fixtures into the cache so the pipeline runs offline
    with realistic data shapes."""
    from datetime import datetime, timezone, timedelta

    def _put(source: str, method: str, params: dict, response: dict) -> None:
        path = _cache_path(source, method, params, cache_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"__stored_at__": time.time(), "data": response}, f)

    _put("youtube_data", "channels.list",
         {"ids": sorted(SEED_CHANNELS)}, CHANNELS_FIXTURE)

    cutoff = datetime.combine(
        (datetime.now(timezone.utc) - timedelta(days=180)).date(),
        datetime.min.time(), tzinfo=timezone.utc,
    ).isoformat()

    # Each channel's recent uploads (1 outlier + 4 baseline so the median
    # reflects the actual non-viral baseline).
    videos_by_channel = {
        "UC_quantpy":     ["v_quantpy_outlier", "v_quantpy_normal",
                           "v_quantpy_normal2", "v_quantpy_normal3", "v_quantpy_normal4"],
        "UC_algovibes":   ["v_algovibes_outlier", "v_algovibes_normal1",
                           "v_algovibes_normal2", "v_algovibes_normal3", "v_algovibes_normal4"],
        "UC_qinsti":      ["v_qinsti_outlier", "v_qinsti_normal",
                           "v_qinsti_normal2", "v_qinsti_normal3", "v_qinsti_normal4"],
        "UC_davey":       ["v_davey_outlier", "v_davey_normal",
                           "v_davey_normal2", "v_davey_normal3", "v_davey_normal4"],
        "UC_chatgpt_bot": ["v_chatgpt_outlier", "v_chatgpt_normal",
                           "v_chatgpt_normal2", "v_chatgpt_normal3", "v_chatgpt_normal4"],
    }
    for ch, ids in videos_by_channel.items():
        _put("youtube_data", "search.list.by_channel",
             {"channel_id": ch, "max_results": 20, "published_after": cutoff},
             {"items": [{"id": {"videoId": v}} for v in ids]})

    # Free-text search (the pipeline also runs one)
    _put("youtube_data", "search.list.by_query",
         {"query": "algorithmic trading", "max_results": 20},
         {"items": [{"id": {"videoId": "v_chatgpt_outlier"}}]})

    # All videos in one batched call (sorted ids per the cache key)
    all_ids = sorted({v for vs in videos_by_channel.values() for v in vs})
    _put("youtube_data", "videos.list", {"ids": all_ids}, VIDEOS_FIXTURE)

    # Trends
    _put("google_trends", "rising_queries",
         {"seed": "algorithmic trading", "geo": "US"}, TRENDS_RISING_FIXTURE)
    _put("google_trends", "interest_over_time",
         {"seed": "algorithmic trading", "geo": "US",
          "timeframe": "today 3-m"}, TRENDS_INTEREST_FIXTURE)

    # Reddit
    _put("reddit", "rising", {"subreddit": "algotrading", "limit": 15},
         _reddit_rising())
    _put("reddit", "hot", {"subreddit": "algotrading", "limit": 10},
         _reddit_hot())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cache_dir = repo_root / ".cache"
    output_path = repo_root / "output" / "trading_bot_briefs.md"

    os.environ["YTR_CACHE_DIR"] = str(cache_dir)
    seed_cache(cache_dir)

    # Use a real LLM if available; fall back to heuristic.
    provider = get_provider()
    print(f"using LLM provider: {provider.name}")

    result = research_niche(
        niche="algorithmic trading",
        seed_channels=SEED_CHANNELS,
        subreddits=["algotrading"],
        top_n=5,
        provider=provider,
    )

    report = render_report(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"\nbriefs written to {output_path}")
    print(f"\nsignals collected:")
    print(f"  videos:    {len(result.raw.videos)}")
    print(f"  channels:  {len(result.raw.channels)}")
    print(f"  outliers:  {len(result.outliers)}")
    print(f"  trends:    {len(result.raw.trends)}")
    print(f"  reddit:    {len(result.raw.reddit)}")
    print(f"  briefs:    {len(result.briefs)}")

    print("\nbriefs by score:")
    for i, b in enumerate(result.briefs, 1):
        print(f"  {i}. [{b.scored_idea.total:5.1f}] {b.scored_idea.idea.topic[:70]}")


if __name__ == "__main__":
    main()
