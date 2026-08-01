"""
about_page.py
----------------
AI Diet Chart & Nutrition Calculator — About
Healthcare-themed, built with CustomTkinter.

Static informational page: project overview, objectives, technology
stack, version, developer credits, and acknowledgements.

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py
(`state('zoomed')`, falling back to `-zoomed` or a manual full-screen
geometry).

Run:
    pip install customtkinter
    python about_page.py
"""

import customtkinter as ctk

APP_VERSION = "1.0.0"

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
COLOR_ENTRY_BG = "#0B3D3A"

WINDOW_W, WINDOW_H = 560, 860
MIN_W, MIN_H = 440, 600
MAX_W, MAX_H = 700, 1000

OBJECTIVES = [
    "Help people understand and track their nutrition and fitness through simple, data-driven tools.",
    "Provide personalized diet and exercise suggestions using AI, tailored to each user's profile and goals.",
    "Make everyday health tracking — BMI, calories, water, weight — quick, visual, and easy to stick with.",
    "Store and manage user health data in a structured, secure database.",
    "Offer a clean, accessible desktop experience that doesn't get in the way of actually using it.",
]

TECHNOLOGIES = [
    ("🐍", "Python", "Core application language"),
    ("🎨", "CustomTkinter", "Modern, themeable desktop UI framework"),
    ("🗄️", "MySQL", "Relational database for accounts, history, and logs"),
    ("✨", "Gemini API", "Powers AI diet plans, food lookup, and health tips"),
    ("🐼", "Pandas", "Data handling and analysis"),
    ("📊", "Matplotlib", "Progress charts and data visualization"),
    ("📄", "ReportLab", "PDF report generation"),
]

DEVELOPERS = [
    ("Piyush", "Full Stack Developer"),
    ("Navdeep", "Full Stack Developer"),
]

ACKNOWLEDGEMENTS = (
    "Thanks to the open-source community behind Python, CustomTkinter, "
    "Pandas, Matplotlib, and ReportLab, whose work this project is built "
    "on — and to Google for the Gemini API that powers the AI features "
    "throughout the app."
)


class AboutPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or {}
        self.on_back = on_back

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — About")
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

        # ---- Logo mark (medical cross in a ring, drawn on canvas) -------
        logo_canvas = ctk.CTkCanvas(outer, width=80, height=80, bg=COLOR_BG, highlightthickness=0)
        logo_canvas.pack(pady=(4, 6))
        self._draw_logo(logo_canvas, 80)

        ctk.CTkLabel(
            outer, text="AI Diet Chart & Nutrition Calculator",
            font=ctk.CTkFont(family="Segoe UI", size=19, weight="bold"),
            text_color=COLOR_WHITE, wraplength=440, justify="center",
        ).pack(padx=16)
        ctk.CTkLabel(
            outer, text=f"Version {APP_VERSION}",
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(2, 14))

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._build_overview_section(scroll)
        self._build_objectives_section(scroll)
        self._build_technologies_section(scroll)
        self._build_developers_section(scroll)
        self._build_acknowledgements_section(scroll)

    def _draw_logo(self, canvas, size):
        cx, cy = size / 2, size / 2
        r = size * (34 / 90)
        u = size / 90
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=COLOR_ACCENT, width=3)
        bar_w, bar_l = 8 * u, 26 * u
        canvas.create_rectangle(cx - bar_w / 2, cy - bar_l / 2, cx + bar_w / 2, cy + bar_l / 2,
                                 fill=COLOR_WHITE, outline="")
        canvas.create_rectangle(cx - bar_l / 2, cy - bar_w / 2, cx + bar_l / 2, cy + bar_w / 2,
                                 fill=COLOR_WHITE, outline="")

    def _section_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", padx=16, pady=(14, 8))
        return card

    # -------------------------------------------------------------- overview
    def _build_overview_section(self, parent):
        card = self._section_card(parent, "📖  About This Project")
        ctk.CTkLabel(
            card,
            text="AI Diet Chart & Nutrition Calculator is a desktop application that "
                 "helps people plan meals, track key health metrics, and build "
                 "sustainable habits — combining structured tracking (BMI, calories, "
                 "water, weight) with AI-generated, personalized guidance for diet "
                 "plans, food lookup, and daily health tips.",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
            wraplength=440, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 16))

    # ------------------------------------------------------------- objectives
    def _build_objectives_section(self, parent):
        card = self._section_card(parent, "🎯  Objectives")
        for obj in OBJECTIVES:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(
                row, text="•", font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT,
            ).pack(side="left", anchor="n", padx=(0, 8))
            ctk.CTkLabel(
                row, text=obj, font=ctk.CTkFont(size=12), text_color=COLOR_WHITE,
                wraplength=400, justify="left", anchor="w",
            ).pack(side="left", fill="x", expand=True)
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    # ----------------------------------------------------------- technologies
    def _build_technologies_section(self, parent):
        card = self._section_card(parent, "🛠️  Technologies Used")
        for icon, name, desc in TECHNOLOGIES:
            row = ctk.CTkFrame(card, fg_color=COLOR_ENTRY_BG, corner_radius=8)
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(
                row, text=icon, font=ctk.CTkFont(size=16),
            ).pack(side="left", padx=(12, 10), pady=10)
            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.pack(side="left", fill="x", expand=True, pady=8)
            ctk.CTkLabel(
                text_col, text=name, font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_WHITE, anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_col, text=desc, font=ctk.CTkFont(size=10),
                text_color=COLOR_MUTED, anchor="w",
            ).pack(anchor="w")
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    # ------------------------------------------------------------- developers
    def _build_developers_section(self, parent):
        card = self._section_card(parent, "👨‍💻  Developer Information")
        for name, role in DEVELOPERS:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=6)

            initials = "".join(w[0] for w in name.split()[:2]).upper()
            ctk.CTkLabel(
                row, text=initials, width=40, height=40, corner_radius=20,
                fg_color=COLOR_ACCENT, text_color="#0B3D3A",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(side="left", padx=(0, 12))

            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.pack(side="left")
            ctk.CTkLabel(
                text_col, text=name, font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLOR_WHITE, anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_col, text=role, font=ctk.CTkFont(size=11),
                text_color=COLOR_ACCENT_SOFT, anchor="w",
            ).pack(anchor="w")
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    # -------------------------------------------------------- acknowledgements
    def _build_acknowledgements_section(self, parent):
        card = self._section_card(parent, "🙏  Acknowledgements")
        ctk.CTkLabel(
            card, text=ACKNOWLEDGEMENTS,
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
            wraplength=440, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 16))

    def _go_back(self):
        from dashboard import DashboardPage
        self.destroy()
        if self.on_back:
            self.on_back()
        else:
            DashboardPage(user_data=self.user_data).mainloop()


if __name__ == "__main__":
    app = AboutPage()
    app.mainloop()