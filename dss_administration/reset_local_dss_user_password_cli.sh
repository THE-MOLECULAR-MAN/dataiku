#!/usr/bin/env bash
set -euo pipefail

# https://doc.dataiku.com/dss/latest/operations/dsscli.html#user-edit

# Replace with the path to your DSS data directory.
DSS_DATA_DIR="/data/dataiku/dss_data"
# Replace new_password with the new password to set.
# Replace local_dss_username_to_reset with the login name of the user to update.
$DSS_DATA_DIR/bin/dsscli user-edit --password new_password local_dss_username_to_reset
