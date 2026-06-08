"""
X-Tweet-Analyzer - Database Module
====================================
SQLite database for storing and querying tweet data.
Uses aiosqlite for async operations.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT,
    description TEXT,
    followers_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    tweet_count INTEGER DEFAULT 0,
    verified INTEGER DEFAULT 0,
    created_at TEXT,
    profile_image_url TEXT,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tweets (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    date TEXT NOT NULL,
    content TEXT NOT NULL,
    username TEXT NOT NULL,
    user_id INTEGER,
    display_name TEXT,
    category TEXT NOT NULL DEFAULT 'original',
    reply_count INTEGER DEFAULT 0,
    retweet_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    lang TEXT,
    source TEXT,
    is_reply INTEGER DEFAULT 0,
    is_retweet INTEGER DEFAULT 0,
    replied_to_user TEXT,
    replied_to_tweet_id INTEGER,
    retweeted_from_user TEXT,
    retweeted_tweet_id INTEGER,
    media_urls TEXT DEFAULT '[]',
    hashtags TEXT DEFAULT '[]',
    mentions TEXT DEFAULT '[]',
    raw_json TEXT,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS scrape_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    total_tweets INTEGER DEFAULT 0,
    original_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    retweet_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_tweets_username ON tweets(username);
CREATE INDEX IF NOT EXISTS idx_tweets_date ON tweets(date);
CREATE INDEX IF NOT EXISTS idx_tweets_category ON tweets(category);
CREATE INDEX IF NOT EXISTS idx_tweets_user_id ON tweets(user_id);
"""


class Database:
    """Async SQLite database handler."""

    def __init__(self, db_path: str = "data/tweets.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Initialize database connection and create tables."""
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def close(self):
        """Close database connection."""
        if self._conn:
            await self._conn.close()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def save_user(self, user) -> None:
        """Save or update user profile."""
        await self._conn.execute("""
            INSERT OR REPLACE INTO users 
            (id, username, display_name, description, followers_count, 
             following_count, tweet_count, verified, created_at, profile_image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username,
            getattr(user, 'displayname', ''),
            getattr(user, 'rawDescription', ''),
            getattr(user, 'followersCount', 0) or 0,
            getattr(user, 'followingCount', 0) or 0,
            getattr(user, 'statusesCount', 0) or 0,
            1 if getattr(user, 'verified', False) else 0,
            str(getattr(user, 'created', '')),
            str(getattr(user, 'profileImageUrl', '')),
        ))
        await self._conn.commit()

    async def save_tweet(self, tweet) -> None:
        """Save a tweet to the database."""
        await self._conn.execute("""
            INSERT OR REPLACE INTO tweets
            (id, url, date, content, username, user_id, display_name,
             category, reply_count, retweet_count, like_count, view_count,
             lang, source, is_reply, is_retweet,
             replied_to_user, replied_to_tweet_id,
             retweeted_from_user, retweeted_tweet_id,
             media_urls, hashtags, mentions, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tweet.id,
            tweet.url,
            tweet.date.isoformat() if hasattr(tweet.date, 'isoformat') else str(tweet.date),
            tweet.content,
            tweet.username,
            tweet.user_id,
            tweet.display_name,
            tweet.category,
            tweet.reply_count,
            tweet.retweet_count,
            tweet.like_count,
            tweet.view_count,
            tweet.lang,
            tweet.source,
            1 if tweet.is_reply else 0,
            1 if tweet.is_retweet else 0,
            tweet.replied_to_user,
            tweet.replied_to_tweet_id,
            tweet.retweeted_from_user,
            tweet.retweeted_tweet_id,
            json.dumps(tweet.media_urls),
            json.dumps(tweet.hashtags),
            json.dumps(tweet.mentions),
            tweet.raw_json[:10000] if tweet.raw_json else None,
        ))
        await self._conn.commit()

    async def get_tweets(
        self,
        username: str,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query tweets with filtering and pagination."""
        conditions = ["username = ?"]
        params: list = [username]

        if category and category != "all":
            conditions.append("category = ?")
            params.append(category)

        if since:
            conditions.append("date >= ?")
            params.append(since.isoformat())

        if until:
            conditions.append("date <= ?")
            params.append(until.isoformat())

        if search:
            conditions.append("content LIKE ?")
            params.append(f"%{search}%")

        where = " AND ".join(conditions)
        query = f"SELECT * FROM tweets WHERE {where} ORDER BY date DESC"

        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_stats(self, username: str) -> Dict[str, Any]:
        """Get tweet statistics for a user."""
        async with self._conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN category='original' THEN 1 ELSE 0 END) as originals,
                SUM(CASE WHEN category='reply' THEN 1 ELSE 0 END) as replies,
                SUM(CASE WHEN category='retweet' THEN 1 ELSE 0 END) as retweets,
                SUM(like_count) as total_likes,
                SUM(retweet_count) as total_retweets,
                SUM(reply_count) as total_replies,
                AVG(like_count) as avg_likes,
                MIN(date) as oldest_tweet,
                MAX(date) as newest_tweet
            FROM tweets WHERE username = ?
        """, (username,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}

    async def get_top_hashtags(self, username: str, limit: int = 20) -> List[Dict]:
        """Get most used hashtags."""
        async with self._conn.execute(
            "SELECT hashtags FROM tweets WHERE username = ? AND hashtags != '[]'",
            (username,)
        ) as cursor:
            rows = await cursor.fetchall()

        hashtag_counts: Dict[str, int] = {}
        for row in rows:
            tags = json.loads(row['hashtags'])
            for tag in tags:
                hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1

        sorted_tags = sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"hashtag": k, "count": v} for k, v in sorted_tags[:limit]]

    async def tweet_exists(self, tweet_id: int) -> bool:
        """Check if a tweet already exists in the database."""
        async with self._conn.execute(
            "SELECT 1 FROM tweets WHERE id = ?", (tweet_id,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_user_list(self) -> List[str]:
        """Get list of all scraped usernames."""
        async with self._conn.execute(
            "SELECT DISTINCT username FROM tweets ORDER BY username"
        ) as cursor:
            rows = await cursor.fetchall()
            return [row['username'] for row in rows]

    async def start_session(self, username: str) -> int:
        """Create a new scrape session record."""
        cursor = await self._conn.execute("""
            INSERT INTO scrape_sessions (username, started_at)
            VALUES (?, ?)
        """, (username, datetime.now().isoformat()))
        await self._conn.commit()
        return cursor.lastrowid

    async def complete_session(self, session_id: int, stats: Dict):
        """Mark a scrape session as completed."""
        await self._conn.execute("""
            UPDATE scrape_sessions
            SET completed_at = ?, total_tweets = ?, original_count = ?,
                reply_count = ?, retweet_count = ?, status = ?
            WHERE id = ?
        """, (
            datetime.now().isoformat(),
            stats.get('total', 0),
            stats.get('originals', 0),
            stats.get('replies', 0),
            stats.get('retweets', 0),
            'completed',
            session_id
        ))
        await self._conn.commit()
