"""
Xquik API client for importing profile search results.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urlparse

import httpx

from .scraper import TweetData

XQUIK_PAGE_SIZE = 200
X_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,15}$")
X_PROFILE_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}


@dataclass
class XquikClient:
    """Small client for the Xquik tweet search endpoint."""

    api_key: str
    base_url: str = "https://xquik.com/api/v1"
    timeout: float = 30.0
    transport: Optional[httpx.AsyncBaseTransport] = None

    async def search_profile(
        self,
        username: str,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> AsyncGenerator[TweetData, None]:
        """Fetch profile tweets from Xquik and yield normalized tweet data."""
        clean_username = normalize_username(username)
        remaining = limit
        cursor = ""

        async with httpx.AsyncClient(
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            while remaining is None or remaining > 0:
                page_limit = (
                    XQUIK_PAGE_SIZE
                    if remaining is None
                    else min(remaining, XQUIK_PAGE_SIZE)
                )
                params: dict[str, Any] = {
                    "q": f"from:{clean_username}",
                    "queryType": "Latest",
                    "limit": page_limit,
                }
                if cursor:
                    params["cursor"] = cursor
                if since:
                    params["sinceTime"] = format_datetime(since)
                if until:
                    params["untilTime"] = format_datetime(until)

                response = await client.get(
                    f"{self.base_url.rstrip('/')}/x/tweets/search",
                    headers={"x-api-key": self.api_key},
                    params=params,
                )
                response.raise_for_status()

                body = response.json()
                raw_tweets = body.get("tweets", [])
                if not isinstance(raw_tweets, list):
                    raise ValueError("Xquik response did not include a tweet list.")
                if not raw_tweets:
                    break

                for raw_tweet in raw_tweets:
                    if not isinstance(raw_tweet, dict):
                        raise ValueError("Xquik tweet item was not an object.")
                    yield tweet_from_xquik(raw_tweet)
                    if remaining is not None:
                        remaining -= 1
                        if remaining <= 0:
                            break

                if remaining is not None and remaining <= 0:
                    break
                cursor = str(body.get("next_cursor") or "")
                if not body.get("has_next_page") or not cursor:
                    break


def normalize_username(username: str) -> str:
    """Normalize a handle, profile URL, or username to a bare username."""
    value = username.strip()
    if not value:
        raise ValueError("X username cannot be empty.")

    if "://" in value:
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in X_PROFILE_HOSTS
        ):
            raise ValueError("Profile URL must use x.com or twitter.com.")
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) != 1:
            raise ValueError("Profile URL must point directly to an X profile.")
        value = path_parts[0]
    else:
        value = value.lstrip("@")

    if not X_USERNAME_PATTERN.fullmatch(value):
        raise ValueError(
            "X username must contain 1 to 15 letters, digits, or underscores."
        )
    return value


def format_datetime(value: datetime) -> str:
    """Format a datetime for Xquik query parameters."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def tweet_from_xquik(raw: dict[str, Any]) -> TweetData:
    """Map a Xquik SearchTweet object into the app's TweetData model."""
    author = raw.get("author")
    if not isinstance(author, dict):
        author = {}

    retweeted_tweet = raw.get("retweeted_tweet")
    if not isinstance(retweeted_tweet, dict):
        retweeted_tweet = {}

    retweeted_author = retweeted_tweet.get("author")
    if not isinstance(retweeted_author, dict):
        retweeted_author = {}

    tweet_id = required_int(raw.get("id"), "id")
    is_reply = bool(raw.get("isReply")) or raw.get("inReplyToId") is not None
    is_retweet = bool(retweeted_tweet) or raw.get("type") == "retweet"

    return TweetData(
        id=tweet_id,
        url=str(raw.get("url") or f"https://x.com/i/status/{tweet_id}"),
        date=parse_datetime(raw.get("createdAt")),
        content=str(raw.get("text") or ""),
        username=str(author.get("username") or ""),
        user_id=optional_int(author.get("id")) or 0,
        display_name=str(author.get("name") or ""),
        reply_count=optional_int(raw.get("replyCount")) or 0,
        retweet_count=optional_int(raw.get("retweetCount")) or 0,
        like_count=optional_int(raw.get("likeCount")) or 0,
        view_count=optional_int(raw.get("viewCount")) or 0,
        lang=str(raw.get("lang") or ""),
        source=str(raw.get("source") or "Xquik"),
        is_reply=is_reply,
        is_retweet=is_retweet,
        replied_to_user=optional_str(raw.get("inReplyToUsername")),
        replied_to_tweet_id=optional_int(raw.get("inReplyToId")),
        retweeted_from_user=optional_str(retweeted_author.get("username")),
        retweeted_tweet_id=optional_int(retweeted_tweet.get("id")),
        media_urls=media_urls(raw.get("media")),
        hashtags=entity_values(raw.get("entities"), "hashtags", ("text", "tag")),
        mentions=entity_values(
            raw.get("entities"), "mentions", ("username", "screen_name")
        ),
        raw_json=json.dumps(raw, ensure_ascii=False, default=str)[:10000],
    )


def parse_datetime(value: Any) -> datetime:
    """Parse a required Xquik timestamp."""
    if not value:
        raise ValueError("Xquik response missing required field: createdAt")
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def required_int(value: Any, field: str) -> int:
    """Convert a required integer-like field."""
    if value is None:
        raise ValueError(f"Xquik response missing required field: {field}")
    return int(value)


def optional_int(value: Any) -> Optional[int]:
    """Convert an optional integer-like field."""
    if value in (None, ""):
        return None
    return int(value)


def optional_str(value: Any) -> Optional[str]:
    """Convert an optional string-like field."""
    if value in (None, ""):
        return None
    return str(value)


def entity_values(entities: Any, key: str, fields: tuple[str, ...]) -> list[str]:
    """Extract entity text values from Xquik search-result entities."""
    if not isinstance(entities, dict):
        return []

    candidates = entities.get(key)
    if candidates is None and key == "mentions":
        candidates = entities.get("user_mentions")
    if not isinstance(candidates, list):
        return []

    values = []
    for item in candidates:
        if isinstance(item, str):
            values.append(item)
            continue
        if not isinstance(item, dict):
            continue
        for field in fields:
            value = item.get(field)
            if value:
                values.append(str(value))
                break
    return values


def media_urls(media: Any) -> list[str]:
    """Extract media URLs from Xquik search-result media objects."""
    if not isinstance(media, list):
        return []

    values = []
    for item in media:
        if not isinstance(item, dict):
            continue
        value = item.get("mediaUrl") or item.get("url")
        if value:
            values.append(str(value))
    return values
