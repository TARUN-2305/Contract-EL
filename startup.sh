#!/bin/bash
echo "Starting ContractGuard AI..."

# Ensure the database and tables are created
echo "Initializing database..."
python scripts/init_db.py

# Start the FastAPI backend in the background
echo "Starting API server on port 8000..."
uvicorn api.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

# Wait a moment for the API to boot
sleep 3

# Start the Streamlit dashboard
echo "Starting Streamlit dashboard..."
streamlit run dashboard.py

# On exit, kill the API server
kill $API_PID
