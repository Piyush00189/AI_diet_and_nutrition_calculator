"""
meal_planner.py
------------------
AI Diet Chart & Nutrition Calculator — Meal Planner
Healthcare-themed, built with CustomTkinter.

A weekly grid: 7 days x 4 meal slots (Breakfast, Lunch, Snacks,
Dinner). Each cell is an editable text field. Existing plans load
from MySQL on open; "Save Changes" saves every edited cell in one go
(new/changed text is upserted, cells cleared to empty are deleted);
each cell also has its own small delete button for an instant,
one-off delete.

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py /
about_page.py / feedback_page.py / exercise_recommendation.py
(`state('zoomed')`, falling back to `-zoomed` or a manual full-screen
geometry).

Run:
    pip install customtkinter mysql-connector-python
    python meal_planner.py
"""

import mysql.connector
import customtkinter as ctk

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
COLOR_SUCCESS = "#8CFFB0"
COLOR_ROW_ALT = "#124742"

MIN_W, MIN_H = 780, 560

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEAL_TYPES = ["Breakfast", "Lunch", "Snacks", "Dinner"]


class MealPlannerPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.user_email = self.user_data.get("email")
        self.on_back = on_back

        self.entries = {}          # (day, meal_type) -> CTkEntry
        self.original_values = {}  # (day, meal_type) -> str (what's currently saved in MySQL)

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Meal Planner")
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
        self._load_plans()

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

        header_row = ctk.CTkFrame(outer, fg_color="transparent")
        header_row.pack(fill="x", padx=16, pady=(6, 4))
        ctk.CTkLabel(
            header_row, text="Weekly Meal Planner",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(side="left")
        self.save_btn = ctk.CTkButton(
            header_row, text="Save Changes", width=140, height=36,
            corner_radius=10, fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_save_all,
        )
        self.save_btn.pack(side="right")

        ctk.CTkLabel(
            outer, text="Plan what you'll eat each day — type in a cell, then Save Changes. "
                        "Clear a cell's text (or hit ✕) to remove that entry.",
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
            wraplength=900, justify="left",
        ).pack(fill="x", padx=16, pady=(0, 4))

        self.status_label = ctk.CTkLabel(
            outer, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=900,
        )
        self.status_label.pack(fill="x", padx=16, pady=(0, 8))

        # ---- Table header (fixed) ---------------------------------------
        self.header_grid = ctk.CTkFrame(outer, fg_color=COLOR_TRACK, corner_radius=8)
        self.header_grid.pack(fill="x", padx=16)
        self.header_grid.grid_columnconfigure(0, weight=0, minsize=110)
        for i in range(1, 5):
            self.header_grid.grid_columnconfigure(i, weight=1, minsize=140)

        ctk.CTkLabel(
            self.header_grid, text="Day", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_WHITE,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        for i, meal_type in enumerate(MEAL_TYPES, start=1):
            ctk.CTkLabel(
                self.header_grid, text=meal_type, font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_WHITE,
            ).grid(row=0, column=i, sticky="w", padx=10, pady=8)

        # ---- Table body (scrollable) -------------------------------------
        self.table_body = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.table_body.pack(fill="both", expand=True, padx=16, pady=(2, 16))
        self.table_body.grid_columnconfigure(0, weight=0, minsize=110)
        for i in range(1, 5):
            self.table_body.grid_columnconfigure(i, weight=1, minsize=140)

        for row_idx, day in enumerate(DAYS):
            row_bg = COLOR_ROW_ALT if row_idx % 2 else "transparent"
            day_cell = ctk.CTkFrame(self.table_body, fg_color=row_bg, corner_radius=6)
            day_cell.grid(row=row_idx, column=0, sticky="nswe", padx=2, pady=2)
            ctk.CTkLabel(
                day_cell, text=day, font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_WHITE,
            ).pack(padx=10, pady=10, anchor="w")

            for col_idx, meal_type in enumerate(MEAL_TYPES, start=1):
                cell = ctk.CTkFrame(self.table_body, fg_color=row_bg, corner_radius=6)
                cell.grid(row=row_idx, column=col_idx, sticky="nswe", padx=2, pady=2)

                entry = ctk.CTkEntry(
                    cell, placeholder_text="—", height=32, corner_radius=8,
                    fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
                )
                entry.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)

                ctk.CTkButton(
                    cell, text="✕", width=24, height=24, corner_radius=6,
                    fg_color="transparent", hover_color=COLOR_TRACK,
                    text_color=COLOR_ERROR, font=ctk.CTkFont(size=11),
                    command=lambda d=day, m=meal_type: self._handle_delete_cell(d, m),
                ).pack(side="left", padx=(0, 8), pady=8)

                self.entries[(day, meal_type)] = entry

    # ------------------------------------------------------------ loading
    def _load_plans(self):
        if not self.user_email:
            self.status_label.configure(
                text_color=COLOR_ERROR,
                text="No logged-in user found — log in first to save/load meal plans.",
            )
            return

        try:
            rows = database.get_meal_plans(self.user_email)
        except mysql.connector.Error as db_err:
            self.status_label.configure(text_color=COLOR_ERROR, text=f"Couldn't load meal plans: {db_err}")
            return

        for row in rows:
            key = (row["day_of_week"], row["meal_type"])
            if key in self.entries:
                self.entries[key].delete(0, "end")
                self.entries[key].insert(0, row["meal_description"])
                self.original_values[key] = row["meal_description"]

    # --------------------------------------------------------------- save
    def _handle_save_all(self):
        if not self.user_email:
            self.status_label.configure(
                text_color=COLOR_ERROR,
                text="No logged-in user found — log in first to save meal plans.",
            )
            return

        self.save_btn.configure(state="disabled", text="Saving...")
        self.status_label.configure(text="")
        self.update_idletasks()

        saved, deleted, errors = 0, 0, []

        for (day, meal_type), entry in self.entries.items():
            new_text = entry.get().strip()
            original = self.original_values.get((day, meal_type), "")

            if new_text == original:
                continue

            try:
                if new_text:
                    database.upsert_meal_plan(self.user_email, day, meal_type, new_text)
                    self.original_values[(day, meal_type)] = new_text
                    saved += 1
                else:
                    database.delete_meal_plan(self.user_email, day, meal_type)
                    self.original_values.pop((day, meal_type), None)
                    deleted += 1
            except (ValueError, mysql.connector.Error) as e:
                errors.append(f"{day} {meal_type}: {e}")

        self.save_btn.configure(state="normal", text="Save Changes")

        if errors:
            self.status_label.configure(text_color=COLOR_ERROR, text="; ".join(errors))
        else:
            self.status_label.configure(
                text_color=COLOR_SUCCESS,
                text=f"Saved. {saved} slot(s) updated, {deleted} removed.",
            )

    # ------------------------------------------------------------- delete
    def _handle_delete_cell(self, day, meal_type):
        entry = self.entries[(day, meal_type)]
        entry.delete(0, "end")

        if not self.user_email:
            return

        key = (day, meal_type)
        if key not in self.original_values:
            return  # nothing saved for this slot yet — nothing to delete

        try:
            database.delete_meal_plan(self.user_email, day, meal_type)
            self.original_values.pop(key, None)
            self.status_label.configure(
                text_color=COLOR_SUCCESS, text=f"Removed {meal_type} for {day}."
            )
        except mysql.connector.Error as db_err:
            self.status_label.configure(text_color=COLOR_ERROR, text=f"Couldn't delete: {db_err}")

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
    app = MealPlannerPage(user_data=demo_user)
    app.mainloop()