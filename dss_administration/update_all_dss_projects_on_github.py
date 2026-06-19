"""Iterate all projects on this DSS instance and push commits to GitHub for any project connected to a remote.

Intended to run as a scheduled scenario.

References:
    https://developer.dataiku.com/latest/tutorials/devtools/using-api-with-git-project/index.html
    https://developer.dataiku.com/latest/api-reference/python/projects.html#dataikuapi.dss.project.DSSProjectGit.get_remote
"""

import dataiku

client = dataiku.api_client()

pushed: set[str] = set()
not_connected: set[str] = set()

for project_key in client.list_project_keys():
    proj = client.get_project(project_key)
    project_git = proj.get_project_git()
    if project_git.get_remote():
        result = project_git.push()
        if result["status"] != "ok":
            print(f"Error pushing {project_key}: {result['status']}, {result['output']}")
        pushed.add(project_key)
    else:
        not_connected.add(project_key)

print(f"Pushed {len(pushed)} projects:\n{pushed}\n")
print(f"{len(not_connected)} projects not connected to GitHub:\n{not_connected}")
