#!/usr/bin/env bash
set -euo pipefail

ROLE_NAME=$(aws sts get-caller-identity --query "Arn" --output text | cut -d'/' -f2)
aws iam get-account-authorization-details --filter Role --query "RoleDetailList[?RoleName==\`$ROLE_NAME\`]"
