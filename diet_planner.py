"""
diet_planner.py
-----------------
AI Diet Chart & Nutrition Calculator — AI Diet Planner
Healthcare-themed, built with CustomTkinter.

Collects age, gender, height, weight, activity level, dietary
preference, allergies, medical conditions, and fitness goal (BMI is
calculated automatically), then asks Gemini to generate a personalized
Indian meal plan — breakfast, lunch, snacks, dinner, a calorie target,
and a water intake target — and displays it as a report.

Every generated plan is saved to the `diet_plan_history` table so it
can be revisited later from the "History" panel, or wiped with
"Clear History". The currently displayed plan can be saved to a local
text file with "Export Plan".

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py /
about_page.py / feedback_page.py / exercise_recommendation.py
(`state('zoomed')`, falling back to `-zoomed` or a manual full-screen
geometry).

SETUP:
    pip install customtkinter google-generativeai python-dotenv
    Create a file named api.env in this same folder containing:
        GEMINI_API_KEY=your_actual_key_here
    Get a free key at https://aistudio.google.com/apikey

Run:
    python diet_planner.py

IMPORTANT: This generates general meal suggestions from an AI model,
not a clinical nutrition plan. It is not a substitute for advice from
a doctor or registered dietitian — especially if medical conditions,
allergies, pregnancy, or other health considerations are involved.
"""

import json
import os
import re
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ImportError:
    genai = None

import database
import session

# ---------------------------------------------------------------------------
# Loads GEMINI_API_KEY from api.env (in the same folder as this file).
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
COLOR_ROW_ALT = "#124742"

MIN_W, MIN_H = 480, 620

GENDER_OPTIONS = ["Male", "Female", "Other"]
ACTIVITY_OPTIONS = [
    "Sedentary", "Lightly Active", "Moderately Active",
    "Very Active", "Extra Active",
]
DIET_OPTIONS = ["Vegetarian", "Non-Vegetarian", "Eggetarian", "Vegan"]
GOAL_OPTIONS = [
    "Weight Loss", "Weight Maintenance", "Muscle Gain", "General Fitness",
]

MEAL_SECTIONS = [
    ("breakfast", "🍳 Breakfast"),
    ("lunch", "🍛 Lunch"),
    ("snacks", "🥗 Snacks"),
    ("dinner", "🍽️ Dinner"),
]


def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)


def classify_bmi(bmi: float) -> str:
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25.0:
        return "Normal"
    elif bmi < 30.0:
        return "Overweight"
    return "Obese"


def generate_diet_plan(profile: dict) -> dict:
    """
    Asks Gemini for a personalized Indian meal plan based on `profile`.
    Returns a dict with keys: calorie_target, water_intake_ml, breakfast,
    lunch, snacks, dinner (each a list of strings), and notes.
    Raises RuntimeError on failure.
    """
    if genai is None:
        raise RuntimeError(
            "google-generativeai isn't installed. Run: pip install google-generativeai"
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

    prompt = f"""
You are a nutrition assistant creating a ONE-DAY Indian meal plan for this person:
- Age: {profile['age']}
- Gender: {profile['gender']}
- Height: {profile['height_cm']} cm
- Weight: {profile['weight_kg']} kg
- BMI: {profile['bmi']:.1f} ({profile['bmi_category']})
- Activity level: {profile['activity_level']}
- Dietary preference: {profile['dietary_preference']}
- Allergies to strictly avoid: {profile['allergies'] or 'None specified'}
- Medical conditions to consider: {profile['medical_conditions'] or 'None specified'}
- Fitness goal: {profile['fitness_goal']}

Create a practical, realistic Indian meal plan (home-style dishes, common
regional foods) that respects the dietary preference and completely avoids
the listed allergies. If medical conditions are listed (e.g. diabetes,
hypertension, thyroid issues), keep general dietary caution in mind (e.g.
lower refined sugar/salt where relevant) but do not attempt to give medical
treatment advice.

Respond with STRICT JSON only — no explanation, no markdown code fences,
just the raw JSON object — in exactly this shape:
{{
  "calorie_target": <integer, kcal/day>,
  "water_intake_ml": <integer, ml/day>,
  "breakfast": ["<item 1>", "<item 2>", ...],
  "lunch": ["<item 1>", "<item 2>", ...],
  "snacks": ["<item 1>", "<item 2>", ...],
  "dinner": ["<item 1>", "<item 2>", ...],
  "notes": "<one short paragraph of practical notes for this person>"
}}
Each meal item should be a short, specific description (dish + rough
portion), e.g. "Vegetable poha with peanuts, 1 bowl (~250 kcal)".
Keep each meal list to 2-4 items. Keep "notes" to 2-3 sentences.
"""

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
                "model (check https://aistudio.google.com/rate-limit) and "
                "update GEMINI_MODEL."
            )
        raise RuntimeError(f"Gemini request failed: {e}")

    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(
            "Couldn't understand Gemini's response. Try generating again."
        )

    try:
        return {
            "calorie_target": int(data["calorie_target"]),
            "water_intake_ml": int(data["water_intake_ml"]),
            "breakfast": list(data["breakfast"]),
            "lunch": list(data["lunch"]),
            "snacks": list(data["snacks"]),
            "dinner": list(data["dinner"]),
            "notes": str(data.get("notes", "")),
        }
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Incomplete meal plan data returned. Try generating again.")


class DietPlannerPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.on_back = on_back

        # Currently displayed plan (whichever was last generated or
        # opened from History) — used by the Export button.
        self.current_profile = None
        self.current_plan = None
        self.current_created_at = None

        # Whether the history panel is currently showing.
        self._history_visible = False

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — AI Diet Planner")
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
            top_row, text="🕑 History", width=90, height=30,
            fg_color="transparent", hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=12),
            command=self._toggle_history,
        ).pack(side="right")

        ctk.CTkLabel(
            outer, text="AI Diet Planner",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 4))
        ctk.CTkLabel(
            outer, text="Get a personalized Indian meal plan powered by AI",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 14))

        self.scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16)

        self._build_form(self.scroll)

        self.error_label = ctk.CTkLabel(
            self.scroll, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=500,
        )
        self.error_label.pack(fill="x", pady=(6, 0))

        self.generate_btn = ctk.CTkButton(
            self.scroll, text="Generate My Diet Plan", height=42,
            corner_radius=10, fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=14, weight="bold"),
            command=self._handle_generate,
        )
        self.generate_btn.pack(fill="x", pady=(12, 20))

        # History panel — built/populated on demand, hidden by default.
        self.history_container = ctk.CTkFrame(self.scroll, fg_color="transparent")

        # Result report area — built dynamically once a plan is generated
        # or opened from history.
        self.report_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.report_container.pack(fill="both", expand=True)

    def _build_form(self, parent):
        d = self.user_data
        row1 = ctk.CTkFrame(parent, fg_color="transparent")
        row1.pack(fill="x")
        row1.grid_columnconfigure((0, 1), weight=1)
        self.age_entry = self._add_entry(row1, "Age", str(d.get("age") or ""), col=0)
        self.gender_menu = self._add_option_menu(row1, "Gender", GENDER_OPTIONS, d.get("gender"), col=1)

        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x")
        row2.grid_columnconfigure((0, 1), weight=1)
        self.height_entry = self._add_entry(row2, "Height (cm)", str(d.get("height_cm") or ""), col=0)
        self.weight_entry = self._add_entry(row2, "Weight (kg)", str(d.get("weight_kg") or ""), col=1)

        row3 = ctk.CTkFrame(parent, fg_color="transparent")
        row3.pack(fill="x")
        row3.grid_columnconfigure((0, 1), weight=1)
        self.activity_menu = self._add_option_menu(
            row3, "Activity Level", ACTIVITY_OPTIONS, d.get("activity_level"), col=0)
        self.diet_menu = self._add_option_menu(
            row3, "Dietary Preference", DIET_OPTIONS, d.get("dietary_preference"), col=1)

        self.goal_menu = self._add_option_menu(
            parent, "Fitness Goal", GOAL_OPTIONS, d.get("fitness_goal"))

        self.allergies_entry = self._add_entry(
            parent, "Allergies (comma-separated, leave blank if none)", "")
        self.medical_entry = self._add_entry(
            parent, "Medical Conditions (comma-separated, leave blank if none)", "")

    def _add_entry(self, parent, label_text, initial_value, col=None):
        holder = parent if col is None else ctk.CTkFrame(parent, fg_color="transparent")
        if col is not None:
            holder.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0))
        ctk.CTkLabel(
            holder, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(10, 0))
        entry = ctk.CTkEntry(
            holder, height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
        )
        entry.insert(0, initial_value)
        entry.pack(fill="x", pady=(4, 0))
        return entry

    def _add_option_menu(self, parent, label_text, options, current_value, col=None):
        holder = parent if col is None else ctk.CTkFrame(parent, fg_color="transparent")
        if col is not None:
            holder.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0))
        ctk.CTkLabel(
            holder, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(10, 0))
        menu = ctk.CTkOptionMenu(
            holder, values=options, height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, button_color=COLOR_TRACK,
            button_hover_color=COLOR_ACCENT, text_color=COLOR_WHITE,
        )
        menu.set(current_value if current_value in options else options[0])
        menu.pack(fill="x", pady=(4, 0))
        return menu

    # ------------------------------------------------------------ generate
    def _handle_generate(self):
        errors, profile = self._validate()
        if errors:
            self.error_label.configure(text=errors[0])
            return

        self.error_label.configure(text="")
        self.generate_btn.configure(state="disabled", text="Generating your plan...")
        self._hide_history()
        self._clear_report()

        def worker():
            try:
                plan = generate_diet_plan(profile)
                self.after(0, lambda: self._on_generate_success(profile, plan))
            except RuntimeError as e:
                self.after(0, lambda: self._on_generate_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _validate(self):
        errors = []
        age_raw = self.age_entry.get().strip()
        height_raw = self.height_entry.get().strip()
        weight_raw = self.weight_entry.get().strip()

        if not age_raw.isdigit() or not (1 <= int(age_raw) <= 120):
            errors.append("Enter a valid age between 1 and 120.")
        age = int(age_raw) if age_raw.isdigit() else None

        try:
            height = float(height_raw)
            if not (50 <= height <= 250):
                raise ValueError
        except ValueError:
            errors.append("Enter a valid height between 50 and 250 cm.")
            height = None

        try:
            weight = float(weight_raw)
            if not (20 <= weight <= 300):
                raise ValueError
        except ValueError:
            errors.append("Enter a valid weight between 20 and 300 kg.")
            weight = None

        profile = None
        if not errors:
            bmi = calculate_bmi(height, weight)
            profile = {
                "age": age,
                "gender": self.gender_menu.get(),
                "height_cm": height,
                "weight_kg": weight,
                "bmi": bmi,
                "bmi_category": classify_bmi(bmi),
                "activity_level": self.activity_menu.get(),
                "dietary_preference": self.diet_menu.get(),
                "allergies": self.allergies_entry.get().strip(),
                "medical_conditions": self.medical_entry.get().strip(),
                "fitness_goal": self.goal_menu.get(),
            }
        return errors, profile

    def _on_generate_success(self, profile, plan):
        self.generate_btn.configure(state="normal", text="Generate My Diet Plan")
        self._save_to_history(profile, plan)
        self._render_report(profile, plan, created_at=datetime.now())

    def _on_generate_error(self, message):
        self.generate_btn.configure(state="normal", text="Generate My Diet Plan")
        self.error_label.configure(text=message)

    def _save_to_history(self, profile, plan):
        """Persists the just-generated plan so it shows up in History
        later. Failures (e.g. demo/placeholder email with no real
        account) are shown quietly in the error label rather than
        blocking the report from displaying."""
        email = self.user_data.get("email")
        if not email:
            return
        try:
            database.insert_diet_plan_record(email, profile, plan)
        except (ValueError, Exception) as e:  # noqa: BLE001 - surface but don't block UI
            self.error_label.configure(
                text=f"Plan generated, but couldn't be saved to History: {e}"
            )

    # -------------------------------------------------------------- history
    def _toggle_history(self):
        if self._history_visible:
            self._hide_history()
        else:
            self._show_history()

    def _show_history(self):
        self._history_visible = True
        self.report_container.pack_forget()
        self._render_history_panel()
        self.history_container.pack(fill="both", expand=True)

    def _hide_history(self):
        self._history_visible = False
        self.history_container.pack_forget()
        for child in self.history_container.winfo_children():
            child.destroy()
        self.report_container.pack(fill="both", expand=True)

    def _render_history_panel(self):
        for child in self.history_container.winfo_children():
            child.destroy()
        h = self.history_container

        header_row = ctk.CTkFrame(h, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            header_row, text="Past Diet Plans", font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(side="left")
        ctk.CTkButton(
            header_row, text="Clear History", width=110, height=28,
            corner_radius=8, fg_color="transparent", hover_color=COLOR_TRACK,
            border_width=1, border_color=COLOR_ERROR, text_color=COLOR_ERROR,
            font=ctk.CTkFont(size=11), command=self._handle_clear_history,
        ).pack(side="right")

        email = self.user_data.get("email")
        entries = []
        if email:
            try:
                entries = database.get_diet_plan_history(email)
            except Exception as e:  # noqa: BLE001
                ctk.CTkLabel(
                    h, text=f"Couldn't load history: {e}", font=ctk.CTkFont(size=12),
                    text_color=COLOR_ERROR, wraplength=520, justify="left",
                ).pack(anchor="w", pady=(0, 10))

        if not entries:
            ctk.CTkLabel(
                h, text="No saved plans yet. Generate one above and it'll show up here.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
                wraplength=520, justify="left",
            ).pack(anchor="w", pady=(0, 14))
        else:
            for entry in entries:
                self._history_row(h, entry)

    def _history_row(self, parent, entry):
        profile, plan, created_at = entry["profile"], entry["plan"], entry["created_at"]
        row = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=12)
        row.pack(fill="x", pady=(0, 10))

        info_col = ctk.CTkFrame(row, fg_color="transparent")
        info_col.pack(side="left", fill="both", expand=True, padx=(14, 6), pady=10)

        date_text = created_at.strftime("%d %b %Y, %I:%M %p") if hasattr(created_at, "strftime") else str(created_at)
        ctk.CTkLabel(
            info_col, text=date_text, font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_WHITE, anchor="w",
        ).pack(fill="x")
        summary = (
            f"{plan.get('calorie_target', '—')} kcal target  ·  "
            f"BMI {profile.get('bmi', 0):.1f}  ·  {profile.get('fitness_goal', '')}"
        )
        ctk.CTkLabel(
            info_col, text=summary, font=ctk.CTkFont(size=11),
            text_color=COLOR_ACCENT_SOFT, anchor="w",
        ).pack(fill="x", pady=(2, 0))

        ctk.CTkButton(
            row, text="View", width=70, height=30, corner_radius=8,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda p=profile, pl=plan, ca=created_at: self._view_history_entry(p, pl, ca),
        ).pack(side="right", padx=14, pady=10)

    def _view_history_entry(self, profile, plan, created_at):
        self._hide_history()
        self._render_report(profile, plan, created_at=created_at)

    def _handle_clear_history(self):
        email = self.user_data.get("email")
        if not email:
            return
        if not messagebox.askyesno(
            "Clear History", "Delete all saved diet plans? This can't be undone."
        ):
            return
        try:
            database.clear_diet_plan_history(email)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Clear History", f"Couldn't clear history: {e}")
            return
        self._render_history_panel()

    # -------------------------------------------------------------- report
    def _clear_report(self):
        for child in self.report_container.winfo_children():
            child.destroy()
        self.current_profile = None
        self.current_plan = None
        self.current_created_at = None

    def _render_report(self, profile, plan, created_at=None):
        self._clear_report()
        self.current_profile = profile
        self.current_plan = plan
        self.current_created_at = created_at or datetime.now()
        r = self.report_container

        # ---- Profile summary strip -----------------------------------
        summary_card = ctk.CTkFrame(r, fg_color=COLOR_CARD, corner_radius=14)
        summary_card.pack(fill="x", pady=(0, 14))
        summary_text = (
            f"{profile['age']} yrs · {profile['gender']} · {profile['height_cm']:.0f} cm · "
            f"{profile['weight_kg']:.0f} kg  |  BMI {profile['bmi']:.1f} ({profile['bmi_category']})  |  "
            f"{profile['activity_level']}  |  {profile['dietary_preference']}"
        )
        ctk.CTkLabel(
            summary_card, text=summary_text, font=ctk.CTkFont(size=11),
            text_color=COLOR_ACCENT_SOFT, wraplength=520, justify="center",
        ).pack(padx=16, pady=12)

        # ---- Calorie / water target row --------------------------------
        target_row = ctk.CTkFrame(r, fg_color="transparent")
        target_row.pack(fill="x", pady=(0, 16))
        target_row.grid_columnconfigure((0, 1), weight=1)

        self._target_card(target_row, 0, "Daily Calorie Target", f"{plan['calorie_target']} kcal")
        self._target_card(target_row, 1, "Daily Water Intake", f"{plan['water_intake_ml']} ml")

        # ---- Meal sections ----------------------------------------------
        for key, label in MEAL_SECTIONS:
            self._meal_card(r, label, plan.get(key, []))

        # ---- Notes --------------------------------------------------
        if plan.get("notes"):
            notes_card = ctk.CTkFrame(r, fg_color=COLOR_CARD, corner_radius=14)
            notes_card.pack(fill="x", pady=(0, 14))
            ctk.CTkLabel(
                notes_card, text="Notes", font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLOR_WHITE,
            ).pack(anchor="w", padx=16, pady=(12, 2))
            ctk.CTkLabel(
                notes_card, text=plan["notes"], font=ctk.CTkFont(size=12),
                text_color=COLOR_ACCENT_SOFT, wraplength=520, justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            r,
            text="This plan is generated by an AI model for general guidance and is "
                 "not a substitute for advice from a doctor or registered dietitian — "
                 "especially given any medical conditions, allergies, or pregnancy.",
            font=ctk.CTkFont(size=10), text_color=COLOR_MUTED,
            wraplength=520, justify="left",
        ).pack(fill="x", pady=(0, 12))

        ctk.CTkButton(
            r, text="⬇  Export Plan", height=38, corner_radius=10,
            fg_color="transparent", hover_color=COLOR_TRACK,
            border_width=1, border_color=COLOR_ACCENT, text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_export,
        ).pack(fill="x", pady=(0, 20))

    def _target_card(self, parent, col, title, value):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.grid(row=0, column=col, sticky="nswe", padx=(0 if col == 0 else 8, 8 if col == 0 else 0))
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(padx=16, pady=(14, 2))
        ctk.CTkLabel(
            card, text=value, font=ctk.CTkFont(size=20, weight="bold"), text_color=COLOR_WHITE,
        ).pack(padx=16, pady=(0, 14))

    def _meal_card(self, parent, label, items):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            card, text=label, font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        if not items:
            ctk.CTkLabel(
                card, text="No items suggested.", font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(anchor="w", padx=16, pady=(0, 12))
            return

        for i, item in enumerate(items):
            row = ctk.CTkFrame(card, fg_color=COLOR_ROW_ALT if i % 2 else "transparent", corner_radius=6)
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(
                row, text=f"•  {item}", font=ctk.CTkFont(size=12), text_color=COLOR_WHITE,
                wraplength=500, justify="left", anchor="w",
            ).pack(fill="x", padx=8, pady=6)
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    # -------------------------------------------------------------- export
    def _handle_export(self):
        if not self.current_plan or not self.current_profile:
            return

        default_name = f"diet_plan_{self.current_created_at.strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile=default_name,
            title="Export Diet Plan",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self._format_plan_as_text(self.current_profile, self.current_plan, self.current_created_at))
        except OSError as e:
            messagebox.showerror("Export Plan", f"Couldn't save the file: {e}")
            return

        messagebox.showinfo("Export Plan", f"Diet plan saved to:\n{file_path}")

    @staticmethod
    def _format_plan_as_text(profile, plan, created_at) -> str:
        date_text = created_at.strftime("%d %b %Y, %I:%M %p") if hasattr(created_at, "strftime") else str(created_at)
        lines = [
            "AI DIET CHART & NUTRITION CALCULATOR",
            "Personalized Diet Plan",
            f"Generated: {date_text}",
            "=" * 48,
            "",
            "PROFILE",
            f"  Age: {profile['age']}",
            f"  Gender: {profile['gender']}",
            f"  Height: {profile['height_cm']:.0f} cm",
            f"  Weight: {profile['weight_kg']:.0f} kg",
            f"  BMI: {profile['bmi']:.1f} ({profile['bmi_category']})",
            f"  Activity Level: {profile['activity_level']}",
            f"  Dietary Preference: {profile['dietary_preference']}",
            f"  Allergies: {profile.get('allergies') or 'None specified'}",
            f"  Medical Conditions: {profile.get('medical_conditions') or 'None specified'}",
            f"  Fitness Goal: {profile['fitness_goal']}",
            "",
            f"Daily Calorie Target: {plan['calorie_target']} kcal",
            f"Daily Water Intake Target: {plan['water_intake_ml']} ml",
            "",
        ]
        for key, label in MEAL_SECTIONS:
            clean_label = label.split(" ", 1)[-1] if " " in label else label
            lines.append(clean_label.upper())
            items = plan.get(key, [])
            if items:
                for item in items:
                    lines.append(f"  - {item}")
            else:
                lines.append("  - No items suggested.")
            lines.append("")

        if plan.get("notes"):
            lines.append("NOTES")
            lines.append(f"  {plan['notes']}")
            lines.append("")

        lines.append(
            "This plan is generated by an AI model for general guidance and is "
            "not a substitute for advice from a doctor or registered dietitian."
        )
        return "\n".join(lines)

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
    app = DietPlannerPage(user_data=demo_user)
    app.mainloop()