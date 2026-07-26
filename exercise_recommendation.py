"""
exercise_recommendation.py
----------------------------
AI Diet Chart & Nutrition Calculator — Exercise Recommendation Page
Healthcare-themed, built with CustomTkinter.

A rule-based recommendation engine (no external API): takes age,
height, weight, and fitness goal, computes BMI, then filters and
ranks a curated exercise list using:
  - MET (Metabolic Equivalent of Task) values to estimate calories
    burned: calories = MET * weight_kg * (duration_minutes / 60)
  - BMI-based filtering (e.g. steering obese/underweight users away
    from high-impact or overly strenuous options)
  - Age-based "senior-friendly" filtering (lower-impact, gentler
    options for age 60+; Advanced difficulty reserved for younger,
    Normal/Overweight-BMI users)
  - Fitness-goal matching (Weight Loss favors higher-MET cardio,
    Muscle Gain favors strength training, etc.)

Run:
    pip install customtkinter
    python exercise_recommendation.py
"""

import customtkinter as ctk

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

COLOR_BEGINNER = "#2FD3B0"     # green
COLOR_INTERMEDIATE = "#F4D03F"  # yellow
COLOR_ADVANCED = "#FF6B6B"      # red

WINDOW_W, WINDOW_H = 760, 820
MIN_W, MIN_H = 600, 560
MAX_W, MAX_H = 960, 1000

GOAL_OPTIONS = [
    "Weight Loss", "Weight Maintenance", "Muscle Gain", "General Fitness",
]

DIFFICULTY_COLORS = {
    "Beginner": COLOR_BEGINNER,
    "Intermediate": COLOR_INTERMEDIATE,
    "Advanced": COLOR_ADVANCED,
}

CATEGORY_ICONS = {
    "Cardio": "🏃",
    "Strength": "💪",
    "Flexibility": "🧘",
    "Low-Impact": "🚶",
    "Balance": "⚖️",
}

# ---------------------------------------------------------------------------
# Exercise database — MET values are standard estimates from the widely
# used Compendium of Physical Activities. duration_min is a sensible
# default session length used to compute an example calorie burn.
# ---------------------------------------------------------------------------
EXERCISES = [
    {"name": "Brisk Walking", "category": "Low-Impact", "met": 3.5, "duration_min": 30,
     "difficulty": "Beginner", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight", "Obese"],
     "suitable_goals": ["Weight Loss", "Weight Maintenance", "General Fitness"],
     "benefits": ["Low joint stress", "Improves cardiovascular health", "Easy to start anywhere"]},

    {"name": "Swimming", "category": "Low-Impact", "met": 6.0, "duration_min": 30,
     "difficulty": "Beginner", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight", "Obese"],
     "suitable_goals": ["Weight Loss", "Weight Maintenance", "General Fitness", "Muscle Gain"],
     "benefits": ["Full-body workout", "Zero impact on joints", "Builds endurance"]},

    {"name": "Stationary Cycling (moderate)", "category": "Cardio", "met": 5.5, "duration_min": 30,
     "difficulty": "Beginner", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight", "Obese"],
     "suitable_goals": ["Weight Loss", "Weight Maintenance", "General Fitness"],
     "benefits": ["Low joint stress", "Builds leg strength", "Easy to control intensity"]},

    {"name": "Yoga (Hatha)", "category": "Flexibility", "met": 2.5, "duration_min": 30,
     "difficulty": "Beginner", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight", "Obese"],
     "suitable_goals": ["Weight Maintenance", "General Fitness"],
     "benefits": ["Improves flexibility", "Reduces stress", "Gentle on joints"]},

    {"name": "Chair Exercises", "category": "Low-Impact", "met": 2.0, "duration_min": 20,
     "difficulty": "Beginner", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight", "Obese"],
     "suitable_goals": ["Weight Maintenance", "General Fitness"],
     "senior_friendly": True,
     "benefits": ["Very gentle", "Improves mobility", "Great for limited mobility or seniors"]},

    {"name": "Water Aerobics", "category": "Low-Impact", "met": 4.0, "duration_min": 30,
     "difficulty": "Beginner", "high_impact": False,
     "suitable_bmi": ["Overweight", "Obese"],
     "suitable_goals": ["Weight Loss", "Weight Maintenance", "General Fitness"],
     "senior_friendly": True,
     "benefits": ["No joint impact", "Builds strength and endurance", "Supportive for higher body weight"]},

    {"name": "Bodyweight Squats", "category": "Strength", "met": 5.0, "duration_min": 15,
     "difficulty": "Beginner", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight"],
     "suitable_goals": ["Muscle Gain", "General Fitness", "Weight Loss"],
     "benefits": ["Builds leg and core strength", "No equipment needed", "Improves functional movement"]},

    {"name": "Resistance Band Training", "category": "Strength", "met": 4.0, "duration_min": 25,
     "difficulty": "Beginner", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight", "Obese"],
     "suitable_goals": ["Muscle Gain", "General Fitness"],
     "benefits": ["Builds strength gently", "Easy on joints", "Great for beginners"]},

    {"name": "Pilates", "category": "Flexibility", "met": 3.0, "duration_min": 30,
     "difficulty": "Intermediate", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight"],
     "suitable_goals": ["Muscle Gain", "General Fitness", "Weight Maintenance"],
     "benefits": ["Strengthens core", "Improves posture", "Builds flexibility"]},

    {"name": "Jogging", "category": "Cardio", "met": 7.0, "duration_min": 30,
     "difficulty": "Intermediate", "high_impact": True,
     "suitable_bmi": ["Underweight", "Normal", "Overweight"],
     "suitable_goals": ["Weight Loss", "General Fitness"],
     "benefits": ["Strong calorie burn", "Builds cardiovascular endurance", "Boosts stamina"]},

    {"name": "Dumbbell Strength Training", "category": "Strength", "met": 5.5, "duration_min": 40,
     "difficulty": "Intermediate", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight"],
     "suitable_goals": ["Muscle Gain", "General Fitness"],
     "benefits": ["Builds muscle mass", "Increases strength", "Boosts metabolism"]},

    {"name": "Dancing (Zumba-style)", "category": "Cardio", "met": 6.5, "duration_min": 30,
     "difficulty": "Intermediate", "high_impact": True,
     "suitable_bmi": ["Underweight", "Normal", "Overweight"],
     "suitable_goals": ["Weight Loss", "General Fitness"],
     "benefits": ["Fun and social", "Strong calorie burn", "Improves coordination"]},

    {"name": "Elliptical Trainer", "category": "Cardio", "met": 5.0, "duration_min": 30,
     "difficulty": "Intermediate", "high_impact": False,
     "suitable_bmi": ["Normal", "Overweight", "Obese"],
     "suitable_goals": ["Weight Loss", "General Fitness"],
     "benefits": ["Low joint impact", "Good calorie burn", "Works upper and lower body"]},

    {"name": "Hiking", "category": "Cardio", "met": 6.0, "duration_min": 45,
     "difficulty": "Intermediate", "high_impact": False,
     "suitable_bmi": ["Normal", "Overweight"],
     "suitable_goals": ["Weight Loss", "General Fitness", "Weight Maintenance"],
     "benefits": ["Builds endurance", "Time outdoors", "Works legs and core"]},

    {"name": "HIIT Circuit", "category": "Cardio", "met": 8.0, "duration_min": 25,
     "difficulty": "Advanced", "high_impact": True,
     "suitable_bmi": ["Normal", "Overweight"],
     "suitable_goals": ["Weight Loss", "General Fitness"],
     "benefits": ["Very high calorie burn", "Time-efficient", "Boosts metabolism for hours after"]},

    {"name": "Running (6 mph)", "category": "Cardio", "met": 9.8, "duration_min": 30,
     "difficulty": "Advanced", "high_impact": True,
     "suitable_bmi": ["Normal", "Overweight"],
     "suitable_goals": ["Weight Loss", "General Fitness"],
     "benefits": ["Excellent calorie burn", "Builds strong cardiovascular fitness", "Improves stamina"]},

    {"name": "Weightlifting (heavy, compound lifts)", "category": "Strength", "met": 6.0, "duration_min": 45,
     "difficulty": "Advanced", "high_impact": False,
     "suitable_bmi": ["Underweight", "Normal", "Overweight"],
     "suitable_goals": ["Muscle Gain"],
     "benefits": ["Maximizes muscle growth", "Builds significant strength", "Increases bone density"]},

    {"name": "Jump Rope", "category": "Cardio", "met": 10.0, "duration_min": 15,
     "difficulty": "Advanced", "high_impact": True,
     "suitable_bmi": ["Normal", "Overweight"],
     "suitable_goals": ["Weight Loss", "General Fitness"],
     "benefits": ["Very high calorie burn in a short time", "Improves coordination", "Builds cardio fitness fast"]},
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


def recommend_exercises(age: int, weight_kg: float, bmi_category: str, fitness_goal: str, top_n: int = 6):
    """
    Rule-based filtering + scoring:
      - Excludes high-impact exercises for Obese BMI or age 60+.
      - Excludes Advanced difficulty unless age < 55 and BMI is
        Normal/Overweight (kept conservative for Underweight/Obese).
      - Excludes Intermediate difficulty for age 70+.
      - Scores remaining exercises by BMI-category match and
        fitness-goal match, then returns the top N with calories
        burned computed for this specific person's weight.
    """
    senior = age >= 60
    very_senior = age >= 70

    eligible = []
    for ex in EXERCISES:
        if ex["high_impact"] and (bmi_category == "Obese" or senior):
            continue
        if ex["difficulty"] == "Advanced" and not (age < 55 and bmi_category in ("Normal", "Overweight")):
            continue
        if ex["difficulty"] == "Intermediate" and very_senior:
            continue
        eligible.append(ex)

    if not eligible:
        # Safety net: everyone should get *something* recommended
        eligible = [ex for ex in EXERCISES if ex["difficulty"] == "Beginner"]

    scored = []
    for ex in eligible:
        score = 0
        if bmi_category in ex["suitable_bmi"]:
            score += 2
        if fitness_goal in ex["suitable_goals"]:
            score += 2
        if senior and ex.get("senior_friendly"):
            score += 1
        scored.append((score, ex))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = [ex for _, ex in scored[:top_n]]

    results = []
    for ex in top:
        calories = ex["met"] * weight_kg * (ex["duration_min"] / 60)
        results.append({**ex, "calories_burned": calories})
    return results


class ExerciseRecommendationPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.on_back = on_back

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Exercise Recommendations")
        self.configure(fg_color=COLOR_BG)
        win_w, win_h = self._compute_responsive_size()
        self._center_window(win_w, win_h)
        self.minsize(MIN_W, MIN_H)
        self.resizable(True, True)

        self._build_ui()

    def _compute_responsive_size(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        target_w = sw * 0.42
        target_h = sh * 0.82
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
            outer, text="Exercise Recommendations",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 4))
        ctk.CTkLabel(
            outer, text="Suggestions tailored to your BMI, age, and fitness goal",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 14))

        self.scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16)

        # ---- Inputs ------------------------------------------------
        d = self.user_data
        row1 = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row1.pack(fill="x")
        row1.grid_columnconfigure((0, 1), weight=1)
        self.age_entry = self._add_entry(row1, "Age", str(d.get("age") or ""), col=0)
        self.weight_entry = self._add_entry(row1, "Weight (kg)", str(d.get("weight_kg") or ""), col=1)

        row2 = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row2.pack(fill="x")
        row2.grid_columnconfigure((0, 1), weight=1)
        self.height_entry = self._add_entry(row2, "Height (cm)", str(d.get("height_cm") or ""), col=0)
        self.goal_menu = self._add_option_menu(row2, "Fitness Goal", GOAL_OPTIONS, d.get("fitness_goal"), col=1)

        self.error_label = ctk.CTkLabel(
            self.scroll, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=500,
        )
        self.error_label.pack(fill="x", pady=(6, 0))

        ctk.CTkButton(
            self.scroll, text="Get Recommendations", height=40,
            corner_radius=10, fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=14, weight="bold"),
            command=self._handle_recommend,
        ).pack(fill="x", pady=(10, 16))

        self.summary_label = ctk.CTkLabel(
            self.scroll, text="", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_ACCENT_SOFT, wraplength=500, justify="center",
        )
        self.summary_label.pack(fill="x", pady=(0, 10))

        self.results_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.results_container.pack(fill="both", expand=True)

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

    # ------------------------------------------------------------ recommend
    def _handle_recommend(self):
        age_raw = self.age_entry.get().strip()
        height_raw = self.height_entry.get().strip()
        weight_raw = self.weight_entry.get().strip()

        if not age_raw.isdigit() or not (1 <= int(age_raw) <= 120):
            self.error_label.configure(text="Enter a valid age between 1 and 120.")
            return
        age = int(age_raw)

        try:
            height = float(height_raw)
            if not (50 <= height <= 250):
                raise ValueError
        except ValueError:
            self.error_label.configure(text="Enter a valid height between 50 and 250 cm.")
            return

        try:
            weight = float(weight_raw)
            if not (20 <= weight <= 300):
                raise ValueError
        except ValueError:
            self.error_label.configure(text="Enter a valid weight between 20 and 300 kg.")
            return

        self.error_label.configure(text="")

        bmi = calculate_bmi(height, weight)
        bmi_category = classify_bmi(bmi)
        fitness_goal = self.goal_menu.get()

        self.summary_label.configure(
            text=f"BMI {bmi:.1f} ({bmi_category})  ·  Age {age}  ·  Goal: {fitness_goal}"
        )

        recommendations = recommend_exercises(age, weight, bmi_category, fitness_goal)
        self._render_results(recommendations)

    def _render_results(self, recommendations):
        for child in self.results_container.winfo_children():
            child.destroy()

        if not recommendations:
            ctk.CTkLabel(
                self.results_container, text="No recommendations found.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(pady=20)
            return

        for ex in recommendations:
            self._exercise_card(self.results_container, ex)

    def _exercise_card(self, parent, ex):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.pack(fill="x", pady=6)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 4))

        icon = CATEGORY_ICONS.get(ex["category"], "🏋️")
        ctk.CTkLabel(
            header, text=f"{icon}  {ex['name']}",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).pack(side="left")

        diff_color = DIFFICULTY_COLORS.get(ex["difficulty"], COLOR_ACCENT)
        ctk.CTkLabel(
            header, text=f"  {ex['difficulty']}  ", fg_color=diff_color,
            text_color="#0B3D3A", font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8,
        ).pack(side="right")

        stats_row = ctk.CTkFrame(card, fg_color="transparent")
        stats_row.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(
            stats_row,
            text=f"⏱  {ex['duration_min']} min    🔥  ~{ex['calories_burned']:.0f} kcal burned    "
                 f"🏷  {ex['category']}",
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")

        for benefit in ex["benefits"]:
            ctk.CTkLabel(
                card, text=f"•  {benefit}", font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
                anchor="w", justify="left", wraplength=460,
            ).pack(fill="x", padx=16, pady=1)

        ctk.CTkFrame(card, fg_color="transparent", height=10).pack()

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
        "fitness_goal": "Weight Loss",
    }
    app = ExerciseRecommendationPage(user_data=demo_user)
    app.mainloop()