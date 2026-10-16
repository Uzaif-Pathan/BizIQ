# BizIQ — Business Intelligence & Strategy Platform

BizIQ helps new and established businesses understand their financial
performance, sales trends, customer patterns, product or service
performance, and opportunities for improvement.

## Main Features

- Business profiles and business-type-specific analysis
- CSV and Excel data import
- Data validation and data availability classification
- Financial and historical trend analysis
- Customer analysis and optional customer segmentation
- Product or service performance analysis
- Benchmarking using documented sources
- Transparent, explainable business viability score
- Evidence-based recommendations
- Dashboard and final business report

## Technology Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, Recharts
- Backend: Python, FastAPI, Pydantic
- Data processing: Pandas, NumPy, OpenPyXL
- Machine learning: scikit-learn
- Database: PostgreSQL
- Database migrations: SQLAlchemy and Alembic

## Development Status

Repository foundation: in progress.
Frontend, backend, database, analytics, ML and recommendations:
implemented incrementally.

## Core Design Principles

- Missing data is not treated as zero.
- Calculations must be reproducible.
- Recommendations must reference supporting findings.
- Benchmarks must identify their source, year, geography and metric.
- Limited-data businesses receive appropriately limited insights.
- ML models are used only when the available data is suitable.
- No guaranteed business success or unsupported probability claims.

## Development

See docs/DEVELOPMENT_ROADMAP.md for the implementation sequence.
See docs/ARCHITECTURE.md for the system architecture.
See docs/ML_MODEL_PLAN.md for the model training plan.
See docs/DATABASE_SCHEMA.md for the database design.
