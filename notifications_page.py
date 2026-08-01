"""
notifications_page.py
------------------------
AI Diet Chart & Nutrition Calculator — Notifications
Healthcare-themed, built with CustomTkinter.

Pulls together four kinds of reminders from data the app already has
— nothing here is randomly generated:
  - Meal Reminders   — today's slots from the Meal Planner (meal_plans
    table), flagged as planned / not yet planned, with a suggested
    time for each meal.
  - Water Reminders  — today's logged water (water_log table) vs. the
    same weight/activity-based goal used on Water Intake Calculator,
    with upcoming reminder times for the rest of the day.
  - Workout Reminders — today's top suggested exercises from the same
    rule-based engine used on Exercise Recommendations, based on the
    user's BMI, age, and fitness goal.
  - Upcoming Diet Schedule — a 3-day look-ahead preview of planned
    meals from the Meal Planner.

Each category can be muted from the Notification Preferences card at
the bottom (saved via preferences.py, same mechanism Settings uses).

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
(`state('zoomed')`, falling back to `-zoomed` or a manual full-screen
geometry).

Run:
    pip install customtkinter mysql-connector-python
    python notifications_page.py
"""

from datetime import datetime, date, time as dt_time

import mysql.connector
import customtkinter as ctk

import database
import session
import preferences
from water_calculator import calculate_water_goal_ml, GLASS_ML
from exercise_recommendation import calculate_bmi, classify_bmi, recommend_exercises

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
COLOR_WATER = "#5DADE2"
COLOR_PENDING = "#F4D03F"

WINDOW_W, WINDOW_H = 560, 860
MIN_W, MIN_H = 440, 600
MAX_W, MAX_H = 680, 1000

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEAL_TYPES = ["Breakfast", "Lunch", "Snacks", "Dinner"]
MEAL_ICONS = {"Breakfast": "🍳", "Lunch": "🍛", "Snacks": "🥗", "Dinner": "🍽️"}
MEAL_TIMES = {"Breakfast": "8:00 AM", "Lunch": "1:00 PM", "Snacks": "4:30 PM", "Dinner": "8:00 PM"}

WATER_REMINDER_TIMES = [
    ("8:00 AM", dt_time(8, 0)), ("10:00 AM", dt_time(10, 0)), ("12:00 PM", dt_time(12, 0)),
    ("2:00 PM", dt_time(14, 0)), ("4:00 PM", dt_time(16, 0)), ("6:00 PM", dt_time(18, 0)),
    ("8:00 PM", dt_time(20, 0)),
]

WORKOUT_TIME_SUGGESTION = "6:30 AM or after work, 30-45 min"

PREF_KEYS = {
    "notif_meal_reminders": "Meal reminders",
    "notif_water_reminders": "Water reminders",
    "notif_workout_reminders": "Workout reminders",
    "notif_diet_schedule": "Upcoming diet schedule",
}


class NotificationsPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.user_email = self.user_data.get("email")
        self.on_back = on_back
        self.pref_vars = {}

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Notifications")
        self.configure(fg_color=COLOR_BG)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        # Deferred, same reasoning as login_page.py / dashboard.py /
        # bmi_calculator.py / calorie_calculator.py: CustomTkinter
        # schedules some of its own window/DPI setup via internal
        # after() calls right after the window is created, and calling
        # state('zoomed') too early gets silently overwritten by that
        # later setup. Queuing it with after() lets it run after that
        # setup has settled.
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
        ctk.CTkButton(
            top_row, text="⟳  Refresh", width=90, height=30,
            fg_color="transparent", hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=12),
            command=self._refresh_all,
        ).pack(side="right")

        ctk.CTkLabel(
            outer, text="🔔  Notifications",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 0))
        ctk.CTkLabel(
            outer, text=datetime.now().strftime("%A, %d %B %Y"),
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 16))

        self.scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.prefs = preferences.load_preferences() or {}

        self.meal_card_body = self._section_card("🍽️  Meal Reminders")
        self.water_card_body = self._section_card("💧  Water Reminders")
        self.workout_card_body = self._section_card("🏃  Workout Reminders")
        self.schedule_card_body = self._section_card("📅  Upcoming Diet Schedule")
        self._build_preferences_section(self.scroll)

        self._refresh_all()

    def _section_card(self, title):
        card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=14)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", padx=16, pady=(14, 6))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))
        return body

    def _clear(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def _empty_state(self, frame, text):
        ctk.CTkLabel(
            frame, text=text, font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            wraplength=440, justify="left", anchor="w",
        ).pack(anchor="w", pady=4)

    def _muted_state(self, frame, category_label):
        ctk.CTkLabel(
            frame, text=f"{category_label} are muted. Turn them back on below to see them here.",
            font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            wraplength=440, justify="left", anchor="w",
        ).pack(anchor="w", pady=4)

    def _reminder_row(self, parent, icon, title, subtitle, badge_text=None, badge_color=COLOR_ACCENT):
        row = ctk.CTkFrame(parent, fg_color=COLOR_ENTRY_BG, corner_radius=10)
        row.pack(fill="x", pady=4)

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(
            top, text=f"{icon}  {title}", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_WHITE, anchor="w",
        ).pack(side="left")
        if badge_text:
            ctk.CTkLabel(
                top, text=f"  {badge_text}  ", fg_color=badge_color,
                text_color="#0B3D3A", font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=8,
            ).pack(side="right")

        ctk.CTkLabel(
            row, text=subtitle, font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
            anchor="w", justify="left", wraplength=420,
        ).pack(anchor="w", padx=12, pady=(2, 8))

    # ============================================================ refresh
    def _refresh_all(self):
        self.prefs = preferences.load_preferences() or {}
        self._refresh_meal_reminders()
        self._refresh_water_reminders()
        self._refresh_workout_reminders()
        self._refresh_diet_schedule()

    # -------------------------------------------------------- meal section
    def _refresh_meal_reminders(self):
        frame = self.meal_card_body
        self._clear(frame)

        if not self.prefs.get("notif_meal_reminders", True):
            self._muted_state(frame, "Meal reminders")
            return
        if not self.user_email:
            self._empty_state(frame, "Log in to see today's meal reminders.")
            return

        today = datetime.now().strftime("%A")
        try:
            plans = database.get_meal_plans(self.user_email)
        except mysql.connector.Error:
            self._empty_state(frame, "Couldn't load your meal plan right now.")
            return

        planned_today = {p["meal_type"]: p["meal_description"] for p in plans if p["day_of_week"] == today}

        for meal_type in MEAL_TYPES:
            icon = MEAL_ICONS[meal_type]
            time_str = MEAL_TIMES[meal_type]
            if meal_type in planned_today:
                self._reminder_row(
                    frame, icon, f"{meal_type} at {time_str}",
                    planned_today[meal_type],
                    badge_text="Planned", badge_color=COLOR_ACCENT,
                )
            else:
                self._reminder_row(
                    frame, icon, f"{meal_type} at {time_str}",
                    "Nothing planned yet — add it in Meal Planner.",
                    badge_text="Not planned", badge_color=COLOR_PENDING,
                )

    # ------------------------------------------------------- water section
    def _refresh_water_reminders(self):
        frame = self.water_card_body
        self._clear(frame)

        if not self.prefs.get("notif_water_reminders", True):
            self._muted_state(frame, "Water reminders")
            return
        if not self.user_email:
            self._empty_state(frame, "Log in to see your water reminders.")
            return

        weight = self.user_data.get("weight_kg")
        activity_level = self.user_data.get("activity_level")
        if not weight:
            self._empty_state(frame, "Add your weight in Settings/Profile to calculate a water goal.")
            return

        goal_ml = calculate_water_goal_ml(float(weight), activity_level or "Sedentary")

        try:
            rows = database.get_water_log(self.user_email, days=1)
        except mysql.connector.Error:
            rows = []
        today_ml = 0.0
        today = date.today()
        for row in rows:
            if row.get("log_date") == today:
                today_ml = float(row.get("total_ml") or 0)

        remaining_ml = max(goal_ml - today_ml, 0)
        glasses_remaining = round(remaining_ml / GLASS_ML)

        if remaining_ml <= 0:
            self._reminder_row(
                frame, "✅", "Goal reached for today",
                f"You've logged {today_ml:.0f} ml of your {goal_ml:.0f} ml goal. Nice work!",
                badge_text="Done", badge_color=COLOR_SUCCESS,
            )
            return

        self._reminder_row(
            frame, "💧", "Keep drinking",
            f"{today_ml:.0f} / {goal_ml:.0f} ml logged today — about {glasses_remaining} "
            f"more glass{'es' if glasses_remaining != 1 else ''} to go.",
            badge_text="In progress", badge_color=COLOR_WATER,
        )

        now_time = datetime.now().time()
        upcoming = [t for label, t in WATER_REMINDER_TIMES if t > now_time]
        upcoming_labels = [label for label, t in WATER_REMINDER_TIMES if t > now_time][:4]
        if upcoming_labels:
            self._reminder_row(
                frame, "⏰", "Next reminder times today",
                ", ".join(upcoming_labels),
                badge_text=None,
            )
        else:
            self._reminder_row(
                frame, "🌙", "That's it for today",
                "No more scheduled reminder times left today — catch up first thing tomorrow.",
                badge_text=None,
            )

    # ----------------------------------------------------- workout section
    def _refresh_workout_reminders(self):
        frame = self.workout_card_body
        self._clear(frame)

        if not self.prefs.get("notif_workout_reminders", True):
            self._muted_state(frame, "Workout reminders")
            return
        if not self.user_email:
            self._empty_state(frame, "Log in to see workout suggestions.")
            return

        d = self.user_data
        age = d.get("age")
        height = d.get("height_cm")
        weight = d.get("weight_kg")
        goal = d.get("fitness_goal") or "General Fitness"

        if not (age and height and weight):
            self._empty_state(
                frame, "Add your age, height, and weight in Settings/Profile to get "
                       "personalized workout reminders."
            )
            return

        bmi = calculate_bmi(float(height), float(weight))
        bmi_category = classify_bmi(bmi)
        top_exercises = recommend_exercises(int(age), float(weight), bmi_category, goal, top_n=2)

        for ex in top_exercises:
            self._reminder_row(
                frame, "🏃", f"{ex['name']} — {ex['duration_min']} min",
                f"Suggested time: {WORKOUT_TIME_SUGGESTION}. "
                f"~{ex['calories_burned']:.0f} kcal burned · {ex['difficulty']} level.",
                badge_text=ex["category"], badge_color=COLOR_ACCENT_SOFT,
            )

        if not top_exercises:
            self._empty_state(frame, "No workout suggestions available right now.")

    # ---------------------------------------------------------- schedule
    def _refresh_diet_schedule(self):
        frame = self.schedule_card_body
        self._clear(frame)

        if not self.prefs.get("notif_diet_schedule", True):
            self._muted_state(frame, "Upcoming diet schedule")
            return
        if not self.user_email:
            self._empty_state(frame, "Log in to see your upcoming diet schedule.")
            return

        try:
            plans = database.get_meal_plans(self.user_email)
        except mysql.connector.Error:
            self._empty_state(frame, "Couldn't load your meal plan right now.")
            return

        by_day = {}
        for p in plans:
            by_day.setdefault(p["day_of_week"], {})[p["meal_type"]] = p["meal_description"]

        today_idx = DAYS.index(datetime.now().strftime("%A"))
        upcoming_days = [DAYS[(today_idx + offset) % 7] for offset in range(3)]
        day_labels = ["Today", "Tomorrow", DAYS[(today_idx + 2) % 7]]

        any_planned = False
        for day_name, label in zip(upcoming_days, day_labels):
            day_plans = by_day.get(day_name, {})
            planned_meals = [f"{MEAL_ICONS[m]} {m}" for m in MEAL_TYPES if m in day_plans]
            if planned_meals:
                any_planned = True
                self._reminder_row(
                    frame, "📅", f"{label} ({day_name})",
                    "Planned: " + ", ".join(planned_meals),
                    badge_text=f"{len(planned_meals)}/4", badge_color=COLOR_ACCENT,
                )
            else:
                self._reminder_row(
                    frame, "📅", f"{label} ({day_name})",
                    "Nothing planned yet.",
                    badge_text="0/4", badge_color=COLOR_MUTED,
                )

        if not any_planned:
            ctk.CTkLabel(
                frame, text="Head to Meal Planner to fill in the days ahead.",
                font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
            ).pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------- preferences
    def _build_preferences_section(self, parent):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(
            card, text="🔕  Notification Preferences", font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", padx=16, pady=(14, 8))

        for key, label in PREF_KEYS.items():
            var = ctk.BooleanVar(value=bool(self.prefs.get(key, True)))
            switch = ctk.CTkSwitch(
                card, text=label, variable=var, onvalue=True, offvalue=False,
                fg_color=COLOR_TRACK, progress_color=COLOR_ACCENT,
                text_color=COLOR_WHITE, font=ctk.CTkFont(size=12),
            )
            switch.pack(anchor="w", padx=16, pady=4)
            self.pref_vars[key] = var

        self.prefs_status_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=11), text_color=COLOR_SUCCESS,
        )
        self.prefs_status_label.pack(anchor="w", padx=16, pady=(4, 0))

        ctk.CTkButton(
            card, text="Save Preferences", height=36, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_save_preferences,
        ).pack(fill="x", padx=16, pady=(10, 16))

    def _handle_save_preferences(self):
        updated = dict(self.prefs)
        for key, var in self.pref_vars.items():
            updated[key] = var.get()
        try:
            preferences.save_preferences(updated)
        except OSError as e:
            self.prefs_status_label.configure(text_color=COLOR_ERROR, text=f"Couldn't save: {e}")
            return
        self.prefs_status_label.configure(text_color=COLOR_SUCCESS, text="Preferences saved.")
        self._refresh_all()

    def _go_back(self):
        from dashboard import DashboardPage
        self.destroy()
        if self.on_back:
            self.on_back()
        else:
            DashboardPage(user_data=self.user_data).mainloop()


if __name__ == "__main__":
    demo_user = {
        "email": "Piyush@gmail.com",
        "full_name": "Piyush Kawatra",
        "age": 70,
        "height_cm": 165,
        "weight_kg": 60,
        "activity_level": "Moderately Active",
        "fitness_goal": "Weight Loss",
    }
    app = NotificationsPage(user_data=demo_user)
    app.mainloop()