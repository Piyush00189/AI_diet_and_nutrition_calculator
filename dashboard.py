"""
dashboard.py
------------
AI Diet Chart & Nutrition Calculator — Dashboard Page
Healthcare-themed, built with CustomTkinter. Responsive layout:
left navigation sidebar + top header + scrollable content area.

Shows: user profile summary, BMI, calorie goal, water intake,
quick action cards, recent meals, a motivational quote, and a
health summary.

LIVE DATA: for a logged-in user (i.e. `user_data`/session has a real
`email`), BMI, calorie goal + calories consumed today, water intake
today, activity streak, and recent meals are all pulled live from
MySQL via database.py (see `_load_live_data`). DEFAULT_USER_DATA is
only ever shown as-is for a guest/no-session run of this file.

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
from datetime import datetime
import os
from tkinter import messagebox

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
# user's real stats overwrite these in _load_live_data().
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
        self.user_data = {
            **DEFAULT_USER_DATA,
            **(user_data or session.get_current_user() or {}),
        }
        self._load_live_data()
        self.active_nav = "Dashboard"

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Dashboard")
        self.configure(fg_color=COLOR_BG)
        self.minsize(MIN_W, MIN_H)

        # Fully transparent from the start (not withdrawn — withdraw()
        # has its own problems, see admin_dashboard.py's history) so
        # nothing is visible yet while the window is still small/
        # unmaximized and its widgets are still being built. It's
        # revealed with a short fade-in at the end of _maximize_window,
        # once maximizing has actually taken effect — this is what
        # smooths the "pop into view" feel when this window replaces
        # whatever page just destroyed itself. Silently does nothing on
        # window managers that don't support per-window alpha.
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            pass

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

    # ============================================================ WINDOW
    def _maximize_window(self):
        """Opens the dashboard filling the screen instead of a fixed
        1100x700. `state('zoomed')` is the normal way to do this on
        Windows and most Linux window managers; macOS's Tk build doesn't
        support that state string and raises a TclError, so it falls
        back to `-zoomed` (some Linux WMs use this attribute instead),
        and finally to manually sizing/positioning the window to the
        full screen if neither is available. Whichever path succeeds,
        it finishes by fading the (until now fully transparent) window
        into view — see __init__."""
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

        self._fade_in()

    def _fade_in(self, duration_ms=180, steps=12):
        """Ramps window opacity from 0 to 1 over `duration_ms` instead of
        just snapping to visible — a smoother transition into this page
        than the abrupt cut of the previous page's window disappearing
        and this one appearing instantly. No-ops quietly if this window
        manager doesn't support per-window alpha (some Linux WMs don't,
        without a compositor running)."""
        step_delay = max(1, duration_ms // steps)

        def _step(i=0):
            try:
                self.attributes("-alpha", min(1.0, (i + 1) / steps))
            except Exception:
                return
            if i + 1 < steps:
                self.after(step_delay, lambda: _step(i + 1))

        _step()

    # =============================================================== DATA
    def _load_live_data(self):
        """Overrides the DEFAULT_USER_DATA placeholders with real,
        computed values from MySQL for the logged-in user: latest BMI,
        calorie goal (TDEE + fitness-goal adjustment) and calories
        consumed today, water goal and water intake today, activity
        streak, and recent logged meals.

        Skipped entirely for a guest session (no real email). Any DB
        error is swallowed per-section so a MySQL hiccup degrades to
        "keep whatever value was already there" instead of crashing
        the dashboard.
        """
        email = self.user_data.get("email")
        if not email or email == DEFAULT_USER_DATA["email"]:
            return

        try:
            user_row = database.get_user_by_email(email) or {}
        except mysql.connector.Error:
            user_row = {}

        height_cm = user_row.get("height_cm") or self.user_data.get("height_cm")
        weight_kg = user_row.get("weight_kg") or self.user_data.get("weight_kg")
        age = user_row.get("age") or self.user_data.get("age")
        gender = user_row.get("gender") or self.user_data.get("gender")
        activity_level = user_row.get("activity_level") or self.user_data.get("activity_level")
        fitness_goal = user_row.get("fitness_goal") or self.user_data.get("fitness_goal")

        if height_cm:
            self.user_data["height_cm"] = height_cm
        if weight_kg:
            self.user_data["weight_kg"] = weight_kg
        if age:
            self.user_data["age"] = age
        if gender:
            self.user_data["gender"] = gender
        if activity_level:
            self.user_data["activity_level"] = activity_level

        # ---- BMI: latest saved calculation, else compute on the fly ----
        try:
            from bmi_calculator import calculate_bmi, classify_bmi
            bmi_history = database.get_bmi_history(email, limit=1)
            if bmi_history:
                self.user_data["bmi"] = bmi_history[0]["bmi"]
                self.user_data["bmi_category"] = bmi_history[0]["category"]
            elif height_cm and weight_kg:
                bmi_value = calculate_bmi(height_cm, weight_kg)
                category, _, _ = classify_bmi(bmi_value)
                self.user_data["bmi"] = bmi_value
                self.user_data["bmi_category"] = category
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
                self.user_data["calorie_goal"] = round(tdee + adjustment)
            self.user_data["calories_consumed"] = round(
                database.get_calories_consumed_today(email)
            )
        except mysql.connector.Error:
            pass

        # ---- Water goal + water intake today ----
        try:
            from water_calculator import calculate_water_goal_ml
            if weight_kg and activity_level:
                self.user_data["water_goal_ml"] = round(
                    calculate_water_goal_ml(weight_kg, activity_level)
                )
            self.user_data["water_intake_ml"] = round(database.get_water_intake_today(email))
        except mysql.connector.Error:
            pass

        # ---- Activity streak ----
        try:
            self.user_data["streak_days"] = database.get_activity_streak_days(email)
        except mysql.connector.Error:
            pass

        # ---- Recent meals (real logged food items, not placeholders) ----
        try:
            food_log = database.get_recent_food_log(email, limit=3)
            self.user_data["recent_meals"] = [
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

        self._stat_card(
            parent, row=0, col=0, title="BMI",
            value=f"{d['bmi']:.1f}", subtitle=d["bmi_category"],
            on_click=self._open_bmi_calculator,
        )
        self._stat_card(
            parent, row=0, col=1, title="Calorie Goal",
            value=f"{d['calories_consumed']:.0f} / {d['calorie_goal']:.0f}",
            subtitle="kcal today",
            progress=d["calories_consumed"] / max(d["calorie_goal"], 1),
            on_click=self._open_calorie_calculator,
        )
        self._stat_card(
            parent, row=0, col=2, title="Water Intake",
            value=f"{d['water_intake_ml']:.0f} / {d['water_goal_ml']:.0f} ml",
            subtitle="today",
            progress=d["water_intake_ml"] / max(d["water_goal_ml"], 1),
            on_click=self._open_water_calculator,
        )
        self._stat_card(
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

        if progress is not None:
            bar = ctk.CTkProgressBar(
                card, height=6, corner_radius=6,
                fg_color=COLOR_TRACK, progress_color=COLOR_ACCENT,
            )
            bar.set(min(progress, 1.0))
            bar.pack(fill="x", padx=16, pady=(0, 14))

        if on_click:
            for widget in (card, title_label, value_label, subtitle_label):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _e: on_click())

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

        meals_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        meals_card.grid(row=row + 1, column=0, columnspan=2, sticky="nswe", padx=8, pady=4)

        if self.user_data["recent_meals"]:
            for meal in self.user_data["recent_meals"]:
                meal_row = ctk.CTkFrame(meals_card, fg_color="transparent")
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
                meals_card, text="No meals logged yet today.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(padx=16, pady=20)

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
        for i, (label, value) in enumerate(metrics):
            col = ctk.CTkFrame(summary_card, fg_color="transparent")
            col.grid(row=0, column=i, sticky="nswe", padx=16, pady=18)
            ctk.CTkLabel(
                col, text=label, font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
            ).pack(anchor="w")
            ctk.CTkLabel(
                col, text=value, font=ctk.CTkFont(size=16, weight="bold"),
                text_color=COLOR_WHITE,
            ).pack(anchor="w")


if __name__ == "__main__":
    app = DashboardPage()
    app.mainloop()