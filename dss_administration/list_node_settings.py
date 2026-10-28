# Paste into a Dataiku notebook cell. Read only: prints this node's general
# settings and global variables as pretty JSON. The notebook's user needs admin rights.
import json

import dataiku

# Setting names containing any of these (case-insensitive) are masked in the output.
SECRET_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "privatekey",
    "passphrase",
    "connectionstring",
)


def is_secret(name):
    return any(f in str(name).lower() for f in SECRET_KEY_FRAGMENTS)


def redact(value):
    if isinstance(value, dict):
        # Also covers {"name": "some.password", "value": "..."} property lists
        name_is_secret = is_secret(value.get("name", ""))
        return {
            k: (
                "***REDACTED***"
                if v and (is_secret(k) or (name_is_secret and k == "value"))
                else redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


client = dataiku.api_client()
node_settings = {
    "general_settings": redact(client.get_general_settings().get_raw()),
    "global_variables": redact(client.get_global_variables()),
}
print(json.dumps(node_settings, indent=2, sort_keys=True, default=str))
