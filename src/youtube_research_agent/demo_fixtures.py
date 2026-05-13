"""Demo fixtures for the algorithmic-trading niche.

Real-world data assembled from public YouTube + creator interviews.
Used by examples/trading_bot_research.py AND by the TradingBot
dashboard's /research surface when use_demo_fixtures=True.

When real API keys are present, the pipeline uses them instead; these
fixtures only seed the cache so first-time runs produce a rich result
even with zero keys configured.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .sources.base import _cache_path


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
        {"id": "UC_chatgpt_bot", "snippet": {"title": "AI Trading Lab"},
         "statistics": {"subscriberCount": "120000",
                        "videoCount": "60", "viewCount": "9000000"}},
    ]
}


VIDEOS_FIXTURE = {
    "items": [
        # QuantPy — 1 outlier + 4 baseline
        {"id": "v_quantpy_outlier",
         "snippet": {"title": "If I Started Algo Trading in 2026 (As a Beginner)",
                     "channelId": "UC_quantpy", "channelTitle": "QuantPy",
                     "publishedAt": "2026-01-12T14:00:00Z"},
         "statistics": {"viewCount": "485000", "likeCount": "28500", "commentCount": "1820"},
         "contentDetails": {"duration": "PT22M14S"}},
        {"id": "v_quantpy_normal",
         "snippet": {"title": "Vectorbt basics: from CSV to Sharpe",
                     "channelId": "UC_quantpy", "channelTitle": "QuantPy",
                     "publishedAt": "2026-03-22T16:00:00Z"},
         "statistics": {"viewCount": "32000", "likeCount": "1200", "commentCount": "180"},
         "contentDetails": {"duration": "PT14M02S"}},
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
        # Algovibes
        {"id": "v_algovibes_outlier",
         "snippet": {"title": "I Built an AI Trading Agent From Scratch (Full Code)",
                     "channelId": "UC_algovibes", "channelTitle": "Algovibes",
                     "publishedAt": "2026-04-02T11:00:00Z"},
         "statistics": {"viewCount": "612000", "likeCount": "39400", "commentCount": "2750"},
         "contentDetails": {"duration": "PT38M51S"}},
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
        # QuantInsti
        {"id": "v_qinsti_outlier",
         "snippet": {"title": "I built 12 trading algorithms and gave them 6 figures",
                     "channelId": "UC_qinsti", "channelTitle": "QuantInsti",
                     "publishedAt": "2026-02-20T10:00:00Z"},
         "statistics": {"viewCount": "780000", "likeCount": "41200", "commentCount": "3680"},
         "contentDetails": {"duration": "PT45M00S"}},
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
        # AI Trading Lab
        {"id": "v_chatgpt_outlier",
         "snippet": {"title": "I Gave ChatGPT $10K to Trade for 30 Days (Real Money)",
                     "channelId": "UC_chatgpt_bot", "channelTitle": "AI Trading Lab",
                     "publishedAt": "2026-03-30T18:00:00Z"},
         "statistics": {"viewCount": "1240000", "likeCount": "82000", "commentCount": "8400"},
         "contentDetails": {"duration": "PT19M22S"}},
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
        # Kevin Davey
        {"id": "v_davey_outlier",
         "snippet": {"title": "Why 95% of Retail Algo Traders Quit (And the Fix)",
                     "channelId": "UC_davey", "channelTitle": "Kevin Davey",
                     "publishedAt": "2026-02-05T14:00:00Z"},
         "statistics": {"viewCount": "295000", "likeCount": "14800", "commentCount": "1340"},
         "contentDetails": {"duration": "PT16M48S"}},
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


TRENDS_RISING_FIXTURE = {
    "rising": [
        {"query": "ai trading bot", "value": 250},
        {"query": "chatgpt trading strategy", "value": 180},
        {"query": "agentic ai trading", "value": 150},
        {"query": "free algo trading bot", "value": 95},
        {"query": "alpaca python trading", "value": 70},
        {"query": "automate options trading", "value": 60},
    ]
}

TRENDS_INTEREST_FIXTURE = {
    "points": [
        {"date": f"2026-02-{d:02d}", "value": v}
        for d, v in zip(
            [4, 11, 18, 25],
            [48, 50, 52, 55],
        )
    ] + [
        {"date": f"2026-03-{d:02d}", "value": v}
        for d, v in zip(
            [4, 11, 18, 25],
            [58, 60, 64, 68],
        )
    ] + [
        {"date": f"2026-04-{d:02d}", "value": v}
        for d, v in zip(
            [1, 8, 15, 22, 29],
            [71, 74, 76, 78, 81],
        )
    ]
}


def _reddit_rising(now_ts: float) -> dict:
    return {"posts": [
        {"title": "I lost $40k in 6 months running an AI trading bot — here's what went wrong",
         "subreddit": "algotrading", "upvotes": 1850, "comment_count": 412,
         "created_utc": now_ts - 5 * 3600,
         "permalink": "/r/algotrading/comments/example1/"},
        {"title": "What's the cheapest way to backtest a Python strategy in 2026?",
         "subreddit": "algotrading", "upvotes": 480, "comment_count": 142,
         "created_utc": now_ts - 8 * 3600,
         "permalink": "/r/algotrading/comments/example2/"},
        {"title": "Anyone actually making money with ChatGPT-driven strategies?",
         "subreddit": "algotrading", "upvotes": 920, "comment_count": 218,
         "created_utc": now_ts - 11 * 3600,
         "permalink": "/r/algotrading/comments/example3/"},
    ]}


def _reddit_hot(now_ts: float) -> dict:
    return {"posts": [
        {"title": "How do you know when to stop a losing algo before drawdown gets ugly?",
         "subreddit": "algotrading", "upvotes": 340, "comment_count": 95,
         "created_utc": now_ts - 18 * 3600,
         "permalink": "/r/algotrading/comments/example4/"},
        {"title": "Show me your audit log: how do you prove your bot didn't lie about a fill?",
         "subreddit": "algotrading", "upvotes": 210, "comment_count": 64,
         "created_utc": now_ts - 14 * 3600,
         "permalink": "/r/algotrading/comments/example5/"},
    ]}


def seed_demo_cache(cache_dir: Path | str) -> None:
    """Seed the cache so the algorithmic-trading niche runs offline with
    realistic data shapes. Idempotent; safe to call repeatedly."""
    cache_path = Path(cache_dir)

    def _put(source: str, method: str, params: dict, response: dict) -> None:
        path = _cache_path(source, method, params, cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"__stored_at__": time.time(), "data": response}, f)

    _put("youtube_data", "channels.list",
         {"ids": sorted(SEED_CHANNELS)}, CHANNELS_FIXTURE)

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=180)).date()
    cutoff = datetime.combine(cutoff_date, datetime.min.time(),
                              tzinfo=timezone.utc).isoformat()

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

    _put("youtube_data", "search.list.by_query",
         {"query": "algorithmic trading", "max_results": 20},
         {"items": [{"id": {"videoId": "v_chatgpt_outlier"}}]})

    all_ids = sorted({v for vs in videos_by_channel.values() for v in vs})
    _put("youtube_data", "videos.list", {"ids": all_ids}, VIDEOS_FIXTURE)

    _put("google_trends", "rising_queries",
         {"seed": "algorithmic trading", "geo": "US"}, TRENDS_RISING_FIXTURE)
    _put("google_trends", "interest_over_time",
         {"seed": "algorithmic trading", "geo": "US",
          "timeframe": "today 3-m"}, TRENDS_INTEREST_FIXTURE)

    now_ts = time.time()
    _put("reddit", "rising", {"subreddit": "algotrading", "limit": 15},
         _reddit_rising(now_ts))
    _put("reddit", "hot", {"subreddit": "algotrading", "limit": 10},
         _reddit_hot(now_ts))
