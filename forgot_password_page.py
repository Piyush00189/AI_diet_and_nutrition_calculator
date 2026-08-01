"""
forgot_password_page.py
------------------------
AI Diet Chart & Nutrition Calculator — Forgot Password Page
Healthcare-themed, built with CustomTkinter.

Two-step flow in one window:
  1. User enters their registered email -> verified against MySQL.
  2. If found, the "new password" section unlocks -> validated,
     then saved to MySQL via database.update_password().

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py /
about_page.py / feedback_page.py / exercise_recommendation.py
(`state('zoomed')`, falling back to `-zoomed` or a manual full-screen
geometry). The compact card is kept centered on screen via `.place()`
so it doesn't stretch or stick to a corner once the window is maximized.

Run:
    pip install customtkinter mysql-connector-python
    python forgot_password_page.py
"""

import re
import customtkinter as ctk
import mysql.connector

import database

# ---------------------------------------------------------------------------
# Theme constants — matches the rest of the app
# ---------------------------------------------------------------------------
COLOR_BG = "#0E4B47"
COLOR_ACCENT = "#2FD3B0"
COLOR_ACCENT_SOFT = "#8FE3D1"
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#155953"
COLOR_ENTRY_BG = "#0B3D3A"
COLOR_ERROR = "#FF8A80"
COLOR_SUCCESS = "#8CFFB0"

CARD_W, CARD_H = 420, 560

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ForgotPasswordPage(ctk.CTk):
    def __init__(self, on_success=None):
        super().__init__()

        # on_success(email): called after the password is reset,
        # e.g. to switch back to the Login page.
        self.on_success = on_success
        self.verified_email = None

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Forgot Password")
        self.configure(fg_color=COLOR_BG)
        self.resizable(True, True)

        # Deferred, same reasoning as the rest of the app's pages:
        # CustomTkinter schedules some of its own window/DPI setup via
        # internal after() calls right after the window is created, and
        # calling state('zoomed') too early gets silently overwritten by
        # that later setup. Queuing it with after() lets it run after
        # that setup has settled.
        self.after(10, self._maximize_window)

        self._build_ui()

    # ------------------------------------------------------------ window
    def _maximize_window(self):
        """Opens the page filling the screen instead of a small centered
        window. `state('zoomed')` is the normal way to do this on
        Windows and most Linux window managers; macOS's Tk build
        doesn't support that state string and raises a TclError, so it
        falls back to `-zoomed` (some Linux WMs use this attribute
        instead), and finally to manually sizing/positioning the window
        to the full screen if neither is available."""
        maximized = False
        try:
            self.state("zoomed")
            maximized = True
        except Exception:
            pass

        if not maximized:
            try:
                self.attributes("-zoomed", True)
                maximized = True
            except Exception:
                pass

        if not maximized:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            self.geometry(f"{screen_w}x{screen_h}+0+0")

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # The card is a fixed-size panel kept centered on screen with
        # .place() (relx/rely + anchor) rather than .pack(fill="both",
        # expand=True), so it stays a compact centered form instead of
        # stretching to fill the now-maximized window.
        self.card = ctk.CTkFrame(
            self, width=CARD_W, height=CARD_H, fg_color=COLOR_BG, corner_radius=20,
            border_width=2, border_color=COLOR_TRACK
        )
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.pack_propagate(False)

        ctk.CTkLabel(
            self.card, text="Reset Your Password",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(30, 4))

        ctk.CTkLabel(
            self.card, text="Enter your registered email to get started",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 24))

        # ---- Step 1: email verification -----------------------------
        ctk.CTkLabel(
            self.card, text="Email", anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", padx=40)

        email_row = ctk.CTkFrame(self.card, fg_color="transparent")
        email_row.pack(fill="x", padx=40, pady=(4, 0))

        self.email_entry = ctk.CTkEntry(
            email_row, placeholder_text="you@example.com",
            height=38, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
        )
        self.email_entry.pack(side="left", fill="x", expand=True)

        self.verify_btn = ctk.CTkButton(
            email_row, text="Verify", width=80, height=38,
            corner_radius=10, fg_color=COLOR_ACCENT,
            hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._handle_verify_email,
        )
        self.verify_btn.pack(side="left", padx=(8, 0))

        self.verify_status = ctk.CTkLabel(
            self.card, text="",
            font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
        )
        self.verify_status.pack(pady=(6, 4), padx=40, anchor="w")

        # ---- Step 2: new password (hidden until email is verified) ---
        self.reset_section = ctk.CTkFrame(self.card, fg_color="transparent")
        # not packed yet — revealed after successful verification

        ctk.CTkLabel(
            self.reset_section, text="New Password", anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", padx=40, pady=(10, 0))
        self.new_password_entry = ctk.CTkEntry(
            self.reset_section, placeholder_text="At least 8 characters", show="•",
            height=38, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
        )
        self.new_password_entry.pack(fill="x", padx=40, pady=(4, 0))

        ctk.CTkLabel(
            self.reset_section, text="Confirm New Password", anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", padx=40, pady=(12, 0))
        self.confirm_password_entry = ctk.CTkEntry(
            self.reset_section, placeholder_text="Re-enter new password", show="•",
            height=38, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
        )
        self.confirm_password_entry.pack(fill="x", padx=40, pady=(4, 0))

        self.reset_status = ctk.CTkLabel(
            self.reset_section, text="", wraplength=340,
            font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
        )
        self.reset_status.pack(pady=(8, 4), padx=40, anchor="w")

        self.reset_btn = ctk.CTkButton(
            self.reset_section, text="Reset Password", height=40,
            corner_radius=10, fg_color=COLOR_ACCENT,
            hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._handle_reset_password,
        )
        self.reset_btn.pack(fill="x", padx=40, pady=(10, 0))

        # ---- Back to login --------------------------------------------
        back_row = ctk.CTkFrame(self.card, fg_color="transparent")
        back_row.pack(pady=(20, 14), side="bottom")
        ctk.CTkLabel(
            back_row, text="Remembered your password?",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(side="left")
        ctk.CTkButton(
            back_row, text="Back to Login",
            fg_color="transparent", hover=False,
            text_color=COLOR_ACCENT, font=ctk.CTkFont(size=12, underline=True),
            width=20, command=self._go_to_login,
        ).pack(side="left", padx=4)

        self.bind("<Return>", lambda _e: self._on_enter())

    def _on_enter(self):
        if self.verified_email is None:
            self._handle_verify_email()
        else:
            self._handle_reset_password()

    # ------------------------------------------------------------ step 1
    def _handle_verify_email(self):
        email = self.email_entry.get().strip()

        if not EMAIL_PATTERN.match(email):
            self.verify_status.configure(text_color=COLOR_ERROR, text="Enter a valid email address.")
            return

        self.verify_btn.configure(state="disabled", text="Checking...")
        self.update_idletasks()

        try:
            found = database.email_exists(email)
        except mysql.connector.Error as db_err:
            self.verify_status.configure(text_color=COLOR_ERROR, text=f"Database error: {db_err}")
            self.verify_btn.configure(state="normal", text="Verify")
            return

        self.verify_btn.configure(state="normal", text="Verify")

        if not found:
            self.verified_email = None
            self.reset_section.pack_forget()
            self.verify_status.configure(
                text_color=COLOR_ERROR,
                text="No account found with this email.",
            )
            return

        self.verified_email = email
        self.email_entry.configure(state="disabled")
        self.verify_btn.configure(state="disabled")
        self.verify_status.configure(
            text_color=COLOR_SUCCESS, text="Email verified. Set your new password below."
        )
        self.reset_section.pack(fill="x")
        self.new_password_entry.focus()

    # ------------------------------------------------------------ step 2
    def _handle_reset_password(self):
        if not self.verified_email:
            return

        new_password = self.new_password_entry.get()
        confirm_password = self.confirm_password_entry.get()

        if len(new_password) < 8 or not re.search(r"[A-Za-z]", new_password) or not re.search(r"\d", new_password):
            self.reset_status.configure(
                text_color=COLOR_ERROR,
                text="Password must be at least 8 characters and include a letter and a number.",
            )
            return

        if new_password != confirm_password:
            self.reset_status.configure(text_color=COLOR_ERROR, text="Passwords do not match.")
            return

        self.reset_btn.configure(state="disabled", text="Resetting...")
        self.update_idletasks()

        try:
            database.update_password(self.verified_email, new_password)
        except ValueError as ve:
            self.reset_status.configure(text_color=COLOR_ERROR, text=str(ve))
            self.reset_btn.configure(state="normal", text="Reset Password")
            return
        except mysql.connector.Error as db_err:
            self.reset_status.configure(text_color=COLOR_ERROR, text=f"Database error: {db_err}")
            self.reset_btn.configure(state="normal", text="Reset Password")
            return

        self.reset_status.configure(text_color=COLOR_SUCCESS, text="Password reset successfully!")
        self.reset_btn.configure(state="normal", text="Reset Password")

        email = self.verified_email
        self.after(700, lambda: self._finish(email))

    def _finish(self, email):
        self.destroy()
        if self.on_success:
            self.on_success(email)

    def _go_to_login(self):
        from login_page import LoginPage
        self.destroy()
        LoginPage().mainloop()


if __name__ == "__main__":
    app = ForgotPasswordPage()
    app.mainloop()