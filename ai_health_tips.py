"""
ai_health_tips.py
--------------------
AI Diet Chart & Nutrition Calculator — AI Health Tips
Healthcare-themed, built with CustomTkinter.

Generates a personalized set of daily health tips via Gemini, based
on the logged-in user's profile: a general daily tip, nutrition
advice, a workout suggestion, a hydration reminder, and a
motivational message. Auto-generates once on open, with a
"Regenerate" button for a fresh set anytime.

SETUP:
    pip install customtkinter google-generativeai python-dotenv
    Create a file named api.env in this same folder containing:
        GEMINI_API_KEY=your_actual_key_here
    Get a free key at https://aistudio.google.com/apikey

Run:
    python ai_health_tips.py

NOTE: These are general AI-generated suggestions, not personalized
medical advice — especially relevant for anyone with medical
conditions, allergies, injuries, or who is pregnant.
"""

import json
import os
import re
import threading
from datetime import datetime

import customtkinter as ctk
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ImportError:
    genai = None

import session
import preferences

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
COLOR_MUTED = "#6FA69E"
COLOR_ERROR = "#FF8A80"

WINDOW_W, WINDOW_H = 560, 800
MIN_W, MIN_H = 440, 600
MAX_W, MAX_H = 700, 980

TIP_SECTIONS = [
    ("daily_tip", "🌞", "Daily Tip"),
    ("nutrition_advice", "🥗", "Nutrition Advice"),
    ("workout_suggestion", "🏃", "Workout Suggestion"),
    ("hydration_reminder", "💧", "Hydration Reminder"),
    ("motivational_message", "✨", "Motivation"),
]


def generate_health_tips(profile: dict) -> dict:
    """
    Asks Gemini for a personalized set of daily health tips based on
    `profile`. Returns a dict with keys: daily_tip, nutrition_advice,
    workout_suggestion, hydration_reminder, motivational_message.
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

    profile_lines = "\n".join(f"- {k}: {v}" for k, v in profile.items() if v)

    prompt = f"""
You are a friendly wellness assistant generating today's personalized
health tips for this person:
{profile_lines if profile_lines else "- No profile details provided; keep tips general and broadly applicable."}

Respond with STRICT JSON only — no explanation, no markdown code fences,
just the raw JSON object — in exactly this shape:
{{
  "daily_tip": "<one short, practical general health tip for today, 1-2 sentences>",
  "nutrition_advice": "<one specific, practical nutrition tip relevant to this person, 1-2 sentences>",
  "workout_suggestion": "<one specific workout or movement suggestion for today, 1-2 sentences>",
  "hydration_reminder": "<one short reminder about water intake, 1 sentence>",
  "motivational_message": "<one short, warm, encouraging message, 1-2 sentences>"
}}
Keep the tone warm and encouraging, not clinical or preachy. Avoid
giving specific medical treatment advice even if medical conditions
are mentioned — keep any such tips general and suggest professional
guidance where relevant.
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
        raise RuntimeError("Couldn't understand Gemini's response. Try regenerating.")

    try:
        return {
            "daily_tip": str(data["daily_tip"]),
            "nutrition_advice": str(data["nutrition_advice"]),
            "workout_suggestion": str(data["workout_suggestion"]),
            "hydration_reminder": str(data["hydration_reminder"]),
            "motivational_message": str(data["motivational_message"]),
        }
    except KeyError:
        raise RuntimeError("Incomplete tips returned. Try regenerating.")


class AIHealthTipsPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.on_back = on_back

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — AI Health Tips")
        self.configure(fg_color=COLOR_BG)
        win_w, win_h = self._compute_responsive_size()
        self._center_window(win_w, win_h)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        self._build_ui()
        if preferences.load_preferences().get("auto_generate_ai_tips", True):
            self._handle_generate()  # auto-generate today's tips on open
        else:
            for label in self.tip_labels.values():
                label.configure(text="Tap Regenerate to see today's tips.")

    def _compute_responsive_size(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        target_w = sw * 0.30
        target_h = sh * 0.80
        aspect = WINDOW_H / WINDOW_W
        if target_h / target_w > aspect:
            target_h = target_w * aspect
        else:
            target_w = target_h / aspect
        w = max(MIN_W, min(MAX_W, int(target_w)))
        h = max(MIN_H, min(MAX_H, int(target_h)))
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

        ctk.CTkLabel(
            outer, text="✨ AI Health Tips",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 2))

        today = datetime.now().strftime("%A, %d %B %Y")
        ctk.CTkLabel(
            outer, text=today,
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 14))

        self.status_label = ctk.CTkLabel(
            outer, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=440,
        )
        self.status_label.pack(fill="x", padx=16, pady=(0, 4))

        self.scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16)

        self.tip_labels = {}
        for key, icon, title in TIP_SECTIONS:
            card = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=14)
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(
                card, text=f"{icon}  {title}",
                font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_WHITE,
            ).pack(anchor="w", padx=16, pady=(12, 4))
            body_label = ctk.CTkLabel(
                card, text="Generating...", font=ctk.CTkFont(size=12),
                text_color=COLOR_ACCENT_SOFT, wraplength=440, justify="left", anchor="w",
            )
            body_label.pack(anchor="w", fill="x", padx=16, pady=(0, 12))
            self.tip_labels[key] = body_label

        ctk.CTkLabel(
            self.scroll,
            text="These are general AI-generated suggestions, not personalized medical "
                 "advice — check with a doctor or registered dietitian for guidance "
                 "specific to any medical conditions, injuries, or pregnancy.",
            font=ctk.CTkFont(size=10), text_color=COLOR_MUTED,
            wraplength=440, justify="left",
        ).pack(fill="x", pady=(8, 16))

        self.generate_btn = ctk.CTkButton(
            outer, text="🔄  Regenerate", height=40,
            corner_radius=10, fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_generate,
        )
        self.generate_btn.pack(fill="x", padx=16, pady=(0, 16))

    # ------------------------------------------------------------ generate
    def _build_profile(self):
        d = self.user_data
        profile = {}
        if d.get("age"):
            profile["Age"] = d["age"]
        if d.get("gender"):
            profile["Gender"] = d["gender"]
        if d.get("height_cm"):
            profile["Height (cm)"] = d["height_cm"]
        if d.get("weight_kg"):
            profile["Weight (kg)"] = d["weight_kg"]
        if d.get("activity_level"):
            profile["Activity level"] = d["activity_level"]
        if d.get("fitness_goal"):
            profile["Fitness goal"] = d["fitness_goal"]
        if d.get("dietary_preference"):
            profile["Dietary preference"] = d["dietary_preference"]
        return profile

    def _handle_generate(self):
        self.status_label.configure(text="")
        self.generate_btn.configure(state="disabled", text="Generating...")
        for label in self.tip_labels.values():
            label.configure(text="Generating...")

        profile = self._build_profile()

        def worker():
            try:
                tips = generate_health_tips(profile)
                self.after(0, lambda: self._on_generate_success(tips))
            except RuntimeError as e:
                self.after(0, lambda: self._on_generate_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_generate_success(self, tips):
        self.generate_btn.configure(state="normal", text="🔄  Regenerate")
        for key, icon, title in TIP_SECTIONS:
            self.tip_labels[key].configure(text=tips.get(key, "—"))

    def _on_generate_error(self, message):
        self.generate_btn.configure(state="normal", text="🔄  Regenerate")
        self.status_label.configure(text=message)
        for label in self.tip_labels.values():
            label.configure(text="Couldn't load — try Regenerate.")

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
    app = AIHealthTipsPage(user_data=demo_user)
    app.mainloop()