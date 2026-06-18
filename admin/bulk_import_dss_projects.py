"""Imports DSS project ZIP archives from a managed folder into this DSS instance.

Run this as a recipe or scenario inside DSS — it uses the in-context API client
and a managed folder to locate the source ZIP files.
"""

import os

import dataiku

client = dataiku.api_client()

# Managed folder containing the project ZIP archives to import.
# Update this ID to match your target folder.
folder_handle = dataiku.Folder("5fuFDP0G")

zip_files = [f for f in folder_handle.list_paths_in_partition() if f.endswith(".zip")]

for zip_file in zip_files:
    local_path = os.path.join("/tmp", os.path.basename(zip_file))

    folder_handle.get_download_stream(zip_file).read_to_file(local_path)

    with open(local_path, "rb") as f:
        import_result = client.prepare_project_import(f).execute()
        print(f"Imported project with key: {import_result}")

    os.remove(local_path)
