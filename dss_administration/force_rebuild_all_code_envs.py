"""Rebuilds all DSS Python code environments from scratch, in parallel."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import dataiku

_lock = threading.Lock()


def get_directory_size(path: str) -> int:
    """Return the total byte size of all non-symlink files under path."""
    total = 0
    for dirpath, _, filenames in os.walk(path, followlinks=False):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            try:
                if not os.path.islink(file_path):
                    total += os.path.getsize(file_path)
            except FileNotFoundError:
                continue
    return total


def human_readable_size(size_bytes: float) -> str:
    """Convert a byte count to a human-readable string (e.g., 1.50 GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} EB"


def _process_code_env(code_env_info: dict) -> None:
    """Rebuild one code environment from scratch and accumulate before/after disk sizes."""
    env_name = code_env_info["envName"]
    try:
        code_env = client.get_code_env(code_env_info["envLang"], env_name)
        print(f"Starting rebuild of {env_name} ...")
        # Update this path to match your DSS data directory (typically DSS_DATA_DIR/code-envs/python).
        env_path = os.path.join("/data/dataiku/dss_data/code-envs/python", env_name)

        size_before = get_directory_size(env_path)
        result = code_env.update_packages(force_rebuild_env=True)

        if not result["messages"]["success"]:
            with _lock:
                failed_builds.append(env_name)
            print(f"FAILED: {env_name}\n{result}")
        else:
            size_after = get_directory_size(env_path)
            with _lock:
                accumulators["before"] += size_before
                accumulators["after"] += size_after

    except Exception as exc:
        print(f"Exception rebuilding {env_name}: {exc}")


client = dataiku.api_client()
code_envs = client.list_code_envs()

failed_builds: list[str] = []
accumulators = {"before": 0, "after": 0}

with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
    executor.map(_process_code_env, code_envs)

if failed_builds:
    print(f"Environments that failed to build: {failed_builds}")

size_before = accumulators["before"]
size_after = accumulators["after"]
change_pct = (
    f"{(size_after - size_before) / size_before:.1%}" if size_before else "N/A"
)
print(
    "Finished rebuilding all code environments from scratch\n"
    f"  Total size before: {human_readable_size(size_before)}\n"
    f"  Total size after:  {human_readable_size(size_after)}\n"
    f"  Change: {change_pct}"
)
