#!/usr/bin/env bash
# Start both backend and frontend in parallel.
# Usage: ./start.sh

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
}
trap cleanup EXIT INT TERM

# Backend (FastAPI + uvicorn)
echo "Starting backend..."
cd "$ROOT/backend"
uv run server.py &
BACKEND_PID=$!

# Frontend (Vite + Tauri)
echo "Starting frontend..."
cd "$ROOT/web"
npm run tauri dev &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both."

wait
