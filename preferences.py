"""
preferences.py
----------------
Local (per-machine) app preferences for the AI Diet Chart &
Nutrition Calculator app, stored as a small JSON file
(app_settings.json) in the same folder. These are separate from
user accounts in MySQL since they're device-level settings, not
something that needs to sync across devices/logins.
"""

import json
import os

PREFS_FILE = "app_settings.json"

DEFAULT_PREFERENCES = {
    # Whether ai_health_tips.py auto-generates a fresh set of tips as
    # soon as it opens (vs. waiting for the user to click Regenerate).
    "auto_generate_ai_tips": True,
    # Reserved for a future daily-reminder feature — saved here now so
    # the Settings page has somewhere real to write it, but no module
    # reads/acts on it yet.
    "daily_water_reminder": False,
}


def load_preferences() -> dict:
    """Returns the saved preferences, merged with defaults for any
    keys that don't exist yet (e.g. after adding a new preference)."""
    prefs = DEFAULT_PREFERENCES.copy()
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r") as f:
                saved = json.load(f)
            prefs.update(saved)
        except (json.JSONDecodeError, OSError):
            pass  # fall back to defaults if the file is missing/corrupt
    return prefs


def save_preferences(prefs: dict) -> None:
    """Writes `prefs` to app_settings.json, fully replacing its contents."""
    with open(PREFS_FILE, "w") as f:
        json.dump(prefs, f, indent=2)