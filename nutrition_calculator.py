"""
nutrition_calculator.py
-------------------------
AI Diet Chart & Nutrition Calculator — Nutrition Calculator Page
Healthcare-themed, built with CustomTkinter.

Search a food item -> Gemini is asked for its average nutrition facts
per 100g -> enter a quantity in grams -> add it to a running table.
The table scales each food's nutrition to the entered quantity and
keeps a running total of calories, protein, carbohydrates, fat,
fiber, and sugar.

PERSISTENCE: every item added is saved to MySQL (food_log table, full
nutrient breakdown included). When the page is reopened, today's saved
items are reloaded automatically — the table is a genuine daily food
log, not a scratchpad that resets whenever you navigate away. Use
"Clear History" to wipe today's saved log (both on screen and in the
database) if you want to start over.

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py /
about_page.py / feedback_page.py / exercise_recommendation.py /
help_contact.py / diet_planner.py / meal_planner.py /
forgot_password_page.py (`state('zoomed')`, falling back to
`-zoomed` or a manual full-screen geometry).

SETUP:
    pip install customtkinter google-generativeai python-dotenv
    Create a file named api.env in this same folder containing:
        GEMINI_API_KEY=your_actual_key_here
    Get a free key at https://aistudio.google.com/apikey

Run:
    python nutrition_calculator.py

NOTE ON ACCURACY: Gemini is asked to *estimate* nutrition facts from
its training knowledge — this is not a lookup against a verified food
database (like USDA FoodData Central). Treat results as approximate,
especially for branded/packaged foods or unusual serving descriptions.
"""

import json
import os
import re
import threading

import customtkinter as ctk
from dotenv import load_dotenv
import mysql.connector

import database

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# ---------------------------------------------------------------------------
# Loads GEMINI_API_KEY from api.env (in the same folder as this file).
# api.env should contain a single line:
#     GEMINI_API_KEY=your_actual_key_here
# Get a free key at https://aistudio.google.com/apikey
#
# MODEL NOTE: Google's free tier eligibility varies by model and can change
# without notice. If you get a "Quota exceeded ... limit: 0" error, it means
# THIS SPECIFIC MODEL has no free-tier allocation for your project right now
# — it's not something retrying will fix. Check which models currently show
# a real (non-zero) limit for your account at:
#     https://aistudio.google.com/rate-limit
# and swap GEMINI_MODEL below to match.
# ---------------------------------------------------------------------------
load_dotenv("api.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"  # check aistudio.google.com/rate-limit if this errors

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

MIN_W, MIN_H = 600, 500

# NUTRIENTS: (key, header label, unit)
NUTRIENTS = [
    ("calories", "Calories", "kcal"),
    ("protein", "Protein", "g"),
    ("carbohydrates", "Carbs", "g"),
    ("fat", "Fat", "g"),
    ("fiber", "Fiber", "g"),
    ("sugar", "Sugar", "g"),
]


def fetch_nutrition_per_100g(food_name: str) -> dict:
    """
    Asks Gemini for average nutrition facts per 100g of `food_name`.
    Returns a dict with keys: calories, protein, carbohydrates, fat,
    fiber, sugar (all per 100g). Raises RuntimeError on failure.
    """
    if genai is None:
        raise RuntimeError(
            "google-generativeai isn't installed. Run: "
            "pip install google-generativeai"
        )
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "No Gemini API key found. Create a file named api.env in the "
            "same folder as this script containing:\n"
            "GEMINI_API_KEY=your_actual_key_here\n"
            "(get a free key at https://aistudio.google.com/apikey)"
        )

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = (
        f'Give the average nutrition facts per 100 grams of "{food_name}" '
        "as a food item. Respond with STRICT JSON only — no explanation, "
        "no markdown code fences, just the raw JSON object — in exactly "
        "this shape:\n"
        '{"calories": <number>, "protein": <number>, "carbohydrates": <number>, '
        '"fat": <number>, "fiber": <number>, "sugar": <number>}\n'
        "All values are per 100 grams: calories in kcal, the rest in grams. "
        "If unsure, give your best reasonable estimate rather than refusing."
    )

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
    except Exception as e:
        error_text = str(e)
        if "quota" in error_text.lower() or "429" in error_text:
            raise RuntimeError(
                f"Gemini quota exceeded for model '{GEMINI_MODEL}'. If the "
                "error mentions 'limit: 0', this model has no free-tier "
                "allocation for your project right now — try a different "
                "model (check https://aistudio.google.com/rate-limit to see "
                "which ones show a real limit) and update GEMINI_MODEL."
            )
        raise RuntimeError(f"Gemini request failed: {e}")

    # Strip ```json ... ``` fences if the model added them anyway
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"Couldn't understand Gemini's response for '{food_name}'. Try "
            "rephrasing the food name (e.g. 'banana' instead of a brand name)."
        )

    try:
        return {
            "calories": float(data["calories"]),
            "protein": float(data["protein"]),
            "carbohydrates": float(data["carbohydrates"]),
            "fat": float(data["fat"]),
            "fiber": float(data["fiber"]),
            "sugar": float(data["sugar"]),
        }
    except (KeyError, TypeError, ValueError):
        raise RuntimeError(f"Incomplete nutrition data returned for '{food_name}'.")


class NutritionCalculatorPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or {}
        self.on_back = on_back

        self.pending_result = None  # last fetched per-100g nutrition dict
        self.pending_food_name = None
        self.table_rows = []  # list of dicts: {name, qty, **scaled nutrients}

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Nutrition Calculator")
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
        self._load_today_history()

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
            outer, text="Nutrition Calculator",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 4))
        ctk.CTkLabel(
            outer, text="Search a food, set the quantity, and build up today's meal log",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 14))

        # ---- Search row -------------------------------------------------
        search_row = ctk.CTkFrame(outer, fg_color="transparent")
        search_row.pack(fill="x", padx=16)

        self.search_entry = ctk.CTkEntry(
            search_row, placeholder_text="e.g. banana, grilled chicken breast, white rice",
            height=38, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda _e: self._handle_search())

        self.search_btn = ctk.CTkButton(
            search_row, text="Search", width=90, height=38,
            corner_radius=10, fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_search,
        )
        self.search_btn.pack(side="left", padx=(8, 0))

        self.search_status_label = ctk.CTkLabel(
            outer, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=600,
        )
        self.search_status_label.pack(fill="x", padx=16, pady=(6, 0))

        # ---- Pending result card (per-100g preview + quantity + add) ----
        self.pending_card = ctk.CTkFrame(outer, fg_color=COLOR_CARD, corner_radius=14)
        # not packed yet — shown once a search succeeds

        self.pending_title_label = ctk.CTkLabel(
            self.pending_card, text="", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_WHITE,
        )
        self.pending_title_label.pack(anchor="w", padx=16, pady=(14, 2))

        self.pending_per100_label = ctk.CTkLabel(
            self.pending_card, text="", font=ctk.CTkFont(size=11),
            text_color=COLOR_MUTED, wraplength=600, justify="left",
        )
        self.pending_per100_label.pack(anchor="w", padx=16, pady=(0, 10))

        qty_row = ctk.CTkFrame(self.pending_card, fg_color="transparent")
        qty_row.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(
            qty_row, text="Quantity (g):", font=ctk.CTkFont(size=12),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(side="left")
        self.quantity_entry = ctk.CTkEntry(
            qty_row, width=80, height=32, corner_radius=8,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
        )
        self.quantity_entry.insert(0, "100")
        self.quantity_entry.pack(side="left", padx=(8, 8))
        ctk.CTkButton(
            qty_row, text="Add to Table", height=32, corner_radius=8,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._handle_add_to_table,
        ).pack(side="left")

        # ---- Table header (fixed, non-scrolling) ------------------------
        table_header_row = ctk.CTkFrame(outer, fg_color="transparent")
        table_header_row.pack(fill="x", padx=16, pady=(18, 6))
        ctk.CTkLabel(
            table_header_row, text="Today's Meal Log",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).pack(side="left")
        self.history_status_label = ctk.CTkLabel(
            table_header_row, text="", font=ctk.CTkFont(size=10), text_color=COLOR_MUTED,
        )
        self.history_status_label.pack(side="right")

        self.header_row = ctk.CTkFrame(outer, fg_color=COLOR_TRACK, corner_radius=8)
        self.header_row.pack(fill="x", padx=16)
        self._build_table_row(
            self.header_row,
            ["Food", "Qty (g)"] + [f"{label} ({unit})" for _, label, unit in NUTRIENTS] + [""],
            bold=True,
        )

        # ---- Table body (scrollable) ------------------------------------
        self.table_body = ctk.CTkScrollableFrame(outer, fg_color="transparent", height=200)
        self.table_body.pack(fill="both", expand=True, padx=16, pady=(2, 6))

        self.empty_row_label = ctk.CTkLabel(
            self.table_body, text="No items added yet today — search a food above to get started.",
            font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
        )
        self.empty_row_label.pack(pady=20)

        # ---- Totals row (fixed, non-scrolling) --------------------------
        self.totals_row = ctk.CTkFrame(outer, fg_color=COLOR_ACCENT, corner_radius=8)
        self.totals_row.pack(fill="x", padx=16, pady=(0, 10))
        self._render_totals_row()

        ctk.CTkButton(
            outer, text="Clear History", width=110, height=30,
            corner_radius=8, fg_color="transparent",
            border_width=1, border_color=COLOR_TRACK,
            hover_color=COLOR_TRACK, text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=11),
            command=self._handle_clear_history,
        ).pack(anchor="e", padx=16, pady=(0, 14))

    def _build_table_row(self, parent, values, bold=False, text_color=None):
        n_cols = len(values)
        weights = [2] + [1] * (n_cols - 2) + [0]  # food name column wider, last col (remove) tight
        for i, w in enumerate(weights):
            parent.grid_columnconfigure(i, weight=w, minsize=40 if i == n_cols - 1 else 60)
        for i, val in enumerate(values):
            ctk.CTkLabel(
                parent, text=val,
                font=ctk.CTkFont(size=12, weight="bold" if bold else "normal"),
                text_color=text_color or COLOR_WHITE,
            ).grid(row=0, column=i, sticky="w", padx=6, pady=6)

    # -------------------------------------------------------- load history
    def _load_today_history(self):
        """Reloads today's saved food_log rows (if any) into the table on
        page open, so previously entered data isn't lost when navigating
        away and back."""
        email = self.user_data.get("email")
        if not email:
            return

        try:
            rows = database.get_food_log_today(email)
        except mysql.connector.Error as db_err:
            self.history_status_label.configure(text=f"Couldn't load today's history: {db_err}")
            return

        if not rows:
            return

        self.table_rows = [
            {
                "name": row["food_name"],
                "qty": float(row["quantity_g"]),
                "calories": float(row["calories"]),
                "protein": float(row.get("protein") or 0),
                "carbohydrates": float(row.get("carbohydrates") or 0),
                "fat": float(row.get("fat") or 0),
                "fiber": float(row.get("fiber") or 0),
                "sugar": float(row.get("sugar") or 0),
            }
            for row in rows
        ]
        self._render_table_body()
        self._render_totals_row()
        self.history_status_label.configure(
            text=f"Loaded {len(self.table_rows)} item(s) from today's saved history."
        )

    # ------------------------------------------------------------- search
    def _handle_search(self):
        food_name = self.search_entry.get().strip()
        if not food_name:
            self.search_status_label.configure(text="Enter a food name to search.")
            return

        self.search_btn.configure(state="disabled", text="Searching...")
        self.search_status_label.configure(text_color=COLOR_ACCENT_SOFT, text=f"Looking up \"{food_name}\"...")
        self.pending_card.pack_forget()

        def worker():
            try:
                result = fetch_nutrition_per_100g(food_name)
                self.after(0, lambda: self._on_search_success(food_name, result))
            except RuntimeError as e:
                self.after(0, lambda: self._on_search_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_success(self, food_name, result):
        self.search_btn.configure(state="normal", text="Search")
        self.search_status_label.configure(text="")

        self.pending_food_name = food_name
        self.pending_result = result

        self.pending_title_label.configure(text=food_name.title())
        summary = " · ".join(
            f"{label}: {result[key]:.1f}{unit}" for key, label, unit in NUTRIENTS
        )
        self.pending_per100_label.configure(text=f"Per 100g — {summary}")

        self.pending_card.pack(fill="x", padx=16, pady=(10, 0), before=self.header_row)

    def _on_search_error(self, message):
        self.search_btn.configure(state="normal", text="Search")
        self.search_status_label.configure(text_color=COLOR_ERROR, text=message)

    # ------------------------------------------------------- add to table
    def _handle_add_to_table(self):
        if not self.pending_result:
            return

        qty_raw = self.quantity_entry.get().strip()
        try:
            qty = float(qty_raw)
            if not (0 < qty <= 5000):
                raise ValueError
        except ValueError:
            self.search_status_label.configure(
                text_color=COLOR_ERROR, text="Enter a valid quantity in grams (1-5000)."
            )
            return

        factor = qty / 100.0
        scaled = {key: self.pending_result[key] * factor for key, _, _ in NUTRIENTS}
        row = {"name": self.pending_food_name, "qty": qty, **scaled}
        self.table_rows.append(row)

        self._render_table_body()
        self._render_totals_row()

        self.pending_card.pack_forget()
        self.pending_result = None
        self.search_entry.delete(0, "end")
        self.search_status_label.configure(
            text_color=COLOR_ACCENT_SOFT, text=f"Added {row['name'].title()} ({qty:.0f}g)."
        )

        user_email = self.user_data.get("email")
        if user_email:
            try:
                database.log_calorie_intake(user_email, scaled["calories"])
            except (ValueError, mysql.connector.Error):
                pass  # don't block the UI if logging fails; the on-screen table still works

            # Also record this item individually (full nutrient breakdown)
            # so it persists — this is what lets _load_today_history()
            # restore the exact table next time this page opens, and lets
            # the Dashboard's "Recent Meals" card show real history.
            try:
                database.insert_food_log(
                    user_email, row["name"], qty, scaled["calories"],
                    protein=scaled["protein"], carbohydrates=scaled["carbohydrates"],
                    fat=scaled["fat"], fiber=scaled["fiber"], sugar=scaled["sugar"],
                )
            except (ValueError, mysql.connector.Error):
                pass

    def _render_table_body(self):
        for child in self.table_body.winfo_children():
            child.destroy()

        if not self.table_rows:
            ctk.CTkLabel(
                self.table_body, text="No items added yet today — search a food above to get started.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(pady=20)
            return

        for idx, row in enumerate(self.table_rows):
            row_frame = ctk.CTkFrame(
                self.table_body,
                fg_color=COLOR_ROW_ALT if idx % 2 else "transparent",
                corner_radius=6,
            )
            row_frame.pack(fill="x", pady=1)

            values = [row["name"].title(), f"{row['qty']:.0f}"]
            values += [f"{row[key]:.1f}" for key, _, _ in NUTRIENTS]
            n_cols = len(values) + 1
            weights = [2] + [1] * (n_cols - 2) + [0]
            for i, w in enumerate(weights):
                row_frame.grid_columnconfigure(i, weight=w, minsize=40 if i == n_cols - 1 else 60)

            for i, val in enumerate(values):
                ctk.CTkLabel(
                    row_frame, text=val, font=ctk.CTkFont(size=12), text_color=COLOR_WHITE,
                ).grid(row=0, column=i, sticky="w", padx=6, pady=6)

            ctk.CTkButton(
                row_frame, text="✕", width=26, height=26, corner_radius=6,
                fg_color="transparent", hover_color=COLOR_TRACK,
                text_color=COLOR_ERROR, font=ctk.CTkFont(size=12),
                command=lambda i=idx: self._handle_remove_row(i),
            ).grid(row=0, column=n_cols - 1, padx=6, pady=6)

    def _handle_remove_row(self, index):
        # Note: this only removes the row from the on-screen table for
        # this session. The original entry stays in food_log (today's
        # database history) — use "Clear History" to actually delete
        # saved entries.
        del self.table_rows[index]
        self._render_table_body()
        self._render_totals_row()

    def _render_totals_row(self):
        for child in self.totals_row.winfo_children():
            child.destroy()

        totals = {key: sum(r[key] for r in self.table_rows) for key, _, _ in NUTRIENTS}
        total_qty = sum(r["qty"] for r in self.table_rows)

        values = ["Total", f"{total_qty:.0f}"]
        values += [f"{totals[key]:.1f}" for key, _, _ in NUTRIENTS]
        values.append("")

        self._build_table_row(self.totals_row, values, bold=True, text_color="#0B3D3A")

    # ------------------------------------------------------- clear history
    def _handle_clear_history(self):
        user_email = self.user_data.get("email")
        if user_email:
            try:
                database.clear_food_log_today(user_email)
            except mysql.connector.Error as db_err:
                self.search_status_label.configure(
                    text_color=COLOR_ERROR, text=f"Couldn't clear saved history: {db_err}"
                )
                return

        self.table_rows = []
        self._render_table_body()
        self._render_totals_row()
        self.history_status_label.configure(text="")
        self.search_status_label.configure(
            text_color=COLOR_SUCCESS, text="Today's history cleared."
        )

    def _go_back(self):
        from dashboard import DashboardPage
        self.destroy()
        if self.on_back:
            self.on_back()
        else:
            DashboardPage(user_data=self.user_data).mainloop()


if __name__ == "__main__":
    app = NutritionCalculatorPage()
    app.mainloop()