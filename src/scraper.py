"""
X-Tweet-Analyzer - Main Scraper Module
=======================================
Handles all tweet scraping using twscrape library.
Supports pagination, rate limiting, and account rotation.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from dataclasses import dataclass, field

import twscrape
from twscrape import API, gather
from twscrape.models import Tweet, User

from .config import Config
from .database import Database

logger = logging.getLogger(__name__)


@dataclass
class TweetData:
    """Normalized tweet data structure."""
    id: int
    url: str
    date: datetime
    content: str
    username: str
    user_id: int
    display_name: str
    reply_count: int = 0
    retweet_count: int = 0
    like_count: int = 0
    view_count: int = 0
    lang: str = ""
    source: str = ""
    is_reply: bool = False
    is_retweet: bool = False
    replied_to_user: Optional[str] = None
    replied_to_tweet_id: Optional[int] = None
    retweeted_from_user: Optional[str] = None
    retweeted_tweet_id: Optional[int] = None
    media_urls: list = field(default_factory=list)
    hashtags: list = field(default_factory=list)
    mentions: list = field(default_factory=list)
    raw_json: str = ""

    @property
    def category(self) -> str:
        """Return tweet category: 'original', 'reply', or 'retweet'."""
        if self.is_retweet:
            return "retweet"
        elif self.is_reply:
            return "reply"
        return "original"


class XScraper:
    """
    Main scraper class for X/Twitter profiles.
    
    Uses twscrape for authentication-based scraping with support for:
    - Full tweet history pagination
    - Rate limit handling with exponential backoff
    - Multiple account rotation
    - Automatic tweet classification
    """

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.api = API()
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    async def setup_accounts(self):
        """Initialize scraper accounts from config."""
        accounts = self.config.get_accounts()
        if not accounts:
            logger.warning("No accounts configured. Running in guest mode (limited).")
            return

        for account in accounts:
            try:
                await self.api.pool.add_account(
                    username=account["username"],
                    password=account["password"],
                    email=account["email"],
                    email_password=account.get("email_password", ""),
                )
                logger.info(f"Account added: @{account['username']}")
            except Exception as e:
                logger.error(f"Failed to add account @{account['username']}: {e}")

        await self.api.pool.login_all()
        logger.info("Account pool initialized successfully.")

    async def get_user_info(self, username: str) -> Optional[User]:
        """Fetch user profile information."""
        username = username.lstrip("@").split("/")[-1]
        try:
            user = await self.api.user_by_login(username)
            logger.info(f"Found user: @{user.username} (ID: {user.id})")
            return user
        except Exception as e:
            logger.error(f"Failed to fetch user @{username}: {e}")
            return None

    def _classify_tweet(self, tweet: Tweet) -> TweetData:
        """Classify and normalize a tweet."""
        import json

        is_retweet = False
        is_reply = False
        retweeted_from_user = None
        retweeted_tweet_id = None
        replied_to_user = None
        replied_to_tweet_id = None

        # Detect retweet
        raw = tweet.rawContent or ""
        if raw.startswith("RT @"):
            is_retweet = True
            # Extract original author
            try:
                rt_part = raw[3:]  # "RT @user: ..."
                retweeted_from_user = rt_part.split(":")[0].lstrip("@").strip()
            except Exception:
                pass

        if tweet.retweetedTweet:
            is_retweet = True
            retweeted_tweet_id = tweet.retweetedTweet.id
            if tweet.retweetedTweet.user:
                retweeted_from_user = tweet.retweetedTweet.user.username

        # Detect reply
        if tweet.inReplyToTweetId or tweet.inReplyToUser:
            is_reply = True
            replied_to_tweet_id = tweet.inReplyToTweetId
            if tweet.inReplyToUser:
                replied_to_user = tweet.inReplyToUser.username

        # Extract media
        media_urls = []
        if tweet.media:
            for m in (tweet.media.photos or []):
                media_urls.append(str(m.url))
            for m in (tweet.media.videos or []):
                if m.variants:
                    best = max(m.variants, key=lambda v: v.bitrate or 0)
                    media_urls.append(str(best.url))

        # Extract hashtags
        hashtags = []
        if tweet.hashtags:
            hashtags = [h.lower() for h in tweet.hashtags]

        # Extract mentions
        mentions = []
        if tweet.mentionedUsers:
            mentions = [u.username for u in tweet.mentionedUsers]

        return TweetData(
            id=tweet.id,
            url=str(tweet.url),
            date=tweet.date,
            content=tweet.rawContent or tweet.renderedContent or "",
            username=tweet.user.username if tweet.user else "",
            user_id=tweet.user.id if tweet.user else 0,
            display_name=tweet.user.displayname if tweet.user else "",
            reply_count=tweet.replyCount or 0,
            retweet_count=tweet.retweetCount or 0,
            like_count=tweet.likeCount or 0,
            view_count=tweet.viewCount or 0,
            lang=tweet.lang or "",
            source=tweet.source or "",
            is_reply=is_reply,
            is_retweet=is_retweet,
            replied_to_user=replied_to_user,
            replied_to_tweet_id=replied_to_tweet_id,
            retweeted_from_user=retweeted_from_user,
            retweeted_tweet_id=retweeted_tweet_id,
            media_urls=media_urls,
            hashtags=hashtags,
            mentions=mentions,
            raw_json=json.dumps(tweet.__dict__, default=str)[:10000],
        )

    async def scrape_profile(
        self,
        username: str,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        progress_callback=None,
    ) -> AsyncGenerator[TweetData, None]:
        """
        Scrape all tweets from a profile with pagination.
        
        Args:
            username: Twitter username (with or without @)
            limit: Maximum tweets to fetch (None = all)
            since: Only fetch tweets after this date
            until: Only fetch tweets before this date
            progress_callback: Optional callback(count, tweet) for progress updates
        
        Yields:
            TweetData objects
        """
        username = username.lstrip("@").split("/")[-1]
        
        user = await self.get_user_info(username)
        if not user:
            raise ValueError(f"User not found: @{username}")

        # Save user to database
        await self.db.save_user(user)

        count = 0
        retry_count = 0
        max_retries = self.config.max_retries

        logger.info(f"Starting scrape for @{username} (limit={limit})")

        try:
            async for tweet in self.api.user_tweets_and_replies(user.id, limit=limit or 9999999):
                # Apply date filters
                if since and tweet.date < since:
                    continue
                if until and tweet.date > until:
                    break

                tweet_data = self._classify_tweet(tweet)
                await self.db.save_tweet(tweet_data)
                
                count += 1
                if progress_callback:
                    progress_callback(count, tweet_data)

                if limit and count >= limit:
                    logger.info(f"Reached limit of {limit} tweets.")
                    break

                # Rate limit handling
                if count % 100 == 0:
                    logger.info(f"Scraped {count} tweets from @{username}...")
                    await asyncio.sleep(self.config.rate_limit_delay)

                yield tweet_data
                retry_count = 0  # Reset on success

        except twscrape.RateLimitError as e:
            wait_time = min(60 * (2 ** retry_count), 900)  # Max 15 min
            logger.warning(f"Rate limited. Waiting {wait_time}s... (retry {retry_count + 1}/{max_retries})")
            if retry_count < max_retries:
                await asyncio.sleep(wait_time)
                retry_count += 1
            else:
                raise

        except Exception as e:
            logger.error(f"Scraping error: {e}")
            raise

        logger.info(f"Completed scraping @{username}: {count} tweets fetched.")


class GuestScraper:
    """
    Fallback guest scraper using public API endpoints.
    Limited to ~3200 recent tweets without authentication.
    """
    
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        logger.warning("Using guest scraper - limited to ~3200 recent tweets")

    async def scrape_profile(self, username: str, limit: Optional[int] = 3200):
        """Scrape using guest API (limited)."""
        # Fallback implementation using httpx
        import httpx
        
        username = username.lstrip("@").split("/")[-1]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            # Note: This uses public endpoints - may require bearer token
            logger.info(f"Guest scraping @{username}...")
            # Implementation depends on current public API availability
            raise NotImplementedError(
                "Guest scraper requires manual bearer token setup. "
                "Please configure accounts in .env for full functionality."
            )
