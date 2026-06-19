#!/bin/bash
# Tim H 2025

find "/data/dataiku/dss_data/run" -type f  ! -path '*/.git*' -exec grep -H "ERROR" {} \;

# Only files modified less than 720 minutes ago (720 min = 12 hours)
# find "/data/dataiku/dss_data/run" -type f  ! -path '*/.git*' -mmin -720 -print
