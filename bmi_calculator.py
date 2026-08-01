"""
bmi_calculator.py
------------------
AI Diet Chart & Nutrition Calculator — BMI Calculator Page
Healthcare-themed, built with CustomTkinter.

Accepts height and weight and calculates BMI automatically as you
type (no button to press) — shows the BMI category with a color
indicator and short health advice, and saves each new calculation to
MySQL (bmi_history table) so the user can see their BMI over time.
A "Clear History" button wipes that saved history.

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py (`state('zoomed')`, falling back to
`-zoomed` or a manual full-screen geometry). The content frame still
uses the same responsive sizing logic as before internally, so it
stays comfortably readable rather than stretching every element edge
to edge on large screens.

Run:
    pip install customtkinter mysql-connector-python
    python bmi_calculator.py
"""

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

# BMI category color indicators
COLOR_UNDERWEIGHT = "#5DADE2"   # blue
COLOR_NORMAL = "#2FD3B0"        # accent green
COLOR_OVERWEIGHT = "#F4D03F"    # yellow
COLOR_OBESE = "#FF6B6B"         # red

WINDOW_W, WINDOW_H = 900, 1000
MIN_W, MIN_H = 400, 400
MAX_W, MAX_H = 900, 1000

# How long to wait (ms) after the user stops typing before recalculating
# and saving — avoids firing a DB write on every single keystroke.
AUTO_CALC_DEBOUNCE_MS = 600

BMI_CATEGORIES = [
    # (upper_bound_exclusive, label, color, advice)
    (18.5, "Underweight", COLOR_UNDERWEIGHT,
     "You may be underweight. Consider a nutrient-rich diet with enough "
     "calories and protein, and speak with a healthcare provider about a "
     "healthy weight gain plan."),
    (25.0, "Normal", COLOR_NORMAL,
     "Your BMI is in the healthy range. Keep up a balanced diet and "
     "regular physical activity to maintain it."),
    (30.0, "Overweight", COLOR_OVERWEIGHT,
     "Your BMI is a bit above the healthy range. Small changes — more "
     "daily movement, more whole foods, less processed food — can help "
     "bring it down over time."),
    (float("inf"), "Obese", COLOR_OBESE,
     "Your BMI is in a range linked to higher health risk. It's worth "
     "talking to a healthcare provider about a personalized, sustainable "
     "weight management plan."),
]


def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)


def classify_bmi(bmi: float):
    """Returns (label, color, advice) for a given BMI value."""
    for upper_bound, label, color, advice in BMI_CATEGORIES:
        if bmi < upper_bound:
            return label, color, advice
    return BMI_CATEGORIES[-1][1:]  # fallback, shouldn't be reached


class BMICalculatorPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.on_back = on_back
        self.user_email = self.user_data.get("email")

        # Debounce timer id for auto-calculation, and the last
        # (height, weight) pair that was actually saved to history —
        # used to avoid writing a duplicate row when nothing changed.
        self._debounce_job = None
        self._last_saved = None

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — BMI Calculator")
        self.configure(fg_color=COLOR_BG)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        # Deferred, same reasoning as login_page.py / dashboard.py:
        # CustomTkinter schedules some of its own window/DPI setup via
        # internal after() calls right after the window is created, and
        # calling state('zoomed') too early gets silently overwritten by
        # that later setup. Queuing it with after() lets it run after
        # that setup has settled.
        self.after(10, self._maximize_window)

        self._build_ui()
        self._load_history()
        # If height/weight were prefilled from the user's profile, show
        # the BMI immediately (but don't write a history row for it —
        # only fresh edits get saved).
        self._recalculate(save=False, show_errors=False)

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
            outer, text="BMI Calculator",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 4))
        ctk.CTkLabel(
            outer, text="Your BMI updates automatically as you type",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
            wraplength=340, justify="center",
        ).pack(pady=(0, 16))

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16)

        # ---- Inputs ------------------------------------------------
        self.height_entry = self._add_entry(
            scroll, "Height (cm)", str(self.user_data.get("height_cm") or ""))
        self.weight_entry = self._add_entry(
            scroll, "Weight (kg)", str(self.user_data.get("weight_kg") or ""))

        # Recalculate (debounced) on every keystroke in either field —
        # this is what makes BMI update automatically without a button.
        self.height_entry.bind("<KeyRelease>", self._on_input_changed)
        self.weight_entry.bind("<KeyRelease>", self._on_input_changed)

        self.error_label = ctk.CTkLabel(
            scroll, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
        )
        self.error_label.pack(fill="x", pady=(6, 0))

        # ---- Result card --------------------------------------------
        self.result_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=14)
        self.result_card.pack(fill="x", pady=(16, 20))

        self.bmi_value_label = ctk.CTkLabel(
            self.result_card, text="—",
            font=ctk.CTkFont(size=32, weight="bold"), text_color=COLOR_WHITE,
        )
        self.bmi_value_label.pack(pady=(20, 2))

        self.category_badge = ctk.CTkLabel(
            self.result_card, text="Enter your height and weight",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_ACCENT_SOFT, fg_color="transparent",
            corner_radius=10,
        )
        self.category_badge.pack(pady=(0, 10))

        self.advice_label = ctk.CTkLabel(
            self.result_card, text="",
            font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            wraplength=320, justify="center",
        )
        self.advice_label.pack(padx=20, pady=(0, 20))

        # ---- History --------------------------------------------------
        history_header = ctk.CTkFrame(scroll, fg_color="transparent")
        history_header.pack(fill="x", pady=(4, 6))
        ctk.CTkLabel(
            history_header, text="BMI History",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).pack(side="left")
        ctk.CTkButton(
            history_header, text="Clear History", width=110, height=26,
            corner_radius=8, fg_color="transparent", hover_color=COLOR_TRACK,
            border_width=1, border_color=COLOR_ERROR, text_color=COLOR_ERROR,
            font=ctk.CTkFont(size=11), command=self._handle_clear_history,
        ).pack(side="right")

        self.history_container = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=14)
        self.history_container.pack(fill="x", pady=(0, 16))

        self.history_empty_label = ctk.CTkLabel(
            self.history_container, text="No BMI history yet.",
            font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
        )
        self.history_empty_label.pack(padx=16, pady=20)

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

    # ------------------------------------------------------------ compute
    def _on_input_changed(self, event=None):
        """Debounces keystrokes: waits until the user pauses typing for
        AUTO_CALC_DEBOUNCE_MS before recalculating, instead of
        recalculating (and potentially saving) on every keystroke."""
        if self._debounce_job is not None:
            self.after_cancel(self._debounce_job)
        self._debounce_job = self.after(AUTO_CALC_DEBOUNCE_MS, self._recalculate)

    def _recalculate(self, save: bool = True, show_errors: bool = True):
        """Reads the current height/weight fields, updates the BMI
        display, and (if `save` is True and the values are valid and
        new) saves a history row. Called automatically after the user
        pauses typing."""
        self._debounce_job = None

        height_raw = self.height_entry.get().strip()
        weight_raw = self.weight_entry.get().strip()

        # Nothing typed yet in one or both fields — reset quietly,
        # no error message needed.
        if not height_raw or not weight_raw:
            if show_errors:
                self.error_label.configure(text="")
            self._reset_result_display()
            return

        try:
            height = float(height_raw)
            if not (50 <= height <= 250):
                raise ValueError
        except ValueError:
            if show_errors:
                self.error_label.configure(text="Enter a valid height between 50 and 250 cm.")
            self._reset_result_display()
            return

        try:
            weight = float(weight_raw)
            if not (20 <= weight <= 300):
                raise ValueError
        except ValueError:
            if show_errors:
                self.error_label.configure(text="Enter a valid weight between 20 and 300 kg.")
            self._reset_result_display()
            return

        self.error_label.configure(text="")

        bmi = calculate_bmi(height, weight)
        label, color, advice = classify_bmi(bmi)

        self.bmi_value_label.configure(text=f"{bmi:.1f}")
        self.category_badge.configure(text=f"  {label}  ", fg_color=color, text_color="#0B3D3A")
        self.advice_label.configure(text=advice)

        if not save or not self.user_email:
            return

        # Skip saving a duplicate row if height/weight haven't actually
        # changed since the last save (e.g. this call came from initial
        # load, or the user typed something then typed it right back).
        current = (height, weight)
        if current == self._last_saved:
            return

        try:
            database.insert_bmi_record(self.user_email, height, weight, bmi, label)
            self._last_saved = current
        except mysql.connector.Error as db_err:
            self.error_label.configure(text=f"Shown here, but couldn't save to history: {db_err}")
            return
        except ValueError as val_err:
            self.error_label.configure(text=str(val_err))
            return

        # Keep session in sync with the latest height/weight
        self.user_data["height_cm"] = height
        self.user_data["weight_kg"] = weight
        session.set_current_user(self.user_data)

        self._load_history()

    def _reset_result_display(self):
        self.bmi_value_label.configure(text="—")
        self.category_badge.configure(
            text="Enter your height and weight", fg_color="transparent", text_color=COLOR_ACCENT_SOFT,
        )
        self.advice_label.configure(text="")

    # ------------------------------------------------------------ history
    def _load_history(self):
        if not self.user_email:
            return

        try:
            records = database.get_bmi_history(self.user_email, limit=10)
        except mysql.connector.Error as db_err:
            self.error_label.configure(text=f"Couldn't load history: {db_err}")
            return

        for child in self.history_container.winfo_children():
            child.destroy()

        if not records:
            ctk.CTkLabel(
                self.history_container, text="No BMI history yet.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(padx=16, pady=20)
            return

        for record in records:
            _, color, _ = classify_bmi(record["bmi"])
            row = ctk.CTkFrame(self.history_container, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=6)

            ctk.CTkLabel(
                row, text=f"● ", font=ctk.CTkFont(size=13), text_color=color,
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=f"{record['bmi']:.1f} · {record['category']}",
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
            "Clear History", "Delete all saved BMI history? This can't be undone."
        ):
            return
        try:
            database.clear_bmi_history(self.user_email)
        except mysql.connector.Error as db_err:
            messagebox.showerror("Clear History", f"Couldn't clear history: {db_err}")
            return
        self._last_saved = None
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
        "height_cm": 165,
        "weight_kg": 60,
    }
    app = BMICalculatorPage(user_data=demo_user)
    app.mainloop()