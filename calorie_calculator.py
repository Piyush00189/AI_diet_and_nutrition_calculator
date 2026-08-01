"""
calorie_calculator.py
-----------------------
AI Diet Chart & Nutrition Calculator — Daily Calorie Calculator
Healthcare-themed, built with CustomTkinter.

Accepts age, gender, height, weight, and activity level. Calculates
BMR using the Mifflin-St Jeor Equation and the daily calorie
requirement (TDEE) by applying an activity multiplier. Saves every
calculation to MySQL (calorie_history table).

There's no "Calculate" button — the result recomputes automatically
on page load (using whatever's already on the profile) and again
whenever age/height/weight loses focus or Enter is pressed, or the
gender/activity dropdowns change.

The saved history entry also resets automatically every 24 hours:
even if age/gender/height/weight/activity level haven't changed, a
fresh history row is written once a rolling 24-hour window has
elapsed since the last save — the same "resets on a rolling 24h
window, not at midnight" pattern used elsewhere in this app (see
database.get_calories_consumed_today / get_water_intake_today). This
happens automatically on load (comparing against the most recent
saved record) and, if the window is left open, on an hourly check —
no action needed from the user.

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py (`state('zoomed')`,
falling back to `-zoomed` or a manual full-screen geometry).

Mifflin-St Jeor Equation:
    Male:   BMR = 10*weight(kg) + 6.25*height(cm) - 5*age + 5
    Female: BMR = 10*weight(kg) + 6.25*height(cm) - 5*age - 161
    Other:  average of the male/female constant, since the equation
            doesn't define a third case — a documented approximation,
            not a clinical standard.

Run:
    pip install customtkinter mysql-connector-python
    python calorie_calculator.py
"""

from datetime import datetime, timedelta

import mysql.connector
import customtkinter as ctk
from tkinter import messagebox

import database
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
COLOR_ENTRY_BG = "#0B3D3A"
COLOR_MUTED = "#6FA69E"
COLOR_ERROR = "#FF8A80"

WINDOW_W, WINDOW_H = 460, 820
MIN_W, MIN_H = 380, 620
MAX_W, MAX_H = 560, 920

GENDER_OPTIONS = ["Male", "Female", "Other"]
ACTIVITY_OPTIONS = [
    "Sedentary", "Lightly Active", "Moderately Active",
    "Very Active", "Extra Active",
]

# Standard activity multipliers used to convert BMR -> TDEE
ACTIVITY_MULTIPLIERS = {
    "Sedentary": 1.2,
    "Lightly Active": 1.375,
    "Moderately Active": 1.55,
    "Very Active": 1.725,
    "Extra Active": 1.9,
}

ACTIVITY_DESCRIPTIONS = {
    "Sedentary": "little or no exercise",
    "Lightly Active": "light exercise 1-3 days/week",
    "Moderately Active": "moderate exercise 3-5 days/week",
    "Very Active": "hard exercise 6-7 days/week",
    "Extra Active": "very hard exercise & physical job",
}

# Rough calorie adjustments for a fitness goal, applied on top of TDEE.
# These are conservative, commonly-cited defaults — not personalized advice.
GOAL_ADJUSTMENTS = {
    "Weight Loss": -500,
    "Weight Maintenance": 0,
    "Muscle Gain": 300,
    "General Fitness": 0,
}

# A saved history entry is treated as "stale" once this much time has
# passed since it was written — at that point the next calculation
# (even with identical inputs) writes a fresh row instead of being
# deduped, effectively resetting on a rolling 24-hour window.
SAVE_RESET_WINDOW = timedelta(hours=24)

# How often (ms) to re-check, while the window is left open, whether
# the 24-hour window has elapsed and a fresh entry should be saved.
AUTO_CHECK_MS = 60 * 60 * 1000  # 1 hour


def calculate_bmr(age: int, gender: str, height_cm: float, weight_kg: float) -> float:
    """Mifflin-St Jeor Equation."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender == "Male":
        return base + 5
    elif gender == "Female":
        return base - 161
    else:
        # No third case in the original equation; average the two
        # constants (+5 and -161) as a documented approximation.
        return base + ((5 + -161) / 2)


def calculate_tdee(bmr: float, activity_level: str) -> float:
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.2)
    return bmr * multiplier


class CalorieCalculatorPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.on_back = on_back
        self.user_email = self.user_data.get("email")

        # Dedupe/reset state: the last (age, gender, height, weight,
        # activity_level) tuple that was actually saved, and when. A
        # new calculation only writes a fresh history row if the inputs
        # changed OR SAVE_RESET_WINDOW has elapsed since _last_saved_at.
        self._last_saved_key = None
        self._last_saved_at = None
        self._auto_check_job = None

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Daily Calorie Calculator")
        self.configure(fg_color=COLOR_BG)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        # Deferred, same reasoning as login_page.py / dashboard.py /
        # bmi_calculator.py: CustomTkinter schedules some of its own
        # window/DPI setup via internal after() calls right after the
        # window is created, and calling state('zoomed') too early gets
        # silently overwritten by that later setup. Queuing it with
        # after() lets it run after that setup has settled.
        self.after(10, self._maximize_window)

        self._build_ui()
        self._load_history()
        self._load_last_saved_state()

        # Auto-calculate immediately using the profile's saved age/
        # gender/height/weight/activity level, so the result shows up
        # without any action from the user. If the last saved entry is
        # more than 24 hours old, this also writes a fresh row.
        self._handle_calculate(silent=True)

        # Keep checking hourly in case the window is left open across
        # the 24-hour boundary, so the reset happens without the user
        # touching anything.
        self._schedule_auto_check()

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

        ctk.CTkLabel(
            outer, text="Daily Calorie Calculator",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 4))
        ctk.CTkLabel(
            outer, text="Uses the Mifflin-St Jeor Equation to estimate your\n"
                        "BMR and daily calorie needs",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
            justify="center",
        ).pack(pady=(0, 16))

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16)

        # ---- Inputs ------------------------------------------------
        self.age_entry = self._add_entry(
            scroll, "Age", str(self.user_data.get("age") or ""))
        self.age_entry.bind("<Return>", lambda _e: self._handle_calculate())
        self.age_entry.bind("<FocusOut>", lambda _e: self._handle_calculate())

        self.gender_menu = self._add_option_menu(
            scroll, "Gender", GENDER_OPTIONS, self.user_data.get("gender"),
            command=lambda _selected: self._handle_calculate(),
        )

        self.height_entry = self._add_entry(
            scroll, "Height (cm)", str(self.user_data.get("height_cm") or ""))
        self.height_entry.bind("<Return>", lambda _e: self._handle_calculate())
        self.height_entry.bind("<FocusOut>", lambda _e: self._handle_calculate())

        self.weight_entry = self._add_entry(
            scroll, "Weight (kg)", str(self.user_data.get("weight_kg") or ""))
        self.weight_entry.bind("<Return>", lambda _e: self._handle_calculate())
        self.weight_entry.bind("<FocusOut>", lambda _e: self._handle_calculate())

        self.activity_menu = self._add_option_menu(
            scroll, "Activity Level", ACTIVITY_OPTIONS, self.user_data.get("activity_level"),
            command=lambda _selected: self._handle_calculate(),
        )

        self.error_label = ctk.CTkLabel(
            scroll, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=340,
        )
        self.error_label.pack(fill="x", pady=(6, 20))

        # ---- Result card --------------------------------------------
        self.result_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=14)
        self.result_card.pack(fill="x", pady=(0, 20))

        result_grid = ctk.CTkFrame(self.result_card, fg_color="transparent")
        result_grid.pack(fill="x", padx=16, pady=(20, 4))
        result_grid.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            result_grid, text="BMR", font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            result_grid, text="Daily Calories (TDEE)", font=ctk.CTkFont(size=12),
            text_color=COLOR_ACCENT_SOFT,
        ).grid(row=0, column=1, sticky="w")

        self.bmr_value_label = ctk.CTkLabel(
            result_grid, text="—", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_WHITE,
        )
        self.bmr_value_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.tdee_value_label = ctk.CTkLabel(
            result_grid, text="—", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_ACCENT,
        )
        self.tdee_value_label.grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.activity_note_label = ctk.CTkLabel(
            self.result_card, text="",
            font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
            wraplength=340, justify="center",
        )
        self.activity_note_label.pack(padx=20, pady=(10, 4))

        self.goal_note_label = ctk.CTkLabel(
            self.result_card, text="",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_ACCENT_SOFT,
            wraplength=340, justify="center",
        )
        self.goal_note_label.pack(padx=20, pady=(0, 20))

        # ---- History --------------------------------------------------
        history_header = ctk.CTkFrame(scroll, fg_color="transparent")
        history_header.pack(fill="x", pady=(4, 6))
        ctk.CTkLabel(
            history_header, text="Calorie History",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).pack(side="left")
        ctk.CTkButton(
            history_header, text="Clear History", width=100, height=26,
            corner_radius=8, fg_color="transparent",
            border_width=1, border_color=COLOR_TRACK,
            hover_color=COLOR_TRACK, text_color=COLOR_ERROR,
            font=ctk.CTkFont(size=11),
            command=self._handle_clear_history,
        ).pack(side="right")

        self.history_container = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=14)
        self.history_container.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self.history_container, text="No calorie history yet.",
            font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
        ).pack(padx=16, pady=20)

    def _add_entry(self, parent, label_text, initial_value):
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(10, 0))
        entry = ctk.CTkEntry(
            parent, height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
        )
        entry.insert(0, initial_value)
        entry.pack(fill="x", pady=(4, 0))
        return entry

    def _add_option_menu(self, parent, label_text, options, current_value, command=None):
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(10, 0))
        menu = ctk.CTkOptionMenu(
            parent, values=options,
            height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, button_color=COLOR_TRACK,
            button_hover_color=COLOR_ACCENT, text_color=COLOR_WHITE,
            command=command,
        )
        menu.set(current_value if current_value in options else options[0])
        menu.pack(fill="x", pady=(4, 0))
        return menu

    # -------------------------------------------------------- reset state
    def _load_last_saved_state(self):
        """Seeds _last_saved_key/_last_saved_at from the most recent
        history row already in the database, so the 24-hour reset
        window is measured from the actual last save — not reset to
        "now" every time the page is reopened."""
        if not self.user_email:
            return
        try:
            records = database.get_calorie_history(self.user_email, limit=1)
        except mysql.connector.Error:
            return
        if not records:
            return
        latest = records[0]
        self._last_saved_key = (
            latest["age"], latest["gender"], latest["height_cm"],
            latest["weight_kg"], latest["activity_level"],
        )
        self._last_saved_at = latest["created_at"]

    def _schedule_auto_check(self):
        self._auto_check_job = self.after(AUTO_CHECK_MS, self._auto_check_tick)

    def _auto_check_tick(self):
        # Silent: this is a background check, not a user action — only
        # a genuinely broken profile value would need surfacing, and
        # that would already have shown up when the page was opened.
        self._handle_calculate(silent=True)
        self._schedule_auto_check()

    def destroy(self):
        if self._auto_check_job is not None:
            self.after_cancel(self._auto_check_job)
            self._auto_check_job = None
        super().destroy()

    # ------------------------------------------------------------ compute
    def _handle_calculate(self, event=None, silent=False):
        """Recomputes BMR/TDEE and saves the result. Runs automatically —
        on page load (silent=True, so incomplete/placeholder fields don't
        flash an error) and whenever age/height/weight loses focus or
        Enter is pressed, or gender/activity level changes (silent=False,
        so a genuinely invalid value does show an error), and on the
        hourly background check (silent=True). There's no separate
        "Calculate" button — these are the only triggers.

        A history row is written whenever the inputs changed since the
        last save, OR the last save is more than SAVE_RESET_WINDOW (24h)
        old — so the saved calorie data resets automatically once a day
        even if nothing on the profile changed."""
        age_raw = self.age_entry.get().strip()
        height_raw = self.height_entry.get().strip()
        weight_raw = self.weight_entry.get().strip()

        if not age_raw.isdigit() or not (1 <= int(age_raw) <= 120):
            if not silent:
                self.error_label.configure(text="Enter a valid age between 1 and 120.")
            return
        age = int(age_raw)

        try:
            height = float(height_raw)
            if not (50 <= height <= 250):
                raise ValueError
        except ValueError:
            if not silent:
                self.error_label.configure(text="Enter a valid height between 50 and 250 cm.")
            return

        try:
            weight = float(weight_raw)
            if not (20 <= weight <= 300):
                raise ValueError
        except ValueError:
            if not silent:
                self.error_label.configure(text="Enter a valid weight between 20 and 300 kg.")
            return

        if not silent:
            self.error_label.configure(text="")

        gender = self.gender_menu.get()
        activity_level = self.activity_menu.get()

        bmr = calculate_bmr(age, gender, height, weight)
        tdee = calculate_tdee(bmr, activity_level)

        self.bmr_value_label.configure(text=f"{bmr:.0f} kcal")
        self.tdee_value_label.configure(text=f"{tdee:.0f} kcal")
        self.activity_note_label.configure(
            text=f"Based on \"{activity_level}\" ({ACTIVITY_DESCRIPTIONS.get(activity_level, '')})"
        )

        fitness_goal = self.user_data.get("fitness_goal")
        if fitness_goal in GOAL_ADJUSTMENTS:
            adjustment = GOAL_ADJUSTMENTS[fitness_goal]
            target = tdee + adjustment
            if adjustment == 0:
                self.goal_note_label.configure(
                    text=f"For {fitness_goal.lower()}, aim for about {target:.0f} kcal/day."
                )
            else:
                direction = "below" if adjustment < 0 else "above"
                self.goal_note_label.configure(
                    text=f"For {fitness_goal.lower()}, a common target is about "
                         f"{target:.0f} kcal/day ({abs(adjustment):.0f} kcal {direction} maintenance)."
                )
        else:
            self.goal_note_label.configure(text="")

        if self.user_email:
            save_key = (age, gender, height, weight, activity_level)
            now = datetime.now()
            window_elapsed = (
                self._last_saved_at is None
                or (now - self._last_saved_at) >= SAVE_RESET_WINDOW
            )
            if save_key != self._last_saved_key or window_elapsed:
                try:
                    database.insert_calorie_record(
                        self.user_email, age, gender, height, weight, activity_level, bmr, tdee
                    )
                    self._last_saved_key = save_key
                    self._last_saved_at = now
                except mysql.connector.Error as db_err:
                    self.error_label.configure(text=f"Saved locally, but database error: {db_err}")

                self._load_history()

            self.user_data["age"] = age
            self.user_data["gender"] = gender
            self.user_data["height_cm"] = height
            self.user_data["weight_kg"] = weight
            self.user_data["activity_level"] = activity_level
            session.set_current_user(self.user_data)

    # ------------------------------------------------------------ history
    def _load_history(self):
        if not self.user_email:
            return

        try:
            records = database.get_calorie_history(self.user_email, limit=10)
        except mysql.connector.Error as db_err:
            self.error_label.configure(text=f"Couldn't load history: {db_err}")
            return

        for child in self.history_container.winfo_children():
            child.destroy()

        if not records:
            ctk.CTkLabel(
                self.history_container, text="No calorie history yet.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(padx=16, pady=20)
            return

        for record in records:
            row = ctk.CTkFrame(self.history_container, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=6)

            ctk.CTkLabel(
                row, text=f"BMR {record['bmr']:.0f} · TDEE {record['tdee']:.0f} kcal",
                font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_WHITE,
            ).pack(side="left")

            created = record["created_at"]
            date_str = created.strftime("%d %b %Y") if hasattr(created, "strftime") else str(created)
            ctk.CTkLabel(
                row, text=date_str,
                font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
            ).pack(side="right")

    def _handle_clear_history(self):
        if not self.user_email:
            return
        if not messagebox.askyesno(
            "Clear Calorie History",
            "This will permanently delete all of your saved calorie calculations. Continue?",
            parent=self,
        ):
            return
        try:
            database.clear_calorie_history(self.user_email)
        except mysql.connector.Error as db_err:
            self.error_label.configure(text=f"Couldn't clear history: {db_err}")
            return
        self._last_saved_key = None  # let the next calculation save fresh
        self._last_saved_at = None
        self._load_history()

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
        "gender": "Male",
        "height_cm": 165,
        "weight_kg": 60,
        "activity_level": "Moderately Active",
        "fitness_goal": "Weight Loss",
    }
    app = CalorieCalculatorPage(user_data=demo_user)
    app.mainloop()