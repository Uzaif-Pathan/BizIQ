"""Shared constants for the BizIQ analytics engine (see contracts/)."""

BUSINESS_TYPES = ("retail", "service", "other")
STATUS_VALUES = ("completed", "partial", "failed")
EVIDENCE_LEVELS = ("low", "medium", "high")
BENCHMARK_STATUS_VALUES = ("available", "partial", "unavailable")

# Evidence-level thresholds (months of valid financial data).
MIN_MONTHS_MEDIUM = 6
MIN_MONTHS_HIGH = 12

PERIOD_FORMAT = "%Y-%m"  # monthly periods are YYYY-MM everywhere
