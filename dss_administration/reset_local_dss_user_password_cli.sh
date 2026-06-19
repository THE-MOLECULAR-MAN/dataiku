#!/bin/bash
# Tim H 2025

# https://doc.dataiku.com/dss/latest/operations/dsscli.html#user-edit
# change password for user

DSS_DATA_DIR="/data/dataiku/dss_data"
$DSS_DATA_DIR/bin/dsscli user-edit --password new_password local_dss_username_to_reset
