#!/usr/bin/env bash
set -e

# Change directory to repository root
cd "$(dirname "$0")"

echo "=========================================================================="
echo " Launching Food Delivery Mediator Simulator - Interactive GUI Window"
echo " Pattern: Event-Driven Architecture (Mediator Topology)"
echo " Reference: Mark Richards & Neal Ford"
echo "=========================================================================="
echo ""
echo "Starting Streamlit web application on http://localhost:8501 ..."
echo "Press Ctrl+C to stop the server."
echo ""

# Launch Streamlit server and open in browser
streamlit run app.py --server.port 8501 --server.headless false
