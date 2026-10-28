# BizIQ website

A responsive React/Vite front-end prototype based on the BizIQ wireframe theme: soft neutral canvas, white panels, restrained blue accent, compact typography, fine borders and practical business workflows.

## Run locally

Requirements: Node.js 18 or newer.

```bash
npm install
npm run dev
```

Open the local URL Vite prints (usually http://localhost:5173).

To build for production:

```bash
npm run build
npm run preview
```

## Tests

```bash
npm test
```

Runs the automated unit tests in `tests/` (Vitest): the API client, the business mapping, the state migration and the number formatters. The screens themselves are covered by the manual checklist in `TESTING.md`.

## What is included

- Registration page (first screen) and sign-in, with per-account workspaces stored in the browser
- Business workspace, searchable business cards, add-business flow and delete-business with confirmation
- Dashboard with data status, metrics, chart, analysis progress and quick actions
- Editable business profile
- Data upload interface, CSV/Excel file selection, upload history and downloadable CSV template
- Financial, customer, product/service, trends and market analysis pages
- Findings, recommendations with completion tracking, and report outline export
- Settings, responsive sidebar, browser-local persistence, print-friendly layouts
- Retail/service-aware interface copy and explicit labelling of illustrative data

## Accounts

Create an account on the registration page (name, email, password of at least 8 characters). Each account starts with an empty workspace and its own businesses. Accounts are stored in this browser's localStorage with a hashed password, which is a front-end convenience and not secure authentication.

## Connecting to the backend

The frontend talks to the FastAPI backend through `src/services/api.ts`.

1. Start the backend from the `backend/` folder: `py -m uvicorn app.main:app --reload` (on macOS/Linux: `python -m uvicorn app.main:app --reload`). Until `backend/requirements.txt` is completed, install `fastapi`, `uvicorn`, `pydantic` and `pydantic-settings` by hand.
2. Start the frontend (`npm install`, then `npm run dev`) and open http://localhost:5173. The backend's default CORS settings allow this origin; another port will be blocked.
3. The API address comes from `VITE_API_BASE_URL` (see `.env.example`). If it is not set, the app uses `http://127.0.0.1:8000/api/v1`.

### What uses the backend

- My businesses: the list is loaded from the server and new businesses are created there.
- Business profile: name, industry, business model, city/state, description and stage are saved to the server.
- Dashboard "Analysis" panel: runs an analysis and shows the latest result. Missing metrics are shown as "Not available", never as 0.
- Findings, Recommendations and Report pages: built from the latest analysis result.
- Businesses that lost their server copy can be saved again with the "Save to server" button.

The backend currently keeps businesses and analyses in memory only (no database yet). Restarting the backend empties its list, and the app then tags those businesses "Not saved on server".

### What is still local-only

- Accounts and sign-in (browser localStorage, not secure authentication).
- The data upload page: files are not sent to the server or parsed.
- Deleting a business: there is no delete endpoint yet, so the button is disabled for businesses saved on the server.
- The dashboard chart, the revenue and expense cards, and the analysis-progress panel use illustrative demo data. Customer count and category counts show "—".
- Team size, website and currency in the business profile.
- The Financial, Customers, Products/Services, Trends and Market pages (marked "not connected").

### Sample output

While the backend uses its development engine (its `method_version` starts with `mock`), results are placeholders. The app labels them "Sample output — not calculated from your data".

## Important implementation notes

This is a front-end prototype that is partly connected to the backend. It does not provide secure authentication, file upload or parsing, validation of uploaded data, or calculations based on uploaded files, and the backend analysis is currently a development placeholder. Before production use, connect a secure backend and database, validate and parse uploads, implement authorization, and ensure each finding can be traced to its source records.

The Google Fonts import is optional; local system fonts are used as fallbacks.
