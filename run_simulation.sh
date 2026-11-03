#!/usr/bin/env bash
set -e

# Ensure current working directory is script directory
cd "$(dirname "$0")"

# Execute Python interactive UI or pass CLI arguments
if [ $# -eq 0 ]; then
    python3 main.py
else
    python3 main.py "$@"
fi
