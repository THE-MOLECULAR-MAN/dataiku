#!/usr/bin/env python
# Written for Python 3.11+

import dataiku


def get_current_user_email() -> str | None:
    """Return the email of the currently authenticated DSS user, or None if unavailable."""
    client = dataiku.api_client()

    # auth_info keys vary by auth source (UI session, API key, impersonation…)
    auth_info = client.get_auth_info()

    # 'email' is present in some auth contexts but not all — try it first
    email = auth_info.get("email")

    # Fall back to looking up the user record by login identifier
    if not email:
        login = (
            auth_info.get("user")
            or auth_info.get("login")
            or auth_info.get("authIdentifier")
        )
        if login:
            try:
                user_settings = client.get_user(login).get_settings().get_raw()
                email = user_settings.get("email")
            except Exception:
                # User may not exist or caller lacks permission
                pass

    return email


print(get_current_user_email())
