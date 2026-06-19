#!/usr/bin/env bash
# Iterates all git-tracked DSS project directories and pushes each to its remote.
# set -e is intentionally omitted so one failing repo does not abort the entire run.
set -uo pipefail

# Replace with the path to the DSS projects configuration directory on your instance.
PATH_TO_REPOS="$HOME/DSS_DATA_DIR/config/projects"

if [ ! -d "$PATH_TO_REPOS" ]; then
    echo "Repo directory not found: $PATH_TO_REPOS" >&2
    exit 1
fi

cd "$PATH_TO_REPOS" || exit 1

echo "Searching for git repositories..."

# -print0 / read -d '' handles directory names that contain spaces.
find . -type d -name '.git' -print0 | while IFS= read -r -d '' ITER_PATH_TO_GIT_DIR; do
    project_dir="$(dirname "${PATH_TO_REPOS}/${ITER_PATH_TO_GIT_DIR}")"
    cd "$project_dir" || { echo "Cannot cd to $project_dir, skipping." >&2; continue; }
    echo "Pushing: $project_dir"
    git remote show origin && git push
done

echo "Script finished successfully."
