"""
dashboard.py
------------
AI Diet Chart & Nutrition Calculator — Dashboard Page
Healthcare-themed, built with CustomTkinter. Responsive layout:
left navigation sidebar + top header + scrollable content area.

Shows: user profile summary, BMI, calorie goal, water intake,
quick action cards, recent meals, a motivational quote, and a
health summary.

PERFORMANCE / LIVE DATA:
Building this page used to call `_load_live_data()` synchronously in
__init__, which does ~7 sequential MySQL round trips (user row, BMI
history, calorie history, calories-today, water-today, streak,
recent food log) before a single widget was drawn — every time you
navigated back to the dashboard from any other page, the window sat
blank/unresponsive until all of that finished.

Now the page renders IMMEDIATELY using whatever `user_data` was
already passed in (i.e. the values from the last time it loaded, or
DEFAULT_USER_DATA for a guest run) — no DB calls block __init__ or
widget construction. Once the window is up, `_start_live_data_refresh()`
kicks off a background thread that does the same DB work off the UI
thread; when it finishes, `_apply_live_data()` is scheduled back onto
the Tk main thread via `self.after(0, ...)` and patches just the
affected labels/progress bars/meal rows in place. So on a fast
connection the numbers refresh a beat after the page appears; on a
slow one you still get an instantly responsive window instead of a
frozen one. Skipped entirely for a guest session (no real email).

The window opens maximized to fill the screen (see _maximize_window)
instead of a fixed 1100x700 — it still has a sane minimum size via
minsize() if the user un-maximizes it.

NOTE: Sidebar nav links and quick-action cards are wired to
placeholder handlers only where no page module exists yet (they
print to the console). Build each remaining feature as its own
module (e.g. water_tracker.py) and swap the placeholder in
`_nav_placeholder` / the relevant `command=` with a real import +
window switch when that file is ready.

Run:
    pip install customtkinter
    python dashboard.py
"""

import random
import threading
from datetime import datetime
import os
from tkinter import messagebox, TclError

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps
import mysql.connector

import database
import session

# ---------------------------------------------------------------------------
# Theme constants — matches splash / login / registration pages
# ---------------------------------------------------------------------------
COLOR_BG = "#0E4B47"
COLOR_SIDEBAR = "#0B3D3A"
COLOR_CARD = "#155953"
COLOR_ACCENT = "#2FD3B0"
COLOR_ACCENT_SOFT = "#8FE3D1"
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#1E6B64"
COLOR_MUTED = "#6FA69E"

# Fallback size only — used if a maximized/fullscreen state can't be
# applied for some reason (see _maximize_window), and as the basis for
# minsize() so the window has a sane floor if the user un-maximizes it.
WINDOW_W, WINDOW_H = 1100, 700
MIN_W, MIN_H = 860, 600

NAV_ITEMS = [
    ("Dashboard", "🏠"),
    ("Meal Planner", "🍽️"),
    ("Progress", "📈"),
    ("Settings", "⚙️"),
]

QUOTES = [
    "Small daily improvements lead to big results.",
    "Take care of your body, it's the only place you have to live.",
    "Health is not about the weight you lose, but the life you gain.",
    "Every meal is a chance to nourish yourself.",
    "Progress, not perfection.",
]

# Only ever shown as-is for a guest / no-session run — a logged-in
# user's real stats overwrite these once the live-data thread returns.
DEFAULT_USER_DATA = {
    "full_name": "Guest User",
    "email": "guest@example.com",
    "bmi": 22.4,
    "bmi_category": "Normal",
    "calorie_goal": 2100,
    "calories_consumed": 1350,
    "water_intake_ml": 1200,
    "water_goal_ml": 2500,
    "weight_kg": 65,
    "height_cm": 170,
    "streak_days": 5,
    "recent_meals": [
        {"name": "Oatmeal & Berries", "calories": 320, "time": "8:15 AM"},
        {"name": "Grilled Chicken Salad", "calories": 480, "time": "1:05 PM"},
        {"name": "Greek Yogurt", "calories": 150, "time": "4:30 PM"},
    ],
}


class DashboardPage(ctk.CTk):
    def __init__(self, user_data: dict = None):
        super().__init__()

        # Prefer explicitly-passed user_data; otherwise pull whoever is
        # currently logged in from session.py; otherwise fall back to
        # the placeholder guest data (e.g. when running this file standalone).
        # NOTE: this is deliberately the only data used to build the initial
        # UI — no DB calls happen here, so the window appears instantly.
        # See _start_live_data_refresh() for how fresh values arrive after.
        self.user_data = {
            **DEFAULT_USER_DATA,
            **(user_data or session.get_current_user() or {}),
        }
        self.active_nav = "Dashboard"

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Dashboard")
        self.configure(fg_color=COLOR_BG)
        self.minsize(MIN_W, MIN_H)

        # Deferred, not called directly: CustomTkinter schedules some of
        # its own window/DPI setup via internal after() calls right after
        # the window is created, and that runs *after* this __init__
        # returns — if we maximize immediately here, that later setup
        # silently overwrites it back to a small centered window (the
        # "flashes full screen then shrinks" you saw). Queuing it with
        # after() instead lets it run after that setup has settled.
        self.after(10, self._maximize_window)

        # Responsive root grid: sidebar (fixed) + main area (grows)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_main_area()

        # Kick off the DB refresh only after every widget exists, so the
        # background thread has real labels/bars to patch once it returns.
        self._start_live_data_refresh()

    # ============================================================ WINDOW
    def _maximize_window(self):
        """Opens the dashboard filling the screen instead of a fixed
        1100x700. `state('zoomed')` is the normal way to do this on
        Windows and most Linux window managers; macOS's Tk build doesn't
        support that state string and raises a TclError, so it falls
        back to `-zoomed` (some Linux WMs use this attribute instead),
        and finally to manually sizing/positioning the window to the
        full screen if neither is available."""
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

    # ================================================== LIVE DATA (async)
    def _start_live_data_refresh(self):
        """Fires off the MySQL work on a background thread so it never
        blocks the UI. Skipped for a guest session (no real email) since
        there's nothing to look up. A snapshot of user_data is captured
        here (not read later from the thread) to avoid any race with the
        main thread mutating self.user_data while the query runs."""
        email = self.user_data.get("email")
        if not email or email == DEFAULT_USER_DATA["email"]:
            return

        base_snapshot = dict(self.user_data)
        threading.Thread(
            target=self._fetch_live_data_worker,
            args=(email, base_snapshot),
            daemon=True,
        ).start()

    def _fetch_live_data_worker(self, email, base):
        """Runs on the background thread — MySQL calls only, no Tk calls.
        Hands the result back to the main thread via self.after(0, ...),
        which is the only safe way to touch widgets from another thread.
        If this window has already been destroyed (user navigated away
        before the query finished) the after() call is skipped."""
        try:
            updates = self._fetch_live_data(email, base)
        except Exception:
            updates = {}

        try:
            self.after(0, lambda: self._apply_live_data(updates))
        except (TclError, RuntimeError):
            pass  # window is gone — nothing to update

    def _fetch_live_data(self, email, base):
        """Computes fresh values from MySQL for the logged-in user:
        latest BMI, calorie goal (TDEE + fitness-goal adjustment) and
        calories consumed today, water goal and water intake today,
        activity streak, and recent logged meals. Returns a dict of only
        the fields it managed to compute — never mutates self.user_data
        directly (that happens back on the main thread in
        _apply_live_data). Any DB error is swallowed per-section so a
        MySQL hiccup just means that section keeps its cached value
        instead of crashing the refresh.
        """
        updates = {}

        try:
            user_row = database.get_user_by_email(email) or {}
        except mysql.connector.Error:
            user_row = {}

        height_cm = user_row.get("height_cm") or base.get("height_cm")
        weight_kg = user_row.get("weight_kg") or base.get("weight_kg")
        age = user_row.get("age") or base.get("age")
        gender = user_row.get("gender") or base.get("gender")
        activity_level = user_row.get("activity_level") or base.get("activity_level")
        fitness_goal = user_row.get("fitness_goal") or base.get("fitness_goal")

        if height_cm:
            updates["height_cm"] = height_cm
        if weight_kg:
            updates["weight_kg"] = weight_kg
        if age:
            updates["age"] = age
        if gender:
            updates["gender"] = gender
        if activity_level:
            updates["activity_level"] = activity_level

        # ---- BMI: latest saved calculation, else compute on the fly ----
        try:
            from bmi_calculator import calculate_bmi, classify_bmi
            bmi_history = database.get_bmi_history(email, limit=1)
            if bmi_history:
                updates["bmi"] = bmi_history[0]["bmi"]
                updates["bmi_category"] = bmi_history[0]["category"]
            elif height_cm and weight_kg:
                bmi_value = calculate_bmi(height_cm, weight_kg)
                category, _, _ = classify_bmi(bmi_value)
                updates["bmi"] = bmi_value
                updates["bmi_category"] = category
        except mysql.connector.Error:
            pass

        # ---- Calorie goal + calories consumed today ----
        try:
            from calorie_calculator import calculate_bmr, calculate_tdee, GOAL_ADJUSTMENTS
            calorie_history = database.get_calorie_history(email, limit=1)
            tdee = None
            if calorie_history:
                tdee = calorie_history[0]["tdee"]
            elif all([age, gender, height_cm, weight_kg, activity_level]):
                tdee = calculate_tdee(
                    calculate_bmr(age, gender, height_cm, weight_kg), activity_level
                )
            if tdee is not None:
                adjustment = GOAL_ADJUSTMENTS.get(fitness_goal, 0)
                updates["calorie_goal"] = round(tdee + adjustment)
            updates["calories_consumed"] = round(
                database.get_calories_consumed_today(email)
            )
        except mysql.connector.Error:
            pass

        # ---- Water goal + water intake today ----
        try:
            from water_calculator import calculate_water_goal_ml
            if weight_kg and activity_level:
                updates["water_goal_ml"] = round(
                    calculate_water_goal_ml(weight_kg, activity_level)
                )
            updates["water_intake_ml"] = round(database.get_water_intake_today(email))
        except mysql.connector.Error:
            pass

        # ---- Activity streak ----
        try:
            updates["streak_days"] = database.get_activity_streak_days(email)
        except mysql.connector.Error:
            pass

        # ---- Recent meals (real logged food items, not placeholders) ----
        try:
            food_log = database.get_recent_food_log(email, limit=3)
            updates["recent_meals"] = [
                {
                    "name": item["food_name"].title(),
                    "calories": round(item["calories"]),
                    "time": (
                        item["created_at"].strftime("%I:%M %p").lstrip("0")
                        if hasattr(item["created_at"], "strftime")
                        else str(item["created_at"])
                    ),
                }
                for item in food_log
            ]
        except mysql.connector.Error:
            pass

        return updates

    def _apply_live_data(self, updates):
        """Runs on the main thread (scheduled via self.after). Merges the
        background thread's results into self.user_data and patches only
        the widgets whose backing values actually changed — no full
        rebuild, just label/progress-bar updates and a meals-list
        refresh, so this is cheap even though it may fire a beat after
        the page first appears."""
        if not updates:
            return
        self.user_data.update(updates)
        d = self.user_data

        if "bmi" in updates or "bmi_category" in updates:
            self.bmi_value_label.configure(text=f"{d['bmi']:.1f}")
            self.bmi_subtitle_label.configure(text=d["bmi_category"])

        if "calorie_goal" in updates or "calories_consumed" in updates:
            self.calorie_value_label.configure(
                text=f"{d['calories_consumed']:.0f} / {d['calorie_goal']:.0f}"
            )
            self.calorie_progress_bar.set(
                min(d["calories_consumed"] / max(d["calorie_goal"], 1), 1.0)
            )

        if "water_goal_ml" in updates or "water_intake_ml" in updates:
            self.water_value_label.configure(
                text=f"{d['water_intake_ml']:.0f} / {d['water_goal_ml']:.0f} ml"
            )
            self.water_progress_bar.set(
                min(d["water_intake_ml"] / max(d["water_goal_ml"], 1), 1.0)
            )

        if "streak_days" in updates:
            self.streak_value_label.configure(text=f"{d['streak_days']} days")

        if "recent_meals" in updates:
            self._render_recent_meals()

        if any(k in updates for k in ("height_cm", "weight_kg", "bmi_category")):
            self.height_value_label.configure(text=f"{d['height_cm']} cm")
            self.weight_value_label.configure(text=f"{d['weight_kg']} kg")
            self.bmi_category_value_label.configure(text=d["bmi_category"])

        if session.get_current_user():
            session.set_current_user(self.user_data)

    # ================================================================ NAV
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLOR_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)

        logo_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_row.pack(fill="x", pady=(24, 30), padx=20)
        ctk.CTkLabel(
            logo_row, text="🥗", font=ctk.CTkFont(size=26),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            logo_row, text="NutriApp",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(side="left")

        self.nav_buttons = {}
        for label, icon in NAV_ITEMS:
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon}   {label}",
                anchor="w", height=42, corner_radius=10,
                fg_color=COLOR_ACCENT if label == self.active_nav else "transparent",
                text_color="#0B3D3A" if label == self.active_nav else COLOR_ACCENT_SOFT,
                hover_color=COLOR_TRACK,
                font=ctk.CTkFont(size=13, weight="bold" if label == self.active_nav else "normal"),
                command=lambda l=label: self._handle_nav_click(l),
            )
            btn.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[label] = btn

        # Logout pinned to the bottom
        ctk.CTkButton(
            sidebar, text="  🚪   Logout",
            anchor="w", height=42, corner_radius=10,
            fg_color="transparent", text_color="#FF8A80",
            hover_color=COLOR_TRACK,
            font=ctk.CTkFont(size=13),
            command=self._handle_logout,
        ).pack(fill="x", padx=14, pady=(10, 20), side="bottom")

    def _handle_nav_click(self, label):
        if label == "Meal Planner":
            self._open_meal_planner()
        elif label == "Progress":
            self._open_progress_tracker()
        elif label == "Settings":
            self._open_settings()
        else:
            self._nav_placeholder(label)

    def _open_settings(self):
        from settings_page import SettingsPage
        self.destroy()
        SettingsPage(user_data=self.user_data).mainloop()

    def _open_meal_planner(self):
        from meal_planner import MealPlannerPage
        self.destroy()
        MealPlannerPage(user_data=self.user_data).mainloop()

    def _open_progress_tracker(self):
        from progress_tracker import ProgressTrackerPage
        self.destroy()
        ProgressTrackerPage(user_data=self.user_data).mainloop()

    def _open_exercise_recommendations(self):
        from exercise_recommendation import ExerciseRecommendationPage
        self.destroy()
        ExerciseRecommendationPage(user_data=self.user_data).mainloop()

    def _nav_placeholder(self, label):
        """Stub for sidebar navigation. Replace with a real import + window
        switch once a page's module exists for a future nav item, e.g.:
            if label == "Some New Section":
                from some_new_section import SomeNewSectionPage
                self.destroy(); SomeNewSectionPage(self.user_data).mainloop()
        """
        print(f"[nav] Clicked '{label}' — create its module and wire it here.")

    def _handle_logout(self):
        from logout_page import confirm_logout
        confirm_logout(self)

    # =========================================================== MAIN AREA
    def _build_main_area(self):
        main = ctk.CTkFrame(self, fg_color=COLOR_BG)
        main.grid(row=0, column=1, sticky="nswe")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self._build_header(main)

        # Scrollable content so the dashboard works on smaller screens too
        content = ctk.CTkScrollableFrame(main, fg_color=COLOR_BG)
        content.grid(row=1, column=0, sticky="nswe", padx=24, pady=(0, 20))
        for col in range(4):
            content.grid_columnconfigure(col, weight=1, uniform="stats")

        self._build_stat_cards(content)
        self._build_quick_actions(content)
        self._build_ai_diet_planner_banner(content)
        self._build_recent_meals_and_quote(content)
        self._build_health_summary(content)

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color=COLOR_SIDEBAR, height=70, corner_radius=0)
        header.grid(row=0, column=0, sticky="nswe")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=24)
        today = datetime.now().strftime("%A, %d %B %Y")
        ctk.CTkLabel(
            left, text=f"Welcome back, {self.user_data['full_name'].split(' ')[0]}!",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", pady=(12, 0))
        ctk.CTkLabel(
            left, text=today,
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=24)

        ctk.CTkButton(
            right, text="🔔", width=42, height=42, corner_radius=21,
            fg_color="transparent", hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=17),
            command=self._open_notifications,
        ).pack(side="right", padx=(0, 10), pady=14)

        initials = "".join(w[0] for w in self.user_data["full_name"].split()[:2]).upper()
        avatar_image = self._load_circular_avatar(42)
        if avatar_image is not None:
            avatar = ctk.CTkButton(
                right, image=avatar_image, text="", width=42, height=42, corner_radius=21,
                fg_color=COLOR_ACCENT, hover_color="#26B79A",
                command=self._open_profile,
            )
            avatar.image = avatar_image  # keep a reference so it isn't garbage-collected
        else:
            avatar = ctk.CTkButton(
                right, text=initials, width=42, height=42, corner_radius=21,
                fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
                font=ctk.CTkFont(size=14, weight="bold"),
                command=self._open_profile,
            )
        avatar.pack(side="right", pady=14)

        name_email = ctk.CTkFrame(right, fg_color="transparent")
        name_email.pack(side="right", padx=(0, 10))
        ctk.CTkLabel(
            name_email, text=self.user_data["full_name"],
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_WHITE,
        ).pack(anchor="e")
        ctk.CTkLabel(
            name_email, text=self.user_data["email"],
            font=ctk.CTkFont(size=10), text_color=COLOR_MUTED,
        ).pack(anchor="e")

    def _load_circular_avatar(self, size):
        """Loads the user's saved profile picture as a circular CTkImage,
        or returns None if there isn't one (caller falls back to initials)."""
        path = self.user_data.get("profile_picture_path")
        if not path or not os.path.exists(path):
            return None
        try:
            img = Image.open(path).convert("RGB")
            img = ImageOps.fit(img, (size, size), Image.LANCZOS)
        except Exception:
            return None

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        img.putalpha(mask)

        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

    def _open_profile(self):
        from profile_page import ProfilePage
        self.destroy()
        ProfilePage(user_data=self.user_data).mainloop()

    def _open_notifications(self):
        from notifications_page import NotificationsPage
        self.destroy()
        NotificationsPage(user_data=self.user_data).mainloop()

    # -------------------------------------------------------- stat cards
    def _build_stat_cards(self, parent):
        d = self.user_data

        self.bmi_value_label, self.bmi_subtitle_label, _ = self._stat_card(
            parent, row=0, col=0, title="BMI",
            value=f"{d['bmi']:.1f}", subtitle=d["bmi_category"],
            on_click=self._open_bmi_calculator,
        )
        self.calorie_value_label, _, self.calorie_progress_bar = self._stat_card(
            parent, row=0, col=1, title="Calorie Goal",
            value=f"{d['calories_consumed']:.0f} / {d['calorie_goal']:.0f}",
            subtitle="kcal today",
            progress=d["calories_consumed"] / max(d["calorie_goal"], 1),
            on_click=self._open_calorie_calculator,
        )
        self.water_value_label, _, self.water_progress_bar = self._stat_card(
            parent, row=0, col=2, title="Water Intake",
            value=f"{d['water_intake_ml']:.0f} / {d['water_goal_ml']:.0f} ml",
            subtitle="today",
            progress=d["water_intake_ml"] / max(d["water_goal_ml"], 1),
            on_click=self._open_water_calculator,
        )
        self.streak_value_label, _, _ = self._stat_card(
            parent, row=0, col=3, title="Current Streak",
            value=f"{d['streak_days']} days", subtitle="Keep it going!",
        )

    def _open_water_calculator(self):
        from water_calculator import WaterCalculatorPage
        self.destroy()
        WaterCalculatorPage(user_data=self.user_data).mainloop()

    def _open_bmi_calculator(self):
        from bmi_calculator import BMICalculatorPage
        self.destroy()
        BMICalculatorPage(user_data=self.user_data).mainloop()

    def _open_calorie_calculator(self):
        from calorie_calculator import CalorieCalculatorPage
        self.destroy()
        CalorieCalculatorPage(user_data=self.user_data).mainloop()

    def _build_ai_diet_planner_banner(self, parent):
        banner = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        banner.grid(row=3, column=0, columnspan=4, sticky="nswe", padx=8, pady=(4, 4))
        banner.grid_columnconfigure(0, weight=1)

        text_col = ctk.CTkFrame(banner, fg_color="transparent")
        text_col.grid(row=0, column=0, sticky="w", padx=20, pady=16)
        ctk.CTkLabel(
            text_col, text="🤖 AI Diet Planner",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col, text="Get a personalized Indian meal plan based on your profile and goals",
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            banner, text="Generate Plan", width=140, height=36,
            corner_radius=10, fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_diet_planner,
        ).grid(row=0, column=1, sticky="e", padx=20, pady=16)

    def _open_diet_planner(self):
        from diet_planner import DietPlannerPage
        self.destroy()
        DietPlannerPage(user_data=self.user_data).mainloop()

    def _stat_card(self, parent, row, col, title, value, subtitle, progress=None, on_click=None):
        """Returns (value_label, subtitle_label, progress_bar_or_None) so
        callers that need to patch this card later (see _apply_live_data)
        can hold onto references without a full rebuild."""
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.grid(row=row, column=col, sticky="nswe", padx=8, pady=8)

        title_label = ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=12),
            text_color=COLOR_ACCENT_SOFT,
        )
        title_label.pack(anchor="w", padx=16, pady=(14, 2))
        value_label = ctk.CTkLabel(
            card, text=value, font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLOR_WHITE,
        )
        value_label.pack(anchor="w", padx=16)
        subtitle_label = ctk.CTkLabel(
            card, text=subtitle, font=ctk.CTkFont(size=11),
            text_color=COLOR_MUTED,
        )
        subtitle_label.pack(anchor="w", padx=16, pady=(0, 10 if progress is None else 6))

        progress_bar = None
        if progress is not None:
            progress_bar = ctk.CTkProgressBar(
                card, height=6, corner_radius=6,
                fg_color=COLOR_TRACK, progress_color=COLOR_ACCENT,
            )
            progress_bar.set(min(progress, 1.0))
            progress_bar.pack(fill="x", padx=16, pady=(0, 14))

        if on_click:
            for widget in (card, title_label, value_label, subtitle_label):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _e: on_click())

        return value_label, subtitle_label, progress_bar

    # ----------------------------------------------------- quick actions
    def _build_quick_actions(self, parent):
        ctk.CTkLabel(
            parent, text="Quick Actions",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(18, 6))

        actions = [
            ("🍎", "Nutrition Calculator", self._action_log_meal),
            ("💡", "AI Health Tip", self._action_ai_health_tip),
            ("⚖️", "Exercise Recommendation", self._open_exercise_recommendations),
            ("🎯", "Set Goals", self._action_set_goals),
        ]
        for i, (icon, label, handler) in enumerate(actions):
            btn = ctk.CTkButton(
                parent, text=f"{icon}\n{label}",
                height=80, corner_radius=14,
                fg_color=COLOR_CARD, hover_color=COLOR_TRACK,
                text_color=COLOR_WHITE,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=handler,
            )
            btn.grid(row=2, column=i, sticky="nswe", padx=8, pady=4)

    # Each of these is a stub — replace with a real page/dialog once you
    # build that module (e.g. meal_log.py, water_tracker.py).
    def _action_log_meal(self):
        from nutrition_calculator import NutritionCalculatorPage
        self.destroy()
        NutritionCalculatorPage(user_data=self.user_data).mainloop()

    def _action_ai_health_tip(self):
        from ai_health_tips import AIHealthTipsPage
        self.destroy()
        AIHealthTipsPage(user_data=self.user_data).mainloop()

    def _action_set_goals(self):
        messagebox.showinfo(
            "Set Goals",
            "Goal setting is coming soon!",
            parent=self,
        )

    # ---------------------------------------------- recent meals + quote
    def _build_recent_meals_and_quote(self, parent):
        row = 4
        ctk.CTkLabel(
            parent, text="Recent Meals",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(20, 6))
        ctk.CTkLabel(
            parent, text="Daily Motivation",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).grid(row=row, column=2, columnspan=2, sticky="w", padx=8, pady=(20, 6))

        self.meals_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        self.meals_card.grid(row=row + 1, column=0, columnspan=2, sticky="nswe", padx=8, pady=4)
        self._render_recent_meals()

        quote_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        quote_card.grid(row=row + 1, column=2, columnspan=2, sticky="nswe", padx=8, pady=4)
        ctk.CTkLabel(
            quote_card, text="❝", font=ctk.CTkFont(size=28), text_color=COLOR_ACCENT,
        ).pack(pady=(20, 0))
        ctk.CTkLabel(
            quote_card, text=random.choice(QUOTES), wraplength=260,
            font=ctk.CTkFont(size=13, slant="italic"), text_color=COLOR_WHITE,
            justify="center",
        ).pack(padx=20, pady=(4, 20))

    def _render_recent_meals(self):
        """(Re)draws the recent-meals list inside self.meals_card. Called
        once at build time and again from _apply_live_data() whenever
        fresh meal rows arrive from the background thread — clears any
        existing rows first so it never duplicates."""
        for child in self.meals_card.winfo_children():
            child.destroy()

        meals = self.user_data["recent_meals"]
        if meals:
            for meal in meals:
                meal_row = ctk.CTkFrame(self.meals_card, fg_color="transparent")
                meal_row.pack(fill="x", padx=16, pady=8)
                ctk.CTkLabel(
                    meal_row, text=meal["name"], font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COLOR_WHITE, anchor="w",
                ).pack(side="left")
                ctk.CTkLabel(
                    meal_row, text=f"{meal['calories']} kcal  ·  {meal['time']}",
                    font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
                ).pack(side="right")
        else:
            ctk.CTkLabel(
                self.meals_card, text="No meals logged yet today.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(padx=16, pady=20)

    # ---------------------------------------------------- health summary
    def _build_health_summary(self, parent):
        row = 6
        ctk.CTkLabel(
            parent, text="Health Summary",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).grid(row=row, column=0, columnspan=4, sticky="w", padx=8, pady=(20, 6))

        summary_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        summary_card.grid(row=row + 1, column=0, columnspan=4, sticky="nswe", padx=8, pady=(4, 16))
        summary_card.grid_columnconfigure((0, 1, 2), weight=1)

        d = self.user_data
        metrics = [
            ("Height", f"{d['height_cm']} cm"),
            ("Weight", f"{d['weight_kg']} kg"),
            ("BMI Category", d["bmi_category"]),
        ]
        value_labels = []
        for i, (label, value) in enumerate(metrics):
            col = ctk.CTkFrame(summary_card, fg_color="transparent")
            col.grid(row=0, column=i, sticky="nswe", padx=16, pady=18)
            ctk.CTkLabel(
                col, text=label, font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
            ).pack(anchor="w")
            value_label = ctk.CTkLabel(
                col, text=value, font=ctk.CTkFont(size=16, weight="bold"),
                text_color=COLOR_WHITE,
            )
            value_label.pack(anchor="w")
            value_labels.append(value_label)

        self.height_value_label, self.weight_value_label, self.bmi_category_value_label = value_labels


if __name__ == "__main__":
    app = DashboardPage()
    app.mainloop()