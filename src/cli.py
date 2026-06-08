"""
X-Tweet-Analyzer - CLI Module
================================
Powerful command-line interface using Click + Rich.

Usage:
    python main.py scrape username
    python main.py scrape @naval --limit 500 --format json
    python main.py serve --port 8000
    python main.py stats username
    python main.py export username --format all
    python main.py list-users
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from .config import Config
from .database import Database
from .scraper import XScraper
from .exporter import TweetExporter

console = Console()


@click.group()
@click.version_option("1.0.0", prog_name="x-analyzer")
def cli():
    """🐦 X-Tweet-Analyzer — Extract and analyze tweets from any X/Twitter profile."""
    pass


@cli.command()
@click.argument("username")
@click.option("--limit", "-l", default=None, type=int, help="Max tweets (default: all)")
@click.option("--since", "-s", default=None, help="Since date YYYY-MM-DD")
@click.option("--until", "-u", default=None, help="Until date YYYY-MM-DD")
@click.option("--output", "-o", default="output", help="Output directory")
@click.option("--db", default="data/tweets.db", help="Database path")
@click.option("--format", "-f", "export_format",
              type=click.Choice(["json", "csv", "markdown", "all"]), default="all")
@click.option("--no-export", is_flag=True, help="Skip export, DB only")
@click.option("--verbose", "-v", is_flag=True)
def scrape(username, limit, since, until, output, db, export_format, no_export, verbose):
    """Scrape all tweets from a profile.
    
    USERNAME can be a handle (@user), URL, or username.
    
    Examples:\n
        x-analyzer scrape elonmusk\n
        x-analyzer scrape @naval --limit 1000\n
        x-analyzer scrape https://x.com/sama --format csv
    """
    asyncio.run(_scrape(username, limit, since, until, output, db, export_format, no_export, verbose))


async def _scrape(username, limit, since, until, output, db_path, export_format, no_export, verbose):
    username = username.lstrip("@")
    if "x.com/" in username or "twitter.com/" in username:
        username = username.split("/")[-1].split("?")[0]

    config = Config.from_env()
    config.output_dir = output
    config.db_path = db_path
    config.ensure_dirs()

    since_dt = datetime.strptime(since, "%Y-%m-%d") if since else None
    until_dt = datetime.strptime(until, "%Y-%m-%d") if until else None

    console.print(Panel(
        f"[bold]Profile:[/bold] [cyan]@{username}[/cyan]\n"
        f"[bold]Limit:[/bold] {limit or 'All'}  [bold]Format:[/bold] {export_format}",
        title="🐦 X-Tweet-Analyzer — Scraping",
        border_style="blue"
    ))

    async with Database(db_path) as db:
        scraper = XScraper(config, db)
        await scraper.setup_accounts()

        original_count = reply_count = retweet_count = 0
        all_tweets = []

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), TaskProgressColumn(), console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Scraping @{username}...", total=limit)

            async for tweet in scraper.scrape_profile(
                username, limit=limit, since=since_dt, until=until_dt
            ):
                if tweet.category == "original":
                    original_count += 1
                elif tweet.category == "reply":
                    reply_count += 1
                else:
                    retweet_count += 1

                all_tweets.append(tweet.__dict__)
                progress.advance(task)

                if verbose:
                    console.print(f"  [{tweet.category}] {tweet.date} — {tweet.content[:80]}...")

        total = original_count + reply_count + retweet_count

        table = Table(title=f"📊 Results for @{username}")
        table.add_column("Category", style="bold")
        table.add_column("Count", justify="right")
        table.add_column("Percentage", justify="right")
        table.add_row("✍️ Original", str(original_count),
                      f"{original_count/total*100:.1f}%" if total else "0%")
        table.add_row("💬 Replies", str(reply_count),
                      f"{reply_count/total*100:.1f}%" if total else "0%")
        table.add_row("🔁 Retweets", str(retweet_count),
                      f"{retweet_count/total*100:.1f}%" if total else "0%")
        table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", "100%")
        console.print(table)

        if not no_export and all_tweets:
            exporter = TweetExporter(output)
            if export_format in ("json", "all"):
                paths = exporter.export_all_json(all_tweets, username)
                for cat, path in paths.items():
                    console.print(f"  ✅ JSON [{cat}]: {path}")
            if export_format in ("csv", "all"):
                paths = exporter.export_all_csv(all_tweets, username)
                for cat, path in paths.items():
                    console.print(f"  ✅ CSV [{cat}]: {path}")
            if export_format in ("markdown", "all"):
                path = exporter.export_all_markdown(all_tweets, username)
                console.print(f"  ✅ Markdown: {path}")

    console.print("\n[green bold]✨ Done![/green bold]")


@cli.command()
@click.argument("username")
@click.option("--db", default="data/tweets.db")
@click.option("--category", "-c",
              type=click.Choice(["all", "original", "reply", "retweet"]), default="all")
@click.option("--format", "-f", "export_format",
              type=click.Choice(["json", "csv", "markdown", "all"]), default="all")
@click.option("--output", "-o", default="output")
def export(username, db, category, export_format, output):
    """Export tweets from database to files."""
    asyncio.run(_export_cmd(username, db, category, export_format, output))


async def _export_cmd(username, db_path, category, export_format, output):
    async with Database(db_path) as db:
        tweets = await db.get_tweets(username, category=category if category != "all" else None)
        stats = await db.get_stats(username)
        if not tweets:
            console.print(f"[red]No tweets found for @{username}[/red]")
            return
        exporter = TweetExporter(output)
        if export_format in ("json", "all"):
            paths = exporter.export_all_json(tweets, username)
            for cat, path in paths.items():
                console.print(f"✅ JSON [{cat}]: {path}")
        if export_format in ("csv", "all"):
            paths = exporter.export_all_csv(tweets, username)
            for cat, path in paths.items():
                console.print(f"✅ CSV [{cat}]: {path}")
        if export_format in ("markdown", "all"):
            path = exporter.export_all_markdown(tweets, username, stats)
            console.print(f"✅ Markdown: {path}")


@cli.command(name="list-users")
@click.option("--db", default="data/tweets.db")
def list_users(db):
    """List all scraped users."""
    asyncio.run(_list_users(db))


async def _list_users(db_path):
    async with Database(db_path) as db:
        users = await db.get_user_list()
        if not users:
            console.print("[yellow]No users in database yet.[/yellow]")
            return
        table = Table(title="Scraped Users")
        table.add_column("Username", style="cyan")
        for user in users:
            table.add_row(f"@{user}")
        console.print(table)


@cli.command()
@click.argument("username")
@click.option("--db", default="data/tweets.db")
def stats(username, db):
    """Show statistics for a scraped profile."""
    asyncio.run(_stats(username, db))


async def _stats(username, db_path):
    async with Database(db_path) as db:
        s = await db.get_stats(username)
        tags = await db.get_top_hashtags(username, 10)
        if not s or not s.get("total"):
            console.print(f"[red]No data for @{username}[/red]")
            return
        console.print(Panel(
            f"[bold]Total:[/bold] {s.get('total', 0):,}\n"
            f"[bold]Originals:[/bold] {s.get('originals', 0):,}  "
            f"[bold]Replies:[/bold] {s.get('replies', 0):,}  "
            f"[bold]Retweets:[/bold] {s.get('retweets', 0):,}\n"
            f"[bold]Total Likes:[/bold] {s.get('total_likes', 0) or 0:,}  "
            f"[bold]Avg Likes:[/bold] {(s.get('avg_likes') or 0):.1f}\n"
            f"[bold]Date Range:[/bold] {s.get('oldest_tweet', '?')} → {s.get('newest_tweet', '?')}",
            title=f"📊 @{username}", border_style="green"
        ))
        if tags:
            table = Table(title="Top Hashtags")
            table.add_column("Hashtag")
            table.add_column("Count", justify="right")
            for tag in tags:
                table.add_row(f"#{tag['hashtag']}", str(tag['count']))
            console.print(table)


@cli.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", "-p", default=8000, type=int)
@click.option("--db", default="data/tweets.db")
def serve(host, port, db):
    """Start the web interface."""
    import uvicorn
    from .api import create_app
    app = create_app(db_path=db)
    console.print(f"[green]🌐 Web UI at http://{host}:{port}[/green]")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
