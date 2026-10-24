#!/usr/bin/env bash
set -e

echo "================================================="
echo " Starting Enterprise-RAG-Platform "
echo "================================================="

if [ -f .env ]; then
  echo "Loading environment from .env"
  export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
else
  echo ".env not found, using .env.example"
  cp .env.example .env
fi

# Run backend API
echo "Starting FastAPI Server on http://0.0.0.0:8000..."
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
