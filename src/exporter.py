"""
X-Tweet-Analyzer - Export Module
==================================
Exports tweet data to JSON, CSV, and Markdown formats.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TweetExporter:
    """Handles exporting tweet data to multiple formats."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, username: str, category: str, ext: str) -> Path:
        subdir = self.output_dir / ext
        subdir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return subdir / f"{username}_{category}_{timestamp}.{ext}"

    def export_json(self, tweets: List[Dict], username: str, category: str = "all",
                    output_path: Optional[str] = None) -> str:
        """Export tweets to JSON."""
        path = Path(output_path) if output_path else self._get_path(username, category, "json")
        export_data = {
            "username": username, "category": category, "total": len(tweets),
            "exported_at": datetime.now().isoformat(), "tweets": tweets,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Exported {len(tweets)} tweets to {path}")
        return str(path)

    def export_all_json(self, tweets: List[Dict], username: str,
                        output_dir: Optional[str] = None) -> Dict[str, str]:
        """Export tweets by category to JSON files."""
        base = Path(output_dir) if output_dir else self.output_dir / "json"
        base.mkdir(parents=True, exist_ok=True)
        categories = {
            "all": tweets,
            "original": [t for t in tweets if t.get("category") == "original"],
            "reply": [t for t in tweets if t.get("category") == "reply"],
            "retweet": [t for t in tweets if t.get("category") == "retweet"],
        }
        paths = {}
        for cat, cat_tweets in categories.items():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = base / f"{username}_{cat}_{ts}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"username": username, "category": cat,
                           "total": len(cat_tweets), "tweets": cat_tweets},
                          f, ensure_ascii=False, indent=2, default=str)
            paths[cat] = str(path)
        return paths

    CSV_FIELDS = [
        "id", "date", "category", "content", "username", "display_name",
        "reply_count", "retweet_count", "like_count", "view_count",
        "lang", "is_reply", "is_retweet",
        "replied_to_user", "retweeted_from_user",
        "hashtags", "mentions", "media_urls", "url",
    ]

    def export_csv(self, tweets: List[Dict], username: str, category: str = "all",
                   output_path: Optional[str] = None) -> str:
        """Export tweets to CSV."""
        path = Path(output_path) if output_path else self._get_path(username, category, "csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for tweet in tweets:
                row = dict(tweet)
                for field in ["hashtags", "mentions", "media_urls"]:
                    val = row.get(field, [])
                    try:
                        parsed = json.loads(val) if isinstance(val, str) else val
                        row[field] = "; ".join(parsed) if isinstance(parsed, list) else str(parsed)
                    except Exception:
                        row[field] = str(val)
                writer.writerow(row)
        return str(path)

    def export_all_csv(self, tweets: List[Dict], username: str,
                       output_dir: Optional[str] = None) -> Dict[str, str]:
        """Export tweets by category to CSV files."""
        base = Path(output_dir) if output_dir else self.output_dir / "csv"
        base.mkdir(parents=True, exist_ok=True)
        categories = {
            "all": tweets,
            "original": [t for t in tweets if t.get("category") == "original"],
            "reply": [t for t in tweets if t.get("category") == "reply"],
            "retweet": [t for t in tweets if t.get("category") == "retweet"],
        }
        paths = {}
        for cat, cat_tweets in categories.items():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = base / f"{username}_{cat}_{ts}.csv"
            self.export_csv(cat_tweets, username, cat, str(path))
            paths[cat] = str(path)
        return paths

    def export_markdown(self, tweets: List[Dict], username: str,
                        stats: Optional[Dict] = None, category: str = "all",
                        output_path: Optional[str] = None) -> str:
        """Export tweets to a Markdown document."""
        path = Path(output_path) if output_path else self._get_path(username, f"{category}_report", "md")
        lines = [
            f"# @{username} — Tweet Analysis Report",
            f"> Generated by **X-Tweet-Analyzer** on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        if stats:
            lines += [
                "## 📊 Statistics", "",
                "| Metric | Value |", "|--------|-------|",
                f"| Total Tweets | {stats.get('total', 0):,} |",
                f"| Original Tweets | {stats.get('originals', 0):,} |",
                f"| Replies | {stats.get('replies', 0):,} |",
                f"| Retweets | {stats.get('retweets', 0):,} |",
                f"| Total Likes | {stats.get('total_likes', 0) or 0:,} |",
                f"| Avg Likes | {(stats.get('avg_likes') or 0):.1f} |", "",
            ]
        cat_labels = {"original": "✍️ Original Tweets", "reply": "💬 Replies",
                      "retweet": "🔁 Retweets", "all": "📝 All Tweets"}
        lines += [f"## {cat_labels.get(category, 'Tweets')}", f"*Total: {len(tweets):,} tweets*", ""]
        for i, tweet in enumerate(tweets[:500], 1):
            date_str = tweet.get("date", "")
            try:
                dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            content = tweet.get("content", "").replace("\n", " ")
            emoji = {"original": "✍️", "reply": "💬", "retweet": "🔁"}.get(tweet.get("category", ""), "")
            lines += [
                f"### {i}. {emoji} [{date_str}]({tweet.get('url', '#')})", "",
                f"> {content}", "",
                f"👍 {tweet.get('like_count', 0):,} | 🔁 {tweet.get('retweet_count', 0):,} | "
                f"💬 {tweet.get('reply_count', 0):,}", "", "---", "",
            ]
        if len(tweets) > 500:
            lines.append(f"*... and {len(tweets)-500:,} more tweets in CSV/JSON exports.*")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return str(path)

    def export_all_markdown(self, tweets: List[Dict], username: str,
                            stats: Optional[Dict] = None) -> str:
        """Export full report to single Markdown file."""
        base = self.output_dir / "markdown"
        base.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = base / f"{username}_full_report_{ts}.md"
        originals = [t for t in tweets if t.get("category") == "original"]
        replies = [t for t in tweets if t.get("category") == "reply"]
        retweets = [t for t in tweets if t.get("category") == "retweet"]
        lines = [
            f"# @{username} — Complete Tweet Analysis",
            f"> Generated by **X-Tweet-Analyzer** on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        if stats:
            lines += [
                "## 📊 Summary", "",
                f"- **Total Tweets:** {stats.get('total', 0):,}",
                f"- **Originals:** {stats.get('originals', 0):,}",
                f"- **Replies:** {stats.get('replies', 0):,}",
                f"- **Retweets:** {stats.get('retweets', 0):,}", "",
            ]
        for section_name, section_tweets, emoji in [
            ("Original Tweets", originals, "✍️"),
            ("Replies", replies, "💬"),
            ("Retweets", retweets, "🔁"),
        ]:
            lines += [f"## {emoji} {section_name}", f"*{len(section_tweets):,} tweets*", ""]
            for i, tweet in enumerate(section_tweets[:200], 1):
                date_str = tweet.get("date", "")
                try:
                    dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
                content = tweet.get("content", "")
                lines += [
                    f"**{i}.** [{date_str}]({tweet.get('url','#')}) — "
                    f"👍{tweet.get('like_count',0):,} 🔁{tweet.get('retweet_count',0):,}",
                    f"> {content}", "",
                ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return str(path)
