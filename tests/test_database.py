"""Tests for the database module."""
import asyncio
import os
import tempfile
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from src.database import Database


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest_asyncio.fixture
async def db(db_path):
    database = Database(db_path)
    await database.connect()
    yield database
    await database.close()


class MockTweet:
    def __init__(self, id=1, category="original"):
        self.id = id
        self.url = f"https://x.com/test/status/{id}"
        self.date = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        self.content = f"Test tweet {id}"
        self.username = "testuser"
        self.user_id = 12345
        self.display_name = "Test User"
        self.category = category
        self.reply_count = 5
        self.retweet_count = 10
        self.like_count = 50
        self.view_count = 1000
        self.lang = "en"
        self.source = "Twitter Web App"
        self.is_reply = category == "reply"
        self.is_retweet = category == "retweet"
        self.replied_to_user = "other_user" if category == "reply" else None
        self.replied_to_tweet_id = 999 if category == "reply" else None
        self.retweeted_from_user = "rt_user" if category == "retweet" else None
        self.retweeted_tweet_id = 888 if category == "retweet" else None
        self.media_urls = []
        self.hashtags = ["test", "python"]
        self.mentions = []
        self.raw_json = "{}"


@pytest.mark.asyncio
async def test_save_and_get_tweet(db):
    """Test saving and retrieving a tweet."""
    tweet = MockTweet(1, "original")
    await db.save_tweet(tweet)
    
    tweets = await db.get_tweets("testuser")
    assert len(tweets) == 1
    assert tweets[0]["id"] == 1
    assert tweets[0]["category"] == "original"
    assert tweets[0]["username"] == "testuser"


@pytest.mark.asyncio
async def test_tweet_categories(db):
    """Test that tweets are properly filtered by category."""
    await db.save_tweet(MockTweet(1, "original"))
    await db.save_tweet(MockTweet(2, "reply"))
    await db.save_tweet(MockTweet(3, "retweet"))
    await db.save_tweet(MockTweet(4, "original"))
    
    all_tweets = await db.get_tweets("testuser")
    originals = await db.get_tweets("testuser", category="original")
    replies = await db.get_tweets("testuser", category="reply")
    retweets = await db.get_tweets("testuser", category="retweet")
    
    assert len(all_tweets) == 4
    assert len(originals) == 2
    assert len(replies) == 1
    assert len(retweets) == 1


@pytest.mark.asyncio
async def test_get_stats(db):
    """Test statistics calculation."""
    await db.save_tweet(MockTweet(1, "original"))
    await db.save_tweet(MockTweet(2, "original"))
    await db.save_tweet(MockTweet(3, "reply"))
    await db.save_tweet(MockTweet(4, "retweet"))
    
    stats = await db.get_stats("testuser")
    
    assert stats["total"] == 4
    assert stats["originals"] == 2
    assert stats["replies"] == 1
    assert stats["retweets"] == 1


@pytest.mark.asyncio
async def test_tweet_exists(db):
    """Test tweet existence check."""
    await db.save_tweet(MockTweet(42))
    
    assert await db.tweet_exists(42) == True
    assert await db.tweet_exists(99) == False


@pytest.mark.asyncio
async def test_search_tweets(db):
    """Test tweet search functionality."""
    t1 = MockTweet(1, "original")
    t1.content = "Hello world python"
    t2 = MockTweet(2, "original")
    t2.content = "Goodbye world"
    
    await db.save_tweet(t1)
    await db.save_tweet(t2)
    
    results = await db.get_tweets("testuser", search="python")
    assert len(results) == 1
    assert "python" in results[0]["content"].lower()


@pytest.mark.asyncio
async def test_user_list(db):
    """Test user list retrieval."""
    await db.save_tweet(MockTweet(1))
    
    t2 = MockTweet(2)
    t2.username = "anotheruser"
    await db.save_tweet(t2)
    
    users = await db.get_user_list()
    assert "testuser" in users
    assert "anotheruser" in users
