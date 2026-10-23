# BizIQ — Analytics Engine (Person 2)

This repository contains Person 2's standalone Python analytics engine for the BizIQ college project. It analyzes business financials, customers, and products/services; reports data-quality issues; produces evidence-based findings and recommendations; and returns a JSON result for Person 3's backend adapter and Person 1's frontend.

## Quick start

Python 3.10+ is recommended.

```bash
pip install -r requirements-dev.txt
python scripts/run_demo.py --scenario retail --summary
```

To save the full machine-readable result and validate it against the shared schema:

```bash
python scripts/run_demo.py --scenario retail --pretty \
  --output output/retail-analysis.json --check-schema
```

Available synthetic scenarios:

```bash
python scripts/run_demo.py --scenario retail --summary
python scripts/run_demo.py --scenario service --summary
python scripts/run_demo.py --scenario cold_start --summary
python scripts/run_demo.py --scenario messy --summary
```

The `messy` scenario intentionally includes data-quality problems; a `partial` result is expected. All included datasets are synthetic.

## Run verification

```bash
cd backend
python -m pytest analytics_engine/tests -q
cd ..
python scripts/check_samples.py
```

The regression suite covers financial, customer and product metrics, validation, segmentation, forecasting, health scoring, recommendations, pipeline behaviour, CLI output, and JSON contract compatibility.

## Use the engine in an adapter

```python
from analytics_engine import run_analysis

result = run_analysis(
    business={
        "business_id": "your-authorized-business-id",
        "business_type": "retail",  # retail, service, or other
        "industry": "general retail",
        "location": "Nashik, Maharashtra",
    },
    data={
        "financials": financials_df,
        "customers": customers_df,  # optional
        "products": products_df,    # optional
    },
)
```

Before passing data, Person 3's adapter must authorize access to the business and fetch only records the user is permitted to analyze. `run_analysis` returns a JSON-safe dictionary and does not connect to a database or web service. The shared response contract is `contracts/analysis-result.schema.json`; integration notes are in `docs/PERSON3_INTEGRATION.md`.

## Key safeguards

- Missing values are not silently represented as zero.
- Data validation issues are returned as structured errors and warnings.
- Financial calculations include formula/period metadata.
- Segmentation and forecasting report evaluation status and can abstain when data is insufficient or model quality is weak.
- Health scoring is a transparent rule-based indicator, not a probability of business success.
- Recommendations are tied to findings and evidence; they are suggestions, not guaranteed outcomes.

## Project layout

- `backend/analytics_engine/` — engine modules and tests
- `contracts/analysis-result.schema.json` — shared JSON response contract
- `data/samples/` — synthetic demo datasets
- `scripts/run_demo.py` — command-line demo
- `scripts/check_samples.py` — all-scenario schema/serialization verification
- `scripts/generate_demo_data.py` — reproducible synthetic data generator
- `docs/ENGINE_FORMULAS.md` — documented formula definitions
- `docs/PERSON3_INTEGRATION.md` — backend integration guidance
- `docs/VERIFICATION.md` — latest test and scenario verification record
