"""Generate synthetic BizIQ sample datasets (no real customer data).

Usage:  python scripts/generate_demo_data.py
Writes to data/samples/<scenario>/{financials,customers,products}.csv and
data/samples/businesses.json. Deterministic (fixed seed), so it is repeatable.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "samples"
RNG = np.random.default_rng(42)

BUSINESSES = {
    "retail": {"business_id": "11111111-1111-4111-8111-111111111111",
               "name": "Demo General Store", "business_type": "retail",
               "industry": "grocery retail", "location": "Nashik, Maharashtra"},
    "service": {"business_id": "22222222-2222-4222-8222-222222222222",
                "name": "Demo Tailoring Studio", "business_type": "service",
                "industry": "personal services", "location": "Pune, Maharashtra"},
    "cold_start": {"business_id": "33333333-3333-4333-8333-333333333333",
                   "name": "Demo New Cafe", "business_type": "other",
                   "industry": "food and beverage", "location": "Nagpur, Maharashtra"},
    "messy": {"business_id": "44444444-4444-4444-8444-444444444444",
              "name": "Demo Messy Records", "business_type": "retail",
              "industry": "general retail", "location": "Thane, Maharashtra"},
}


def months(start: str, n: int) -> list[str]:
    return [str(p) for p in pd.period_range(start, periods=n, freq="M")]


def financials(bid, start, n, base, growth, cost_ratio, complete, season=0.15):
    rows = []
    for i, m in enumerate(months(start, n)):
        seasonal = 1 + season * np.sin(2 * np.pi * (i % 12) / 12)
        rev = base * (1 + growth) ** i * seasonal * RNG.normal(1, 0.04)
        exp = rev * cost_ratio * RNG.normal(1, 0.03)
        rows.append((bid, m, round(rev), round(exp), complete))
    return pd.DataFrame(rows, columns=["business_id", "period", "revenue", "expenses",
                                        "expenses_complete"])


def customers(bid, fin, n_customers, loyal_share=0.25, spend_share=0.9):
    ids = [f"C{i:03d}" for i in range(1, n_customers + 1)]
    loyal = set(ids[: int(n_customers * loyal_share)])
    rows = []
    for _, f in fin.iterrows():
        active = [c for c in ids if (c in loyal and RNG.random() < 0.8) or RNG.random() < 0.12]
        if not active:
            continue
        w = RNG.gamma(2.0, 1.0, len(active))
        w = np.array([x * (3 if c in loyal else 1) for x, c in zip(w, active)])
        amounts = f["revenue"] * spend_share * w / w.sum()
        for c, a in zip(active, amounts):
            t = int(max(1, round(a / RNG.uniform(250, 600))))
            rows.append((bid, f["period"], c, t, round(a, 2)))
    return pd.DataFrame(rows, columns=["business_id", "period", "customer_id",
                                       "transactions", "amount_spent"])


def products(bid, fin, specs):
    shares = np.array([s[2] for s in specs], dtype=float)
    rows = []
    for k, (_, f) in enumerate(fin.iterrows()):
        drift = np.array([s[3] * k for s in specs])  # some products trend up/down
        w = np.clip(shares + drift, 0.01, None) * RNG.normal(1, 0.05, len(specs))
        w = w / w.sum()
        for (pid, name, _, _, price, margin), share in zip(specs, w):
            rev = f["revenue"] * share
            units = max(1, round(rev / price))
            rows.append((bid, f["period"], pid, name, units, round(rev, 2),
                         round(rev * (1 - margin), 2)))
    return pd.DataFrame(rows, columns=["business_id", "period", "product_id",
                                       "product_name", "units_sold", "revenue", "cost"])


PRODUCT_SPECS = [  # id, name, base share, monthly share drift, price, gross margin
    ("P01", "Rice (5kg)", 0.28, 0.000, 320, 0.12),
    ("P02", "Cooking oil (1L)", 0.20, 0.001, 150, 0.10),
    ("P03", "Snacks", 0.16, 0.002, 40, 0.30),
    ("P04", "Soft drinks", 0.14, -0.002, 45, 0.22),
    ("P05", "Toiletries", 0.12, 0.000, 120, 0.25),
    ("P06", "Stationery", 0.06, -0.001, 30, 0.35),
    ("P07", "Frozen foods", 0.04, 0.001, 200, 0.18),
]


def write(scenario: str, **tables: pd.DataFrame) -> None:
    d = OUT / scenario
    d.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(d / f"{name}.csv", index=False)


def messy_financials(bid: str) -> pd.DataFrame:
    """A deliberately broken table that exercises every validation rule."""
    rows = [
        (bid, "2025-01", 100000, 82000, "true"),
        (bid, "2025-02", 104000, 85000, "true"),
        (bid, "2025-03", 98000, 80000, "true"),
        (bid, "2025-03", 98000, 80000, "true"),    # exact duplicate
        (bid, "2025-04", 101000, 83000, "true"),
        (bid, "2025-05", "₹25,000", 84000, "true"),  # formatted string
        (bid, "2025-06", None, 86000, "true"),      # missing revenue
        (bid, "2025-07", -5000, 79000, "true"),     # negative revenue
        (bid, "2025-08", 99000, 81000, "maybe"),    # bad flag value
        (bid, "2025-09", 1500000, 82000, "true"),   # outlier
        (bid, "2025-13", 100000, 80000, "true"),    # invalid month
        (bid, "Oct 2025", 100000, 80000, "true"),   # wrong format
        (bid, "2025-12", 102000, 84000, "true"),
        (bid, "2025-12", 111000, 84000, "true"),    # conflicting duplicate
    ]
    return pd.DataFrame(rows, columns=["business_id", "period", "revenue", "expenses",
                                       "expenses_complete"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    b = BUSINESSES["retail"]["business_id"]
    fin = financials(b, "2024-01", 24, 250000, 0.012, 0.78, True)
    write("retail", financials=fin, customers=customers(b, fin, 140),
          products=products(b, fin, PRODUCT_SPECS))

    b = BUSINESSES["service"]["business_id"]
    fin = financials(b, "2025-01", 12, 90000, 0.008, 0.68, False, season=0.10)
    write("service", financials=fin, customers=customers(b, fin, 35, 0.35))

    b = BUSINESSES["cold_start"]["business_id"]
    fin = financials(b, "2025-08", 3, 60000, 0.05, 0.85, False, season=0.0)
    write("cold_start", financials=fin)

    b = BUSINESSES["messy"]["business_id"]
    write("messy", financials=messy_financials(b))

    (OUT / "businesses.json").write_text(json.dumps(BUSINESSES, indent=2, ensure_ascii=False))
    print("Sample data written to", OUT)


if __name__ == "__main__":
    main()
