# 🐦 X-Tweet-Analyzer

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![twscrape](https://img.shields.io/badge/scraper-twscrape-orange)](https://github.com/vladkens/twscrape)

**Powerful X/Twitter profile analyzer & tweet scraper**  
Extract, classify, and export all tweets from any public profile.

[Features](#-features) · [Quick Start](#-quick-start) · [CLI Usage](#-cli-usage) · [Web UI](#-web-ui) · [Structure](#-structure)

</div>

---

## ✨ Features

- 🔍 **Deep Scraping** — Extract ALL tweets from any public profile (paginated, no limit)
- 📂 **Auto-Classification** — Automatically separates tweets into 3 categories:
  - ✍️ **Original Tweets** — Posts the user wrote themselves
  - 💬 **Replies** — Responses to other users
  - 🔁 **Retweets** — Content the user re-shared
- 🗄️ **SQLite Storage** — All data persisted locally for re-querying without re-scraping
- 📤 **Multi-format Export** — JSON, CSV (per category), and beautiful Markdown reports
- 🌐 **Web Interface** — Beautiful dark-mode UI with real-time progress, filtering, and charts
- ⌨️ **Powerful CLI** — Rich terminal interface with progress bars and statistics
- 🔄 **Rate Limit Handling** — Automatic retry with exponential backoff
- 👥 **Multi-Account Pool** — Rotate through multiple accounts to avoid rate limits
- 🐳 **Docker Ready** — One-command deployment with Docker Compose
- 🔎 **Search & Filter** — Query tweets by date range, category, or keyword

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/estelar-latam/X-Tweet-Analyzer.git
cd X-Tweet-Analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Accounts

```bash
cp .env.example .env
# Edit .env with your Twitter credentials

# OR for multiple accounts (recommended):
cp accounts.example.json accounts.json
# Edit accounts.json with your accounts
```

### 3. Scrape a Profile

```bash
# Basic scrape
python main.py scrape elonmusk

# With options
python main.py scrape @naval --limit 1000 --format json

# Using full URL
python main.py scrape https://x.com/sama --since 2024-01-01
```

---

## ⌨️ CLI Usage

```
Usage: python main.py [OPTIONS] COMMAND [ARGS]...

Commands:
  scrape       Scrape all tweets from a profile
  export       Export tweets from database to files
  stats        Show statistics for a scraped profile
  list-users   List all scraped users in the database
  serve        Start the web interface server
```

### Scrape Command

```bash
python main.py scrape USERNAME [OPTIONS]

Options:
  -l, --limit INTEGER        Max tweets to fetch (default: all)
  -s, --since TEXT           Fetch since date (YYYY-MM-DD)
  -u, --until TEXT           Fetch until date (YYYY-MM-DD)
  -o, --output TEXT          Output directory (default: output)
  -f, --format [json|csv|markdown|all]  Export format (default: all)
  --no-export                Skip file export (DB only)
  -v, --verbose              Verbose output

Examples:
  python main.py scrape elonmusk
  python main.py scrape @naval --limit 500
  python main.py scrape sama --since 2024-01-01 --format csv
  python main.py scrape https://x.com/1nose_Yuragi --format all
```

### Stats Command

```bash
python main.py stats USERNAME
# Shows total/original/reply/retweet counts, engagement stats, top hashtags
```

### Export Command

```bash
python main.py export USERNAME --format all
python main.py export USERNAME --category reply --format markdown
```

### Web Server

```bash
python main.py serve --port 8000
# Open http://localhost:8000
```

---

## 🌐 Web UI

The web interface provides:

- **Real-time scraping** with live progress updates
- **Tweet feed** with category tabs (All / Original / Replies / Retweets)
- **Statistics dashboard** with distribution chart
- **Search & filter** tweets by keyword
- **Pagination** for large datasets
- **One-click export** to JSON / CSV / Markdown
- **Saved profiles** list for quick access

### Screenshots

```
http://localhost:8000
```

---

## 🐳 Docker

```bash
# Build and start
docker-compose up -d

# Access web UI
open http://localhost:8000

# CLI inside container
docker-compose exec analyzer python main.py scrape username
```

---

## 📁 Structure

```
X-Tweet-Analyzer/
├── src/
│   ├── __init__.py          # Package init
│   ├── scraper.py           # Main scraper (twscrape)
│   ├── database.py          # SQLite async database
│   ├── exporter.py          # JSON/CSV/Markdown export
│   ├── config.py            # Configuration management
│   ├── cli.py               # CLI interface (Click + Rich)
│   └── api.py               # FastAPI web backend
├── web/
│   └── index.html           # Single-file web UI
├── tests/
│   ├── test_scraper.py      # Scraper tests
│   ├── test_database.py     # Database tests
│   └── test_exporter.py     # Exporter tests
├── data/                    # SQLite databases (gitignored)
├── output/                  # Exported files (gitignored)
│   ├── json/
│   ├── csv/
│   └── markdown/
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project metadata
├── Dockerfile               # Docker image
├── docker-compose.yml       # Docker Compose
├── .env.example             # Environment template
├── accounts.example.json    # Accounts template
└── README.md
```

---

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TWITTER_USERNAME` | — | Twitter account username |
| `TWITTER_PASSWORD` | — | Twitter account password |
| `TWITTER_EMAIL` | — | Twitter account email |
| `ACCOUNTS_FILE` | accounts.json | Path to accounts JSON |
| `DB_PATH` | data/tweets.db | SQLite database path |
| `OUTPUT_DIR` | output | Export output directory |
| `RATE_LIMIT_DELAY` | 1.0 | Delay between requests (seconds) |
| `MAX_RETRIES` | 5 | Max retries on rate limit |
| `WEB_HOST` | 127.0.0.1 | Web server host |
| `WEB_PORT` | 8000 | Web server port |
| `LOG_LEVEL` | INFO | Logging verbosity |

---

## 📊 Output Examples

### JSON Output

```json
{
  "username": "1nose_Yuragi",
  "category": "original",
  "total": 142,
  "tweets": [
    {
      "id": 1234567890,
      "date": "2024-01-15T12:30:00+00:00",
      "content": "Tweet content here...",
      "category": "original",
      "like_count": 523,
      "retweet_count": 89,
      "reply_count": 12,
      "hashtags": ["tag1", "tag2"],
      "url": "https://x.com/user/status/1234567890"
    }
  ]
}
```

### CSV Columns

`id, date, category, content, username, display_name, reply_count, retweet_count, like_count, view_count, lang, is_reply, is_retweet, replied_to_user, retweeted_from_user, hashtags, mentions, media_urls, url`

---

## 🧪 Tests

```bash
pytest tests/ -v --cov=src
```

---

## ⚠️ Important Notes

- **Requires Twitter accounts** for full scraping capabilities (twscrape)
- Public profiles can be scraped; private profiles require following
- Respect Twitter's Terms of Service and rate limits
- This tool is for personal/research use only
- Guest mode is limited to ~3200 recent tweets

---

## 📜 License

MIT License — see [LICENSE](LICENSE)

---

<div align="center">

Made with ❤️ by [estelar-latam](https://github.com/estelar-latam)

⭐ Star this repo if it helped you!

</div>
