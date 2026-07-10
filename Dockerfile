# syntax=docker/dockerfile:1

# ---- Stage 1: build the React/Vite SPA ----
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# base="" in src/api/client.ts -> the SPA calls the API on its own origin.
RUN npm run build

# ---- Stage 2: Python runtime that serves the API + the built SPA ----
FROM python:3.10-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .
# app/main.py mounts frontend/dist and returns index.html for client routes.
COPY --from=frontend /app/frontend/dist ./frontend/dist

EXPOSE 8000
# Render (and most PaaS) inject $PORT; fall back to 8000 for local runs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
