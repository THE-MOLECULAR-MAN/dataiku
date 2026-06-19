#!/bin/zsh
# Tim H 2026

# Finding when a DSS service was started/stopped

# do it on the DSS instance
find /data/dataiku/dss_data/run -type f -name "*.log*" -exec grep 'DSS startup\|Stopping service' "{}" \; | sort

# do it using pipes on a zip file
unzip -p ~/Downloads/dssLogs_2026_03_30_latest.zip "*" | grep 'DSS startup\|Stopping service' | sort
