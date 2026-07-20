"""
X-Tweet-Analyzer - Configuration Module
==========================================
Handles all configuration via environment variables and config files.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    # Database
    db_path: str = "data/tweets.db"

    # Scraping
    rate_limit_delay: float = 1.0
    max_retries: int = 5
    tweets_per_page: int = 100
    default_limit: Optional[int] = None

    # Output
    output_dir: str = "output"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Web server
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Accounts file
    accounts_file: str = "accounts.json"

    # Xquik API source
    xquik_api_key: Optional[str] = None
    xquik_base_url: str = "https://xquik.com/api/v1"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            db_path=os.getenv("DB_PATH", "data/tweets.db"),
            rate_limit_delay=float(os.getenv("RATE_LIMIT_DELAY", "1.0")),
            max_retries=int(os.getenv("MAX_RETRIES", "5")),
            default_limit=int(v) if (v := os.getenv("DEFAULT_LIMIT")) else None,
            output_dir=os.getenv("OUTPUT_DIR", "output"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            log_file=os.getenv("LOG_FILE"),
            host=os.getenv("WEB_HOST", "127.0.0.1"),
            port=int(os.getenv("WEB_PORT", "8000")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            accounts_file=os.getenv("ACCOUNTS_FILE", "accounts.json"),
            xquik_api_key=os.getenv("XQUIK_API_KEY"),
            xquik_base_url=os.getenv("XQUIK_BASE_URL", "https://xquik.com/api/v1"),
        )

    def get_accounts(self) -> List[Dict[str, str]]:
        """Load Twitter accounts from JSON file or environment variables."""
        accounts = []

        # Try loading from JSON file first
        accounts_path = Path(self.accounts_file)
        if accounts_path.exists():
            try:
                with open(accounts_path) as f:
                    data = json.load(f)
                    accounts = (
                        data if isinstance(data, list) else data.get("accounts", [])
                    )
            except Exception as e:
                print(f"Warning: Could not load accounts file: {e}")

        # Fall back to environment variables
        if not accounts:
            username = os.getenv("TWITTER_USERNAME")
            password = os.getenv("TWITTER_PASSWORD")
            email = os.getenv("TWITTER_EMAIL")

            if username and password and email:
                accounts.append(
                    {
                        "username": username,
                        "password": password,
                        "email": email,
                        "email_password": os.getenv("TWITTER_EMAIL_PASSWORD", ""),
                    }
                )

        return accounts

    def ensure_dirs(self):
        """Create necessary directories."""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        exports = Path(self.output_dir)
        for subdir in ["json", "csv", "markdown"]:
            (exports / subdir).mkdir(parents=True, exist_ok=True)
