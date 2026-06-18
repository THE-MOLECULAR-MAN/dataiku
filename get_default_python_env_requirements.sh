#!/bin/bash

# This script is intended to be run on a DSS instance to capture the default Python environment's packages.
# It will write the list of installed packages to ~/dss_default_requirements.txt

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
