"""
login_page.py
--------------
AI Diet Chart & Nutrition Calculator — Login Page
Healthcare-themed, built with CustomTkinter.

Single login form for both regular users and admins. On submit, the
email/password pair is checked against the `admins` table first
(database.get_admin_by_email) — if it matches, the Admin Dashboard
opens. Otherwise the form falls through to the normal `users` lookup
and behaves exactly as before. A default admin account
(admin1@gmail.com / admin1234) is auto-created by database.py the
first time it's imported, so that combination works out of the box.

DISPLAY: the window itself now opens maximized/full-screen (same
approach as dashboard.py's `_maximize_window` — `state('zoomed')`,
falling back to `-zoomed` or a manual full-screen geometry). The
login card stays a fixed, comfortably-sized panel (sized the same
way as before, via `_compute_responsive_size`) but is now centered
inside that full window rather than being the whole window. Fonts,
padding, and the logo still scale with `self.scale` relative to the
screen resolution, same as before.

REMEMBER ME: a checkbox under the password field. When checked at
login time, `session.remember_login(email)` writes a small token
(email + 7-day expiry, never the password) to disk via session.py,
so `app.py` can skip straight to the dashboard on the next launch.
Left unchecked, any previously remembered login is cleared, so the
app goes back to asking for login every run as before.

Run:
    pip install customtkinter mysql-connector-python
    python login_page.py
"""

import customtkinter as ctk
import mysql.connector

import database
import session

# ---------------------------------------------------------------------------
# Theme constants — calm, clinical "healthcare" palette
# ---------------------------------------------------------------------------
COLOR_BG = "#0E4B47"             # primary background (deep teal)
COLOR_ACCENT = "#2FD3B0"         # mint / medical teal accent
COLOR_ACCENT_SOFT = "#8FE3D1"    # softer mint for secondary text
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#155953"          # border / track color
COLOR_ENTRY_BG = "#0B3D3A"
COLOR_CARD = "#123F3C"           # card background, one step lighter than the
                                  # full-screen COLOR_BG behind it so the
                                  # centered panel still reads as a card

# Base/reference design size (what the proportions below were tuned at)
BASE_W, BASE_H = 1000, 200

# Responsive bounds for the login CARD (not the window, which now fills
# the screen) so the card stays a sensible size on any desktop screen size
MIN_W, MIN_H = 340, 440
MAX_W, MAX_H = 1000, 700


class LoginPage(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ---- responsive sizing for the CARD, not the window -----------
        self.win_w, self.win_h = self._compute_responsive_size()
        self.scale = self.win_w / BASE_W

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Login")
        self.configure(fg_color=COLOR_BG)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        # Deferred, same reasoning as dashboard.py: CustomTkinter schedules
        # some of its own window/DPI setup via internal after() calls right
        # after the window is created, and calling state('zoomed') too
        # early gets silently overwritten by that later setup. Queuing it
        # with after() lets it run after that setup has settled.
        self.after(10, self._maximize_window)

        self._build_ui()

    # ------------------------------------------------------------ window
    def _maximize_window(self):
        """Opens the login page filling the screen instead of a small
        centered window. `state('zoomed')` is the normal way to do this
        on Windows and most Linux window managers; macOS's Tk build
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

    # ------------------------------------------------------------ sizing
    def _compute_responsive_size(self):
        """Sizes the login CARD (not the window) relative to screen size,
        the same proportions as before: ~30% of screen width and ~55% of
        screen height, preserving the card's aspect ratio."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        target_w = sw * 0.30
        target_h = sh * 0.55

        aspect = BASE_H / BASE_W
        if target_h / target_w > aspect:
            target_h = target_w * aspect
        else:
            target_w = target_h / aspect

        w = max(MIN_W, min(MAX_W, int(target_w)))
        h = max(MIN_H, min(MAX_H, int(target_h)))
        return w, h

    def _px(self, value):
        """Scales a base-design pixel value by the current responsive scale."""
        return max(1, round(value * self.scale))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Full-window background frame — the card below is centered
        # inside this, rather than the card being the whole window.
        outer = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        outer.pack(fill="both", expand=True)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(
            outer, width=self.win_w, height=self.win_h,
            fg_color=COLOR_CARD, corner_radius=self._px(20),
            border_width=2, border_color=COLOR_TRACK,
        )
        card.grid(row=0, column=0)
        # Keep the card at its computed size regardless of what's packed
        # inside it — without this, pack() on the children would shrink
        # or grow the frame to fit them instead of staying a fixed panel.
        card.grid_propagate(False)
        card.pack_propagate(False)

        # Small logo mark (medical cross in a ring) drawn on canvas
        logo_size = self._px(90)
        logo_canvas = ctk.CTkCanvas(
            card, width=logo_size, height=logo_size, bg=COLOR_CARD, highlightthickness=0
        )
        logo_canvas.pack(pady=(self._px(30), self._px(6)))
        self._draw_logo(logo_canvas, logo_size)

        title_size = max(15, self._px(22))
        subtitle_size = max(10, self._px(12))
        label_size = max(9, self._px(12))
        entry_h = max(30, self._px(38))
        pad_x = self._px(40)

        ctk.CTkLabel(
            card, text="Welcome Back",
            font=ctk.CTkFont(family="Segoe UI", size=title_size, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(self._px(6), self._px(4)))

        ctk.CTkLabel(
            card, text="Log in to your nutrition dashboard",
            font=ctk.CTkFont(family="Segoe UI", size=subtitle_size),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, self._px(26)))

        # Email field
        ctk.CTkLabel(
            card, text="Email", anchor="w",
            font=ctk.CTkFont(size=label_size), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", padx=pad_x)
        self.email_entry = ctk.CTkEntry(
            card, placeholder_text="you@example.com",
            height=entry_h, corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
        )
        self.email_entry.pack(fill="x", pady=(self._px(4), self._px(16)), padx=pad_x)

        # Password field
        ctk.CTkLabel(
            card, text="Password", anchor="w",
            font=ctk.CTkFont(size=label_size), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", padx=pad_x)

        password_row = ctk.CTkFrame(card, fg_color="transparent")
        password_row.pack(fill="x", pady=(self._px(4), self._px(6)), padx=pad_x)
        password_row.grid_columnconfigure(0, weight=1)

        self.password_entry = ctk.CTkEntry(
            password_row, placeholder_text="••••••••", show="•",
            height=entry_h, corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
        )
        self.password_entry.grid(row=0, column=0, sticky="ew")

        self.password_toggle_btn = ctk.CTkButton(
            password_row, text="👁", width=entry_h, height=entry_h,
            corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=max(11, self._px(13))),
            command=self._toggle_password_visibility,
        )
        self.password_toggle_btn.grid(row=0, column=1, padx=(self._px(6), 0))

        # Remember me checkbox
        self.remember_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            card, text="Remember me", variable=self.remember_var,
            fg_color=COLOR_ACCENT, hover_color="#26B79A",
            checkmark_color=COLOR_BG,
            text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=max(9, self._px(11))),
        ).pack(anchor="w", pady=(0, self._px(8)), padx=pad_x)

        forgot_row = ctk.CTkFrame(card, fg_color="transparent")
        forgot_row.pack(fill="x", padx=pad_x)
        ctk.CTkButton(
            forgot_row, text="Forgot password?",
            fg_color="transparent", hover=False,
            text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=max(9, self._px(11)), underline=True),
            anchor="e", width=20, command=self._go_to_forgot_password,
        ).pack(side="right")

        self.error_label = ctk.CTkLabel(
            card, text="", text_color="#FF8A80",
            font=ctk.CTkFont(size=max(9, self._px(11))),
        )
        self.error_label.pack(pady=(0, self._px(6)))

        # Login button
        ctk.CTkButton(
            card, text="Log In", height=max(32, self._px(40)),
            corner_radius=self._px(10), fg_color=COLOR_ACCENT,
            hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=max(11, self._px(14)), weight="bold"),
            command=self._handle_login,
        ).pack(fill="x", pady=(self._px(14), self._px(10)), padx=pad_x)

        # Face ID login button
        ctk.CTkButton(
            card, text="🧬  Log in with Face ID", height=max(28, self._px(36)),
            corner_radius=self._px(10), fg_color="transparent",
            border_width=1, border_color=COLOR_TRACK, hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=max(10, self._px(12))),
            command=self._go_to_face_login,
        ).pack(fill="x", pady=(0, self._px(10)), padx=pad_x)

        # Sign-up row
        signup_row = ctk.CTkFrame(card, fg_color="transparent")
        signup_row.pack(pady=(self._px(6), 0))
        ctk.CTkLabel(
            signup_row, text="New here?",
            font=ctk.CTkFont(size=label_size), text_color=COLOR_ACCENT_SOFT,
        ).pack(side="left")
        ctk.CTkButton(
            signup_row, text="Create an account",
            fg_color="transparent", hover=False,
            text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=label_size, underline=True),
            width=20, command=self._go_to_signup,
        ).pack(side="left", padx=4)

        # Enter key submits the form
        self.bind("<Return>", lambda _e: self._handle_login())

    def _draw_logo(self, canvas, size):
        """Small medical-cross-in-a-ring mark, drawn on canvas so no
        external image file is required. Scales with `size`."""
        cx, cy = size / 2, size / 2
        r = size * (34 / 90)  # proportions from the original 90px design
        u = size / 90         # unit scale relative to the original design

        canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                            outline=COLOR_ACCENT, width=max(2, round(3 * self.scale)))
        bar_w, bar_l = 8 * u, 26 * u
        canvas.create_rectangle(cx - bar_w / 2, cy - bar_l / 2,
                                 cx + bar_w / 2, cy + bar_l / 2,
                                 fill=COLOR_WHITE, outline="")
        canvas.create_rectangle(cx - bar_l / 2, cy - bar_w / 2,
                                 cx + bar_l / 2, cy + bar_w / 2,
                                 fill=COLOR_WHITE, outline="")

    # ---------------------------------------------------------------- logic
    def _toggle_password_visibility(self):
        if self.password_entry.cget("show") == "":
            self.password_entry.configure(show="•")
            self.password_toggle_btn.configure(text="👁")
        else:
            self.password_entry.configure(show="")
            self.password_toggle_btn.configure(text="🙈")

    def _handle_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()

        if not email or not password:
            self.error_label.configure(text="Please enter both email and password.")
            return

        self.error_label.configure(text_color="#FF8A80", text="")

        # Admin accounts share this same form and are checked first — the
        # `admins` table is completely separate from `users`, so this is
        # purely a routing decision and never touches the users query
        # below unless the email isn't a registered admin.
        try:
            admin = database.get_admin_by_email(email)
        except mysql.connector.Error as db_err:
            self.error_label.configure(text=f"Database error: {db_err}")
            return

        if admin and database.verify_password(password, admin["password_hash"]):
            self._open_admin_dashboard(admin)
            return

        try:
            user = database.get_user_by_email(email)
        except mysql.connector.Error as db_err:
            self.error_label.configure(text=f"Database error: {db_err}")
            return

        if not user or not database.verify_password(password, user["password_hash"]):
            self.error_label.configure(text="Invalid email or password.")
            return

        session.set_current_user(user)

        # Remember me: persist a token (email + expiry only, never the
        # password) so app.py can skip straight to the dashboard on the
        # next launch. Unchecked clears any previously remembered login.
        if self.remember_var.get():
            session.remember_login(email)
        else:
            session.forget_remembered_login()

        from dashboard import DashboardPage
        self.destroy()
        full_user_data = {k: v for k, v in user.items() if k != "password_hash"}
        DashboardPage(user_data=full_user_data).mainloop()

    def _open_admin_dashboard(self, admin: dict):
        from admin_dashboard import AdminDashboard
        self.destroy()
        admin_data = {k: v for k, v in admin.items() if k != "password_hash"}
        AdminDashboard(admin_data=admin_data).mainloop()

    def _go_to_signup(self):
        from registration_page import RegistrationPage
        self.destroy()
        RegistrationPage(on_success=_open_login_after_signup).mainloop()

    def _go_to_forgot_password(self):
        from forgot_password_page import ForgotPasswordPage
        self.destroy()
        ForgotPasswordPage(on_success=_open_login_after_signup).mainloop()

    def _go_to_face_login(self):
        from face_login_page import FaceLoginPage
        self.destroy()
        FaceLoginPage().mainloop()


def _open_login_after_signup(email: str = ""):
    """Called by RegistrationPage once a new account is created.
    Reopens the Login page with the email pre-filled."""
    login = LoginPage()
    if email:
        login.email_entry.insert(0, email)
        login.password_entry.focus()
    login.mainloop()


if __name__ == "__main__":
    app = LoginPage()
    app.mainloop()