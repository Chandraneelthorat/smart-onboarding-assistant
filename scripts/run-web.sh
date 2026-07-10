#!/usr/bin/env bash
# Build the Vite frontend, then run the API + SPA on one port (default 8000).
# Client routes (/login, /app/hr/tickets, …) are served via index.html fallback.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
npm run build
cd "$ROOT"
exec uv run uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
