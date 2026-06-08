"""Tests for the export module."""
import json
import csv
import os
import tempfile
from pathlib import Path

import pytest

from src.exporter import TweetExporter


def make_tweets(n=5):
    """Create sample tweet data."""
    tweets = []
    categories = ["original", "reply", "retweet"]
    for i in range(n):
        tweets.append({
            "id": i + 1,
            "date": f"2024-01-{i+1:02d}T12:00:00",
            "content": f"Tweet {i+1} content #test @mention",
            "username": "testuser",
            "display_name": "Test User",
            "category": categories[i % 3],
            "like_count": i * 10,
            "retweet_count": i * 2,
            "reply_count": i,
            "view_count": i * 100,
            "url": f"https://x.com/testuser/status/{i+1}",
            "hashtags": '["test"]',
            "mentions": '["mention"]',
            "media_urls": '[]',
            "lang": "en",
            "is_reply": categories[i % 3] == "reply",
            "is_retweet": categories[i % 3] == "retweet",
            "replied_to_user": "other" if categories[i % 3] == "reply" else None,
            "retweeted_from_user": "rtuser" if categories[i % 3] == "retweet" else None,
        })
    return tweets


@pytest.fixture
def output_dir(tmp_path):
    return str(tmp_path / "output")


@pytest.fixture
def exporter(output_dir):
    return TweetExporter(output_dir)


def test_export_json(exporter, output_dir):
    tweets = make_tweets(5)
    path = exporter.export_json(tweets, "testuser", "all")
    
    assert Path(path).exists()
    with open(path) as f:
        data = json.load(f)
    
    assert data["username"] == "testuser"
    assert data["total"] == 5
    assert len(data["tweets"]) == 5


def test_export_all_json(exporter):
    tweets = make_tweets(6)
    paths = exporter.export_all_json(tweets, "testuser")
    
    assert "all" in paths
    assert "original" in paths
    assert "reply" in paths
    assert "retweet" in paths
    
    # Verify all files exist
    for p in paths.values():
        assert Path(p).exists()


def test_export_csv(exporter):
    tweets = make_tweets(5)
    path = exporter.export_csv(tweets, "testuser")
    
    assert Path(path).exists()
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 5
    assert "content" in rows[0]
    assert "category" in rows[0]


def test_export_all_csv(exporter):
    tweets = make_tweets(6)
    paths = exporter.export_all_csv(tweets, "testuser")
    
    assert len(paths) == 4  # all, original, reply, retweet
    for p in paths.values():
        assert Path(p).exists()


def test_export_markdown(exporter):
    tweets = make_tweets(3)
    stats = {
        "total": 3,
        "originals": 1,
        "replies": 1,
        "retweets": 1,
        "total_likes": 30,
        "avg_likes": 10.0,
        "oldest_tweet": "2024-01-01",
        "newest_tweet": "2024-01-03",
    }
    path = exporter.export_markdown(tweets, "testuser", stats)
    
    assert Path(path).exists()
    content = Path(path).read_text(encoding="utf-8")
    
    assert "@testuser" in content
    assert "Statistics" in content
    assert "Tweet 1 content" in content


def test_empty_export(exporter):
    """Test exporting empty tweet list."""
    path = exporter.export_json([], "testuser", "all")
    
    assert Path(path).exists()
    with open(path) as f:
        data = json.load(f)
    
    assert data["total"] == 0
    assert data["tweets"] == []
