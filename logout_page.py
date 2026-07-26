"""
logout_page.py
---------------
AI Diet Chart & Nutrition Calculator — Logout Confirmation
Healthcare-themed modal dialog, built with CustomTkinter.

Pops up over the current window (e.g. the Dashboard) and asks the
user to confirm before logging out. On confirmation, it clears the
session (session.py) and returns to the Login page. On cancel, it
just closes and the user stays where they were.

Usage (e.g. from dashboard.py):
    from logout_page import confirm_logout

    def _handle_logout(self):
        confirm_logout(self)
"""

import customtkinter as ctk

import session

# ---------------------------------------------------------------------------
# Theme constants — matches the rest of the app
# ---------------------------------------------------------------------------
COLOR_BG = "#0E4B47"
COLOR_CARD = "#155953"
COLOR_ACCENT = "#2FD3B0"
COLOR_ACCENT_SOFT = "#8FE3D1"
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#1E6B64"
COLOR_DANGER = "#FF8A80"

DIALOG_W, DIALOG_H = 340, 220


class LogoutConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent

        self.title("Log Out")
        self.configure(fg_color=COLOR_BG)
        self.resizable(False, False)
        self._center_on_parent(parent, DIALOG_W, DIALOG_H)

        # Make it a proper modal: block interaction with the parent
        # window until this dialog is closed.
        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self._build_ui()

        # Also treat closing the window (the X button) as "Cancel"
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _center_on_parent(self, parent, w, h):
        try:
            parent.update_idletasks()
            px, py = parent.winfo_x(), parent.winfo_y()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
        except Exception:
            x, y = 100, 100
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        card = ctk.CTkFrame(
            self, fg_color=COLOR_CARD, corner_radius=16,
        )
        card.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            card, text="🚪", font=ctk.CTkFont(size=30),
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            card, text="Log Out?",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            card, text="Are you sure you want to log out of your account?",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
            wraplength=260, justify="center",
        ).pack(pady=(0, 18))

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.pack(pady=(0, 16))

        ctk.CTkButton(
            button_row, text="Cancel", width=110, height=36,
            corner_radius=10, fg_color="transparent",
            border_width=1, border_color=COLOR_TRACK,
            hover_color=COLOR_TRACK, text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=13),
            command=self._cancel,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            button_row, text="Log Out", width=110, height=36,
            corner_radius=10, fg_color=COLOR_DANGER,
            hover_color="#E06F66", text_color="#3A0A06",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._confirm,
        ).pack(side="left", padx=6)

    def _cancel(self):
        self.grab_release()
        self.destroy()

    def _confirm(self):
        session.clear_session()

        self.grab_release()
        self.destroy()

        from login_page import LoginPage
        self.parent.destroy()
        LoginPage().mainloop()


def confirm_logout(parent):
    """Convenience function: opens the logout confirmation dialog on top
    of `parent` (the current CTk window, e.g. the Dashboard)."""
    LogoutConfirmDialog(parent)


if __name__ == "__main__":
    # Standalone preview: shows a stand-in window with a Logout button.
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title("Logout Dialog Preview")
    root.geometry("400x300")
    root.configure(fg_color=COLOR_BG)

    ctk.CTkButton(
        root, text="Logout", command=lambda: confirm_logout(root)
    ).pack(expand=True)

    root.mainloop()