# Frontend manual test checklist

These checks cover the parts of the frontend that talk to the backend. Items marked
**(not yet run)** describe the expected behaviour but have not been run by hand yet.
Everything else was observed during manual testing with the in-memory backend and the
mock analysis engine (`method_version` starting with `mock`).

## Setup

1. Start the backend from `backend/`: `py -m uvicorn app.main:app --reload`
2. Start the frontend from `frontend/`: `npm run dev`, and open http://localhost:5173
   (the backend's default CORS settings only allow this address).
3. Register a local account (browser-only, not real authentication).

The backend keeps data in memory, so **restarting it empties its list**. Businesses created
before a restart then show "Not saved on server". Use clearly synthetic data only.

Sample file for the upload page (save as `test-data.csv`, "All files" type in Notepad):

```
date,revenue,expenses,notes
2026-08-01,10000,6500,Synthetic test data
2026-09-01,12000,7000,Synthetic test data
```

## 1. Businesses

- **Create:** Add business with a name of at least 2 letters, Retail, `Nashik, Maharashtra`.
  A card appears without a "Not saved on server" tag, and `GET /api/v1/businesses` at
  http://127.0.0.1:8000/docs lists it with `city` Nashik and `state` Maharashtra.
- **Short name (not yet run):** a 1-letter name is blocked by the browser before it is sent.
- **Server down while creating:** stop the backend and create a business. The form stays open
  and shows "Cannot reach the BizIQ server…". No card is added.
- **Server down on load:** with the backend stopped, reload. A banner says "Could not load from
  the server" and businesses saved on this device are still listed.
- **Backend restarted:** restart the backend and reload. Earlier businesses now show "Not saved
  on server" and their delete button works. Businesses that are on the server have a greyed-out
  delete button (no delete endpoint yet).
- **Save to server:** click it on a tagged business. The tag disappears, the delete button
  greys out, and its profile description and stage are kept.
- **Save to server fails:** stop the backend and click it. "Cannot reach the BizIQ server…"
  appears on that card and the tag stays.

## 2. Profile

- Change the name to `Batch Shop Renamed` and the location to `Pune, Maharashtra`, then save.
  "Changes saved" appears, `GET /api/v1/businesses` shows the new name and `city` Pune, and the
  change survives a reload.
- On a business that is not saved on the server, saving shows an amber note saying the changes
  were saved on this device only.

## 3. Dashboard

- **Run analysis:** the Analysis panel shows "No analysis yet" and a Run analysis button. After
  running it shows the status, evidence level, benchmark status, method version, a "Sample output"
  notice, revenue, expenses, profit, profit margin, counts and limitations.
- **Reload:** the latest analysis loads again without clicking.
- **Server down:** Run again shows "Cannot reach the BizIQ server…" and keeps the earlier result.
- **Not saved on server:** the panel explains that the business must be saved first and has no
  Run button.
- **Analysis status panel:** a fresh server business shows 1 of 4 steps (25%). After an analysis,
  2 of 4 (50%). After ticking the recommendation, 3 of 4. After adding a data file, 4 of 4 (100%).
- **No invented numbers:** Customer count and the category count show "—". The revenue chart and
  the revenue/expense cards are labelled illustrative.

## 4. Findings, Recommendations, Report

- Before any analysis, each page shows "No … yet" with a Go to dashboard button.
- After an analysis, Findings lists the real finding (expand it to see evidence and metric) and
  Recommendations lists the real recommendation. Ticking it updates the progress and survives a
  reload.
- Report: the preview shows real revenue, expenses and profit with the sample-output warning, and
  Export CSV contains the metrics, recommendation and limitations.
- For a business not on the server, all three pages show "Not saved on the server".

## 5. Upload page (local only)

- Adding a `.csv` file shows a green message, a row in "Uploaded files" with status "Uploaded —
  validation needed", and the dashboard's Business data step turns Done.
- **(not yet run)** A `.txt` file is rejected with "Unsupported file type", and a file over 10 MB
  is rejected.
- The file is not read or sent anywhere.

## 6. Build

- `npm run build` in `frontend/` finishes with `✓ built`.

## Known limits

- Accounts, uploads and deleting a business are local-only.
- The dashboard chart and the revenue/expense cards are demo data.
- Results are placeholders until the backend uses a real analysis engine.
- There are no automated frontend tests yet.
