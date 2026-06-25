#!/usr/bin/env zsh
# Searches DSS log files for startup and shutdown events.
set -euo pipefail

# Replace with the path to your DSS run directory (typically DSS_DATA_DIR/run).
find /data/dataiku/dss_data/run -type f -name "*.log*" -exec grep 'DSS startup\|Stopping service' "{}" \; | sort

# Replace the zip filename below with the actual log archive you want to inspect.
unzip -p ~/Downloads/dssLogs_2026_03_30_latest.zip "*" | grep 'DSS startup\|Stopping service' | sort
