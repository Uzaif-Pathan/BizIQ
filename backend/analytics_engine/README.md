# BizIQ analytics engine (Person 2)

Standalone Python package. No FastAPI or PostgreSQL needed.

## Run the tests
    pip install pandas numpy scikit-learn pytest
    cd backend && python -m pytest analytics_engine/tests -q

## Regenerate the synthetic sample data
    python scripts/generate_demo_data.py      # writes data/samples/

## Status
- [x] Step 1: validation (`analytics_engine/validation`), sample data, JSON contract schema
- [ ] Step 2: financial metrics
- [ ] Step 3: customer / product analytics
- [ ] Step 4: K-Means + forecasting
- [ ] Step 5: health score
- [ ] Step 6: recommendations
- [ ] Step 7: `run_analysis`, CLI demo, evidence level
