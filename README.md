# BizIQ

Business analytics for small businesses: upload monthly financials, customer and product records, and get
measured metrics, findings and evidence-backed recommendations. Results are suggestions to investigate, not
predictions of success. Synthetic data in `data/samples/` is for demonstration only.

## Parts

| Folder | What it is |
|---|---|
| `frontend/` | React + Vite app (see `frontend/README.md`) |
| `backend/` | FastAPI API, database models and migrations (`backend/app`, `backend/alembic`) |
| `backend/analytics_engine/` | Standalone Python analytics engine (see its `README.md`) |
| `contracts/` | JSON schemas and examples shared by the engine, API and frontend |
| `data/samples/` | Synthetic sample datasets (retail, service, cold start, messy) |
| `database/` | Reference data (benchmarks) and seed files |
| `docs/` | Architecture, formulas, recommendation rules, integration notes |
| `scripts/` | Sample generator, demo runner, sample checker |

## Run the backend

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cd backend
cp .env.example .env        # set DATABASE_URL for database features
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs. The API starts without a database; routes that need one return a
clear 503 until `DATABASE_URL` is set.

## Run the frontend

```bash
cd frontend && npm install && npm run dev
```

## Try the engine without the app

```bash
python scripts/run_demo.py --scenario retail --summary
python scripts/check_samples.py
```

## Tests

```bash
cd backend && python -m pytest -q          # backend and analytics engine
cd frontend && npm test                    # frontend
```

## Rules the project follows

- Missing data is never treated as zero; unknown stays unknown.
- No invented industry benchmarks; benchmark data always shows its source, year and level.
- Synthetic and mock data is labelled as such.
- Credentials, virtual environments and caches are not committed.
