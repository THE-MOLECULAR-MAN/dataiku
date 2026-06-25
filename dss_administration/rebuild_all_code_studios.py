"""Stops all running Code Studio instances across all projects, then rebuilds each without cache."""

import time

import dataiku

POLL_INTERVAL = 5  # seconds between instance-state checks
STOPPED_STATES = frozenset({"STOPPED", "FAILED", "ERROR", "NONE", ""})


def _instances_still_running(cs) -> list[dict]:
    """Return any Code Studio instances that have not yet reached a terminal state."""
    status = cs.get_status()
    return [
        i for i in status.get("instances", [])
        if i.get("state", "STOPPED") not in STOPPED_STATES
    ]


def wait_for_all_stopped(cs, label: str) -> None:
    """Block until every instance of the given Code Studio is in a terminal state."""
    while True:
        running = _instances_still_running(cs)
        if not running:
            return
        states = ", ".join(i.get("state", "?") for i in running)
        print(f"{label}   {len(running)} instance(s) still active ({states}) — polling...")
        time.sleep(POLL_INTERVAL)


client = dataiku.api_client()

for project_info in client.list_projects():
    project_key = project_info["projectKey"]
    project = client.get_project(project_key)

    try:
        code_studios = project.list_code_studios()
    except Exception as exc:
        print(f"[{project_key}] Cannot list code studios, skipping: {exc}")
        continue

    if not code_studios:
        continue

    for cs_def in code_studios:
        cs_id = cs_def["id"]
        cs_name = cs_def.get("name", cs_id)
        label = f"[{project_key} / {cs_name}]"
        cs = project.get_code_studio(cs_id)

        print(f"{label} Stopping all instances...")
        cs.stop_all_instances()
        wait_for_all_stopped(cs, label)
        print(f"{label} All instances stopped.")

        print(f"{label} Rebuilding without cache...")
        future = cs.rebuild(no_cache=True)
        future.wait_for_result()
        print(f"{label} Rebuild complete.")
