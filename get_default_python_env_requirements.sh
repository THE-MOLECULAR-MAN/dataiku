#!/usr/bin/env bash
set -euo pipefail

# Captures the default DSS Python environment's installed packages to ~/dss_default_requirements.txt.
# Run on the DSS host as the service account user.

# Replace with your DSS installation directory (the directory containing dss_data/).
DSS_INSTALL_DIR="/data/dataiku"
DSS_PYENV="$DSS_INSTALL_DIR/dss_data/pyenv"

if [ -f "$DSS_PYENV/bin/activate" ]; then
  echo "Using DSS built-in Python env: $DSS_PYENV"
  source "$DSS_PYENV/bin/activate"
  pip freeze > ~/dss_default_requirements.txt
  deactivate
  echo "Wrote requirements to ~/dss_default_requirements.txt"
else
  echo "Could not find DSS built-in Python env at: $DSS_PYENV"
fi
