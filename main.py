#!/usr/bin/env python3
"""
X-Tweet-Analyzer - Main Entry Point
======================================
Run the CLI or web server.

Usage:
    python main.py scrape username
    python main.py scrape @naval --limit 500
    python main.py serve --port 8000
    python main.py stats username
    python main.py export username --format all
    python main.py list-users
"""

import sys
from src.cli import cli

if __name__ == "__main__":
    cli()
