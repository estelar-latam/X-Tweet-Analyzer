"""
Pytest configuration and shared fixtures for X-Tweet-Analyzer tests.
"""
import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()
