#!/usr/bin/env python3
"""Convenience launcher for the BizIQ analytics CLI."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from analytics_engine.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
