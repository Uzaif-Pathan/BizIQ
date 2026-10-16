import sys
from pathlib import Path

# Make `analytics_engine` importable without installing it (backend/ on sys.path).
BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"
