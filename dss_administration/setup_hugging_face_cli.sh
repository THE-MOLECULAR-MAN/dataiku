#!/usr/bin/env bash
# Sets up the Hugging Face CLI for the dataiku service account.
# Designed for Alma Linux 8 / Fleet Manager. Run as root or with sudo.
set -euo pipefail

# dataclasses is in the standard library since Python 3.7; no need to install it.
sudo -u dataiku pip3 install --user --upgrade huggingface-hub

# Prompts for a Hugging Face access token interactively.
sudo -u dataiku huggingface-cli login
