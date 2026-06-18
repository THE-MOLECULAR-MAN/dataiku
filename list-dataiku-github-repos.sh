#!/bin/bash
# Tim H 2025

# list all the DSS plugin repos in the dataiku org on GitHub
gh search repos "dss-plugin-" --owner dataiku --json fullName -q '.[] | select(.fullName | startswith("dataiku/dss-plugin-")) | .fullName'
