"""
admin_dashboard.py
-------------------
AI Diet Chart & Nutrition Calculator — Admin Dashboard
Same healthcare-themed palette, fonts, and button styling as login_page.py.
Built with CustomTkinter. Left sidebar + main content area, with the
main area swapping between Dashboard / Users / AI Diet Records /
Meal History / Feedback / Admin Management panels without opening new
windows. "Logout" lives in the sidebar menu too, but — unlike the other
items — it doesn't swap the content area; it triggers the logout flow
directly.

The Admin Management panel lets a signed-in admin view, search, create,
edit, and delete other admin accounts (the built-in default admin —
database.DEFAULT_ADMIN_EMAIL — can be edited but never deleted, so
there's always at least one working admin login).

Data comes straight from the existing `diet_app` MySQL database via
database.get_connection() — no new tables required. If you'd rather
keep all SQL inside database.py (matching the rest of the app's
architecture), move the small helper functions near the top of this
file (marked "DB HELPERS") over there and import them instead.

Run:
    pip install customtkinter mysql-connector-python
    python admin_dashboard.py
"""

import re
from tkinter import messagebox

import customtkinter as ctk
import mysql.connector

import database

# ---------------------------------------------------------------------------
# Theme constants — identical to login_page.py
# ---------------------------------------------------------------------------
COLOR_BG = "#0E4B47"             # primary background (deep teal)
COLOR_ACCENT = "#2FD3B0"         # mint / medical teal accent
COLOR_ACCENT_SOFT = "#8FE3D1"    # softer mint for secondary text
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#155953"          # border / track color
COLOR_ENTRY_BG = "#0B3D3A"
COLOR_DANGER = "#FF8A80"
COLOR_SIDEBAR = "#0B3D3A"        # slightly darker panel for the sidebar

# Base/reference design size (proportions tuned at this size)
BASE_W, BASE_H = 1200, 750

MIN_W, MIN_H = 960, 620
MAX_W, MAX_H = 1500, 950

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# DB HELPERS — thin wrappers around database.get_connection(). Kept here so
# this file is a self-contained drop-in; feel free to relocate them into
# database.py alongside get_feedback()/get_average_rating() if you'd rather
# keep all SQL in the data layer.
#
# (Admin-account CRUD — get_all_admins / insert_admin / update_admin /
# delete_admin / admin_email_exists — already lives in database.py
# alongside the rest of the `admins` table logic, since it needs the same
# bcrypt hashing helper used for `users`.)
# ---------------------------------------------------------------------------

def _fetch_all_users(search: str = ""):
    conn = database.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        if search:
            cursor.execute(
                """
                SELECT id, full_name, email, phone, age, gender, activity_level,
                       fitness_goal, created_at
                FROM users
                WHERE full_name LIKE %s OR email LIKE %s
                ORDER BY created_at DESC
                """,
                (f"%{search}%", f"%{search}%"),
            )
        else:
            cursor.execute(
                """
                SELECT id, full_name, email, phone, age, gender, activity_level,
                       fitness_goal, created_at
                FROM users
                ORDER BY created_at DESC
                """
            )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def _fetch_all_feedback(limit: int = 100):
    conn = database.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT feedback.rating, feedback.comment, feedback.created_at,
                   users.full_name, users.email
            FROM feedback
            JOIN users ON users.email = feedback.email
            ORDER BY feedback.created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def _fetch_all_diet_plan_history(search: str = "", limit: int = 150):
    """All AI-generated diet plans across every user (most recent first),
    joined with the owning account's name/email. Powers the AI Diet
    Records page."""
    conn = database.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        if search:
            cursor.execute(
                """
                SELECT diet_plan_history.id, diet_plan_history.calorie_target,
                       diet_plan_history.created_at,
                       users.full_name, users.email
                FROM diet_plan_history
                JOIN users ON users.email = diet_plan_history.email
                WHERE users.full_name LIKE %s OR users.email LIKE %s
                ORDER BY diet_plan_history.created_at DESC
                LIMIT %s
                """,
                (f"%{search}%", f"%{search}%", limit),
            )
        else:
            cursor.execute(
                """
                SELECT diet_plan_history.id, diet_plan_history.calorie_target,
                       diet_plan_history.created_at,
                       users.full_name, users.email
                FROM diet_plan_history
                JOIN users ON users.email = diet_plan_history.email
                ORDER BY diet_plan_history.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def _fetch_all_meal_plans(search: str = "", limit: int = 200):
    """Every saved weekly meal-plan slot across every user (most recently
    updated first), joined with the owning account's name/email. Powers
    the Meal History page."""
    conn = database.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        if search:
            cursor.execute(
                """
                SELECT meal_plans.day_of_week, meal_plans.meal_type,
                       meal_plans.meal_description, meal_plans.updated_at,
                       users.full_name, users.email
                FROM meal_plans
                JOIN users ON users.email = meal_plans.email
                WHERE users.full_name LIKE %s OR users.email LIKE %s
                ORDER BY meal_plans.updated_at DESC
                LIMIT %s
                """,
                (f"%{search}%", f"%{search}%", limit),
            )
        else:
            cursor.execute(
                """
                SELECT meal_plans.day_of_week, meal_plans.meal_type,
                       meal_plans.meal_description, meal_plans.updated_at,
                       users.full_name, users.email
                FROM meal_plans
                JOIN users ON users.email = meal_plans.email
                ORDER BY meal_plans.updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def _fetch_overview_stats():
    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        (total_users,) = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) FROM feedback")
        (total_feedback,) = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) FROM diet_plan_history")
        (total_plans,) = cursor.fetchone()

        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= (NOW() - INTERVAL 7 DAY)"
        )
        (new_this_week,) = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    avg_rating, _ = database.get_average_rating()
    return {
        "total_users": total_users,
        "total_feedback": total_feedback,
        "total_plans": total_plans,
        "new_this_week": new_this_week,
        "avg_rating": avg_rating,
    }


def _delete_user_by_email(email: str):
    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email = %s", (email,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def _is_valid_admin_session(admin_data) -> bool:
    """Returns True only if `admin_data` is a dict with an `email` that
    still exists in the `admins` table right now. This is what gates
    access to the whole Admin Dashboard (see AdminDashboard.__init__ and
    show_page): a caller can't open the dashboard just by constructing
    it with an arbitrary dict, and a session already open in one window
    stops working the moment that admin account is deleted elsewhere. On
    a database error, fail closed (treat the session as invalid) rather
    than risk letting an unauthenticated caller in."""
    if not isinstance(admin_data, dict):
        return False
    email = admin_data.get("email")
    if not email:
        return False
    try:
        return database.get_admin_by_email(email) is not None
    except mysql.connector.Error:
        return False


# ---------------------------------------------------------------------------
class AdminFormDialog(ctk.CTkToplevel):
    """Modal used for both "Add Admin" and "Edit Admin". In edit mode,
    `existing_email` is the row being edited and the password field is
    optional (leave blank to keep the current password). `on_saved` is
    called with no arguments after a successful save so the caller can
    refresh its table."""

    def __init__(self, parent, scale, existing_admin: dict = None, on_saved=None):
        super().__init__(parent)
        self.parent_app = parent
        self.scale = scale
        self.existing_admin = existing_admin
        self.on_saved = on_saved
        self.is_edit = existing_admin is not None

        self.title("Edit Admin" if self.is_edit else "Add Admin")
        self.configure(fg_color=COLOR_BG)
        self.resizable(False, False)

        # Keep the dialog modal and on top of the dashboard window.
        self.transient(parent)
        self.grab_set()

        self._build_form()

        # Size the window to fit what was actually built (instead of a
        # guessed fixed height) so every field and button is always
        # visible, then clamp to the screen and center over the parent.
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        max_h = self.winfo_screenheight() - self._px(80)
        h = min(h, max_h)
        self._center_over_parent(w, h)

        self.after(50, lambda: self.name_entry.focus_set())

    def _px(self, value):
        return max(1, round(value * self.scale))

    def _center_over_parent(self, w, h):
        self.update_idletasks()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_form(self):
        pad = self._px(24)
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=pad, pady=pad)

        ctk.CTkLabel(
            wrapper, text="Edit Admin" if self.is_edit else "Add New Admin",
            anchor="w", font=ctk.CTkFont(size=max(15, self._px(16)), weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", pady=(0, self._px(4)))

        subtitle = (
            "Leave the password blank to keep it unchanged."
            if self.is_edit else
            "The new admin can log in immediately with these credentials."
        )
        ctk.CTkLabel(
            wrapper, text=subtitle, anchor="w",
            font=ctk.CTkFont(size=max(12, self._px(13))),
            text_color=COLOR_ACCENT_SOFT, wraplength=self._px(360),
        ).pack(anchor="w", pady=(0, self._px(16)))

        entry_h = max(30, self._px(36))

        ctk.CTkLabel(
            wrapper, text="Full Name", anchor="w",
            font=ctk.CTkFont(size=max(12, self._px(13))), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(
            wrapper, height=entry_h, corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            font=ctk.CTkFont(size=max(12, self._px(13))),
        )
        self.name_entry.pack(fill="x", pady=(self._px(4), self._px(12)))

        ctk.CTkLabel(
            wrapper, text="Email", anchor="w",
            font=ctk.CTkFont(size=max(12, self._px(13))), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")
        self.email_entry = ctk.CTkEntry(
            wrapper, height=entry_h, corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            font=ctk.CTkFont(size=max(12, self._px(13))),
        )
        self.email_entry.pack(fill="x", pady=(self._px(4), self._px(12)))

        pw_label_text = "New Password (optional)" if self.is_edit else "Password"
        ctk.CTkLabel(
            wrapper, text=pw_label_text, anchor="w",
            font=ctk.CTkFont(size=max(12, self._px(13))), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")
        self.password_entry = ctk.CTkEntry(
            wrapper, height=entry_h, corner_radius=self._px(10), show="•",
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            font=ctk.CTkFont(size=max(12, self._px(13))),
        )
        self.password_entry.pack(fill="x", pady=(self._px(4), self._px(12)))

        confirm_label_text = "Confirm New Password" if self.is_edit else "Confirm Password"
        ctk.CTkLabel(
            wrapper, text=confirm_label_text, anchor="w",
            font=ctk.CTkFont(size=max(12, self._px(13))), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")
        self.confirm_password_entry = ctk.CTkEntry(
            wrapper, height=entry_h, corner_radius=self._px(10), show="•",
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            font=ctk.CTkFont(size=max(12, self._px(13))),
        )
        self.confirm_password_entry.pack(fill="x", pady=(self._px(4), self._px(4)))

        self.error_label = ctk.CTkLabel(
            wrapper, text="", anchor="w", text_color=COLOR_DANGER,
            font=ctk.CTkFont(size=max(12, self._px(13))), wraplength=self._px(360),
        )
        self.error_label.pack(anchor="w", pady=(self._px(4), self._px(8)))

        if self.is_edit:
            self.name_entry.insert(0, self.existing_admin.get("full_name", ""))
            self.email_entry.insert(0, self.existing_admin.get("email", ""))

        btn_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        btn_row.pack(fill="x", pady=(self._px(8), 0))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="Cancel", height=max(30, self._px(38)),
            corner_radius=self._px(10), fg_color="transparent",
            border_width=1, border_color=COLOR_TRACK, hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=max(12, self._px(13))),
            command=self.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, self._px(8)))

        ctk.CTkButton(
            btn_row, text="Save Changes" if self.is_edit else "Create Admin",
            height=max(30, self._px(38)), corner_radius=self._px(10),
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=max(12, self._px(13)), weight="bold"),
            command=self._save,
        ).grid(row=0, column=1, sticky="ew", padx=(self._px(8), 0))

    def _save(self):
        full_name = self.name_entry.get().strip()
        email = self.email_entry.get().strip().lower()
        password = self.password_entry.get()
        confirm_password = self.confirm_password_entry.get()

        if not full_name:
            self.error_label.configure(text="Full name is required.")
            return
        if not EMAIL_PATTERN.match(email):
            self.error_label.configure(text="Enter a valid email address.")
            return
        if not self.is_edit and len(password) < 8:
            self.error_label.configure(text="Password must be at least 8 characters.")
            return
        if self.is_edit and password and len(password) < 8:
            self.error_label.configure(text="New password must be at least 8 characters.")
            return
        if (not self.is_edit or password) and password != confirm_password:
            self.error_label.configure(text="Passwords don't match.")
            return

        try:
            if self.is_edit:
                database.update_admin(
                    original_email=self.existing_admin["email"],
                    full_name=full_name,
                    new_email=email,
                    new_password=password or None,
                )
            else:
                database.insert_admin(full_name, email, password)
        except ValueError as err:
            self.error_label.configure(text=str(err))
            return
        except mysql.connector.Error as db_err:
            self.error_label.configure(text=f"Database error: {db_err}")
            return

        if self.on_saved:
            self.on_saved()
        self.destroy()


# ---------------------------------------------------------------------------
class AdminDashboard(ctk.CTk):

    # (key, icon, label, is_action) — items with is_action=True don't get a
    # content page and don't get highlighted as "active"; their command
    # fires immediately instead of swapping the main area (currently only
    # Logout).
    NAV_ITEMS = [
        ("overview", "📊", "Dashboard", False),
        ("users", "👥", "Users", False),
        ("ai_diet_records", "🍽", "AI Diet Records", False),
        ("meal_history", "📅", "Meal History", False),
        ("feedback", "⭐", "Feedback", False),
        ("admin_management", "🛠", "Admin Management", False),
        ("logout", "⎋", "Logout", True),
    ]

    def __init__(self, admin_data: dict = None):
        super().__init__()

        if not _is_valid_admin_session(admin_data):
            # Let the window construction finish normally (CustomTkinter
            # defers some of its own setup via internal after() calls —
            # withdrawing before that runs can leave the window stuck
            # invisible even after a later deiconify()), then bounce to
            # the Login Page on the next idle tick instead.
            self.after(10, self._deny_access)
            return

        self.admin_data = admin_data
        self.active_page = "overview"
        self.nav_buttons = {}

        # ---- responsive sizing ---------------------------------------
        self.win_w, self.win_h = self._compute_responsive_size()
        self.scale = self.win_w / BASE_W

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Admin Dashboard")
        self.configure(fg_color=COLOR_BG)
        # Start centered at the computed responsive size (used purely as a
        # fallback / pre-maximize geometry — see _maximize_window below,
        # which takes over once the window is fully built).
        self._center_window(self.win_w, self.win_h)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_main_area()
        # Skip re-verifying here — we just verified above, and re-checking
        # from inside our own constructor (before mainloop() has even been
        # called on this window) risks starting a nested mainloop mid-
        # construction if it ever needed to redirect. Later, user-driven
        # navigation clicks go through the normal post-startup check.
        self.show_page("overview", _verify_session=False)

        # Deferred, not called directly: CustomTkinter schedules some of
        # its own window/DPI setup via internal after() calls right after
        # the window is created, and that runs *after* this __init__
        # returns — maximizing immediately here would get silently
        # overwritten back to a small centered window once that later
        # setup runs. Queuing it with after() instead lets it apply after
        # that setup has settled (same approach as dashboard.py).
        self.after(10, self._maximize_window)

    # ------------------------------------------------------------ window state
    def _maximize_window(self):
        """Opens the admin dashboard filling the screen instead of a
        smaller centered window. `state('zoomed')` is the normal way to
        do this on Windows and most Linux window managers; macOS's Tk
        build doesn't support that state string and raises a TclError,
        so it falls back to `-zoomed` (some Linux WMs use this attribute
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

    # ------------------------------------------------------------ access control
    def _deny_access(self):
        """Bounces an unauthorized/expired session straight to the Login
        Page. Called either right at startup (invalid admin_data was
        passed in) or from show_page() if the logged-in admin account no
        longer exists (e.g. another admin deleted it mid-session)."""
        messagebox.showerror(
            "Access denied",
            "You must be logged in as an admin to view this page. "
            "Please log in again.",
        )
        self.destroy()
        from login_page import LoginPage
        LoginPage().mainloop()

    # ------------------------------------------------------------ sizing
    def _compute_responsive_size(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        target_w = sw * 0.78
        target_h = sh * 0.82

        aspect = BASE_H / BASE_W
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

    def _px(self, value):
        return max(1, round(value * self.scale))

    # ------------------------------------------------------------ sidebar
    def _build_sidebar(self):
        sidebar_w = self._px(230)
        sidebar = ctk.CTkFrame(
            self, width=sidebar_w, corner_radius=0, fg_color=COLOR_SIDEBAR,
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(len(self.NAV_ITEMS) + 2, weight=1)

        # Logo + title row
        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.pack(fill="x", pady=(self._px(24), self._px(20)), padx=self._px(20))

        logo_size = self._px(40)
        logo_canvas = ctk.CTkCanvas(
            header, width=logo_size, height=logo_size, bg=COLOR_SIDEBAR, highlightthickness=0
        )
        logo_canvas.pack(side="left")
        self._draw_logo(logo_canvas, logo_size)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=(self._px(10), 0))
        ctk.CTkLabel(
            title_box, text="NutriAI", anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=max(16, self._px(18)), weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box, text="Admin Panel", anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=max(11, self._px(12))),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")

        ctk.CTkFrame(sidebar, height=1, fg_color=COLOR_TRACK).pack(fill="x", padx=self._px(20))

        # Nav buttons — one per NAV_ITEMS entry, including Logout. Regular
        # items swap the main content area; action items (Logout) fire
        # their command straight away and are visually separated with a
        # divider above them.
        nav_font = ctk.CTkFont(family="Segoe UI", size=max(13, self._px(14)))
        for key, icon, label, is_action in self.NAV_ITEMS:
            if is_action:
                ctk.CTkFrame(sidebar, height=1, fg_color=COLOR_TRACK).pack(
                    fill="x", padx=self._px(20), pady=(self._px(10), 0)
                )
                btn = ctk.CTkButton(
                    sidebar, text=f"  {icon}   {label}", anchor="w",
                    height=max(34, self._px(42)), corner_radius=self._px(10),
                    fg_color="transparent", hover_color=COLOR_TRACK,
                    text_color=COLOR_DANGER, font=nav_font,
                    command=self._handle_logout,
                )
            else:
                btn = ctk.CTkButton(
                    sidebar, text=f"  {icon}   {label}", anchor="w",
                    height=max(34, self._px(42)), corner_radius=self._px(10),
                    fg_color="transparent", hover_color=COLOR_TRACK,
                    text_color=COLOR_ACCENT_SOFT, font=nav_font,
                    command=lambda k=key: self.show_page(k),
                )
            btn.pack(fill="x", padx=self._px(14), pady=(self._px(14), 0))
            self.nav_buttons[key] = btn

        # Spacer + footer (admin chip)
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        ctk.CTkFrame(sidebar, height=1, fg_color=COLOR_TRACK).pack(fill="x", padx=self._px(20))

        admin_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        admin_row.pack(fill="x", padx=self._px(20), pady=(self._px(14), self._px(18)))

        avatar = ctk.CTkLabel(
            admin_row, text=self._initials(self.admin_data.get("full_name", "Admin")),
            width=self._px(34), height=self._px(34), corner_radius=self._px(17),
            fg_color=COLOR_ACCENT, text_color="#0B3D3A",
            font=ctk.CTkFont(size=max(12, self._px(13)), weight="bold"),
        )
        avatar.pack(side="left")

        name_box = ctk.CTkFrame(admin_row, fg_color="transparent")
        name_box.pack(side="left", padx=(self._px(8), 0))
        ctk.CTkLabel(
            name_box, text=self.admin_data.get("full_name", "Admin"), anchor="w",
            font=ctk.CTkFont(size=max(12, self._px(13)), weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            name_box, text="Administrator", anchor="w",
            font=ctk.CTkFont(size=max(10, self._px(11))),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")

    def _draw_logo(self, canvas, size):
        """Same medical-cross-in-a-ring mark as login_page.py, scaled down."""
        cx, cy = size / 2, size / 2
        r = size * (34 / 90)
        u = size / 90

        canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                            outline=COLOR_ACCENT, width=max(2, round(2 * self.scale)))
        bar_w, bar_l = 8 * u, 26 * u
        canvas.create_rectangle(cx - bar_w / 2, cy - bar_l / 2,
                                 cx + bar_w / 2, cy + bar_l / 2,
                                 fill=COLOR_WHITE, outline="")
        canvas.create_rectangle(cx - bar_l / 2, cy - bar_w / 2,
                                 cx + bar_l / 2, cy + bar_w / 2,
                                 fill=COLOR_WHITE, outline="")

    @staticmethod
    def _initials(name: str) -> str:
        parts = [p for p in name.strip().split() if p]
        if not parts:
            return "A"
        if len(parts) == 1:
            return parts[0][0].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    # ------------------------------------------------------------ main area
    def _build_main_area(self):
        main = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # Header bar
        self.header = ctk.CTkFrame(main, fg_color="transparent", height=self._px(60))
        self.header.grid(row=0, column=0, sticky="ew", padx=self._px(28), pady=(self._px(22), self._px(6)))
        self.header.grid_columnconfigure(0, weight=1)

        self.page_title_label = ctk.CTkLabel(
            self.header, text="Dashboard", anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=max(18, self._px(22)), weight="bold"),
            text_color=COLOR_WHITE,
        )
        self.page_title_label.grid(row=0, column=0, sticky="w")

        self.page_subtitle_label = ctk.CTkLabel(
            self.header, text="A quick look at how the app is being used", anchor="w",
            font=ctk.CTkFont(size=max(11, self._px(12))),
            text_color=COLOR_ACCENT_SOFT,
        )
        self.page_subtitle_label.grid(row=1, column=0, sticky="w")

        # Content container — pages are swapped inside here
        self.content_container = ctk.CTkFrame(main, fg_color="transparent")
        self.content_container.grid(row=1, column=0, sticky="nsew", padx=self._px(28), pady=(self._px(6), self._px(20)))
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        # Only build a content frame for real pages — Logout is an action
        # item and never gets its own page.
        self.pages = {}
        for key, _icon, _label, is_action in self.NAV_ITEMS:
            if is_action:
                continue
            frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
            frame.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = frame

    # ------------------------------------------------------------ navigation
    def show_page(self, key: str, _verify_session: bool = True):
        if key not in self.pages:
            # Defensive: action items (Logout) are wired straight to their
            # own command and should never reach show_page, but if they
            # ever do, don't try to render a page that doesn't exist.
            return

        if _verify_session and not _is_valid_admin_session(self.admin_data):
            # The session that got us into this window is no longer
            # valid (e.g. this admin account was deleted from another
            # window) — every page is gated the same way, so bounce out
            # instead of rendering data for a session that no longer
            # exists.
            self._deny_access()
            return

        self.active_page = key
        titles = {
            "overview": ("Dashboard", "A quick look at how the app is being used"),
            "users": ("Users", "View, search, and remove registered accounts"),
            "ai_diet_records": ("AI Diet Records", "Every AI-generated diet plan, across all users"),
            "meal_history": ("Meal History", "Saved weekly meal-plan slots, across all users"),
            "feedback": ("Feedback", "What users are saying, most recent first"),
            "admin_management": ("Admin Management", "View, add, edit, search, and remove admin accounts"),
        }
        title, subtitle = titles[key]
        self.page_title_label.configure(text=title)
        self.page_subtitle_label.configure(text=subtitle)

        for nav_key, btn in self.nav_buttons.items():
            if nav_key == "logout":
                continue  # Logout keeps its own danger styling, never "active"
            if nav_key == key:
                btn.configure(fg_color=COLOR_TRACK, text_color=COLOR_WHITE)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_ACCENT_SOFT)

        # Rebuild the page fresh each time so it always shows current data
        for widget in self.pages[key].winfo_children():
            widget.destroy()

        builders = {
            "overview": self._build_overview_page,
            "users": self._build_users_page,
            "ai_diet_records": self._build_ai_diet_records_page,
            "meal_history": self._build_meal_history_page,
            "feedback": self._build_feedback_page,
            "admin_management": self._build_admin_management_page,
        }
        builders[key](self.pages[key])
        self.pages[key].tkraise()

    # ------------------------------------------------------------ Overview page
    def _build_overview_page(self, parent):
        try:
            stats = _fetch_overview_stats()
        except mysql.connector.Error as db_err:
            self._show_db_error(parent, db_err)
            return

        cards_row = ctk.CTkFrame(parent, fg_color="transparent")
        cards_row.pack(fill="x")
        for i in range(4):
            cards_row.grid_columnconfigure(i, weight=1, uniform="cards")

        avg_rating = stats["avg_rating"]
        avg_rating_text = f"{avg_rating:.1f} ★" if avg_rating is not None else "—"

        card_data = [
            ("Total Users", str(stats["total_users"]), "👥"),
            ("New This Week", str(stats["new_this_week"]), "🆕"),
            ("AI Plans Generated", str(stats["total_plans"]), "🍽"),
            ("Avg. Feedback Rating", avg_rating_text, "⭐"),
        ]
        for i, (label, value, icon) in enumerate(card_data):
            self._stat_card(cards_row, label, value, icon).grid(
                row=0, column=i, sticky="nsew", padx=(0 if i == 0 else self._px(12), 0)
            )

        # Recent users preview
        recent_box = ctk.CTkFrame(parent, fg_color=COLOR_ENTRY_BG, corner_radius=self._px(14))
        recent_box.pack(fill="both", expand=True, pady=(self._px(20), 0))

        header_row = ctk.CTkFrame(recent_box, fg_color="transparent")
        header_row.pack(fill="x", padx=self._px(18), pady=(self._px(16), self._px(6)))
        ctk.CTkLabel(
            header_row, text="Recently Registered Users", anchor="w",
            font=ctk.CTkFont(size=max(14, self._px(15)), weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(side="left")
        ctk.CTkButton(
            header_row, text="View all →", fg_color="transparent", hover=False,
            text_color=COLOR_ACCENT, font=ctk.CTkFont(size=max(11, self._px(12)), underline=True),
            width=20, command=lambda: self.show_page("users"),
        ).pack(side="right")

        try:
            recent_users = _fetch_all_users()[:6]
        except mysql.connector.Error as db_err:
            self._show_db_error(recent_box, db_err)
            return

        table_area = ctk.CTkFrame(recent_box, fg_color="transparent")
        table_area.pack(fill="both", expand=True, padx=self._px(18), pady=(0, self._px(16)))
        self._build_table(
            table_area,
            columns=[("Name", 3), ("Email", 4), ("Goal", 2), ("Joined", 2)],
            rows=[
                [u["full_name"], u["email"], u["fitness_goal"], self._fmt_date(u["created_at"])]
                for u in recent_users
            ],
        )

    def _stat_card(self, parent, label, value, icon):
        card = ctk.CTkFrame(parent, fg_color=COLOR_ENTRY_BG, corner_radius=self._px(14))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=self._px(16), pady=self._px(14))

        ctk.CTkLabel(
            inner, text=icon, font=ctk.CTkFont(size=max(14, self._px(18))),
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner, text=value, anchor="w",
            font=ctk.CTkFont(size=max(18, self._px(22)), weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", pady=(self._px(6), 0))
        ctk.CTkLabel(
            inner, text=label, anchor="w",
            font=ctk.CTkFont(size=max(12, self._px(13))),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")
        return card

    # ------------------------------------------------------------ Users page
    def _build_users_page(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Search row
        search_row = ctk.CTkFrame(parent, fg_color="transparent")
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, self._px(12)))
        search_row.grid_columnconfigure(0, weight=1)

        self.user_search_entry = ctk.CTkEntry(
            search_row, placeholder_text="Search by name or email…",
            height=max(30, self._px(36)), corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            font=ctk.CTkFont(size=max(12, self._px(13))),
        )
        self.user_search_entry.grid(row=0, column=0, sticky="ew", padx=(0, self._px(10)))
        self.user_search_entry.bind("<Return>", lambda _e: self._refresh_users_table())

        ctk.CTkButton(
            search_row, text="Search", width=self._px(90), height=max(30, self._px(36)),
            corner_radius=self._px(10), fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=max(12, self._px(13)), weight="bold"),
            command=self._refresh_users_table,
        ).grid(row=0, column=1)

        box = ctk.CTkFrame(parent, fg_color=COLOR_ENTRY_BG, corner_radius=self._px(14))
        box.grid(row=1, column=0, sticky="nsew")
        self.users_table_area = ctk.CTkFrame(box, fg_color="transparent")
        self.users_table_area.pack(fill="both", expand=True, padx=self._px(16), pady=self._px(16))

        self._refresh_users_table()

    def _refresh_users_table(self):
        for widget in self.users_table_area.winfo_children():
            widget.destroy()

        search = self.user_search_entry.get().strip()
        try:
            users = _fetch_all_users(search)
        except mysql.connector.Error as db_err:
            self._show_db_error(self.users_table_area, db_err)
            return

        if not users:
            ctk.CTkLabel(
                self.users_table_area, text="No matching users found.",
                text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=max(12, self._px(13))),
            ).pack(pady=self._px(20))
            return

        self._build_table(
            self.users_table_area,
            columns=[("Name", 3), ("Email", 4), ("Age", 1), ("Goal", 2), ("Joined", 2), ("", 1)],
            rows=[
                [
                    u["full_name"], u["email"], str(u["age"]), u["fitness_goal"],
                    self._fmt_date(u["created_at"]),
                    ("Delete", lambda email=u["email"], name=u["full_name"]: self._confirm_delete_user(email, name)),
                ]
                for u in users
            ],
            scrollable=True,
        )

    def _confirm_delete_user(self, email: str, name: str):
        confirmed = messagebox.askyesno(
            "Delete account",
            f"Permanently delete {name}'s account ({email})?\n\n"
            "This removes all of their logs, plans, and history and cannot be undone.",
        )
        if not confirmed:
            return
        try:
            _delete_user_by_email(email)
        except mysql.connector.Error as db_err:
            messagebox.showerror("Database error", str(db_err))
            return
        self._refresh_users_table()

    # ------------------------------------------------------------ AI Diet Records page
    def _build_ai_diet_records_page(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        search_row = ctk.CTkFrame(parent, fg_color="transparent")
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, self._px(12)))
        search_row.grid_columnconfigure(0, weight=1)

        self.diet_records_search_entry = ctk.CTkEntry(
            search_row, placeholder_text="Search by name or email…",
            height=max(30, self._px(36)), corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            font=ctk.CTkFont(size=max(12, self._px(13))),
        )
        self.diet_records_search_entry.grid(row=0, column=0, sticky="ew", padx=(0, self._px(10)))
        self.diet_records_search_entry.bind("<Return>", lambda _e: self._refresh_diet_records_table())

        ctk.CTkButton(
            search_row, text="Search", width=self._px(90), height=max(30, self._px(36)),
            corner_radius=self._px(10), fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=max(12, self._px(13)), weight="bold"),
            command=self._refresh_diet_records_table,
        ).grid(row=0, column=1)

        box = ctk.CTkFrame(parent, fg_color=COLOR_ENTRY_BG, corner_radius=self._px(14))
        box.grid(row=1, column=0, sticky="nsew")
        self.diet_records_table_area = ctk.CTkFrame(box, fg_color="transparent")
        self.diet_records_table_area.pack(fill="both", expand=True, padx=self._px(16), pady=self._px(16))

        self._refresh_diet_records_table()

    def _refresh_diet_records_table(self):
        for widget in self.diet_records_table_area.winfo_children():
            widget.destroy()

        search = self.diet_records_search_entry.get().strip()
        try:
            records = _fetch_all_diet_plan_history(search)
        except mysql.connector.Error as db_err:
            self._show_db_error(self.diet_records_table_area, db_err)
            return

        if not records:
            ctk.CTkLabel(
                self.diet_records_table_area, text="No AI diet plans have been generated yet.",
                text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=max(12, self._px(13))),
            ).pack(pady=self._px(20))
            return

        self._build_table(
            self.diet_records_table_area,
            columns=[("User", 3), ("Email", 4), ("Calorie Target", 2), ("Generated", 2)],
            rows=[
                [
                    r["full_name"], r["email"],
                    f'{r["calorie_target"]} kcal' if r["calorie_target"] else "—",
                    self._fmt_date(r["created_at"]),
                ]
                for r in records
            ],
            scrollable=True,
        )

    # ------------------------------------------------------------ Meal History page
    def _build_meal_history_page(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        search_row = ctk.CTkFrame(parent, fg_color="transparent")
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, self._px(12)))
        search_row.grid_columnconfigure(0, weight=1)

        self.meal_history_search_entry = ctk.CTkEntry(
            search_row, placeholder_text="Search by name or email…",
            height=max(30, self._px(36)), corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            font=ctk.CTkFont(size=max(12, self._px(13))),
        )
        self.meal_history_search_entry.grid(row=0, column=0, sticky="ew", padx=(0, self._px(10)))
        self.meal_history_search_entry.bind("<Return>", lambda _e: self._refresh_meal_history_table())

        ctk.CTkButton(
            search_row, text="Search", width=self._px(90), height=max(30, self._px(36)),
            corner_radius=self._px(10), fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=max(12, self._px(13)), weight="bold"),
            command=self._refresh_meal_history_table,
        ).grid(row=0, column=1)

        box = ctk.CTkFrame(parent, fg_color=COLOR_ENTRY_BG, corner_radius=self._px(14))
        box.grid(row=1, column=0, sticky="nsew")
        self.meal_history_table_area = ctk.CTkFrame(box, fg_color="transparent")
        self.meal_history_table_area.pack(fill="both", expand=True, padx=self._px(16), pady=self._px(16))

        self._refresh_meal_history_table()

    def _refresh_meal_history_table(self):
        for widget in self.meal_history_table_area.winfo_children():
            widget.destroy()

        search = self.meal_history_search_entry.get().strip()
        try:
            slots = _fetch_all_meal_plans(search)
        except mysql.connector.Error as db_err:
            self._show_db_error(self.meal_history_table_area, db_err)
            return

        if not slots:
            ctk.CTkLabel(
                self.meal_history_table_area, text="No meal plans have been saved yet.",
                text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=max(12, self._px(13))),
            ).pack(pady=self._px(20))
            return

        self._build_table(
            self.meal_history_table_area,
            columns=[("User", 2), ("Day", 1), ("Meal", 1), ("Description", 4), ("Updated", 2)],
            rows=[
                [
                    s["full_name"], s["day_of_week"], s["meal_type"],
                    s["meal_description"], self._fmt_date(s["updated_at"]),
                ]
                for s in slots
            ],
            scrollable=True,
        )

    # ------------------------------------------------------------ Feedback page
    def _build_feedback_page(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        try:
            feedback_rows = _fetch_all_feedback()
        except mysql.connector.Error as db_err:
            self._show_db_error(parent, db_err)
            return

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        if not feedback_rows:
            ctk.CTkLabel(
                scroll, text="No feedback submitted yet.",
                text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=max(12, self._px(13))),
            ).pack(pady=self._px(20))
            return

        for row in feedback_rows:
            card = ctk.CTkFrame(scroll, fg_color=COLOR_ENTRY_BG, corner_radius=self._px(12))
            card.pack(fill="x", pady=(0, self._px(10)))

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=self._px(16), pady=(self._px(12), self._px(4)))

            ctk.CTkLabel(
                top, text="★" * row["rating"] + "☆" * (5 - row["rating"]),
                text_color=COLOR_ACCENT, font=ctk.CTkFont(size=max(13, self._px(15))),
            ).pack(side="left")
            ctk.CTkLabel(
                top, text=f'{row["full_name"]}  ·  {row["email"]}',
                text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=max(11, self._px(12))),
            ).pack(side="left", padx=(self._px(10), 0))
            ctk.CTkLabel(
                top, text=self._fmt_date(row["created_at"]),
                text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=max(11, self._px(12))),
            ).pack(side="right")

            if row["comment"]:
                ctk.CTkLabel(
                    card, text=row["comment"], anchor="w", justify="left", wraplength=self._px(900),
                    text_color=COLOR_WHITE, font=ctk.CTkFont(size=max(12, self._px(13))),
                ).pack(fill="x", padx=self._px(16), pady=(0, self._px(12)))
            else:
                ctk.CTkFrame(card, height=self._px(6), fg_color="transparent").pack()

    # ------------------------------------------------------------ Admin Management page
    def _build_admin_management_page(self, parent):
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # "Signed in as" strip — small reminder of who's currently logged in
        signed_in_row = ctk.CTkFrame(parent, fg_color=COLOR_ENTRY_BG, corner_radius=self._px(12))
        signed_in_row.grid(row=0, column=0, sticky="ew", pady=(0, self._px(14)))
        inner = ctk.CTkFrame(signed_in_row, fg_color="transparent")
        inner.pack(fill="x", padx=self._px(18), pady=self._px(12))
        ctk.CTkLabel(
            inner, text=f'Signed in as {self.admin_data.get("full_name", "Admin")}  ·  '
                        f'{self.admin_data.get("email", "")}',
            anchor="w", font=ctk.CTkFont(size=max(11, self._px(12))),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")

        # Search + Add Admin row
        search_row = ctk.CTkFrame(parent, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", pady=(0, self._px(12)))
        search_row.grid_columnconfigure(0, weight=1)

        self.admin_search_entry = ctk.CTkEntry(
            search_row, placeholder_text="Search admins by name or email…",
            height=max(30, self._px(36)), corner_radius=self._px(10),
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
            font=ctk.CTkFont(size=max(12, self._px(13))),
        )
        self.admin_search_entry.grid(row=0, column=0, sticky="ew", padx=(0, self._px(10)))
        self.admin_search_entry.bind("<Return>", lambda _e: self._refresh_admin_management_table())

        ctk.CTkButton(
            search_row, text="Search", width=self._px(90), height=max(30, self._px(36)),
            corner_radius=self._px(10), fg_color="transparent",
            border_width=1, border_color=COLOR_ACCENT, hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT, font=ctk.CTkFont(size=max(12, self._px(13)), weight="bold"),
            command=self._refresh_admin_management_table,
        ).grid(row=0, column=1, padx=(0, self._px(10)))

        ctk.CTkButton(
            search_row, text="+ Add Admin", width=self._px(130), height=max(30, self._px(36)),
            corner_radius=self._px(10), fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=max(12, self._px(13)), weight="bold"),
            command=lambda: self._open_admin_dialog(existing_admin=None),
        ).grid(row=0, column=2)

        box = ctk.CTkFrame(parent, fg_color=COLOR_ENTRY_BG, corner_radius=self._px(14))
        box.grid(row=2, column=0, sticky="nsew")
        self.admin_mgmt_table_area = ctk.CTkFrame(box, fg_color="transparent")
        self.admin_mgmt_table_area.pack(fill="both", expand=True, padx=self._px(16), pady=self._px(16))

        self._refresh_admin_management_table()

    def _refresh_admin_management_table(self):
        for widget in self.admin_mgmt_table_area.winfo_children():
            widget.destroy()

        search = self.admin_search_entry.get().strip()
        try:
            admins = database.get_all_admins(search)
        except mysql.connector.Error as db_err:
            self._show_db_error(self.admin_mgmt_table_area, db_err)
            return

        if not admins:
            ctk.CTkLabel(
                self.admin_mgmt_table_area, text="No matching admins found.",
                text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=max(12, self._px(13))),
            ).pack(pady=self._px(20))
            return

        columns = [("Name", 3), ("Email", 4), ("Created", 2), ("", 3)]
        container = ctk.CTkScrollableFrame(self.admin_mgmt_table_area, fg_color="transparent")
        container.pack(fill="both", expand=True)
        for i, (_label, weight) in enumerate(columns):
            container.grid_columnconfigure(i, weight=weight)

        header_font = ctk.CTkFont(size=max(11, self._px(12)), weight="bold")
        for col, (label, _weight) in enumerate(columns):
            ctk.CTkLabel(
                container, text=label, anchor="w", text_color=COLOR_ACCENT_SOFT, font=header_font,
            ).grid(row=0, column=col, sticky="ew", padx=(0, self._px(8)), pady=(0, self._px(8)))

        row_font = ctk.CTkFont(size=max(12, self._px(13)))
        for r, admin in enumerate(admins, start=1):
            row_bg = COLOR_BG if r % 2 == 0 else "transparent"
            is_default = admin["email"] == database.DEFAULT_ADMIN_EMAIL

            name_text = admin["full_name"] + ("  (default)" if is_default else "")
            ctk.CTkLabel(
                container, text=name_text, anchor="w", text_color=COLOR_WHITE,
                font=row_font, fg_color=row_bg,
            ).grid(row=r, column=0, sticky="ew", padx=(0, self._px(8)), pady=self._px(4))
            ctk.CTkLabel(
                container, text=admin["email"], anchor="w", text_color=COLOR_WHITE,
                font=row_font, fg_color=row_bg,
            ).grid(row=r, column=1, sticky="ew", padx=(0, self._px(8)), pady=self._px(4))
            ctk.CTkLabel(
                container, text=self._fmt_date(admin["created_at"]), anchor="w", text_color=COLOR_WHITE,
                font=row_font, fg_color=row_bg,
            ).grid(row=r, column=2, sticky="ew", padx=(0, self._px(8)), pady=self._px(4))

            actions = ctk.CTkFrame(container, fg_color=row_bg)
            actions.grid(row=r, column=3, sticky="w", padx=(0, self._px(8)), pady=self._px(4))

            ctk.CTkButton(
                actions, text="Edit", width=self._px(60), height=self._px(26),
                corner_radius=self._px(8), fg_color="transparent",
                border_width=1, border_color=COLOR_ACCENT, hover_color=COLOR_TRACK,
                text_color=COLOR_ACCENT, font=ctk.CTkFont(size=max(11, self._px(12))),
                command=lambda a=admin: self._open_admin_dialog(existing_admin=a),
            ).pack(side="left", padx=(0, self._px(6)))

            delete_btn = ctk.CTkButton(
                actions, text="Delete", width=self._px(60), height=self._px(26),
                corner_radius=self._px(8), fg_color="transparent",
                border_width=1, border_color=COLOR_DANGER, hover_color=COLOR_TRACK,
                text_color=COLOR_DANGER, font=ctk.CTkFont(size=max(11, self._px(12))),
                command=lambda a=admin: self._confirm_delete_admin(a["email"], a["full_name"]),
            )
            if is_default:
                # The default admin always exists as a fallback login, so
                # it can be edited but never deleted from this screen.
                delete_btn.configure(state="disabled", border_color=COLOR_TRACK, text_color=COLOR_TRACK)
            delete_btn.pack(side="left")

    def _open_admin_dialog(self, existing_admin: dict = None):
        AdminFormDialog(
            self, self.scale, existing_admin=existing_admin,
            on_saved=self._refresh_admin_management_table,
        )

    def _confirm_delete_admin(self, email: str, name: str):
        if email == database.DEFAULT_ADMIN_EMAIL:
            messagebox.showinfo("Can't delete", "The default admin account can't be deleted.")
            return

        confirmed = messagebox.askyesno(
            "Delete admin",
            f"Remove {name}'s admin access ({email})?\n\n"
            "They will no longer be able to log in to the Admin Dashboard.",
        )
        if not confirmed:
            return
        try:
            database.delete_admin(email)
        except ValueError as err:
            messagebox.showerror("Can't delete", str(err))
            return
        except mysql.connector.Error as db_err:
            messagebox.showerror("Database error", str(db_err))
            return
        self._refresh_admin_management_table()

    # ------------------------------------------------------------ shared table helper
    def _build_table(self, parent, columns, rows, scrollable=False):
        """columns: list of (label, relative_width). rows: list of lists —
        a plain string per cell, or a (button_text, callback) tuple for an
        action cell."""
        container = ctk.CTkScrollableFrame(parent, fg_color="transparent") if scrollable else ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True)
        for i, (_label, weight) in enumerate(columns):
            container.grid_columnconfigure(i, weight=weight)

        header_font = ctk.CTkFont(size=max(11, self._px(12)), weight="bold")
        for col, (label, _weight) in enumerate(columns):
            ctk.CTkLabel(
                container, text=label, anchor="w", text_color=COLOR_ACCENT_SOFT, font=header_font,
            ).grid(row=0, column=col, sticky="ew", padx=(0, self._px(8)), pady=(0, self._px(8)))

        row_font = ctk.CTkFont(size=max(12, self._px(13)))
        for r, row_data in enumerate(rows, start=1):
            row_bg = COLOR_BG if r % 2 == 0 else "transparent"
            for col, cell in enumerate(row_data):
                if isinstance(cell, tuple):
                    text, callback = cell
                    ctk.CTkButton(
                        container, text=text, width=self._px(70), height=self._px(26),
                        corner_radius=self._px(8), fg_color="transparent",
                        border_width=1, border_color=COLOR_DANGER, hover_color=COLOR_TRACK,
                        text_color=COLOR_DANGER, font=ctk.CTkFont(size=max(11, self._px(12))),
                        command=callback,
                    ).grid(row=r, column=col, sticky="w", padx=(0, self._px(8)), pady=self._px(4))
                else:
                    ctk.CTkLabel(
                        container, text=str(cell), anchor="w", text_color=COLOR_WHITE,
                        font=row_font, fg_color=row_bg,
                    ).grid(row=r, column=col, sticky="ew", padx=(0, self._px(8)), pady=self._px(4))

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _fmt_date(value) -> str:
        try:
            return value.strftime("%b %d, %Y")
        except AttributeError:
            return str(value)

    def _show_db_error(self, parent, db_err):
        ctk.CTkLabel(
            parent, text=f"Database error: {db_err}", text_color=COLOR_DANGER,
            font=ctk.CTkFont(size=max(12, self._px(13))), wraplength=self._px(700),
        ).pack(pady=self._px(20))

    def _handle_logout(self):
        confirmed = messagebox.askyesno("Log out", "Log out of the admin panel?")
        if not confirmed:
            return
        self.destroy()
        from login_page import LoginPage
        LoginPage().mainloop()


if __name__ == "__main__":
    # Running this file directly no longer opens the dashboard on its
    # own — AdminDashboard now refuses to open without a real admin
    # session (see _is_valid_admin_session), so this goes through the
    # same Login Page every other entry point uses.
    from login_page import LoginPage
    LoginPage().mainloop()