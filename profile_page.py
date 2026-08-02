"""
profile_page.py
-----------------
AI Diet Chart & Nutrition Calculator — User Profile Page
Healthcare-themed, built with CustomTkinter.

Lets the logged-in user view and edit: profile picture, full name,
email, phone, age, gender, height, weight, activity level, and
fitness goal. Saves to MySQL via database.update_profile().

Editing email re-checks it isn't already used by another account
before saving, since email is the app's login identifier.

DISPLAY: opens maximized/full-screen on launch, same approach as
login_page.py / dashboard.py / bmi_calculator.py / calorie_calculator.py
/ notifications_page.py / ai_health_tips.py / settings_page.py /
about_page.py / feedback_page.py / exercise_recommendation.py /
help_contact.py / diet_planner.py / meal_planner.py /
forgot_password_page.py / nutrition_calculator.py (`state('zoomed')`,
falling back to `-zoomed` or a manual full-screen geometry).

Run:
    pip install customtkinter mysql-connector-python pillow
    python profile_page.py
"""

import os
import re
import shutil
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps
import mysql.connector

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

MIN_W, MIN_H = 380, 560
AVATAR_SIZE = 110

GENDER_OPTIONS = ["Male", "Female", "Other"]
ACTIVITY_OPTIONS = [
    "Sedentary", "Lightly Active", "Moderately Active",
    "Very Active", "Extra Active",
]
GOAL_OPTIONS = [
    "Weight Loss", "Weight Maintenance", "Muscle Gain", "General Fitness",
]

PROFILE_PICTURES_DIR = "profile_pictures"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?\d{7,15}$")


class ProfilePage(ctk.CTk):
    def __init__(self, user_data: dict = None, on_back=None):
        super().__init__()

        # Prefer explicitly-passed user_data; otherwise use the session's
        # logged-in user. A profile page with nobody logged in doesn't
        # make sense, so this is the one place we require it.
        self.user_data = user_data or session.get_current_user()
        self.on_back = on_back

        if not self.user_data or "email" not in self.user_data:
            raise ValueError(
                "ProfilePage requires a logged-in user (pass user_data "
                "or log in first so session.py has a current user)."
            )

        # The email this row is currently stored under in MySQL — used to
        # locate the row when saving, even if the user changes their email.
        self.original_email = self.user_data["email"]

        self.new_picture_path = None  # local path of a newly-picked photo

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Profile")
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

        # Back button
        top_row = ctk.CTkFrame(outer, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkButton(
            top_row, text="←  Back", width=70, height=30,
            fg_color="transparent", hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=12),
            command=self._go_back,
        ).pack(side="left")

        ctk.CTkLabel(
            outer, text="My Profile",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(6, 16))

        # ---- Profile picture -------------------------------------------
        self.avatar_label = ctk.CTkLabel(outer, text="", image=None)
        self.avatar_label.pack(pady=(0, 8))
        self._refresh_avatar()

        ctk.CTkButton(
            outer, text="Change Photo", width=160, height=32,
            corner_radius=8, fg_color=COLOR_CARD, hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=12),
            command=self._handle_change_photo,
        ).pack(pady=(0, 18))

        # Scrollable form for the rest — keeps the content usable at any
        # window height, and centers nicely in a maximized window since
        # it's constrained to a comfortable reading width.
        form_wrap = ctk.CTkFrame(outer, fg_color="transparent")
        form_wrap.pack(fill="both", expand=True, padx=16)
        form_wrap.grid_columnconfigure(0, weight=1)
        form_wrap.grid_columnconfigure(1, weight=0, minsize=440)
        form_wrap.grid_columnconfigure(2, weight=1)
        form_wrap.grid_rowconfigure(0, weight=1)

        form = ctk.CTkScrollableFrame(form_wrap, fg_color="transparent", width=440)
        form.grid(row=0, column=1, sticky="nswe")

        # ---- Editable identity fields -----------------------------------
        self.full_name_entry = self._add_entry(
            form, "Full Name", self.user_data.get("full_name", ""))
        self.email_entry = self._add_entry(
            form, "Email", self.user_data.get("email", ""))
        self.phone_entry = self._add_entry(
            form, "Phone", self.user_data.get("phone") or "")

        # ---- Editable health fields --------------------------------
        self.age_entry = self._add_entry(
            form, "Age", str(self.user_data.get("age") or ""))
        self.gender_menu = self._add_option_menu(
            form, "Gender", GENDER_OPTIONS, self.user_data.get("gender"))
        self.height_entry = self._add_entry(
            form, "Height (cm)", str(self.user_data.get("height_cm") or ""))
        self.weight_entry = self._add_entry(
            form, "Weight (kg)", str(self.user_data.get("weight_kg") or ""))
        self.activity_menu = self._add_option_menu(
            form, "Activity Level", ACTIVITY_OPTIONS, self.user_data.get("activity_level"))
        self.goal_menu = self._add_option_menu(
            form, "Fitness Goal", GOAL_OPTIONS, self.user_data.get("fitness_goal"))

        self.message_label = ctk.CTkLabel(
            outer, text="", wraplength=380,
            font=ctk.CTkFont(size=12), text_color=COLOR_ERROR,
        )
        self.message_label.pack(pady=(6, 4))

        self.save_btn = ctk.CTkButton(
            outer, text="Update", width=340, height=40,
            corner_radius=10, fg_color=COLOR_ACCENT,
            hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._handle_update_click,
        )
        self.save_btn.pack(pady=(4, 18))

    def _add_readonly(self, parent, label_text, value):
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(
            parent, text=value, anchor="w",
            font=ctk.CTkFont(size=13), text_color=COLOR_MUTED,
        ).pack(fill="x", pady=(2, 0))

    def _add_entry(self, parent, label_text, initial_value):
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(10, 0))
        entry = ctk.CTkEntry(
            parent, height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, border_color=COLOR_TRACK,
            text_color=COLOR_WHITE,
        )
        entry.insert(0, initial_value)
        entry.pack(fill="x", pady=(4, 0))
        return entry

    def _add_option_menu(self, parent, label_text, options, current_value):
        ctk.CTkLabel(
            parent, text=label_text, anchor="w",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(fill="x", pady=(10, 0))
        menu = ctk.CTkOptionMenu(
            parent, values=options,
            height=36, corner_radius=10,
            fg_color=COLOR_ENTRY_BG, button_color=COLOR_TRACK,
            button_hover_color=COLOR_ACCENT, text_color=COLOR_WHITE,
        )
        menu.set(current_value if current_value in options else options[0])
        menu.pack(fill="x", pady=(4, 0))
        return menu

    # ------------------------------------------------------------- avatar
    def _refresh_avatar(self):
        path = self.new_picture_path or self.user_data.get("profile_picture_path")
        image = self._load_circular_image(path)
        self.avatar_label.configure(image=image)
        self.avatar_label.image = image  # keep a reference

    def _load_circular_image(self, path):
        """Loads `path` (or falls back to an initials avatar) as a
        circular CTkImage sized AVATAR_SIZE x AVATAR_SIZE."""
        size = AVATAR_SIZE
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert("RGB")
                img = ImageOps.fit(img, (size, size), Image.LANCZOS)
            except Exception:
                img = self._initials_image(size)
        else:
            img = self._initials_image(size)

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        img.putalpha(mask)

        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

    def _initials_image(self, size):
        """Fallback avatar: solid accent circle with the user's initials."""
        full_name = self.user_data.get("full_name", "?")
        initials = "".join(w[0] for w in full_name.split()[:2]).upper() or "?"

        img = Image.new("RGB", (size, size), COLOR_ACCENT)
        draw = ImageDraw.Draw(img)
        # Centered text without needing a specific font file
        bbox = draw.textbbox((0, 0), initials)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
            initials, fill="#0B3D3A",
        )
        return img

    def _handle_change_photo(self):
        filepath = filedialog.askopenfilename(
            title="Choose a profile picture",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")],
        )
        if not filepath:
            return

        os.makedirs(PROFILE_PICTURES_DIR, exist_ok=True)
        ext = os.path.splitext(filepath)[1]
        dest = os.path.join(
            PROFILE_PICTURES_DIR, f"{self.original_email.split('@')[0]}{ext}"
        )
        try:
            shutil.copy(filepath, dest)
        except Exception as e:
            self.message_label.configure(text_color=COLOR_ERROR, text=f"Couldn't load image: {e}")
            return

        self.new_picture_path = dest
        self._refresh_avatar()

    # ------------------------------------------------------------ validate
    def _validate(self):
        errors = []

        full_name = self.full_name_entry.get().strip()
        new_email = self.email_entry.get().strip()
        phone = self.phone_entry.get().strip()
        age_raw = self.age_entry.get().strip()
        height_raw = self.height_entry.get().strip()
        weight_raw = self.weight_entry.get().strip()

        if len(full_name) < 2 or not all(c.isalpha() or c.isspace() for c in full_name):
            errors.append("Enter a valid full name (letters only).")

        if not EMAIL_PATTERN.match(new_email):
            errors.append("Enter a valid email address.")

        if not PHONE_PATTERN.match(phone):
            errors.append("Enter a valid phone number (7-15 digits).")

        age = None
        if not age_raw.isdigit() or not (1 <= int(age_raw) <= 120):
            errors.append("Enter a valid age between 1 and 120.")
        else:
            age = int(age_raw)

        height = None
        try:
            height = float(height_raw)
            if not (50 <= height <= 250):
                errors.append("Enter a valid height between 50 and 250 cm.")
                height = None
        except ValueError:
            errors.append("Enter a valid numeric height (cm).")

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
            "email": new_email,
            "phone": phone,
            "age": age,
            "gender": self.gender_menu.get(),
            "height_cm": height,
            "weight_kg": weight,
            "activity_level": self.activity_menu.get(),
            "fitness_goal": self.goal_menu.get(),
        }
        return errors, cleaned

    # ---------------------------------------------------------------- save
    def _handle_update_click(self):
        """Validates the form, then asks for confirmation before writing
        anything to MySQL — the actual save happens in _perform_update()
        only if the user confirms."""
        errors, data = self._validate()
        if errors:
            self.message_label.configure(text_color=COLOR_ERROR, text=errors[0])
            return

        self.message_label.configure(text="")
        self._show_update_confirm(data)

    def _show_update_confirm(self, data):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Update")
        dialog.configure(fg_color=COLOR_BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        w, h = 320, 190
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        card = ctk.CTkFrame(dialog, fg_color=COLOR_CARD, corner_radius=16)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            card, text="Update Profile?",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(18, 4))
        ctk.CTkLabel(
            card, text="Save these changes to your profile?",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
            wraplength=240, justify="center",
        ).pack(pady=(0, 16))

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.pack(pady=(0, 14))

        def _cancel():
            dialog.grab_release()
            dialog.destroy()

        def _confirm():
            dialog.grab_release()
            dialog.destroy()
            self._perform_update(data)

        ctk.CTkButton(
            button_row, text="Cancel", width=100, height=34,
            corner_radius=8, fg_color="transparent",
            border_width=1, border_color=COLOR_TRACK,
            hover_color=COLOR_TRACK, text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=12), command=_cancel,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            button_row, text="Update", width=100, height=34,
            corner_radius=8, fg_color=COLOR_ACCENT,
            hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=12, weight="bold"), command=_confirm,
        ).pack(side="left", padx=6)

        dialog.protocol("WM_DELETE_WINDOW", _cancel)

    def _perform_update(self, data):
        self.save_btn.configure(state="disabled", text="Updating...")
        self.message_label.configure(text="")
        self.update_idletasks()

        try:
            database.update_profile(
                original_email=self.original_email,
                full_name=data["full_name"],
                new_email=data["email"],
                phone=data["phone"],
                age=data["age"],
                gender=data["gender"],
                height_cm=data["height_cm"],
                weight_kg=data["weight_kg"],
                activity_level=data["activity_level"],
                fitness_goal=data["fitness_goal"],
                profile_picture_path=self.new_picture_path,  # None = unchanged
            )
        except ValueError as ve:
            self.message_label.configure(text_color=COLOR_ERROR, text=str(ve))
            self.save_btn.configure(state="normal", text="Update")
            return
        except mysql.connector.Error as db_err:
            self.message_label.configure(text_color=COLOR_ERROR, text=f"Database error: {db_err}")
            self.save_btn.configure(state="normal", text="Update")
            return

        # The row is now stored under the new email — update our local
        # bookkeeping so a second update in this same session still works.
        self.original_email = data["email"]

        # Keep session + local copy in sync with what we just saved
        self.user_data.update(data)
        if self.new_picture_path:
            self.user_data["profile_picture_path"] = self.new_picture_path
        session.set_current_user(self.user_data)

        self.message_label.configure(text_color=COLOR_SUCCESS, text="Profile updated successfully!")
        self.save_btn.configure(state="normal", text="Update")

    def _go_back(self):
        from dashboard import DashboardPage
        self.destroy()
        if self.on_back:
            self.on_back()
        else:
            DashboardPage(user_data=self.user_data).mainloop()


if __name__ == "__main__":
    # Standalone preview with placeholder data (no login required).
    demo_user = {
        "full_name": "Piyush Kawatra",
        "email": "Piyush@gmail.com",
        "phone": "9876543210",
        "age": 70,
        "gender": "Male",
        "height_cm": 165,
        "weight_kg": 60,
        "activity_level": "Moderately Active",
        "fitness_goal": "Weight Loss",
        "profile_picture_path": None,
    }
    app = ProfilePage(user_data=demo_user)
    app.mainloop()