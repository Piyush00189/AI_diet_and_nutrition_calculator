"""
progress_tracker.py
----------------------
AI Diet Chart & Nutrition Calculator — Progress Tracker
Healthcare-themed, built with CustomTkinter + Matplotlib.

Shows four trend graphs — BMI, Weight, Calorie Intake, and Water
Intake — over time, pulled from MySQL, with a Weekly (last 7 days) /
Monthly (last 30 days) toggle.

The charts refresh automatically — on a timer (every
AUTO_REFRESH_MS) and again whenever this window regains focus — so
new BMI/food/water entries logged elsewhere in the app show up here
without the user having to close and reopen the page.

Data sources:
  - BMI & Weight: bmi_history (created whenever the BMI Calculator is used)
  - Calorie Intake: calorie_log (a running daily total, updated whenever
    a food is added in the Nutrition Calculator)
  - Water Intake: water_log (a running daily total, updated whenever
    water is logged in the Water Intake Calculator)

If you haven't used those pages yet, the corresponding graph will
just show "No data yet for this period" — that's expected, not a bug.

Run:
    pip install customtkinter mysql-connector-python matplotlib
    python progress_tracker.py
"""

from datetime import datetime

import mysql.connector
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

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
COLOR_MUTED = "#6FA69E"
COLOR_ERROR = "#FF8A80"
COLOR_WATER = "#5DADE2"
COLOR_BMI = "#2FD3B0"
COLOR_WEIGHT = "#F4D03F"
COLOR_CALORIE = "#FF8A65"

WINDOW_W, WINDOW_H = 1000, 760
MIN_W, MIN_H = 780, 600

FILTERS = {"Weekly": 7, "Monthly": 30}

# How often (ms) to automatically re-pull data and redraw the charts,
# so new entries logged elsewhere in the app (BMI Calculator, Nutrition
# Calculator, Water Intake Calculator) show up here on their own.
AUTO_REFRESH_MS = 30_000


class ProgressTrackerPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.user_email = self.user_data.get("email")
        self.on_back = on_back
        self.filter_days = FILTERS["Weekly"]

        # Handle for the pending auto-refresh timer, so it can be
        # cancelled cleanly when the window closes.
        self._refresh_job = None

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Progress Tracker")
        self.configure(fg_color=COLOR_BG)
        win_w, win_h = self._compute_responsive_size()
        self._center_window(win_w, win_h)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        self._build_ui()
        self._refresh_charts()

        # Re-pull data whenever the window regains focus (e.g. the user
        # switched to another page to log something, then came back)...
        self.bind("<FocusIn>", self._on_focus_in)
        # ...and again on a fixed timer, in case the window is just
        # left open and sitting in the background.
        self._schedule_auto_refresh()

    def _compute_responsive_size(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = max(MIN_W, min(int(sw * 0.65), 1300))
        h = max(MIN_H, min(int(sh * 0.85), 950))
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

        header_row = ctk.CTkFrame(outer, fg_color="transparent")
        header_row.pack(fill="x", padx=16, pady=(6, 4))
        ctk.CTkLabel(
            header_row, text="Progress Tracker",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(side="left")

        self.filter_menu = ctk.CTkSegmentedButton(
            header_row, values=list(FILTERS.keys()),
            fg_color=COLOR_TRACK, selected_color=COLOR_ACCENT,
            selected_hover_color="#26B79A", unselected_color=COLOR_TRACK,
            text_color=COLOR_WHITE, text_color_disabled=COLOR_MUTED,
            command=self._handle_filter_change,
        )
        self.filter_menu.set("Weekly")
        self.filter_menu.pack(side="right")

        self.status_label = ctk.CTkLabel(
            outer, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=900,
        )
        self.status_label.pack(fill="x", padx=16, pady=(0, 6))

        self.chart_frame = ctk.CTkFrame(outer, fg_color=COLOR_CARD, corner_radius=14)
        self.chart_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        self.figure = Figure(figsize=(9, 6), dpi=100, facecolor=COLOR_CARD)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _handle_filter_change(self, value):
        self.filter_days = FILTERS.get(value, 7)
        self._refresh_charts()

    # ------------------------------------------------------- auto-refresh
    def _on_focus_in(self, event=None):
        # <FocusIn> also fires for child widgets gaining focus, not just
        # the window itself — only refresh when the toplevel is the
        # actual target, so typing/clicking inside the page doesn't
        # trigger a redraw on every widget focus change.
        if event is not None and event.widget is not self:
            return
        self._refresh_charts()

    def _schedule_auto_refresh(self):
        self._refresh_job = self.after(AUTO_REFRESH_MS, self._auto_refresh_tick)

    def _auto_refresh_tick(self):
        self._refresh_charts()
        self._schedule_auto_refresh()

    def destroy(self):
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        super().destroy()

    # ------------------------------------------------------------- data
    def _refresh_charts(self):
        self.status_label.configure(text="")

        if not self.user_email:
            self.status_label.configure(
                text_color=COLOR_ERROR,
                text="No logged-in user found — log in first to see your progress.",
            )
            self._draw_charts([], [], [], [])
            return

        try:
            bmi_rows = database.get_bmi_history_range(self.user_email, days=self.filter_days)
        except mysql.connector.Error as db_err:
            self.status_label.configure(text_color=COLOR_ERROR, text=f"Couldn't load BMI/weight history: {db_err}")
            bmi_rows = []

        try:
            calorie_rows = database.get_calorie_log(self.user_email, days=self.filter_days)
        except mysql.connector.Error as db_err:
            self.status_label.configure(text_color=COLOR_ERROR, text=f"Couldn't load calorie log: {db_err}")
            calorie_rows = []

        try:
            water_rows = database.get_water_log(self.user_email, days=self.filter_days)
        except mysql.connector.Error as db_err:
            self.status_label.configure(text_color=COLOR_ERROR, text=f"Couldn't load water log: {db_err}")
            water_rows = []

        bmi_points = [(row["created_at"], row["bmi"]) for row in bmi_rows]
        weight_points = [(row["created_at"], row["weight_kg"]) for row in bmi_rows]
        calorie_points = [(row["log_date"], row["total_kcal"]) for row in calorie_rows]
        water_points = [(row["log_date"], row["total_ml"]) for row in water_rows]

        self._draw_charts(bmi_points, weight_points, calorie_points, water_points)

    # ------------------------------------------------------------ drawing
    def _style_axis(self, ax, title, color):
        ax.set_facecolor(COLOR_CARD)
        ax.set_title(title, color=COLOR_WHITE, fontsize=11, fontweight="bold", loc="left")
        ax.tick_params(colors=COLOR_ACCENT_SOFT, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(COLOR_TRACK)
        ax.grid(True, color=COLOR_TRACK, linewidth=0.5, alpha=0.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

    def _plot_series(self, ax, points, title, color, ylabel):
        self._style_axis(ax, title, color)

        if not points:
            ax.text(
                0.5, 0.5, "No data yet for this period",
                transform=ax.transAxes, ha="center", va="center",
                color=COLOR_MUTED, fontsize=9,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            return

        dates = [p[0] if isinstance(p[0], datetime) else datetime.combine(p[0], datetime.min.time()) for p in points]
        values = [p[1] for p in points]

        ax.plot(dates, values, color=color, marker="o", markersize=4, linewidth=2)
        floor = min(values) * 0.98 if min(values) > 0 else 0
        ax.fill_between(dates, values, floor, color=color, alpha=0.15)
        ax.set_ylabel(ylabel, color=COLOR_ACCENT_SOFT, fontsize=9)

        # Rotate this axis's own date labels (rather than figure-wide
        # autofmt_xdate, which only rotates/keeps labels on the bottom
        # row and silently hides them on every other row).
        for label in ax.get_xticklabels():
            label.set_rotation(30)
            label.set_ha("right")

    def _draw_charts(self, bmi_points, weight_points, calorie_points, water_points):
        self.figure.clear()
        self.figure.subplots_adjust(hspace=0.65, wspace=0.3, top=0.94, bottom=0.1, left=0.09, right=0.97)

        ax_bmi = self.figure.add_subplot(2, 2, 1)
        ax_weight = self.figure.add_subplot(2, 2, 2)
        ax_calories = self.figure.add_subplot(2, 2, 3)
        ax_water = self.figure.add_subplot(2, 2, 4)

        self._plot_series(ax_bmi, bmi_points, "BMI", COLOR_BMI, "BMI")
        self._plot_series(ax_weight, weight_points, "Weight (kg)", COLOR_WEIGHT, "kg")
        self._plot_series(ax_calories, calorie_points, "Calorie Intake", COLOR_CALORIE, "kcal")
        self._plot_series(ax_water, water_points, "Water Intake", COLOR_WATER, "ml")

        self.canvas.draw()

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
    }
    app = ProgressTrackerPage(user_data=demo_user)
    app.mainloop()