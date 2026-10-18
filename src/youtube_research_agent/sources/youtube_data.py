"""YouTube Data API v3 client.

Wraps the four endpoints we actually need:
  - channels.list (statistics, snippet)
  - search.list   (find recent videos by channel or by query)
  - videos.list   (full stats per video id)

All responses are cached via cached_call() so re-runs during dev don't
burn quota.

Quota notes (Apr 2026):
  - Daily quota = 10,000 units, default.
  - search.list = 100 units / call. ← the expensive one.
  - videos.list = 1 unit per id batch (up to 50 ids).
  - channels.list = 1 unit per id batch (up to 50 ids).

So a single "look at 5 channels and get their last 50 videos each"
research pass is ~5 search.list calls (500 units) + 1 videos.list batch
(1 unit) + 1 channels.list batch (1 unit) = ~502 units. You get ~20
runs/day on the default quota.
"""

from __future__ import annotations

import os
import statistics
from datetime import datetime, timezone, timedelta
from typing import Any

from ..models import Channel, Video
from .base import Source, cached_call


class YouTubeDataSource(Source):
    name = "youtube_data"

    def __init__(self, api_key: str | None = None,
                 cache_max_age_seconds: int | None = None) -> None:
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self.cache_max_age = cache_max_age_seconds   # None = use default
        self._client = None

    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy-import + lazy-build the googleapiclient discovery object.

        Lazy because: (1) the client import is slow, (2) tests that
        only hit the cache should never need it.
        """
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise RuntimeError(
                "YOUTUBE_API_KEY not set. Set it in .env or pass api_key=. "
                "(Tests should hit the cache directly via tests/fixtures/.)"
            )
        from googleapiclient.discovery import build  # type: ignore
        self._client = build("youtube", "v3", developerKey=self.api_key,
                             cache_discovery=False)
        return self._client

    def _kwargs(self) -> dict:
        return {} if self.cache_max_age is None else {"max_age_seconds": self.cache_max_age}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_channels(self, channel_ids: list[str]) -> list[Channel]:
        """Fetch Channel objects for the given channel ids."""
        if not channel_ids:
            return []
        raw = cached_call(
            source=self.name,
            method="channels.list",
            params={"ids": sorted(channel_ids)},
            compute=lambda: self._raw_channels_list(channel_ids),
            **self._kwargs(),
        )
        return [self._parse_channel(item) for item in raw.get("items", [])]

    def get_videos(self, video_ids: list[str]) -> list[Video]:
        """Fetch Video objects with full statistics."""
        if not video_ids:
            return []
        raw = cached_call(
            source=self.name,
            method="videos.list",
            params={"ids": sorted(video_ids)},
            compute=lambda: self._raw_videos_list(video_ids),
            **self._kwargs(),
        )
        return [self._parse_video(item) for item in raw.get("items", [])]

    def recent_videos_by_channel(
        self, channel_id: str, *, max_results: int = 25,
        published_after_days: int = 180,
    ) -> list[str]:
        """Return video ids for a channel's recent uploads.

        max_results capped at 50 by the API. published_after limits to
        the last N days so quota doesn't go to ancient archive material.
        """
        # Day-precision cutoff so the cache key is stable for a 24h
        # window — within a single day all reruns share the cache.
        cutoff_date = (datetime.now(timezone.utc)
                       - timedelta(days=published_after_days)).date()
        cutoff = datetime.combine(cutoff_date, datetime.min.time(),
                                  tzinfo=timezone.utc).isoformat()
        raw = cached_call(
            source=self.name,
            method="search.list.by_channel",
            params={"channel_id": channel_id, "max_results": max_results,
                    "published_after": cutoff},
            compute=lambda: self._raw_search_by_channel(channel_id, max_results, cutoff),
            **self._kwargs(),
        )
        return [it["id"]["videoId"] for it in raw.get("items", [])
                if it.get("id", {}).get("videoId")]

    def search_videos(self, query: str, *, max_results: int = 25) -> list[str]:
        """Free-text video search; returns video ids."""
        raw = cached_call(
            source=self.name,
            method="search.list.by_query",
            params={"query": query, "max_results": max_results},
            compute=lambda: self._raw_search_by_query(query, max_results),
            **self._kwargs(),
        )
        return [it["id"]["videoId"] for it in raw.get("items", [])
                if it.get("id", {}).get("videoId")]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def hydrate_baselines(self, channels: list[Channel],
                          videos_by_channel: dict[str, list[Video]]) -> None:
        """Fill `channel.median_views_per_video` from a recent-video sample."""
        for ch in channels:
            sample = videos_by_channel.get(ch.id, [])
            if sample:
                ch.median_views_per_video = float(
                    statistics.median(v.view_count for v in sample)
                )

    # ------------------------------------------------------------------
    # Raw API calls (mockable in tests via the cache)
    # ------------------------------------------------------------------

    def _raw_channels_list(self, ids: list[str]) -> dict:
        return self._get_client().channels().list(
            part="snippet,statistics", id=",".join(ids),
        ).execute()

    def _raw_videos_list(self, ids: list[str]) -> dict:
        return self._get_client().videos().list(
            part="snippet,statistics,contentDetails", id=",".join(ids),
        ).execute()

    def _raw_search_by_channel(self, channel_id: str, max_results: int,
                                published_after: str) -> dict:
        return self._get_client().search().list(
            part="id", channelId=channel_id, maxResults=max_results,
            order="date", type="video", publishedAfter=published_after,
        ).execute()

    def _raw_search_by_query(self, query: str, max_results: int) -> dict:
        return self._get_client().search().list(
            part="id", q=query, maxResults=max_results,
            order="viewCount", type="video",
        ).execute()

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_channel(item: dict[str, Any]) -> Channel:
        s = item.get("statistics", {})
        sn = item.get("snippet", {})
        return Channel(
            id=item["id"],
            title=sn.get("title", ""),
            subscriber_count=int(s.get("subscriberCount", 0) or 0),
            video_count=int(s.get("videoCount", 0) or 0),
            view_count=int(s.get("viewCount", 0) or 0),
        )

    @staticmethod
    def _parse_video(item: dict[str, Any]) -> Video:
        sn = item.get("snippet", {})
        st = item.get("statistics", {})
        cd = item.get("contentDetails", {})
        duration = _parse_iso8601_duration(cd.get("duration", "PT0S"))
        return Video(
            id=item["id"],
            title=sn.get("title", ""),
            channel_id=sn.get("channelId", ""),
            channel_title=sn.get("channelTitle", ""),
            published_at=sn.get("publishedAt", ""),
            view_count=int(st.get("viewCount", 0) or 0),
            like_count=int(st.get("likeCount", 0) or 0),
            comment_count=int(st.get("commentCount", 0) or 0),
            duration_seconds=duration,
            description=sn.get("description", ""),
            tags=sn.get("tags", []) or [],
            is_short=(duration > 0 and duration < 60),
        )


def _parse_iso8601_duration(iso: str) -> int:
    """Minimal ISO-8601 duration parser for PTxHxMxS (no fractional seconds).

    YouTube only ever sends hours/minutes/seconds, so this covers it.
    """
    if not iso.startswith("PT"):
        return 0
    iso = iso[2:]
    total = 0
    num = ""
    for ch in iso:
        if ch.isdigit():
            num += ch
        elif ch == "H":
            total += int(num or 0) * 3600
            num = ""
        elif ch == "M":
            total += int(num or 0) * 60
            num = ""
        elif ch == "S":
            total += int(num or 0)
            num = ""
    return total
