"""Tests for the Xquik import client."""

from datetime import datetime, timezone

import httpx
import pytest

from src.xquik_client import XquikClient, normalize_username, tweet_from_xquik


def sample_tweet(tweet_id="123", text="Hello #x @user"):
    return {
        "id": tweet_id,
        "text": text,
        "createdAt": "2025-01-15T12:00:00Z",
        "url": f"https://x.com/xquikcom/status/{tweet_id}",
        "lang": "en",
        "source": "Twitter Web App",
        "isReply": True,
        "inReplyToId": "99",
        "inReplyToUsername": "other",
        "likeCount": 42,
        "retweetCount": 5,
        "replyCount": 3,
        "viewCount": 1500,
        "author": {
            "id": "987",
            "username": "xquikcom",
            "name": "Xquik",
        },
        "entities": {
            "hashtags": [{"text": "x"}],
            "user_mentions": [{"screen_name": "user"}],
        },
        "media": [{"mediaUrl": "https://pbs.twimg.com/media/example.jpg"}],
    }


def test_tweet_from_xquik_maps_search_tweet():
    tweet = tweet_from_xquik(sample_tweet())

    assert tweet.id == 123
    assert tweet.username == "xquikcom"
    assert tweet.user_id == 987
    assert tweet.display_name == "Xquik"
    assert tweet.date == datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
    assert tweet.category == "reply"
    assert tweet.replied_to_user == "other"
    assert tweet.replied_to_tweet_id == 99
    assert tweet.like_count == 42
    assert tweet.media_urls == ["https://pbs.twimg.com/media/example.jpg"]
    assert tweet.hashtags == ["x"]
    assert tweet.mentions == ["user"]


@pytest.mark.asyncio
async def test_search_profile_paginates_and_authenticates():
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "tweets": [sample_tweet("1")],
                    "has_next_page": True,
                    "next_cursor": "next-page",
                },
            )
        return httpx.Response(
            200,
            json={
                "tweets": [sample_tweet("2")],
                "has_next_page": False,
                "next_cursor": "",
            },
        )

    client = XquikClient(
        api_key="sample",
        base_url="https://example.test/api/v1",
        transport=httpx.MockTransport(handler),
    )

    tweets = [
        tweet
        async for tweet in client.search_profile(
            "https://x.com/xquikcom",
            limit=2,
            since=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    ]

    assert [tweet.id for tweet in tweets] == [1, 2]
    assert len(requests) == 2
    first_params = dict(requests[0].url.params)
    second_params = dict(requests[1].url.params)
    assert requests[0].headers["x-api-key"] == "sample"
    assert "authorization" not in requests[0].headers
    assert first_params["q"] == "from:xquikcom"
    assert first_params["queryType"] == "Latest"
    assert first_params["limit"] == "2"
    assert first_params["sinceTime"] == "2025-01-01T00:00:00Z"
    assert second_params["cursor"] == "next-page"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("xquikcom", "xquikcom"),
        ("@xquikcom", "xquikcom"),
        ("https://x.com/xquikcom?lang=en", "xquikcom"),
        ("https://www.twitter.com/xquikcom/", "xquikcom"),
    ],
)
def test_normalize_username_accepts_handles_and_profile_urls(value, expected):
    assert normalize_username(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://example.com/x.com/xquikcom",
        "https://x.com/xquikcom/status/123",
        "xquik-com",
        "a" * 16,
    ],
)
def test_normalize_username_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_username(value)


def test_tweet_from_xquik_requires_created_at():
    raw_tweet = sample_tweet()
    del raw_tweet["createdAt"]

    with pytest.raises(ValueError, match="createdAt"):
        tweet_from_xquik(raw_tweet)
