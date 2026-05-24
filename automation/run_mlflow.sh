#!/bin/bash
# Start MLflow Tracking Server natively on macOS
# Backend store: SQLite database in user_data/mlflow.db
# Artifacts: local ./mlruns directory

echo "Starting native macOS MLflow Tracking Server on http://127.0.0.1:5000..."
./venv/bin/mlflow server \
    --backend-store-uri sqlite:///user_data/mlflow.db \
    --default-artifact-root ./mlruns \
    --host 127.0.0.1 \
    --port 5000
