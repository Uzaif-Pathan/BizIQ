#!/usr/bin/env python3
"""Seed the database with a demo user and the SYNTHETIC sample businesses (retail, service, cold start).

    cd <repo root>
    python scripts/seed_demo_data.py

Needs DATABASE_URL (backend/.env) and an up-to-date schema (`cd backend && alembic upgrade head`).
Safe to run twice: a business that already exists (same name) is skipped. The "messy" sample is not
loaded here because it is deliberately invalid (the database rejects its negative and duplicate rows);
it is meant for the import/validation flow.

How the sample files are stored: the samples give one total expense figure per month, which goes into
`other_expenses` (the breakdown is unknown). Product cost goes into `monthly_product_metrics.total_cost`.
Customer ids are the anonymous references C001, C002, ... from the sample file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)  # so backend/.env is found

import pandas as pd  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Business, BusinessGoal, CustomerActivity, MonthlyFinancial, MonthlyProductMetric, ProductService, User,
)

SAMPLES = ROOT / "data" / "samples"
SCENARIOS = ("retail", "service", "cold_start")
DEMO_EMAIL = "demo@biziq.local"


def _none(v):
    return None if pd.isna(v) else v


def _bool(v):
    if pd.isna(v):
        return None
    return str(v).strip().lower() in ("true", "1", "yes")


def _period(p: str):
    y, m = str(p).split("-")
    from datetime import date
    return date(int(y), int(m), 1)


def ensure_demo_user(db) -> int:
    owner_id = get_settings().default_owner_user_id
    if db.get(User, owner_id) is None:
        db.add(User(user_id=owner_id, full_name="Demo User (synthetic)", email=DEMO_EMAIL,
                    password_hash="not-a-real-hash"))  # placeholder: real login does not exist yet
        db.flush()
        db.execute(text("SELECT setval(pg_get_serial_sequence('app_users','user_id'), "
                        "(SELECT MAX(user_id) FROM app_users))"))
    return owner_id


def seed_business(db, owner_id: int, scenario: str, meta: dict) -> str:
    if db.scalar(select(Business.business_id).where(Business.business_name == meta["name"])):
        return "skipped (already exists)"
    city, _, state = (meta.get("location") or "").partition(",")
    biz = Business(owner_user_id=owner_id, business_name=meta["name"], industry_name=meta["industry"],
                   business_type=meta["business_type"], city=city.strip() or None, state=state.strip() or None,
                   stage="new" if scenario == "cold_start" else "established",
                   description="Synthetic demo data. Not a real business.")
    db.add(biz)
    db.flush()
    db.add(BusinessGoal(business_id=biz.business_id, goal_type="GENERAL", description="Understand profit and growth",
                        status="ACTIVE"))

    folder = SAMPLES / scenario
    fin = pd.read_csv(folder / "financials.csv")
    for r in fin.itertuples():
        db.add(MonthlyFinancial(business_id=biz.business_id, period_start=_period(r.period), revenue=_none(r.revenue),
                                other_expenses=_none(r.expenses), expenses_complete=_bool(r.expenses_complete)))
    if (folder / "customers.csv").exists():
        for r in pd.read_csv(folder / "customers.csv").itertuples():
            db.add(CustomerActivity(business_id=biz.business_id, customer_ref=str(r.customer_id),
                                    period_start=_period(r.period), transactions=_none(r.transactions),
                                    amount_spent=_none(r.amount_spent)))
    if (folder / "products.csv").exists():
        pro = pd.read_csv(folder / "products.csv")
        items = {}
        for pid, name in pro[["product_id", "product_name"]].drop_duplicates().itertuples(index=False):
            item = ProductService(business_id=biz.business_id, item_name=str(name), item_type="PRODUCT")
            db.add(item)
            items[pid] = item
        db.flush()
        for r in pro.itertuples():
            db.add(MonthlyProductMetric(product_id=items[r.product_id].product_id, period_start=_period(r.period),
                                        units_sold=None if pd.isna(r.units_sold) else int(r.units_sold),
                                        total_revenue=_none(r.revenue), total_cost=_none(r.cost)))
    return f"created (id {biz.business_id})"


def main() -> int:
    if not get_settings().database_url:
        print("DATABASE_URL is not set. Copy backend/.env.example to backend/.env and set it.")
        return 1
    businesses = json.loads((SAMPLES / "businesses.json").read_text())
    with SessionLocal() as db:
        owner = ensure_demo_user(db)
        for scenario in SCENARIOS:
            print(f"{scenario:11} {seed_business(db, owner, scenario, businesses[scenario])}")
        db.commit()
    print("Done. Synthetic demo data only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
