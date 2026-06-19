import logging
from pprint import pprint as pp
from typing import Any

import dataikuapi

##############################################################################
# Config — replace these values with your own before running
##############################################################################
# Replace with your DSS instance URL.
DSS_URL = "https://REDACTED.dataiku-sandbox.io"
# Replace with your DSS API key secret.
API_KEY = "REDACTED"


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_remote_api_key_info(host: str, api_secret: str) -> dict[str, Any]:
    """Connect to a remote DSS instance, identify the API key type, and return its permissions."""
    # Initialize the remote client
    # This uses the external API client package which is standard for remote connections
    client = dataikuapi.DSSClient(host, api_secret)

    result = {
        "host": host,
        "auth_identifier": None,
        "key_type": "Unknown",
        "permissions": {},
        "auth_info": {},
    }

    # 1. Retrieve Authentication Context
    try:
        # get_auth_info() returns the current context using this instance of the API client
        auth_info = client.get_auth_info()
        result["auth_info"] = auth_info

        # 'authIdentifier' maps to the user's login or the API key's ID
        auth_id = auth_info.get("authIdentifier")
        if not auth_id:
            logger.error("Could not retrieve authIdentifier from connection.")
            return result

        result["auth_identifier"] = auth_id
        logger.info(f"Successfully authenticated. Identifier: {auth_id}")

    except Exception as e:
        logger.error(f"Failed to connect or retrieve auth info from {host}. Error: {e}")
        return result

    # 2. Check for Global API Key Permissions
    # We attempt to read the general settings, which requires the key to have Admin rights.
    try:
        general_settings = client.get_general_settings().get_raw()
        global_api_keys = general_settings.get("apiKeys", [])

        # Search the global keys for our authenticated ID
        matched_key = next(
            (key for key in global_api_keys if key.get("id") == auth_id), None
        )

        if matched_key:
            result["key_type"] = "Global API Key"
            result["permissions"] = {
                "admin": matched_key.get("admin", False),
                "read_all_projects": matched_key.get("readAllProjects", False),
                "read_all_project_content": matched_key.get(
                    "readAllProjectContent", False
                ),
                "allowed_projects": matched_key.get("allowedProjects", []),
                "groups": matched_key.get("groups", []),
            }
            logger.info("Matched as a Global API Key. Extracted precise permissions.")
            return result

    except Exception as e:
        logger.debug(
            f"Could not retrieve Global API Keys (likely not an Admin key): {e}"
        )

    # 3. Check for Personal API Key Permissions
    # If the key acts on behalf of a specific user, we can fetch their settings
    try:
        own_user = client.get_own_user().get_settings().get_raw()
        result["key_type"] = "Personal API Key"
        result["permissions"]["user_profile"] = own_user.get("userProfile")
        result["permissions"]["groups"] = own_user.get("groups", [])
        result["permissions"]["is_admin"] = "admin" in own_user.get(
            "groups", []
        ) or "administrators" in own_user.get("groups", [])
        logger.info(
            "Matched as a Personal API Key. Extracted user profile permissions."
        )
    except Exception as e:
        logger.debug(f"Could not retrieve Personal API Key user settings: {e}")

        # Fallback if it's neither Admin nor Personal, but groups are attached directly
        if "groups" in auth_info:
            result["key_type"] = "Group-assigned Global API Key"
            result["permissions"]["groups"] = auth_info["groups"]

    # 4. Implicit Permissions Check
    # Regardless of the key type, we can list what projects it actively has access to.
    try:
        result["permissions"]["accessible_projects"] = client.list_project_keys()
    except Exception as e:
        logger.warning(f"Could not list accessible projects: {e}")
        result["permissions"]["accessible_projects"] = []

    return result


##############################################################################
# MAIN
##############################################################################

if __name__ == "__main__":
    res = get_remote_api_key_info(DSS_URL, API_KEY)
    pp(res)
    print("script end.")
