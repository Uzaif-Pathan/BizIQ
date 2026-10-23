"""BizIQ analytics engine (Person 2).

A standalone Python package: no FastAPI, no database. Person 3 calls
``run_analysis`` through a small adapter.
"""

__version__ = "0.1.0"


def __getattr__(name):  # lazy export: keeps ``import analytics_engine`` cheap
    if name == "run_analysis":
        from .pipeline import run_analysis
        return run_analysis
    raise AttributeError(name)
