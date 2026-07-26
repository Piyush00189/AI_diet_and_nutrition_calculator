"""
settings_page.py
-------------------
AI Diet Chart & Nutrition Calculator — Settings
Healthcare-themed, built with CustomTkinter.

Sections:
  1. Change Password — verifies the current password, then updates
     to a new one via database.update_password() (bcrypt-hashed).
  2. Biometric Login — lets the user enable/disable Face ID login
     for their account (captures + stores a face encoding via
     face_auth.py / face_capture_window.py; matched later by
     face_login_page.py).
  3. App Preferences — local, per-machine settings stored in
     app_settings.json via preferences.py.
  4. Help & Support / Feedback / About — links out to the Help &
     Contact page, the Feedback page, and the About page.

Note: Gemini API key configuration is intentionally NOT here. This
app uses one shared api.env file read by the AI pages (Nutrition
Calculator, Diet Planner, AI Health Tips) — since it isn't scoped
per-user, exposing it in a per-user Settings page isn't appropriate.
If you need to change it, edit api.env directly.

Run:
    pip install customtkinter mysql-connector-python
    python settings_page.py
"""

import re

import mysql.connector
import customtkinter as ctk

import database
import session
import preferences
import face_auth

# ---------------------------------------------------------------------------
# Theme constants — matches the rest of the app
# ---------------------------------------------------------------------------
COLOR_BG = "#0E4B47"
COLOR_CARD = "#155953"
COLOR_ACCENT = "#2FD3B0"
COLOR_ACCENT_SOFT = "#8FE3D1"
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#1E6B64"
COLOR_ENTRY_BG = "#0B3D3A"
COLOR_MUTED = "#6FA69E"
COLOR_ERROR = "#FF8A80"
COLOR_SUCCESS = "#8CFFB0"

WINDOW_W, WINDOW_H = 520, 860
MIN_W, MIN_H = 420, 620
MAX_W, MAX_H = 640, 1000

class SettingsPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.user_email = self.user_data.get("email")
        self.on_back = on_back

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Settings")
        self.configure(fg_color=COLOR_BG)
        win_w, win_h = self._compute_responsive_size()
        self._center_window(win_w, win_h)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        self._build_ui()

    def _compute_responsive_size(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        target_w = sw * 0.28
        target_h = sh * 0.80
        aspect = WINDOW_H / WINDOW_W
        if target_h / target_w > aspect:
            target_h = target_w * aspect
        else:
            target_w = target_h / aspect
        w = max(MIN_W, min(MAX_W, int(target_w)))
        h = max(MIN_H, min(MAX_H, int(target_h)))
        return w, h

    def _center_window(self, w, h):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        outer = ctk.CTkFrame(
            self, fg_color=COLOR_BG, corner_radius=20,
            border_width=2, border_color=COLOR_TRACK
        )
        outer.pack(fill="both", expand=True, padx=16, pady=16)

        top_row = ctk.CTkFrame(outer, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkButton(
            top_row, text="←  Back", width=70, height=30,
            fg_color="transparent", hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=12),
            command=self._go_back,
        ).pack(side="left")

        ctk.CTkLabel(
            outer, text="⚙️  Settings",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 16))

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._build_password_section(scroll)
        self._build_biometric_section(scroll)
        self._build_preferences_section(scroll)
        self._build_help_support_section(scroll)
        self._build_feedback_section(scroll)
        self._build_about_section(scroll)

    def _section_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", padx=16, pady=(14, 8))
        return card

    def _add_entry(self, parent, label_text, show=None):
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", padx=16, pady=(6, 0))
        entry = ctk.CTkEntry(
            parent, height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            show=show or "",
        )
        entry.pack(fill="x", padx=16, pady=(4, 0))
        return entry

    # -------------------------------------------------------- password
    def _build_password_section(self, parent):
        card = self._section_card(parent, "🔒  Change Password")

        if not self.user_email:
            ctk.CTkLabel(
                card, text="Log in first to change your password.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(anchor="w", padx=16, pady=(0, 14))
            return

        self.current_pw_entry = self._add_entry(card, "Current Password", show="•")
        self.new_pw_entry = self._add_entry(card, "New Password", show="•")
        self.confirm_pw_entry = self._add_entry(card, "Confirm New Password", show="•")

        self.password_status_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=400, justify="left",
        )
        self.password_status_label.pack(anchor="w", padx=16, pady=(6, 0))

        self.password_btn = ctk.CTkButton(
            card, text="Update Password", height=36, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_update_password,
        )
        self.password_btn.pack(fill="x", padx=16, pady=(10, 16))

    def _handle_update_password(self):
        current_pw = self.current_pw_entry.get()
        new_pw = self.new_pw_entry.get()
        confirm_pw = self.confirm_pw_entry.get()

        if not current_pw or not new_pw or not confirm_pw:
            self.password_status_label.configure(text_color=COLOR_ERROR, text="Fill in all three fields.")
            return

        if len(new_pw) < 8 or not re.search(r"[A-Za-z]", new_pw) or not re.search(r"\d", new_pw):
            self.password_status_label.configure(
                text_color=COLOR_ERROR,
                text="New password must be at least 8 characters and include a letter and a number.",
            )
            return

        if new_pw != confirm_pw:
            self.password_status_label.configure(text_color=COLOR_ERROR, text="New passwords do not match.")
            return

        self.password_btn.configure(state="disabled", text="Updating...")
        self.password_status_label.configure(text="")
        self.update_idletasks()

        try:
            user = database.get_user_by_email(self.user_email)
        except mysql.connector.Error as db_err:
            self.password_status_label.configure(text_color=COLOR_ERROR, text=f"Database error: {db_err}")
            self.password_btn.configure(state="normal", text="Update Password")
            return

        if not user or not database.verify_password(current_pw, user["password_hash"]):
            self.password_status_label.configure(text_color=COLOR_ERROR, text="Current password is incorrect.")
            self.password_btn.configure(state="normal", text="Update Password")
            return

        try:
            database.update_password(self.user_email, new_pw)
        except (ValueError, mysql.connector.Error) as e:
            self.password_status_label.configure(text_color=COLOR_ERROR, text=str(e))
            self.password_btn.configure(state="normal", text="Update Password")
            return

        self.current_pw_entry.delete(0, "end")
        self.new_pw_entry.delete(0, "end")
        self.confirm_pw_entry.delete(0, "end")
        self.password_status_label.configure(text_color=COLOR_SUCCESS, text="Password updated successfully.")
        self.password_btn.configure(state="normal", text="Update Password")

    # -------------------------------------------------------- biometric
    def _build_biometric_section(self, parent):
        card = self._section_card(parent, "🧬  Biometric Login")

        if not self.user_email:
            ctk.CTkLabel(
                card, text="Log in first to set up Face ID login.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(anchor="w", padx=16, pady=(0, 14))
            return

        try:
            self.biometric_enabled = database.is_biometric_enabled(self.user_email)
        except mysql.connector.Error:
            self.biometric_enabled = False

        self.biometric_status_label = ctk.CTkLabel(
            card,
            text=f"Status: {'Enabled ✅' if self.biometric_enabled else 'Disabled'}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_SUCCESS if self.biometric_enabled else COLOR_MUTED,
        )
        self.biometric_status_label.pack(anchor="w", padx=16, pady=(0, 4))

        ctk.CTkLabel(
            card, text="Use your face instead of a password to log in on this device.",
            font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
            wraplength=420, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        self.biometric_msg_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=420, justify="left",
        )
        self.biometric_msg_label.pack(anchor="w", padx=16, pady=(0, 4))

        self.biometric_btn = ctk.CTkButton(
            card, height=36, corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_toggle_biometric,
            **self._biometric_btn_style(self.biometric_enabled),
        )
        self.biometric_btn.pack(fill="x", padx=16, pady=(0, 16))

    def _biometric_btn_style(self, enabled):
        if enabled:
            return dict(
                text="Disable Biometric", fg_color="transparent",
                border_width=1, border_color=COLOR_ERROR, hover_color=COLOR_TRACK,
                text_color=COLOR_ERROR,
            )
        return dict(
            text="Enable Biometric", fg_color=COLOR_ACCENT,
            hover_color="#26B79A", text_color="#0B3D3A",
        )

    def _handle_toggle_biometric(self):
        if self.biometric_enabled:
            self._handle_disable_biometric()
        else:
            self._handle_enable_biometric()

    def _handle_enable_biometric(self):
        if not face_auth.dependencies_available():
            self.biometric_msg_label.configure(
                text_color=COLOR_ERROR, text=face_auth.dependencies_error_message(),
            )
            return

        from face_capture_window import FaceCaptureWindow
        FaceCaptureWindow(self, on_captured=self._on_face_captured)

    def _on_face_captured(self, encoding):
        encoding_bytes = face_auth.encoding_to_bytes(encoding)
        try:
            database.enable_biometric(self.user_email, encoding_bytes)
        except (ValueError, mysql.connector.Error) as e:
            self.biometric_msg_label.configure(text_color=COLOR_ERROR, text=str(e))
            return

        self.biometric_enabled = True
        self.biometric_status_label.configure(text="Status: Enabled ✅", text_color=COLOR_SUCCESS)
        self.biometric_msg_label.configure(
            text_color=COLOR_SUCCESS, text="Face ID enabled — you can now use it from the Login screen.",
        )
        self.biometric_btn.configure(**self._biometric_btn_style(True))

    def _handle_disable_biometric(self):
        try:
            database.disable_biometric(self.user_email)
        except mysql.connector.Error as e:
            self.biometric_msg_label.configure(text_color=COLOR_ERROR, text=f"Database error: {e}")
            return

        self.biometric_enabled = False
        self.biometric_status_label.configure(text="Status: Disabled", text_color=COLOR_MUTED)
        self.biometric_msg_label.configure(text_color=COLOR_SUCCESS, text="Face ID disabled for this account.")
        self.biometric_btn.configure(**self._biometric_btn_style(False))

    # -------------------------------------------------------- preferences
    def _build_preferences_section(self, parent):
        card = self._section_card(parent, "🛠️  App Preferences")

        prefs = preferences.load_preferences()
        self.pref_vars = {}

        self._add_preference_switch(
            card, prefs, "auto_generate_ai_tips",
            "Auto-generate AI Health Tips on open",
            "If off, you'll need to tap Regenerate on that page instead.",
        )
        self._add_preference_switch(
            card, prefs, "daily_water_reminder",
            "Daily water reminder (coming soon)",
            "Saved now for a future reminder feature — not active yet.",
        )

        ctk.CTkButton(
            card, text="Save Preferences", height=36, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_save_preferences,
        ).pack(fill="x", padx=16, pady=(10, 8))

        self.preferences_status_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=11), text_color=COLOR_SUCCESS,
        )
        self.preferences_status_label.pack(anchor="w", padx=16, pady=(0, 16))

    def _add_preference_switch(self, parent, prefs, key, label_text, note_text):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(6, 0))

        var = ctk.BooleanVar(value=bool(prefs.get(key, False)))
        switch = ctk.CTkSwitch(
            row, text=label_text, variable=var,
            onvalue=True, offvalue=False,
            fg_color=COLOR_TRACK, progress_color=COLOR_ACCENT,
            text_color=COLOR_WHITE, font=ctk.CTkFont(size=12),
        )
        switch.pack(anchor="w")
        ctk.CTkLabel(
            parent, text=note_text, font=ctk.CTkFont(size=10), text_color=COLOR_MUTED,
        ).pack(anchor="w", padx=(38, 16), pady=(0, 4))

        self.pref_vars[key] = var

    def _handle_save_preferences(self):
        prefs = {key: var.get() for key, var in self.pref_vars.items()}
        try:
            preferences.save_preferences(prefs)
        except OSError as e:
            self.preferences_status_label.configure(text_color=COLOR_ERROR, text=f"Couldn't save: {e}")
            return
        self.preferences_status_label.configure(text_color=COLOR_SUCCESS, text="Preferences saved.")

    # -------------------------------------------------------- help & support
    def _build_help_support_section(self, parent):
        card = self._section_card(parent, "🆘  Help & Support")
        ctk.CTkLabel(
            card, text="FAQs, a getting-started guide, troubleshooting tips, and ways to contact us.",
            font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
            wraplength=420, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        ctk.CTkButton(
            card, text="Open Help & Contact", height=36, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_help_contact,
        ).pack(fill="x", padx=16, pady=(0, 16))

    def _open_help_contact(self):
        from help_contact import HelpContactPage
        self.destroy()
        HelpContactPage(user_data=self.user_data).mainloop()

    # ------------------------------------------------------------ feedback
    def _build_feedback_section(self, parent):
        card = self._section_card(parent, "💬  Feedback")
        ctk.CTkLabel(
            card, text="Rate the app and leave a comment — it helps us improve NutriApp.",
            font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
            wraplength=420, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        ctk.CTkButton(
            card, text="Rate & Give Feedback", height=36, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=COLOR_TRACK,
            hover_color=COLOR_TRACK, text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=12),
            command=self._open_feedback,
        ).pack(fill="x", padx=16, pady=(0, 16))

    def _open_feedback(self):
        from feedback_page import FeedbackPage
        self.destroy()
        FeedbackPage(user_data=self.user_data).mainloop()

    # -------------------------------------------------------------- about
    def _build_about_section(self, parent):
        card = self._section_card(parent, "ℹ️  About")
        ctk.CTkLabel(
            card, text="App version, technologies used, and developer credits.",
            font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
        ).pack(anchor="w", padx=16, pady=(0, 10))
        ctk.CTkButton(
            card, text="View About This App", height=36, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=COLOR_TRACK,
            hover_color=COLOR_TRACK, text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=12),
            command=self._open_about,
        ).pack(fill="x", padx=16, pady=(0, 16))

    def _open_about(self):
        from about_page import AboutPage
        self.destroy()
        AboutPage(
            user_data=self.user_data,
            on_back=lambda: SettingsPage(user_data=self.user_data).mainloop(),
        ).mainloop()

    def _go_back(self):
        from dashboard import DashboardPage
        self.destroy()
        if self.on_back:
            self.on_back()
        else:
            DashboardPage(user_data=self.user_data).mainloop()


if __name__ == "__main__":
    demo_user = {
        "email": "priya@example.com",
        "full_name": "Priya Sharma",
    }
    app = SettingsPage(user_data=demo_user)
    app.mainloop()