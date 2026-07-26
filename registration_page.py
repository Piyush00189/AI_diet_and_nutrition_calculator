import re
import customtkinter as ctk
import mysql.connector

import database
import session

# ---------------------------------------------------------------------------
# Theme constants — matches the splash screen / login page
# ---------------------------------------------------------------------------
COLOR_BG = "#0E4B47"
COLOR_ACCENT = "#2FD3B0"
COLOR_ACCENT_SOFT = "#8FE3D1"
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#155953"
COLOR_ENTRY_BG = "#0B3D3A"
COLOR_ERROR = "#FF8A80"
COLOR_SUCCESS = "#8CFFB0"

WINDOW_W, WINDOW_H = 480, 700

GENDER_OPTIONS = ["Male", "Female", "Other"]
ACTIVITY_OPTIONS = [
    "Sedentary",
    "Lightly Active",
    "Moderately Active",
    "Very Active",
    "Extra Active",
]
GOAL_OPTIONS = [
    "Weight Loss",
    "Weight Maintenance",
    "Muscle Gain",
    "General Fitness",
]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?\d{7,15}$")


class RegistrationPage(ctk.CTk):
    def __init__(self, on_success=None):
        super().__init__()

        # on_success(email): optional extra hook fired right after a
        # successful registration (e.g. for analytics/logging). It does
        # NOT control navigation — a new account now always lands
        # straight on the Dashboard instead of the Login page, since
        # they just gave us all the info a login would collect anyway.
        self.on_success = on_success

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Register")
        self.configure(fg_color=COLOR_BG)
        self._center_window(WINDOW_W, WINDOW_H)
        self.resizable(False, False)

        self._build_ui()

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

        ctk.CTkLabel(
            outer, text="Create Your Account",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(20, 2))

        ctk.CTkLabel(
            outer, text="Tell us about yourself to personalize your plan",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 14))

        # Scrollable form area — keeps the window a reasonable size
        # even with 11 fields.
        form = ctk.CTkScrollableFrame(
            outer, fg_color="transparent", width=400, height=430,
            scrollbar_button_color=COLOR_TRACK,
        )
        form.pack(fill="both", expand=True, padx=16)

        self.full_name_entry = self._add_entry(form, "Full Name", "e.g. Piyush Kawatra")
        self.email_entry = self._add_entry(form, "Email", "you@example.com")
        self.password_entry = self._add_password_entry(form, "Password", "At least 8 characters")
        self.confirm_password_entry = self._add_password_entry(
            form, "Confirm Password", "Re-enter password")
        self.phone_entry = self._add_entry(form, "Phone Number", "e.g. 9876543210")
        self.age_entry = self._add_entry(form, "Age", "e.g. 28")
        self.gender_menu = self._add_option_menu(form, "Gender", GENDER_OPTIONS)
        self.height_entry = self._add_entry(form, "Height (cm)", "e.g. 170")
        self.weight_entry = self._add_entry(form, "Weight (kg)", "e.g. 65")
        self.activity_menu = self._add_option_menu(form, "Activity Level", ACTIVITY_OPTIONS)
        self.goal_menu = self._add_option_menu(form, "Fitness Goal", GOAL_OPTIONS)

        # Error / status message
        self.message_label = ctk.CTkLabel(
            outer, text="", wraplength=380,
            font=ctk.CTkFont(size=12), text_color=COLOR_ERROR,
        )
        self.message_label.pack(pady=(8, 4))

        self.register_btn = ctk.CTkButton(
            outer, text="Register", width=340, height=40,
            corner_radius=10, fg_color=COLOR_ACCENT,
            hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._handle_register,
        )
        self.register_btn.pack(pady=(4, 8))

        login_row = ctk.CTkFrame(outer, fg_color="transparent")
        login_row.pack(pady=(0, 14))
        ctk.CTkLabel(
            login_row, text="Already have an account?",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(side="left")
        ctk.CTkButton(
            login_row, text="Log In",
            fg_color="transparent", hover=False,
            text_color=COLOR_ACCENT, font=ctk.CTkFont(size=12, underline=True),
            width=20, command=self._go_to_login,
        ).pack(side="left", padx=4)

    def _add_entry(self, parent, label_text, placeholder, show=None):
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(8, 0))
        entry = ctk.CTkEntry(
            parent, placeholder_text=placeholder,
            height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
            show=show if show else "",
        )
        entry.pack(fill="x", pady=(4, 0))
        return entry

    def _add_password_entry(self, parent, label_text, placeholder):
        """Like _add_entry, but masks the input and adds a 👁 button
        alongside it that toggles the password's visibility."""
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(8, 0))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(4, 0))
        row.grid_columnconfigure(0, weight=1)

        entry = ctk.CTkEntry(
            row, placeholder_text=placeholder,
            height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
            show="•",
        )
        entry.grid(row=0, column=0, sticky="ew")

        toggle_btn = ctk.CTkButton(
            row, text="👁", width=36, height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=13),
            command=lambda: self._toggle_password_visibility(entry, toggle_btn),
        )
        toggle_btn.grid(row=0, column=1, padx=(6, 0))

        return entry

    def _toggle_password_visibility(self, entry, toggle_btn):
        if entry.cget("show") == "":
            entry.configure(show="•")
            toggle_btn.configure(text="👁")
        else:
            entry.configure(show="")
            toggle_btn.configure(text="🙈")

    def _add_option_menu(self, parent, label_text, options):
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(8, 0))
        menu = ctk.CTkOptionMenu(
            parent, values=options,
            height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, button_color=COLOR_TRACK,
            button_hover_color=COLOR_ACCENT, text_color=COLOR_WHITE,
        )
        menu.set(options[0])
        menu.pack(fill="x", pady=(4, 0))
        return menu

    # ------------------------------------------------------------ validation
    def _validate(self):
        """Returns a list of error messages (empty list = all valid)."""
        errors = []

        full_name = self.full_name_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        confirm_password = self.confirm_password_entry.get()
        phone = self.phone_entry.get().strip()
        age_raw = self.age_entry.get().strip()
        height_raw = self.height_entry.get().strip()
        weight_raw = self.weight_entry.get().strip()

        # Full name: letters/spaces only, at least 2 characters
        if len(full_name) < 2 or not all(c.isalpha() or c.isspace() for c in full_name):
            errors.append("Enter a valid full name (letters only).")

        # Email
        if not EMAIL_PATTERN.match(email):
            errors.append("Enter a valid email address.")

        # Password: min 8 chars, at least one letter and one digit
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            errors.append("Password must be at least 8 characters and include a letter and a number.")

        # Confirm password
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Phone: 7-15 digits, optional leading +
        if not PHONE_PATTERN.match(phone):
            errors.append("Enter a valid phone number (7-15 digits).")

        # Age
        age = None
        if not age_raw.isdigit() or not (1 <= int(age_raw) <= 120):
            errors.append("Enter a valid age between 1 and 120.")
        else:
            age = int(age_raw)

        # Height (cm)
        height = None
        try:
            height = float(height_raw)
            if not (50 <= height <= 250):
                errors.append("Enter a valid height between 50 and 250 cm.")
                height = None
        except ValueError:
            errors.append("Enter a valid numeric height (cm).")

        # Weight (kg)
        weight = None
        try:
            weight = float(weight_raw)
            if not (20 <= weight <= 300):
                errors.append("Enter a valid weight between 20 and 300 kg.")
                weight = None
        except ValueError:
            errors.append("Enter a valid numeric weight (kg).")

        cleaned = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "phone": phone,
            "age": age,
            "gender": self.gender_menu.get(),
            "height": height,
            "weight": weight,
            "activity_level": self.activity_menu.get(),
            "fitness_goal": self.goal_menu.get(),
        }
        return errors, cleaned

    # ---------------------------------------------------------------- logic
    def _handle_register(self):
        errors, data = self._validate()

        if errors:
            self.message_label.configure(text_color=COLOR_ERROR, text=errors[0])
            return

        self.register_btn.configure(state="disabled", text="Registering...")
        self.message_label.configure(text_color=COLOR_ACCENT_SOFT, text="")
        self.update_idletasks()

        try:
            database.insert_user(
                full_name=data["full_name"],
                email=data["email"],
                password=data["password"],
                phone=data["phone"],
                age=data["age"],
                gender=data["gender"],
                height_cm=data["height"],
                weight_kg=data["weight"],
                activity_level=data["activity_level"],
                fitness_goal=data["fitness_goal"],
            )
        except ValueError as ve:
            # e.g. duplicate email
            self.message_label.configure(text_color=COLOR_ERROR, text=str(ve))
            self.register_btn.configure(state="normal", text="Register")
            return
        except mysql.connector.Error as db_err:
            self.message_label.configure(
                text_color=COLOR_ERROR,
                text=f"Database error: {db_err}",
            )
            self.register_btn.configure(state="normal", text="Register")
            return

        # Log the brand-new account straight into a session — same shape
        # login_page.py uses (full row minus the password hash) — so the
        # Dashboard we're about to open has real profile data to work with.
        user_row = database.get_user_by_email(data["email"]) or {}
        user_row.pop("password_hash", None)
        session.set_current_user(user_row)

        self.message_label.configure(
            text_color=COLOR_SUCCESS, text="Account created successfully!"
        )
        self.register_btn.configure(state="normal", text="Register")

        if self.on_success:
            self.on_success(data["email"])

        self.after(600, lambda: self._finish(user_row))

    def _finish(self, user_data):
        from dashboard import DashboardPage
        self.destroy()
        DashboardPage(user_data=user_data).mainloop()

    def _go_to_login(self):
        from login_page import LoginPage
        self.destroy()
        LoginPage().mainloop()


if __name__ == "__main__":
    app = RegistrationPage()
    app.mainloop()