#!/bin/bash
set -euo pipefail

# Replace with the path to your DSS run directory (typically DSS_DATA_DIR/run).
find "/data/dataiku/dss_data/run" -type f ! -path '*/.git*' -exec grep -H "ERROR" {} \;

# Only files modified less than 720 minutes ago (720 min = 12 hours)
# find "/data/dataiku/dss_data/run" -type f  ! -path '*/.git*' -mmin -720 -print
