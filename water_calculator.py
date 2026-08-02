"""
water_calculator.py
---------------------
AI Diet Chart & Nutrition Calculator — Water Intake Calculator
Healthcare-themed, built with CustomTkinter.

Calculates a recommended daily water intake from body weight and
activity level, then lets the user log water as they drink it through
the day and see progress toward that goal on a progress bar, plus a
few general hydration tips.

The on-screen tally is seeded from the user's real rolling-24-hour
water total (database.get_water_intake_today) so it matches what the
Dashboard shows, instead of always starting back at 0 when this page
reopens.

Formula (a commonly cited general guideline, not personalized medical
advice):
    base = weight_kg * 30 ml
    + an activity-level adjustment (more activity -> more fluid loss)

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py /
about_page.py / feedback_page.py / exercise_recommendation.py /
help_contact.py / diet_planner.py / meal_planner.py /
forgot_password_page.py / nutrition_calculator.py / profile_page.py /
progress_tracker.py / registration_page.py (`state('zoomed')`,
falling back to `-zoomed` or a manual full-screen geometry).

Run:
    pip install customtkinter
    python water_calculator.py
"""

import customtkinter as ctk
import mysql.connector

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
COLOR_WATER = "#5DADE2"  # a "water blue" accent for the progress bar

MIN_W, MIN_H = 380, 600

ACTIVITY_OPTIONS = [
    "Sedentary", "Lightly Active", "Moderately Active",
    "Very Active", "Extra Active",
]

# Extra fluid recommended on top of the base weight-based amount,
# to account for water lost through sweat/exertion.
ACTIVITY_ADJUSTMENTS_ML = {
    "Sedentary": 0,
    "Lightly Active": 300,
    "Moderately Active": 500,
    "Very Active": 750,
    "Extra Active": 1000,
}

ML_PER_KG = 30  # commonly cited general guideline (~30-35 ml per kg)
GLASS_ML = 250

HYDRATION_TIPS = [
    "Keep a water bottle with you so it's easy to sip throughout the day.",
    "Drink a glass of water with each meal and snack.",
    "Set reminders if you tend to forget to drink water during busy hours.",
    "Fruits and vegetables like cucumber, watermelon, and oranges add to your fluid intake too.",
    "Thirst and dark yellow urine are simple signs you may need more water.",
    "Spread your intake across the day rather than drinking it all at once.",
]

QUICK_ADD_OPTIONS = [
    ("Glass", 250),
    ("Bottle", 500),
    ("Large Bottle", 1000),
]


def calculate_water_goal_ml(weight_kg: float, activity_level: str) -> float:
    base = weight_kg * ML_PER_KG
    adjustment = ACTIVITY_ADJUSTMENTS_ML.get(activity_level, 0)
    return base + adjustment


class WaterCalculatorPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.on_back = on_back

        self.goal_ml = None
        self.current_ml = 0.0

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Water Intake Calculator")
        self.configure(fg_color=COLOR_BG)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        # Deferred, same reasoning as the rest of the app's pages:
        # CustomTkinter schedules some of its own window/DPI setup via
        # internal after() calls right after the window is created, and
        # calling state('zoomed') too early gets silently overwritten by
        # that later setup. Queuing it with after() lets it run after
        # that setup has settled.
        self.after(10, self._maximize_window)

        self._build_ui()

        # Auto-calculate immediately using the profile's saved weight/
        # activity level, so the goal + progress show up without any
        # action from the user.
        self._handle_calculate(silent=True)

    # ------------------------------------------------------------ window
    def _maximize_window(self):
        """Opens the page filling the screen instead of a small centered
        window. `state('zoomed')` is the normal way to do this on
        Windows and most Linux window managers; macOS's Tk build
        doesn't support that state string and raises a TclError, so it
        falls back to `-zoomed` (some Linux WMs use this attribute
        instead), and finally to manually sizing/positioning the window
        to the full screen if neither is available.

        `update_idletasks()` before and after: the "before" call flushes
        any geometry CustomTkinter itself has queued so we're not racing
        its own setup, and the "after" call forces the centered content
        column to immediately recompute against the new window size
        instead of waiting for the next idle cycle."""
        self.update_idletasks()

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

        self.update_idletasks()

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
            outer, text="💧 Water Intake Calculator",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 4))
        ctk.CTkLabel(
            outer, text="A general estimate based on body weight and activity level",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
            wraplength=340, justify="center",
        ).pack(pady=(0, 16))

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16)

        # ---- Inputs ------------------------------------------------
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

        # ---- Result + progress card --------------------------------
        self.result_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=14)
        self.result_card.pack(fill="x", pady=(0, 20))

        self.goal_label = ctk.CTkLabel(
            self.result_card, text="Enter your weight and activity level above",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_WHITE,
            wraplength=340, justify="center",
        )
        self.goal_label.pack(pady=(20, 4), padx=16)

        self.glasses_label = ctk.CTkLabel(
            self.result_card, text="", font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
        )
        self.glasses_label.pack(pady=(0, 14))

        self.progress_bar = ctk.CTkProgressBar(
            self.result_card, height=16, corner_radius=8,
            fg_color=COLOR_TRACK, progress_color=COLOR_WATER,
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 6))

        self.progress_text_label = ctk.CTkLabel(
            self.result_card, text="0 ml / — ml logged today",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        )
        self.progress_text_label.pack(pady=(0, 16))

        quick_add_row = ctk.CTkFrame(self.result_card, fg_color="transparent")
        quick_add_row.pack(pady=(0, 16))
        for label, ml in QUICK_ADD_OPTIONS:
            ctk.CTkButton(
                quick_add_row, text=f"+ {label}\n{ml} ml", width=100, height=50,
                corner_radius=10, fg_color=COLOR_ENTRY_BG, hover_color=COLOR_TRACK,
                text_color=COLOR_WHITE, font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda m=ml: self._handle_quick_add(m),
            ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.result_card, text="Reset Today's Log", width=140, height=28,
            corner_radius=8, fg_color="transparent",
            border_width=1, border_color=COLOR_TRACK,
            hover_color=COLOR_TRACK, text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=11),
            command=self._handle_reset,
        ).pack(pady=(0, 18))

        # ---- Hydration tips ----------------------------------------
        ctk.CTkLabel(
            scroll, text="Hydration Tips",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).pack(anchor="w", pady=(4, 6))

        tips_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=14)
        tips_card.pack(fill="x", pady=(0, 16))
        for tip in HYDRATION_TIPS:
            row = ctk.CTkFrame(tips_card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(
                row, text="💧", font=ctk.CTkFont(size=12),
            ).pack(side="left", padx=(0, 8), anchor="n")
            ctk.CTkLabel(
                row, text=tip, font=ctk.CTkFont(size=12), text_color=COLOR_WHITE,
                wraplength=380, justify="left", anchor="w",
            ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            scroll,
            text="This is a general estimate, not personalized medical advice. "
                 "If you have kidney, heart, or other conditions that affect fluid "
                 "intake, or are pregnant, check with a healthcare provider for "
                 "guidance specific to you.",
            font=ctk.CTkFont(size=10), text_color=COLOR_MUTED,
            wraplength=380, justify="left",
        ).pack(fill="x", pady=(0, 16))

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
            button_hover_color=COLOR_WATER, text_color=COLOR_WHITE,
            command=command,
        )
        menu.set(current_value if current_value in options else options[0])
        menu.pack(fill="x", pady=(4, 0))
        return menu

    # ------------------------------------------------------------ compute
    def _handle_calculate(self, event=None, silent=False):
        """Recomputes the water goal (and re-seeds today's logged total).
        Runs automatically — on page load (silent=True, so a not-yet-filled
        weight doesn't flash an error), and whenever the activity level
        changes or the weight field loses focus / Enter is pressed
        (silent=False, so a genuinely invalid weight does show an error).
        There's no separate "Calculate" button — these are the only
        triggers."""
        weight_raw = self.weight_entry.get().strip()

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

        activity_level = self.activity_menu.get()
        self.goal_ml = calculate_water_goal_ml(weight, activity_level)

        # Seed the on-screen tally from the user's real rolling-24-hour
        # total (same number the Dashboard shows) instead of always
        # restarting at 0 when this page reopens.
        user_email = self.user_data.get("email")
        self.current_ml = 0.0
        if user_email:
            try:
                self.current_ml = database.get_water_intake_today(user_email)
            except mysql.connector.Error:
                pass

        liters = self.goal_ml / 1000
        self.goal_label.configure(
            text=f"Recommended intake: {self.goal_ml:.0f} ml ({liters:.1f} L) per day"
        )
        glasses = self.goal_ml / GLASS_ML
        self.glasses_label.configure(text=f"That's about {glasses:.0f} glasses ({GLASS_ML}ml each)")

        if self.user_data.get("weight_kg") is not None:
            self.user_data["weight_kg"] = weight
        self.user_data["activity_level"] = activity_level
        if session.get_current_user():
            session.set_current_user(self.user_data)

        self._update_progress()

    # -------------------------------------------------------------- log
    def _handle_quick_add(self, ml):
        if self.goal_ml is None:
            self.error_label.configure(text="Enter a valid weight above to set your intake goal.")
            return
        self.current_ml += ml
        self._update_progress()

        user_email = self.user_data.get("email")
        if user_email:
            try:
                database.log_water_intake(user_email, ml)
            except (ValueError, mysql.connector.Error):
                pass  # don't block the UI if logging fails; the on-screen tally still works

    def _handle_reset(self):
        self.current_ml = 0.0
        self._update_progress()

    def _update_progress(self):
        if self.goal_ml is None:
            return
        fraction = min(self.current_ml / self.goal_ml, 1.0) if self.goal_ml else 0
        self.progress_bar.set(fraction)
        self.progress_text_label.configure(
            text=f"{self.current_ml:.0f} ml / {self.goal_ml:.0f} ml logged today "
                 f"({fraction * 100:.0f}%)"
        )

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
        "weight_kg": 70,
        "activity_level": "Moderately Active",
    }
    app = WaterCalculatorPage(user_data=demo_user)
    app.mainloop()