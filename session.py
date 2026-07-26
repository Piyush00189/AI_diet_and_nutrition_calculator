"""
session.py
----------
Minimal in-memory session store for the AI Diet Chart & Nutrition
Calculator app. Holds the currently logged-in user's data so any page
(dashboard, logout dialog, etc.) can check who's logged in without
passing the dict around manually everywhere.

This is intentionally simple (a module-level variable) since the app
is a single-process desktop app. If you later add "remember me" /
persistent sessions across app restarts, this is the file to extend
(e.g. write a session token to disk).
"""

_current_user = None  # dict with at least "email"; None when logged out


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
    """Call this on logout to wipe the current session."""
    global _current_user
    _current_user = None