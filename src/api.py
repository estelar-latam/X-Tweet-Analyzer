"""
X-Tweet-Analyzer - FastAPI Backend
=====================================
REST API + web interface for the X-Tweet-Analyzer.
"""

import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import Config
from .database import Database
from .scraper import XScraper
from .exporter import TweetExporter

logger = logging.getLogger(__name__)

_db: Optional[Database] = None
_config: Optional[Config] = None
_scrape_status = {}


def create_app(db_path: str = "data/tweets.db") -> FastAPI:
    """Create and configure the FastAPI application."""
    config = Config.from_env()
    config.db_path = db_path

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _db, _config
        _config = config
        _db = Database(db_path)
        await _db.connect()
        logger.info("Database connected")
        yield
        await _db.close()

    app = FastAPI(
        title="X-Tweet-Analyzer",
        description="X/Twitter profile analyzer and tweet scraper",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    # Mount static files
    static_path = Path(__file__).parent.parent / "web" / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = Path(__file__).parent.parent / "web" / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"))
        return HTMLResponse("""
        <h1>🐦 X-Tweet-Analyzer API</h1>
        <p>Web UI not found. Start from the project root with: python main.py serve</p>
        <p><a href="/docs">API Documentation →</a></p>
        """)

    class ScrapeRequest(BaseModel):
        username: str
        limit: Optional[int] = None
        since: Optional[str] = None
        until: Optional[str] = None

    @app.post("/api/scrape")
    async def start_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
        """Start scraping a profile in the background."""
        username = req.username.lstrip("@").split("/")[-1]

        if _scrape_status.get(username, {}).get("status") == "running":
            return {"message": f"Already scraping @{username}", "status": "running"}

        _scrape_status[username] = {"status": "running", "total": 0, "originals": 0,
                                     "replies": 0, "retweets": 0, "error": None}

        background_tasks.add_task(_scrape_bg, username, req.limit, req.since, req.until)
        return {"message": f"Started scraping @{username}", "username": username, "status": "running"}

    async def _scrape_bg(username, limit, since, until):
        from datetime import datetime
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d") if since else None
            until_dt = datetime.strptime(until, "%Y-%m-%d") if until else None

            scraper = XScraper(_config, _db)
            await scraper.setup_accounts()

            async for tweet in scraper.scrape_profile(username, limit=limit, since=since_dt, until=until_dt):
                s = _scrape_status[username]
                s["total"] = s.get("total", 0) + 1
                s[tweet.category + "s"] = s.get(tweet.category + "s", 0) + 1

            _scrape_status[username]["status"] = "completed"
        except Exception as e:
            _scrape_status[username].update({"status": "error", "error": str(e)})
            logger.error(f"Scrape error @{username}: {e}")

    @app.get("/api/scrape/status/{username}")
    async def scrape_status(username: str):
        return _scrape_status.get(username.lstrip("@"), {"status": "not_started"})

    @app.get("/api/users")
    async def list_users():
        users = await _db.get_user_list()
        return {"users": users}

    @app.get("/api/tweets/{username}")
    async def get_tweets(
        username: str,
        category: Optional[str] = Query("all"),
        limit: int = Query(50, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        search: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ):
        from datetime import datetime
        since_dt = datetime.fromisoformat(since) if since else None
        until_dt = datetime.fromisoformat(until) if until else None
        tweets = await _db.get_tweets(
            username,
            category=category if category not in ("all", None) else None,
            limit=limit, offset=offset, since=since_dt, until=until_dt, search=search,
        )
        return {"username": username, "category": category, "count": len(tweets), "tweets": tweets}

    @app.get("/api/stats/{username}")
    async def get_stats(username: str):
        stats = await _db.get_stats(username)
        tags = await _db.get_top_hashtags(username)
        return {"username": username, "stats": stats, "top_hashtags": tags}

    @app.get("/api/export/{username}")
    async def export_tweets(
        username: str,
        format: str = Query("json"),
        category: str = Query("all"),
        output: str = "output",
    ):
        tweets = await _db.get_tweets(username, category=category if category != "all" else None)
        stats = await _db.get_stats(username)
        if not tweets:
            raise HTTPException(404, f"No tweets found for @{username}")
        exporter = TweetExporter(output)
        paths = {}
        if format in ("json", "all"):
            paths["json"] = exporter.export_all_json(tweets, username)
        if format in ("csv", "all"):
            paths["csv"] = exporter.export_all_csv(tweets, username)
        if format in ("markdown", "all"):
            paths["markdown"] = exporter.export_all_markdown(tweets, username, stats)
        return {"username": username, "format": format, "exported": paths}

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    return app
