# Paste into a Dataiku notebook cell. Read only: lists every Connection and its
# current settings as pretty JSON. The notebook's user needs admin rights.
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


def redact(value):
    if isinstance(value, dict):
        return {
            k: (
                "***REDACTED***"
                if any(f in k.lower() for f in SECRET_KEY_FRAGMENTS) and v
                else redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


client = dataiku.api_client()
connections = {
    name: redact(client.get_connection(name).get_settings().get_raw())
    for name in sorted(client.list_connections())
}
print(json.dumps(connections, indent=2, sort_keys=True, default=str))
