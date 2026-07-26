import sys
import traceback

import mysql.connector
import customtkinter as ctk

import database

from splash_screen import SplashScreen
from login_page import LoginPage


def _show_fatal_error(message: str):
    """Best-effort error dialog for startup failures (e.g. the MySQL
    server isn't running), so the app doesn't just vanish with a
    console-only traceback."""
    try:
        root = ctk.CTk()
        root.withdraw()
        from tkinter import messagebox
        messagebox.showerror("AI Diet Chart & Nutrition Calculator — Startup Error", message)
        root.destroy()
    except Exception:
        # If even the error dialog can't be shown, fall back to console.
        print(message, file=sys.stderr)


def _open_login():
    """Called by SplashScreen once it finishes closing itself."""
    login = LoginPage()
    login.mainloop()


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    try:
        splash = SplashScreen(on_finish=_open_login)
        splash.mainloop()
    except mysql.connector.Error as db_err:
        _show_fatal_error(
            "Could not connect to the database.\n\n"
            f"{db_err}\n\n"
            "Check that MySQL is running and the credentials in "
            "database.py / api.env are correct."
        )
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - top-level safety net
        traceback.print_exc()
        _show_fatal_error(f"An unexpected error occurred while starting the app:\n\n{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()