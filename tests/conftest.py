"""Test-wide environment: the suite runs fully offline against in-memory servers."""

from __future__ import annotations

import os

# Must be set before agent.config is imported anywhere, since it reads env at import time.
os.environ.setdefault("AGENT_MODEL", "mock")
os.environ.setdefault("AGENT_API_KEY", "test-key")
os.environ.setdefault("AGENT_RATE_LIMIT_PER_MINUTE", "5")
