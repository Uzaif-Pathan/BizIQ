# API routes (v1)

Base path: `/api/v1`. Interactive docs: `http://127.0.0.1:8000/docs`.

| Method | Route | What it does |
| --- | --- | --- |
| GET | `/health` | Health check (also at `/health` without the prefix) |
| POST | `/businesses` | Create a business (201) |
| GET | `/businesses?limit=50&offset=0` | List businesses, newest first |
| GET | `/businesses/{id}` | One business |
| PATCH | `/businesses/{id}` | Partial update, including `goals` |
| POST | `/businesses/{id}/analyses` | Run an analysis now (201, status completed or failed) |
| GET | `/businesses/{id}/analyses` | Analysis history, newest first |
| GET | `/analyses/{id}` | Full analysis result (the shared contract) |
| GET | `/analyses/{id}/findings` | Findings only |
| GET | `/analyses/{id}/recommendations` | Recommendations only |
| GET | `/analyses/{id}/report` | Report payload: business + analysis. 409 if the run did not complete |

Errors always look like `{"error": {"code", "message", "details"}}`.

## Analysis runs
- The run is saved as `pending`, the engine runs, then it is saved as `completed` or `failed`.
- A failed run still returns all eight contract fields: metrics all `null`, empty lists,
  `evidence_level: "insufficient"`, `benchmark_status: "unavailable"`, and an `error_message`.
- The engine is a function chosen in `app/services/analytics_service.py`
  (`get_analytics_engine`). Today it is `mock_engine`. To connect Person 2's engine, write a
  function that returns the same dict shape and return it from `get_analytics_engine`.

## Storage
Businesses and analyses are kept in memory (`app/repositories/memory.py`) until the database
models are ready. To switch, write database versions of the two repository classes with the
same method names and change the two functions in `app/api/deps.py`.
