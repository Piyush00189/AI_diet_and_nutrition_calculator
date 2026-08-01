"""
feedback_page.py
-------------------
AI Diet Chart & Nutrition Calculator — Feedback
Healthcare-themed, built with CustomTkinter.

Lets a logged-in user rate the app 1-5 stars and leave an optional
comment. Submissions are saved to MySQL via database.insert_feedback()
(feedback table, created automatically by database.py). Also shows
the user's own recent feedback history underneath the form.

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py /
about_page.py (`state('zoomed')`, falling back to `-zoomed` or a
manual full-screen geometry).

Run:
    pip install customtkinter mysql-connector-python
    python feedback_page.py
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
COLOR_STAR_ON = "#FFC94D"
COLOR_STAR_OFF = "#3E7A73"

WINDOW_W, WINDOW_H = 520, 780
MIN_W, MIN_H = 420, 560
MAX_W, MAX_H = 640, 940

RATING_LABELS = {
    1: "Poor — needs real work",
    2: "Fair — some things bother me",
    3: "Good — does the job",
    4: "Great — happy with it",
    5: "Excellent — love it!",
}


class FeedbackPage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        self.user_data = user_data or session.get_current_user() or {}
        self.user_email = self.user_data.get("email")
        self.on_back = on_back

        self.selected_rating = 0
        self.star_buttons = []

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Feedback")
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

        ctk.CTkLabel(
            outer, text="💬  Feedback",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 0))
        ctk.CTkLabel(
            outer, text="Tell us how NutriApp is working for you",
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 16))

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._build_rating_section(scroll)
        self._build_history_section(scroll)

    def _section_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(anchor="w", padx=16, pady=(14, 8))
        return card

    # ------------------------------------------------------------ rating
    def _build_rating_section(self, parent):
        card = self._section_card(parent, "⭐  Rate Your Experience")

        if not self.user_email:
            ctk.CTkLabel(
                card, text="Log in first to submit feedback.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(anchor="w", padx=16, pady=(0, 14))
            return

        stars_row = ctk.CTkFrame(card, fg_color="transparent")
        stars_row.pack(padx=16, pady=(4, 4))

        self.star_buttons = []
        for i in range(1, 6):
            star_btn = ctk.CTkButton(
                stars_row, text="☆", width=44, height=44, corner_radius=10,
                fg_color="transparent", hover_color=COLOR_TRACK,
                text_color=COLOR_STAR_OFF, font=ctk.CTkFont(size=26),
                command=lambda r=i: self._set_rating(r),
            )
            star_btn.grid(row=0, column=i - 1, padx=3)
            # Hovering previews the rating without committing to it
            star_btn.bind("<Enter>", lambda _e, r=i: self._preview_rating(r))
            star_btn.bind("<Leave>", lambda _e: self._preview_rating(self.selected_rating))
            self.star_buttons.append(star_btn)

        self.rating_caption_label = ctk.CTkLabel(
            card, text="Tap a star to rate", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_ACCENT_SOFT,
        )
        self.rating_caption_label.pack(pady=(2, 10))

        ctk.CTkLabel(
            card, text="Comments (optional)", anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", padx=16, pady=(0, 0))
        self.comment_box = ctk.CTkTextbox(
            card, height=110, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE, border_width=1,
        )
        self.comment_box.pack(fill="x", padx=16, pady=(4, 0))

        self.feedback_status_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=400, justify="left",
        )
        self.feedback_status_label.pack(anchor="w", padx=16, pady=(6, 0))

        self.submit_btn = ctk.CTkButton(
            card, text="Submit Feedback", height=36, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_submit_feedback,
        )
        self.submit_btn.pack(fill="x", padx=16, pady=(10, 16))

    def _preview_rating(self, rating):
        """Fills stars up to `rating` with the accent color, without
        changing self.selected_rating — used for hover previews."""
        for i, btn in enumerate(self.star_buttons, start=1):
            if i <= rating:
                btn.configure(text="★", text_color=COLOR_STAR_ON)
            else:
                btn.configure(text="☆", text_color=COLOR_STAR_OFF)

    def _set_rating(self, rating):
        self.selected_rating = rating
        self._preview_rating(rating)
        self.rating_caption_label.configure(
            text=f"{rating} / 5 — {RATING_LABELS[rating]}",
        )
        self.feedback_status_label.configure(text="")

    def _handle_submit_feedback(self):
        if self.selected_rating == 0:
            self.feedback_status_label.configure(
                text_color=COLOR_ERROR, text="Please select a star rating before submitting.",
            )
            return

        comment = self.comment_box.get("1.0", "end").strip()

        self.submit_btn.configure(state="disabled", text="Submitting...")
        self.feedback_status_label.configure(text="")
        self.update_idletasks()

        try:
            database.insert_feedback(self.user_email, self.selected_rating, comment)
        except ValueError as e:
            self.feedback_status_label.configure(text_color=COLOR_ERROR, text=str(e))
            self.submit_btn.configure(state="normal", text="Submit Feedback")
            return
        except mysql.connector.Error as db_err:
            self.feedback_status_label.configure(
                text_color=COLOR_ERROR, text=f"Database error: {db_err}",
            )
            self.submit_btn.configure(state="normal", text="Submit Feedback")
            return

        self.comment_box.delete("1.0", "end")
        self.feedback_status_label.configure(
            text_color=COLOR_SUCCESS, text="Thanks! Your feedback has been saved.",
        )
        self.submit_btn.configure(state="normal", text="Submit Feedback")
        self._refresh_history()

    # ----------------------------------------------------------- history
    def _build_history_section(self, parent):
        self.history_card = self._section_card(parent, "🕓  Your Recent Feedback")
        self.history_list_frame = ctk.CTkFrame(self.history_card, fg_color="transparent")
        self.history_list_frame.pack(fill="x", padx=16, pady=(0, 16))
        self._refresh_history()

    def _refresh_history(self):
        for widget in self.history_list_frame.winfo_children():
            widget.destroy()

        if not self.user_email:
            ctk.CTkLabel(
                self.history_list_frame, text="Log in to see your past feedback.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(anchor="w")
            return

        try:
            entries = database.get_feedback(self.user_email, limit=5)
        except mysql.connector.Error:
            ctk.CTkLabel(
                self.history_list_frame, text="Couldn't load feedback history right now.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(anchor="w")
            return

        if not entries:
            ctk.CTkLabel(
                self.history_list_frame, text="You haven't submitted any feedback yet.",
                font=ctk.CTkFont(size=12), text_color=COLOR_MUTED,
            ).pack(anchor="w")
            return

        for entry in entries:
            row = ctk.CTkFrame(self.history_list_frame, fg_color=COLOR_ENTRY_BG, corner_radius=10)
            row.pack(fill="x", pady=4)

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(8, 0))
            stars_text = "★" * entry["rating"] + "☆" * (5 - entry["rating"])
            ctk.CTkLabel(
                top, text=stars_text, font=ctk.CTkFont(size=13),
                text_color=COLOR_STAR_ON,
            ).pack(side="left")
            ctk.CTkLabel(
                top, text=entry["created_at"].strftime("%d %b %Y"),
                font=ctk.CTkFont(size=10), text_color=COLOR_MUTED,
            ).pack(side="right")

            if entry.get("comment"):
                ctk.CTkLabel(
                    row, text=entry["comment"], font=ctk.CTkFont(size=11),
                    text_color=COLOR_ACCENT_SOFT, anchor="w", justify="left",
                    wraplength=420,
                ).pack(anchor="w", padx=12, pady=(4, 8))
            else:
                ctk.CTkFrame(row, fg_color="transparent", height=4).pack()

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
    app = FeedbackPage(user_data=demo_user)
    app.mainloop()