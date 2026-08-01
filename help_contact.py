"""
help_contact.py
----------------
AI Diet Chart & Nutrition Calculator — Help & Contact Page
Healthcare-themed, built with CustomTkinter. Matches the layout of
dashboard.py: left navigation sidebar + top header + scrollable
content area.

Shows: searchable FAQ accordion, a "Getting Started" user guide,
an in-app contact form, direct email support info, and a
troubleshooting accordion for common technical issues.

NOTE: The contact form does not send real email by itself — see
`_submit_contact_form` for where to plug in an SMTP call or a
support-ticket DB insert. Right now it saves submissions locally to
`support_tickets.json` next to this file and shows a confirmation,
so nothing is lost while that integration is pending.

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py /
about_page.py / feedback_page.py / exercise_recommendation.py
(`state('zoomed')`, falling back to `-zoomed` or a manual full-screen
geometry).

Run:
    pip install customtkinter
    python help_contact.py
"""

import json
import os
import webbrowser
from datetime import datetime

import customtkinter as ctk
from tkinter import messagebox

import session

# ---------------------------------------------------------------------------
# Theme constants — matches splash / login / registration / dashboard pages
# ---------------------------------------------------------------------------
COLOR_BG = "#0E4B47"
COLOR_SIDEBAR = "#0B3D3A"
COLOR_CARD = "#155953"
COLOR_ACCENT = "#2FD3B0"
COLOR_ACCENT_SOFT = "#8FE3D1"
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#1E6B64"
COLOR_MUTED = "#6FA69E"
COLOR_DANGER = "#FF8A80"
COLOR_INPUT = "#0F3F3B"

MIN_W, MIN_H = 860, 600

NAV_ITEMS = [
    ("Dashboard", "🏠"),
    ("Meal Planner", "🍽️"),
    ("Water Tracker", "💧"),
    ("Progress", "📈"),
    ("Settings", "⚙️"),
    ("Help & Contact", "❓"),
]

SUPPORT_EMAIL = "support@nutriapp.com"
SUPPORT_HOURS = "Mon–Fri, 9:00 AM – 6:00 PM IST"
TICKETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "support_tickets.json")

DEFAULT_USER_DATA = {
    "full_name": "Guest User",
    "email": "guest@example.com",
}

# ---------------------------------------------------------------------------
# Content data — edit freely, no layout code needs to change
# ---------------------------------------------------------------------------
FAQ_ITEMS = [
    (
        "How is my calorie goal calculated?",
        "Your daily calorie goal is based on your age, gender, height, weight, "
        "and activity level using the Mifflin-St Jeor formula to estimate your "
        "BMR, then adjusted by your activity multiplier and fitness goal "
        "(lose, maintain, or gain weight). You can recalculate it any time from "
        "the Calorie Goal card on your dashboard.",
    ),
    (
        "How do I log a meal?",
        "From the dashboard, use the 'Log Meal' quick action or open the "
        "Nutrition Calculator. Search for a food item or enter it manually, "
        "confirm the portion size, and it's added to your log for the day.",
    ),
    (
        "How do I track my water intake?",
        "Tap the Water Intake card on your dashboard or use the Water Tracker "
        "from the sidebar. Log each glass or bottle as you drink it — your "
        "progress bar updates automatically against your daily goal.",
    ),
    (
        "Can I edit my profile information?",
        "Yes. Open Settings or tap your avatar in the top-right corner to "
        "update your name, email, height, weight, activity level, fitness "
        "goal, or profile picture at any time.",
    ),
    (
        "How accurate is the AI Diet Planner?",
        "The AI Diet Planner generates a personalized Indian meal plan based "
        "on the profile details and goals you've provided. It's a helpful "
        "starting point, not a substitute for advice from a registered "
        "dietitian, especially if you have a medical condition.",
    ),
    (
        "Is my health data private and secure?",
        "Your account is protected with a bcrypt-hashed password, and your "
        "health data is only used to power your own dashboard, charts, and "
        "meal recommendations. It is never shared with third parties.",
    ),
    (
        "How do I reset my password?",
        "On the login screen, select 'Forgot Password' and follow the "
        "prompts. If you're already logged in, you can also change your "
        "password from Settings.",
    ),
    (
        "Can I see my BMI and calorie history over time?",
        "Yes — the Progress page charts your BMI, weight, and calorie trends "
        "from your saved history so you can see how you're tracking against "
        "your goals week over week.",
    ),
]

GUIDE_STEPS = [
    (
        "1",
        "Create your profile",
        "Sign up with your name, email, and password, then fill in your age, "
        "gender, height, weight, activity level, and fitness goal.",
    ),
    (
        "2",
        "Check your dashboard",
        "Your BMI, calorie goal, and water goal are calculated automatically "
        "and shown as cards at the top of your dashboard.",
    ),
    (
        "3",
        "Log meals and water daily",
        "Use the quick action buttons to log meals and water intake as you "
        "go — your progress bars and streak update in real time.",
    ),
    (
        "4",
        "Generate an AI meal plan",
        "Tap 'Generate Plan' on the AI Diet Planner banner for a personalized "
        "weekly Indian meal plan based on your profile.",
    ),
    (
        "5",
        "Track your progress",
        "Visit the Progress page any time to see BMI, weight, and calorie "
        "trends charted over the last 30 days.",
    ),
    (
        "6",
        "Reach out if you're stuck",
        "Use the contact form on this page, or email support directly — "
        "we usually reply within one business day.",
    ),
]

TROUBLESHOOTING_ITEMS = [
    (
        "The app won't launch / shows a database connection error",
        "Make sure MySQL is running locally and that the credentials in "
        "database.py (DB_CONFIG) match your MySQL setup. Confirm the "
        "'diet_app' database exists — run `python database.py` once to "
        "create it and all required tables.",
    ),
    (
        "I forgot my password and the reset isn't working",
        "Double-check you're entering the email address you registered with. "
        "If the issue continues, contact support with your registered email "
        "so we can help you regain access.",
    ),
    (
        "My profile picture isn't updating",
        "Make sure the image file is a common format (JPG or PNG) and isn't "
        "corrupted. After uploading, the picture is saved to your account and "
        "should appear the next time the app restarts — try relaunching if it "
        "doesn't refresh immediately.",
    ),
    (
        "My water or calorie log isn't saving",
        "This usually means the app couldn't reach the database at the "
        "moment you logged it. Check your MySQL connection is active, then "
        "try logging the entry again.",
    ),
    (
        "The AI Diet Planner isn't generating a plan",
        "Confirm your profile has height, weight, activity level, and "
        "fitness goal filled in — the planner needs all of these. If it "
        "still fails, check your internet connection and try again.",
    ),
]

CONTACT_SUBJECTS = [
    "General Question",
    "Bug Report",
    "Feature Request",
    "Account / Login Issue",
    "Billing",
    "Other",
]


class HelpContactPage(ctk.CTk):
    def __init__(self, user_data: dict = None):
        super().__init__()

        self.user_data = {
            **DEFAULT_USER_DATA,
            **(user_data or session.get_current_user() or {}),
        }
        self.active_nav = "Help & Contact"

        # Keep references to accordion state so toggle buttons can find them
        self._faq_bodies = {}
        self._trouble_bodies = {}

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Help & Contact")
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

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_main_area()

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

    # ================================================================ NAV
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLOR_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)

        logo_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_row.pack(fill="x", pady=(24, 30), padx=20)
        ctk.CTkLabel(
            logo_row, text="🥗", font=ctk.CTkFont(size=26),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            logo_row, text="NutriApp",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(side="left")

        self.nav_buttons = {}
        for label, icon in NAV_ITEMS:
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon}   {label}",
                anchor="w", height=42, corner_radius=10,
                fg_color=COLOR_ACCENT if label == self.active_nav else "transparent",
                text_color="#0B3D3A" if label == self.active_nav else COLOR_ACCENT_SOFT,
                hover_color=COLOR_TRACK,
                font=ctk.CTkFont(size=13, weight="bold" if label == self.active_nav else "normal"),
                command=lambda l=label: self._handle_nav_click(l),
            )
            btn.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[label] = btn

        ctk.CTkButton(
            sidebar, text="  🚪   Logout",
            anchor="w", height=42, corner_radius=10,
            fg_color="transparent", text_color=COLOR_DANGER,
            hover_color=COLOR_TRACK,
            font=ctk.CTkFont(size=13),
            command=self._handle_logout,
        ).pack(fill="x", padx=14, pady=(10, 20), side="bottom")

    def _handle_nav_click(self, label):
        if label == "Help & Contact":
            return  # already here
        if label == "Dashboard":
            self._open_dashboard()
        elif label == "Meal Planner":
            self._open_module("meal_planner", "MealPlannerPage")
        elif label == "Water Tracker":
            self._open_module("water_tracker", "WaterTrackerPage")
        elif label == "Progress":
            self._open_module("progress_tracker", "ProgressTrackerPage")
        elif label == "Settings":
            self._open_module("settings_page", "SettingsPage")
        else:
            print(f"[nav] Clicked '{label}' — no module wired up yet.")

    def _open_dashboard(self):
        from dashboard import DashboardPage
        self.destroy()
        DashboardPage(user_data=self.user_data).mainloop()

    def _open_module(self, module_name, class_name):
        """Generic lazy-import navigation helper, mirroring dashboard.py's
        per-page import pattern. Falls back gracefully if a module isn't
        built yet instead of crashing the whole app."""
        try:
            module = __import__(module_name, fromlist=[class_name])
            page_class = getattr(module, class_name)
        except (ImportError, AttributeError):
            print(f"[nav] '{module_name}.{class_name}' isn't available yet.")
            return
        self.destroy()
        page_class(user_data=self.user_data).mainloop()

    def _handle_logout(self):
        try:
            from logout_page import confirm_logout
            confirm_logout(self)
        except ImportError:
            print("[nav] logout_page module not found.")

    # =========================================================== MAIN AREA
    def _build_main_area(self):
        main = ctk.CTkFrame(self, fg_color=COLOR_BG)
        main.grid(row=0, column=1, sticky="nswe")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self._build_header(main)

        content = ctk.CTkScrollableFrame(main, fg_color=COLOR_BG)
        content.grid(row=1, column=0, sticky="nswe", padx=24, pady=(0, 20))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)

        self._build_intro_banner(content)
        self._build_guide_section(content)
        self._build_faq_section(content)
        self._build_troubleshooting_section(content)
        self._build_contact_and_email_section(content)

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color=COLOR_SIDEBAR, height=70, corner_radius=0)
        header.grid(row=0, column=0, sticky="nswe")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=24)
        ctk.CTkLabel(
            left, text="Help & Contact",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", pady=(12, 0))
        ctk.CTkLabel(
            left, text="Guides, answers, and ways to reach us",
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=24)
        initials = "".join(w[0] for w in self.user_data["full_name"].split()[:2]).upper()
        ctk.CTkButton(
            right, text=initials, width=42, height=42, corner_radius=21,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._open_dashboard,
        ).pack(side="right", pady=14)

    # ------------------------------------------------------- intro banner
    def _build_intro_banner(self, parent):
        banner = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        banner.grid(row=0, column=0, columnspan=2, sticky="nswe", padx=8, pady=(4, 16))
        banner.grid_columnconfigure(0, weight=1)

        text_col = ctk.CTkFrame(banner, fg_color="transparent")
        text_col.grid(row=0, column=0, sticky="w", padx=20, pady=16)
        ctk.CTkLabel(
            text_col, text="🙋 We're here to help",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col,
            text="Browse the FAQ, follow the getting-started guide, or send us a message directly.",
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            banner, text=f"✉️  Email {SUPPORT_EMAIL}", width=220, height=36,
            corner_radius=10, fg_color=COLOR_ACCENT, hover_color="#26B79A",
            text_color="#0B3D3A", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_email_client,
        ).grid(row=0, column=1, sticky="e", padx=20, pady=16)

    # ----------------------------------------------------- guide section
    def _build_guide_section(self, parent):
        ctk.CTkLabel(
            parent, text="Getting Started Guide",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).grid(row=1, column=0, sticky="w", padx=8, pady=(4, 8))

        guide_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        guide_card.grid(row=2, column=0, sticky="nswe", padx=8, pady=(0, 20))

        for i, (num, title, desc) in enumerate(GUIDE_STEPS):
            row = ctk.CTkFrame(guide_card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(14 if i == 0 else 6, 6 if i < len(GUIDE_STEPS) - 1 else 16))

            badge = ctk.CTkLabel(
                row, text=num, width=28, height=28, corner_radius=14,
                fg_color=COLOR_ACCENT, text_color="#0B3D3A",
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            badge.pack(side="left", anchor="n", padx=(0, 12))

            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                text_col, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLOR_WHITE, anchor="w", justify="left",
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_col, text=desc, font=ctk.CTkFont(size=11),
                text_color=COLOR_MUTED, anchor="w", justify="left",
                wraplength=460,
            ).pack(anchor="w", pady=(2, 0))

    # ------------------------------------------------------- FAQ section
    def _build_faq_section(self, parent):
        ctk.CTkLabel(
            parent, text="Frequently Asked Questions",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).grid(row=3, column=0, sticky="w", padx=8, pady=(4, 8))

        # Search box to filter the FAQ list live
        search_row = ctk.CTkFrame(parent, fg_color="transparent")
        search_row.grid(row=4, column=0, sticky="we", padx=8, pady=(0, 8))
        self.faq_search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            search_row, placeholder_text="🔍  Search FAQs…",
            fg_color=COLOR_INPUT, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE, height=36, corner_radius=10,
            textvariable=self.faq_search_var,
        )
        search_entry.pack(fill="x")
        self.faq_search_var.trace_add("write", lambda *_: self._filter_faqs())

        self.faq_list_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.faq_list_frame.grid(row=5, column=0, sticky="nswe", padx=8, pady=(0, 20))

        self.faq_cards = []  # (question_lower, card_frame)
        self._render_faq_items(FAQ_ITEMS)

    def _render_faq_items(self, items):
        for widget in self.faq_list_frame.winfo_children():
            widget.destroy()
        self.faq_cards.clear()
        self._faq_bodies.clear()

        if not items:
            ctk.CTkLabel(
                self.faq_list_frame, text="No matching questions. Try a different search term.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(pady=16)
            return

        for i, (question, answer) in enumerate(items):
            card = self._accordion_item(
                self.faq_list_frame, key=f"faq_{i}",
                header_text=question, body_text=answer,
                body_store=self._faq_bodies,
            )
            card.pack(fill="x", pady=5)
            self.faq_cards.append((question.lower(), card))

    def _filter_faqs(self):
        query = self.faq_search_var.get().strip().lower()
        if not query:
            self._render_faq_items(FAQ_ITEMS)
            return
        filtered = [(q, a) for q, a in FAQ_ITEMS if query in q.lower() or query in a.lower()]
        self._render_faq_items(filtered)

    # ----------------------------------------------- troubleshooting section
    def _build_troubleshooting_section(self, parent):
        ctk.CTkLabel(
            parent, text="Troubleshooting",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).grid(row=6, column=0, sticky="w", padx=8, pady=(4, 8))

        trouble_frame = ctk.CTkFrame(parent, fg_color="transparent")
        trouble_frame.grid(row=7, column=0, sticky="nswe", padx=8, pady=(0, 20))

        for i, (issue, fix) in enumerate(TROUBLESHOOTING_ITEMS):
            card = self._accordion_item(
                trouble_frame, key=f"trouble_{i}",
                header_text=f"⚠️  {issue}", body_text=fix,
                body_store=self._trouble_bodies,
            )
            card.pack(fill="x", pady=5)

    # ---------------------------------------- shared accordion item builder
    def _accordion_item(self, parent, key, header_text, body_text, body_store):
        """Builds one collapsible FAQ / troubleshooting row: a clickable
        header that toggles a body frame with the full answer."""
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=12)

        header_btn = ctk.CTkButton(
            card, text=f"{header_text}     ▾", anchor="w",
            fg_color="transparent", hover_color=COLOR_TRACK,
            text_color=COLOR_WHITE, height=40, corner_radius=10,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._toggle_accordion(key, body_store, header_btn, header_text),
        )
        header_btn.pack(fill="x", padx=6, pady=6)

        body = ctk.CTkLabel(
            card, text=body_text, font=ctk.CTkFont(size=11),
            text_color=COLOR_MUTED, justify="left", anchor="w",
            wraplength=460,
        )
        body_store[key] = {"widget": body, "visible": False}
        return card

    def _toggle_accordion(self, key, body_store, header_btn, header_text):
        entry = body_store[key]
        if entry["visible"]:
            entry["widget"].pack_forget()
            header_btn.configure(text=f"{header_text}     ▾")
            entry["visible"] = False
        else:
            entry["widget"].pack(fill="x", padx=18, pady=(0, 12), anchor="w")
            header_btn.configure(text=f"{header_text}     ▴")
            entry["visible"] = True

    # ------------------------------------------- contact form + email card
    def _build_contact_and_email_section(self, parent):
        ctk.CTkLabel(
            parent, text="Contact Support",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_WHITE,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(4, 8))

        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.grid(row=2, column=1, rowspan=6, sticky="nswe", padx=8, pady=(0, 20))
        outer.grid_columnconfigure(0, weight=1)

        self._build_contact_form(outer)
        self._build_email_support_card(outer)

    def _build_contact_form(self, parent):
        form_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        form_card.pack(fill="x", pady=(0, 14))

        inner = ctk.CTkFrame(form_card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(
            inner, text="Send us a message",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_WHITE,
        ).pack(anchor="w", pady=(0, 10))

        self.contact_name_var = ctk.StringVar(value=self.user_data.get("full_name", ""))
        self.contact_email_var = ctk.StringVar(value=self.user_data.get("email", ""))
        self.contact_subject_var = ctk.StringVar(value=CONTACT_SUBJECTS[0])

        self._labeled_entry(inner, "Name", self.contact_name_var)
        self._labeled_entry(inner, "Email", self.contact_email_var)

        ctk.CTkLabel(
            inner, text="Subject", font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w", pady=(8, 2))
        ctk.CTkOptionMenu(
            inner, values=CONTACT_SUBJECTS, variable=self.contact_subject_var,
            fg_color=COLOR_INPUT, button_color=COLOR_TRACK, button_hover_color=COLOR_ACCENT,
            text_color=COLOR_WHITE, dropdown_fg_color=COLOR_INPUT,
            corner_radius=10, height=36,
        ).pack(fill="x")

        ctk.CTkLabel(
            inner, text="Message", font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w", pady=(8, 2))
        self.contact_message_box = ctk.CTkTextbox(
            inner, height=110, fg_color=COLOR_INPUT, text_color=COLOR_WHITE,
            corner_radius=10, border_color=COLOR_TRACK, border_width=1,
        )
        self.contact_message_box.pack(fill="x")

        self.contact_status_label = ctk.CTkLabel(
            inner, text="", font=ctk.CTkFont(size=10), text_color=COLOR_ACCENT,
        )
        self.contact_status_label.pack(anchor="w", pady=(8, 0))

        ctk.CTkButton(
            inner, text="Submit", height=38, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._submit_contact_form,
        ).pack(fill="x", pady=(12, 0))

    def _labeled_entry(self, parent, label, variable):
        ctk.CTkLabel(
            parent, text=label, font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(anchor="w", pady=(0, 2))
        ctk.CTkEntry(
            parent, textvariable=variable, height=36, corner_radius=10,
            fg_color=COLOR_INPUT, border_color=COLOR_TRACK, text_color=COLOR_WHITE,
        ).pack(fill="x", pady=(0, 4))

    def _submit_contact_form(self):
        name = self.contact_name_var.get().strip()
        email = self.contact_email_var.get().strip()
        subject = self.contact_subject_var.get().strip()
        message = self.contact_message_box.get("1.0", "end").strip()

        if not name or not email or not message:
            self.contact_status_label.configure(
                text="Please fill in your name, email, and a message.",
                text_color=COLOR_DANGER,
            )
            return
        if "@" not in email or "." not in email.split("@")[-1]:
            self.contact_status_label.configure(
                text="Please enter a valid email address.", text_color=COLOR_DANGER,
            )
            return

        ticket = {
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            self._save_ticket_locally(ticket)
            saved_ok = True
        except OSError:
            saved_ok = False

        # --- INTEGRATION POINT ---
        # Wire up real delivery here once ready, e.g.:
        #   send_support_email(ticket)               # SMTP call
        #   database.insert_support_ticket(**ticket)  # if a support_tickets
        #                                              # table is added to database.py
        # For now the ticket is only persisted locally (see _save_ticket_locally).

        self.contact_message_box.delete("1.0", "end")
        if saved_ok:
            self.contact_status_label.configure(
                text="Thanks — your message has been received. We'll reply by email soon.",
                text_color=COLOR_ACCENT,
            )
            messagebox.showinfo(
                "Message sent",
                "Thanks for reaching out! Our team will get back to you at "
                f"{email} within one business day.",
            )
        else:
            self.contact_status_label.configure(
                text="Something went wrong saving your message locally — "
                     f"please email us directly at {SUPPORT_EMAIL}.",
                text_color=COLOR_DANGER,
            )

    def _save_ticket_locally(self, ticket: dict) -> None:
        """Placeholder persistence so no submission is lost before a real
        email/DB integration exists. Appends to a JSON file next to this
        script."""
        tickets = []
        if os.path.exists(TICKETS_FILE):
            try:
                with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                    tickets = json.load(f)
            except (json.JSONDecodeError, OSError):
                tickets = []
        tickets.append(ticket)
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(tickets, f, indent=2)

    def _build_email_support_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.pack(fill="x")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(
            inner, text="📧  Prefer email?",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner, text=SUPPORT_EMAIL,
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_ACCENT,
        ).pack(anchor="w", pady=(6, 0))
        ctk.CTkLabel(
            inner, text=f"Support hours: {SUPPORT_HOURS}",
            font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            inner, text="Typical response time: within 1 business day",
            font=ctk.CTkFont(size=11), text_color=COLOR_MUTED,
        ).pack(anchor="w", pady=(2, 12))

        ctk.CTkButton(
            inner, text="Open Email Client", height=36, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=COLOR_ACCENT,
            hover_color=COLOR_TRACK, text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_email_client,
        ).pack(fill="x")

    def _open_email_client(self):
        subject = "NutriApp Support Request"
        webbrowser.open(f"mailto:{SUPPORT_EMAIL}?subject={subject}")


if __name__ == "__main__":
    app = HelpContactPage()
    app.mainloop()