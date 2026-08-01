"""
session.py
----------
Session store for the AI Diet Chart & Nutrition Calculator app.

In-memory current-user store (as before), plus an optional persistent
"remember me" token written to disk so the user can skip login on the
next launch. Only the email + an expiry timestamp are ever persisted
to disk — never the password or password hash.

If the user did NOT check "Remember me" at login, no token is written
and the app will ask for login again on every run (the original
behavior). If they did check it, `app.py` can call
`try_restore_session()` on startup to skip the login screen for up to
SESSION_DAYS days.
"""

import json
import os
from datetime import datetime, timedelta

import database

_current_user = None  # dict with at least "email"; None when logged out

SESSION_DIR = os.path.join(os.path.expanduser("~"), ".ai_diet_chart")
SESSION_FILE = os.path.join(SESSION_DIR, "session.json")
SESSION_DAYS = 7


def set_current_user(user: dict) -> None:
    """Call this right after a successful login."""
    global _current_user
    _current_user = user


def get_current_user():
    """Returns the logged-in user's dict, or None if nobody is logged in."""
    return _current_user


def is_logged_in() -> bool:
    return _current_user is not None


def clear_session() -> None:
    """Call this on logout to wipe the current session AND any
    remembered login on disk, so the app doesn't silently auto-login
    again next launch."""
    global _current_user
    _current_user = None
    forget_remembered_login()


# --------------------------------------------------------------- remember me
def remember_login(email: str) -> None:
    """Persist only the email + an expiry timestamp (never the password
    or password hash) so the app can auto-login on next launch."""
    os.makedirs(SESSION_DIR, exist_ok=True)
    data = {
        "email": email,
        "expires_at": (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat(),
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)


def forget_remembered_login() -> None:
    """Deletes the remembered-login file, if any. Safe to call even if
    it doesn't exist."""
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except OSError:
        pass


def try_restore_session():
    """Checks for a valid, non-expired remembered login on disk and,
    if found, re-fetches that user from MySQL (so data is always
    fresh, not a stale cached copy) and sets them as the current user.

    Returns a user dict with password_hash stripped, ready to hand to
    DashboardPage(user_data=...), or None if there's no valid
    remembered session (in which case the caller should fall back to
    showing the splash screen / login page as normal).
    """
    if not os.path.exists(SESSION_FILE):
        return None

    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
        expires_at = datetime.fromisoformat(data["expires_at"])
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        forget_remembered_login()
        return None

    if datetime.now() > expires_at:
        forget_remembered_login()
        return None

    try:
        user = database.get_user_by_email(data["email"])
    except Exception:
        # DB might be briefly unreachable; don't crash startup over it,
        # just fall back to the normal login flow.
        return None

    if not user:
        # Account no longer exists / was deleted.
        forget_remembered_login()
        return None

    set_current_user(user)
    return {k: v for k, v in user.items() if k != "password_hash"}