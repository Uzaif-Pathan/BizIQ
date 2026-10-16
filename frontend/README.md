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

## Important implementation notes

This is a working front-end prototype. It does not provide secure authentication, a backend database, cloud file storage, actual spreadsheet parsing, data validation, or calculations based on uploaded files. The dashboard chart and example metrics are illustrative demo data, labelled accordingly. Files are not transmitted to a server; local state is stored in this browser's localStorage. Before production use, connect a secure backend, validate and parse uploads, implement authorization, and ensure each finding can be traced to its source records.

The Google Fonts import is optional; local system fonts are used as fallbacks.
