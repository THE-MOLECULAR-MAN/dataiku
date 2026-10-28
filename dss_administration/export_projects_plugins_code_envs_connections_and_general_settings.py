#!/usr/bin/env python
# coding: utf-8

# In[1]:


import io
import json
import os
import zipfile
# import datetime
from datetime import datetime
from zoneinfo import ZoneInfo
import copy

import dataiku
from dataikuapi import DSSClient
from dataikuapi.utils import DataikuException


# In[2]:


EXPORT_FOLDER_ID = "byFny0zw"

# If True, skip a project when the export folder already holds an export for
# its current last-modified date (a modified project is exported again).
SKIP_ALREADY_EXPORTED = True

# All timestamps in file names use this zone, so the already-exported check
# gives the same result wherever the script runs.
TIMEZONE = ZoneInfo("US/Eastern")

# The export folder is meant to be enough to rebuild a DSS design node, so files are
# kept small: input datasets are always exported (the flow can't be rebuilt without
# them), intermediate and output datasets never are (exportAllDatasets stays off).
# https://developer.dataiku.com/latest/api-reference/python/projects.html#dataikuapi.dss.project.DSSProject.export_to_file
EXPORT_OPTIONS = {
    'exportAllInputDatasets': True, # does not include managed folders that have files like screenshots
    'exportUploads': True,
    'exportGitRepository': True,
    #'exportManagedFS': True,
    'exportAnalysisModels': True,
    'exportSavedModels': True,
    'exportModelEvaluationStores': True,
    #'exportAllInputManagedFolders': True,
    'exportInsightsData': True,
    'exportPromptStudioHistories': True,
     }

# Managed folder data is exported per project, not per folder (DSS only offers an
# on/off option): it is included only when all the project's managed folders add up
# to at most this many bytes. The project holding the export folder never includes
# managed folders, so the backup can't contain itself.
MAX_MANAGED_FOLDER_BYTES = 1024 ** 3

# DSS rejects project exports above a max size (~20 GB by default). Tried in
# order until one fits; the name is appended to the uploaded file name. Every
# tier keeps the input datasets: a project that still doesn't fit is reported as
# failed rather than exported without its inputs.
EXPORT_OPTION_TIERS = [
    ('full', EXPORT_OPTIONS),
    # drop the model artifacts and insights data, which are the usual bulk
    ('no_models', {
        'exportAllInputDatasets': True,
        'exportUploads': True,
        'exportGitRepository': True,
        'exportPromptStudioHistories': True,
    }),
]

# Dev plugin files that are not exported: whole virtual environments and other
# bulk that can be recreated (skipped directories, files over the size cap)
PLUGIN_EXCLUDED_DIRS = {'site-packages', 'venv', '.venv', 'env', 'node_modules', '__pycache__', '.git'}
MAX_PLUGIN_FILE_BYTES = 25 * 1024 * 1024


# In[3]:


export_timestamp = datetime.now(TIMEZONE).strftime('%Y%m%d_%H%M%S')

client = dataiku.api_client()


class TrackedFolder:
    """ Export folder handle that remembers what was uploaded, for the manifest """
    def __init__(self, folder):
        self._folder = folder
        self.uploaded = []

    def upload_stream(self, name, stream):
        self._folder.upload_stream(name, stream)
        self.uploaded.append(name)

    def __getattr__(self, attr):
        return getattr(self._folder, attr)


export_folder_handle = TrackedFolder(dataiku.Folder(EXPORT_FOLDER_ID))


# In[4]:


SENSITIVE_FIELDS = [
    "password", "passwords", "apiKey", "apiKeys", "token", "tokens",
    "secret", "secrets", "privateKey", "privateKeys", "key", "appSecret",
    "appSecretContent", "credential", "credentials", "accessKey",
    "secretKey", "authToken", "connectionString", "pwd", "passphrase"
]

# Names that contain a sensitive word but hold a setting, not a secret (e.g.
# credentialsMode, tokenEndpoint, project_key), which are needed to rebuild a node
NON_SECRET_SUFFIXES = ("mode", "method", "endpoint", "format", "filtering")
NON_SECRET_PARTS = ("claimkey", "projectkey", "workspacekey")


def is_sensitive_name(name):
    """ True if a field name looks like it holds a secret """
    normalized = str(name).lower().replace('_', '')
    if normalized.endswith(NON_SECRET_SUFFIXES) or any(part in normalized for part in NON_SECRET_PARTS):
        return False
    return any(sensitive.lower() in normalized for sensitive in SENSITIVE_FIELDS)


def sanitize_dict(obj):
    """ Recursively scan a dictionary and remove/sanitize sensitive information """
    if not isinstance(obj, dict):
        return obj
    
    result = copy.deepcopy(obj)
    
    # Name/value pair, e.g. {"key": "spark.foo", "value": "...", "secret": false}:
    # keep the name, redact the value if it is flagged secret or the name looks sensitive
    is_pair = isinstance(result.get('key'), str) and 'value' in result
    if is_pair and isinstance(result['value'], str) and result['value'] \
            and (result.get('secret') is True or is_sensitive_name(result['key'])):
        result['value'] = "[REDACTED]"
    
    for key, value in list(result.items()):
        if is_pair and key in ('key', 'value'):
            continue
        # Check if the key contains any sensitive field names
        if is_sensitive_name(key):
            if isinstance(value, str) and value:  # Only replace non-empty strings
                result[key] = "[REDACTED]"
            elif isinstance(value, dict):  # If it's a dictionary, still process it
                result[key] = sanitize_dict(value)
            elif isinstance(value, list):  # Redact string items, still process dicts
                result[key] = ["[REDACTED]" if isinstance(item, str) and item else sanitize_dict(item)
                               for item in value]
        # Recursively process nested dictionaries
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value)
        # Process items in lists
        elif isinstance(value, list):
            result[key] = [sanitize_dict(item) if isinstance(item, dict) else item for item in value]
            
    return result


def sanitize_any(data):
    """ sanitize_dict for a dict or a (nested) list of dicts """
    if isinstance(data, list):
        return [sanitize_any(item) for item in data]
    return sanitize_dict(dict(data)) if isinstance(data, dict) else data


def upload_json(filename, data):
    """ Sanitize `data` and upload it to the export folder as JSON """
    payload = json.dumps(sanitize_any(data), indent=4, default=str).encode('utf-8')
    export_folder_handle.upload_stream(filename, io.BytesIO(payload))


def export_section(label, filename, build):
    """ Upload the result of build() as <filename>_<timestamp>.json.
    A failing section is reported and skipped so the others still run. """
    try:
        upload_json(f'{filename}_{export_timestamp}.json', build())
        print(f"Exported {label}.")
    except Exception as e:
        print(f"Error exporting {label}: {e}")


# In[5]:


project_keys = client.list_project_keys()

# File names already in the export folder, without the leading slash
existing_export_files = set()
if SKIP_ALREADY_EXPORTED:
    existing_export_files = {p.lstrip('/') for p in export_folder_handle.list_paths_in_partition()}

def already_exported(project_key, formatted_date):
    """ Name of the existing export (full or reduced-tier) for this project and date, or None """
    base = f'PROJECT__{project_key}__{formatted_date}'
    names = {f'{base}.zip'} | {f'{base}__{tier}.zip' for tier, _ in EXPORT_OPTION_TIERS[1:]}
    matches = sorted(names & existing_export_files)
    return matches[0] if matches else None


def tier_from_file_name(file_name):
    """ Export tier an existing export was made with, from the tier suffix in its name """
    for tier, _ in EXPORT_OPTION_TIERS[1:]:
        if file_name.endswith(f'__{tier}.zip'):
            return tier
    return EXPORT_OPTION_TIERS[0][0]


def load_recorded_folder_notes(max_manifests=10):
    """ {(project_key, zip file): managed folder note} from the manifests already in the export
    folder, so a skipped project keeps what was decided when it was exported """
    notes = {}
    manifests = sorted(n for n in existing_export_files if n.startswith('manifest_') and n.endswith('.json'))
    for manifest_name in manifests[-max_manifests:]:  # oldest first, newer entries win
        try:
            stream = export_folder_handle.get_download_stream('/' + manifest_name)
            try:
                previous = json.loads(stream.read())
            finally:
                stream.close()
        except Exception as e:
            print(f"Could not read {manifest_name}: {e}")
            continue
        for entry in previous.get('projects', []):
            if entry.get('file') and entry.get('managed_folders'):
                notes[(entry['project_key'], entry['file'])] = entry['managed_folders']
    return notes


recorded_folder_notes = load_recorded_folder_notes() if SKIP_ALREADY_EXPORTED else {}


def warn_about_root_datasets(project):
    """ An input dataset on a filesystem connection with path '.' exports everything in the connection """
    for dataset in project.list_datasets():
        if dataset['type'] != 'Filesystem':
            continue
        try:
            params = project.get_dataset(dataset['name']).get_settings().get_raw().get('params', {})
        except Exception:
            continue
        if params.get('path', '').strip('/') in ('', '.'):
            print(f"  WARNING: dataset {dataset['name']} points at the root of connection "
                  f"{params.get('connection')}: exporting input datasets includes everything in it")


def managed_folder_export_options(project):
    """ Export options for the project's managed folders, and a note saying what was decided """
    folders = project.list_managed_folders()
    if not folders:
        return {}, 'none'
    if any(folder['id'] == EXPORT_FOLDER_ID for folder in folders):
        return {}, 'excluded: project holds the export folder itself'
    total_bytes = 0
    for folder in folders:
        try:
            contents = project.get_managed_folder(folder['id']).list_contents()['items']
        except Exception as e:
            return {}, f"excluded: could not size folder {folder['id']}: {str(e)[:80]}"
        total_bytes += sum(item.get('size', 0) for item in contents)
    size_mb = round(total_bytes / 1024 ** 2)
    if total_bytes > MAX_MANAGED_FOLDER_BYTES:
        return {}, f"excluded: {size_mb} MB is over the {MAX_MANAGED_FOLDER_BYTES // 1024 ** 2} MB cap"
    return {'exportAllInputManagedFolders': True}, f'included: {size_mb} MB'


project_results = []  # one entry per project, for the manifest

for project_key in project_keys:
    project = client.get_project(project_key)    
    
    # Get the summary of the project, which includes the last modified timestamp
    project_summary = project.get_summary()
    #print(project_summary)

    # The last modified timestamp can be extracted as follows
    # The timestamp is typically in milliseconds since epoch (standard Unix time)
    last_modified_timestamp = project_summary.get('versionTag', None).get('lastModifiedOn', None)
    # print(last_modified_timestamp)

    # Convert the timestamp to a human-readable format, if necessary
    if last_modified_timestamp:
        last_modified_date = datetime.fromtimestamp(last_modified_timestamp / 1000, tz=TIMEZONE)
        formatted_date = last_modified_date.strftime('%Y-%m-%d-%H-%M-%S')
        # print(f"Project '{project_key}' was last modified on: {formatted_date}")
    else:
        formatted_date='unknown_date'
    
    existing_file = already_exported(project_key, formatted_date) if SKIP_ALREADY_EXPORTED else None
    if existing_file:
        print(f"Skipping {project_key}: already exported for {formatted_date}")
        project_results.append({
            'project_key': project_key, 'status': 'skipped_already_exported',
            'tier': tier_from_file_name(existing_file), 'file': existing_file,
            'managed_folders': recorded_folder_notes.get((project_key, existing_file), 'unknown: not recorded'),
        })
        continue

    warn_about_root_datasets(project)
    folder_options, folder_note = managed_folder_export_options(project)
    print(f"  managed folders {folder_note}")

    export_file_path = '/tmp/{}.zip'.format(project_key)

    # Export the project to a local file. DSS refuses exports above its max
    # export size, so on that error retry with progressively lighter options.
    export_suffix = ''
    export_succeeded = False
    failure_reason = None
    for tier_name, tier_options in EXPORT_OPTION_TIERS:
        print(f"Starting export for {project_key} ({tier_name}) ...")
        try:
            project.export_to_file(export_file_path, options={**tier_options, **folder_options})
            export_succeeded = True
            if tier_name != 'full':
                export_suffix = f'__{tier_name}'
            print(f"Finished export for {project_key} ({tier_name}) ...")
            break
        except DataikuException as e:
            # export_to_file leaves a partial file behind on failure
            if os.path.exists(export_file_path):
                os.remove(export_file_path)
            failure_reason = str(e)
            if 'larger than the max allowed size' in str(e):
                print(f"Export too large for {project_key} ({tier_name}): {e}")
                continue
            print(f"Export failed for {project_key} ({tier_name}), skipping project: {e}")
            break

    if not export_succeeded:
        print(f"WARNING: no export produced for {project_key}")
        project_results.append({'project_key': project_key, 'status': 'failed', 'reason': failure_reason})
        continue

    # Upload the exported file to the managed folder
    with open(export_file_path, 'rb') as f:
        print(f"Starting copy to folder: {project_key} ...")
        upload_filename=f'PROJECT__{project_key}__{formatted_date}{export_suffix}.zip'
        export_folder_handle.upload_stream(upload_filename, f)
        print(f"Finished copying to folder: {project_key} ...")
    os.remove(export_file_path)
    project_results.append({'project_key': project_key, 'status': 'exported',
                            'tier': tier_name, 'file': upload_filename,
                            'managed_folders': folder_note})


# In[6]:


plugins = client.list_plugins()

# Filter the plugins to include only those installed from the store
store_plugins = [plugin['id'] for plugin in plugins] # if plugin.get('isInstalledFromStore', False)]

# Path for the output text file
plugins_output_file_path = '/tmp/store_plugins.txt'

# Write the plugin IDs to a text file
with open(plugins_output_file_path, 'w') as output_file:
    for plugin_id in store_plugins:
        output_file.write(plugin_id + '\n')

# Upload the text file to the managed folder
with open(plugins_output_file_path, 'rb') as f:
    export_folder_handle.upload_stream(f'list_plugins_{export_timestamp}.txt', f)

# Cleaning up the temporary file
os.remove(plugins_output_file_path)

print("Plugin IDs exported to the managed folder.")


def plugin_file_paths(nodes):
    """ Paths of the files worth exporting in a plugin's list_files() tree (directories have 'children') """
    for node in nodes:
        if node['name'] in PLUGIN_EXCLUDED_DIRS:
            print(f"  skipping {node['path']} (excluded directory)")
        elif node.get('children') is not None:
            yield from plugin_file_paths(node['children'])
        elif node.get('size', 0) > MAX_PLUGIN_FILE_BYTES:
            print(f"  skipping {node['path']} ({node['size'] // 1024 // 1024} MB, over the size cap)")
        else:
            yield node['path']


def build_plugin_details():
    """ Version, dev flag and settings (presets / parameter sets) of every plugin """
    details = []
    for plugin in client.list_plugins():
        entry = dict(plugin)
        try:
            entry['settings'] = client.get_plugin(plugin['id']).get_settings().get_raw()
        except Exception as e:
            entry['settings_error'] = str(e)
        details.append(entry)
    return details


export_section('plugin details', 'plugins', build_plugin_details)

# Dev plugins can't be reinstalled from the store, so save their files
for plugin in client.list_plugins():
    if not plugin.get('isDev'):
        continue
    try:
        dev_plugin = client.get_plugin(plugin['id'])
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as plugin_zip:
            for path in plugin_file_paths(dev_plugin.list_files()):
                try:
                    plugin_zip.writestr(path, dev_plugin.get_file(path).read())
                except Exception as e:
                    print(f"  could not read {plugin['id']}/{path}: {e}")
        zip_buffer.seek(0)
        export_folder_handle.upload_stream(f"plugin_dev_{plugin['id']}_{export_timestamp}.zip", zip_buffer)
        print(f"Exported dev plugin files: {plugin['id']}")
    except Exception as e:
        print(f"Error exporting dev plugin {plugin['id']}: {e}")


# In[7]:


try:
    # Retrieve list of all connections
    connections = client.list_connections()
    
    # Prepare detailed connection information for export
    connections_details = []
    for conn in connections:
        # Obtain connection details
        conn_detail = client.get_connection(conn).get_definition()
        
        # Add connection details to list
        #connections_details.append(conn_detail)
        sanitized_conn = sanitize_dict(conn_detail)
        
        # Add sanitized connection details to list
        connections_details.append(sanitized_conn)
        
    # Define output file name and path
    connections_output_filepath = '/tmp/connections.txt'
    
    # Write connection details to JSON file
    with open(connections_output_filepath, 'w') as file:
        json.dump(connections_details, file, indent=4)


    # Upload the text file to the managed folder
    with open(connections_output_filepath, 'rb') as f:
        export_folder_handle.upload_stream(f"list_connections_{export_timestamp}.json", f)
        os.remove(connections_output_filepath)
        
    print(f"Connection details successfully exported to managed folder.")

except Exception as e:
    print(f"An error occurred: {e}")


# In[8]:


# Code Environment names
code_env_name_list = sorted([env['envName'] for env in client.list_code_envs()])

with open('code_env_names.txt', 'w') as f:
    f.write('\n'.join(code_env_name_list))
    
# Upload the text file to the managed folder
with open('code_env_names.txt', 'rb') as f:
    export_folder_handle.upload_stream(f"list_codeenvs_{export_timestamp}.txt", f)
    
    os.remove('code_env_names.txt')


# In[9]:


def export_code_environments():
    """ Exports all code environment settings to a JSON file. """
    try:
        # Get all code environments
        code_envs_list = client.list_code_envs()
        
        # Group the definitions by language ("python", "r", ...): a code env is
        # only found when looked up with its own language
        code_envs_details = {}
        for env in code_envs_list:
            env_name = env.get("envName")
            env_lang = env.get("envLang", "PYTHON").lower()
            try:
                env_details = client.get_code_env(env_lang, env_name).get_definition()
                code_envs_details.setdefault(env_lang, []).append(env_details)
            except Exception as e:
                print(f"Error exporting {env_lang} environment {env_name}: {str(e)}")
        
        # Define output file name and path with timestamp
        output_filename = f"code_environments_export.json"
        
        # Write code environment details to JSON file
        with open(output_filename, 'w') as file:
            json.dump(sanitize_dict(code_envs_details), file, indent=4)
            
        with open(output_filename, 'rb') as f:
            export_folder_handle.upload_stream(f"list_codeenvs_{export_timestamp}.json", f)
            os.remove(output_filename)
        
        print(f"\nCode environment details successfully saved to {output_filename}")
    
    except Exception as e:
        print(f"An error occurred during export: {str(e)}")
        return None

    
export_code_environments()


# In[10]:


settings_raw = client.get_general_settings().get_raw()
settings_output_filename = 'general_settings.json'
with open(settings_output_filename, 'w') as file:
    json.dump(sanitize_dict(settings_raw), file, indent=4)

with open(settings_output_filename, 'rb') as f:
    export_folder_handle.upload_stream(f"general_settings_{export_timestamp}.json", f)
    os.remove(settings_output_filename)

print('Finished exporting settings.')


# In[11]:


# Instance-level objects that are not part of the general settings or project exports.
# Secrets (API key values, passwords) are redacted by sanitize_dict and must be re-created.

export_section('users', 'users', client.list_users)
export_section('groups', 'groups', client.list_groups)
export_section('global API keys (key values redacted)', 'global_api_keys',
               lambda: [dict(k) for k in client.list_global_api_keys()])
export_section('instance info and licensing status', 'instance_info',
               lambda: {'instance': client.get_instance_info().raw,
                        'licensing_status': client.get_licensing_status()})
export_section('global variables', 'global_variables', client.get_global_variables)
export_section('custom meanings', 'meanings',
               lambda: [client.get_meaning(m['id']).get_definition() for m in client.list_meanings()])
export_section('clusters', 'clusters',
               lambda: [{'definition': dict(c),
                         'settings': client.get_cluster(c['id']).get_settings().get_raw()}
                        for c in client.list_clusters()])
export_section('messaging channels', 'messaging_channels',
               lambda: [ch.get_raw() for ch in client.list_messaging_channels()])
export_section('workspaces', 'workspaces',
               lambda: [{'settings': client.get_workspace(w['workspaceKey']).get_settings().get_raw(),
                         'objects': client.get_workspace(w['workspaceKey']).list_objects()}
                        for w in client.list_workspaces()])
export_section('data collections', 'data_collections',
               lambda: [dc.get_raw() for dc in client.list_data_collections()])


def build_project_folder_tree(folder):
    """ Project folder hierarchy with the projects in each folder """
    return {
        'id': folder.id,
        'name': folder.get_name(),
        'project_keys': folder.list_project_keys(),
        'children': [build_project_folder_tree(child) for child in folder.list_child_folders()],
    }


export_section('project folder tree', 'project_folders',
               lambda: build_project_folder_tree(client.get_root_project_folder()))


# In[12]:


# Code studio templates. The settings hold the whole definition (blocks, container
# configs, permissions); the built image itself can't be exported, so the build state
# and everything the template depends on is recorded to rebuild it on a new node.

def build_code_studio_templates():
    templates = []
    for item in client.list_code_studio_templates():
        settings = item.to_code_studio_template().get_settings()
        raw = settings.get_raw()
        blocks = raw.get('params', {}).get('blocks', [])
        container_confs = [raw.get('defaultContainerConf')] + list(raw.get('containerConfs', []))
        templates.append({
            'id': item.id,
            'label': item.label,
            'settings': raw,
            'build': {
                'last_built': item.last_built,
                'built_container_confs': settings.get_built_container_confs(),
                'built_for_all_container_confs': settings.get_built_for_all_container_confs(),
            },
            'requires': {
                # each: envLang / envName / versionId, see the code environments export
                'code_envs': [b['params'] for b in blocks if b.get('type') == 'add_codeenv'],
                # blocks provided by plugins, see the plugins export
                'plugin_block_types': [b['type'] for b in blocks if b.get('type', '').startswith('pycdstdioblk_')],
                # defined in the general settings (containerSettings)
                'container_confs': sorted({c for c in container_confs if c}),
                # see the groups export
                'groups': sorted({p['group'] for p in raw.get('permissions', []) if 'group' in p}),
            },
        })
    return templates


def build_code_studio_instances():
    """ Which project code studios exist and which template each uses. Their definitions
    are already inside the project exports (project_config/code_studios/). """
    instances = []
    for project_key in client.list_project_keys():
        for studio in client.get_project(project_key).list_code_studios():
            instances.append({'project_key': project_key, 'id': studio.id, 'name': studio.name,
                              'owner': studio.owner, 'template_id': studio.template_id})
    return instances


export_section('code studio templates', 'code_studio_templates', build_code_studio_templates)
export_section('code studio instances', 'code_studio_instances', build_code_studio_instances)

# Newer DSS versions can also export a template as a zip; older ones return NotFound
for item in client.list_code_studio_templates():
    template_zip_path = f'/tmp/code_studio_template_{item.id}.zip'
    try:
        with open(template_zip_path, 'wb') as f:
            for chunk in item.to_code_studio_template().get_export_stream().iter_content(chunk_size=32768):
                f.write(chunk)
        with open(template_zip_path, 'rb') as f:
            export_folder_handle.upload_stream(f'code_studio_template_{item.id}_{export_timestamp}.zip', f)
        print(f"Exported code studio template zip: {item.id}")
    except Exception as e:
        print(f"Code studio template zip not available for {item.id}: {str(e)[:100]}")
    finally:
        if os.path.exists(template_zip_path):
            os.remove(template_zip_path)


# In[13]:


# Manifest: what this run produced, so the folder can be used to rebuild a node
def build_manifest():
    return {
        'created': export_timestamp,
        'timezone': str(TIMEZONE),
        'dss_version': client.get_instance_info().raw.get('dssVersion'),
        'project_export_tiers': {name: options for name, options in EXPORT_OPTION_TIERS},
        'projects': project_results,
        # this run's uploads plus the project zips it relies on (also those from earlier runs)
        'files': sorted(set(export_folder_handle.uploaded) | {p['file'] for p in project_results if p.get('file')}),
        'rebuild_order': [
            'install DSS (same or newer version, see dss_version) and apply the licence (instance_info)',
            'general_settings: containers, Spark, auth, mail, ... (re-enter redacted secrets)',
            'groups, users, global_api_keys (API keys and passwords are not exported, re-create them)',
            'list_connections (re-enter credentials)',
            'plugins: install from the store by id and version, restore settings, unzip plugin_dev_* for dev plugins',
            'list_codeenvs_*.json: recreate and build the code environments',
            'clusters, messaging_channels, meanings, global_variables',
            'code_studio_templates: recreate, then rebuild the images (see requires and build)',
            'project_folders, workspaces, data_collections',
            'import the PROJECT__*.zip files (input datasets included; other datasets are rebuilt by running the flow)',
        ],
    }


export_section('manifest', 'manifest', build_manifest)


# In[ ]:
