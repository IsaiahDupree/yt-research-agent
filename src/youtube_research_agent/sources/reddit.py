"""Reddit source via PRAW.

Pulls hot/rising posts from one or more subreddits and computes upvote
velocity as the headline acceleration metric. Caches the raw response
for 24h.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from ..models import RedditSignal
from .base import Source, cached_call


class RedditSource(Source):
    name = "reddit"

    def __init__(self,
                 client_id: str | None = None,
                 client_secret: str | None = None,
                 user_agent: str | None = None,
                 cache_max_age_seconds: int | None = None) -> None:
        self.client_id = client_id or os.environ.get("REDDIT_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET", "")
        self.user_agent = (user_agent
                           or os.environ.get("REDDIT_USER_AGENT")
                           or "yt-research-agent/0.1")
        self.cache_max_age = cache_max_age_seconds
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not (self.client_id and self.client_secret):
            raise RuntimeError(
                "REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET not set. "
                "(Tests should hit the cache directly via seeded fixtures.)"
            )
        try:
            import praw   # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "praw not installed. `pip install praw`."
            ) from e
        self._client = praw.Reddit(
            client_id=self.client_id, client_secret=self.client_secret,
            user_agent=self.user_agent,
        )
        return self._client

    def _kwargs(self) -> dict:
        return {} if self.cache_max_age is None else {"max_age_seconds": self.cache_max_age}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def hot_posts(self, subreddit: str, *, limit: int = 25) -> list[RedditSignal]:
        """Return the current `hot` posts in a subreddit as signals."""
        raw = cached_call(
            source=self.name,
            method="hot",
            params={"subreddit": subreddit, "limit": limit},
            compute=lambda: self._raw_listing(subreddit, "hot", limit),
            **self._kwargs(),
        )
        return [self._parse_post(p) for p in raw.get("posts", [])]

    def rising_posts(self, subreddit: str, *, limit: int = 25) -> list[RedditSignal]:
        """Return `rising` posts — newer than hot, indicates acceleration."""
        raw = cached_call(
            source=self.name,
            method="rising",
            params={"subreddit": subreddit, "limit": limit},
            compute=lambda: self._raw_listing(subreddit, "rising", limit),
            **self._kwargs(),
        )
        return [self._parse_post(p) for p in raw.get("posts", [])]

    # ------------------------------------------------------------------
    # Raw API calls
    # ------------------------------------------------------------------

    def _raw_listing(self, subreddit: str, kind: str, limit: int) -> dict:
        c = self._get_client()
        sub = c.subreddit(subreddit)
        listing = getattr(sub, kind)(limit=limit)
        posts = []
        for p in listing:
            posts.append({
                "title": p.title,
                "subreddit": str(p.subreddit),
                "upvotes": int(p.score),
                "comment_count": int(p.num_comments),
                "created_utc": float(p.created_utc),
                "permalink": "https://reddit.com" + p.permalink,
            })
        return {"posts": posts}

    # ------------------------------------------------------------------
    # Parser
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_post(p: dict) -> RedditSignal:
        created = float(p.get("created_utc", 0))
        if created > 0:
            hours = max(
                (datetime.now(timezone.utc).timestamp() - created) / 3600.0,
                0.1,
            )
        else:
            hours = 0.1
        return RedditSignal(
            title=p["title"], subreddit=p["subreddit"],
            upvotes=int(p.get("upvotes", 0)),
            comment_count=int(p.get("comment_count", 0)),
            hours_since_post=hours,
            url=p.get("permalink", ""),
        )
