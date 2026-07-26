"""
face_login_page.py
---------------------
AI Diet Chart & Nutrition Calculator — Face ID Login
Healthcare-themed, built with CustomTkinter.

Shows a live webcam preview. Tapping "Scan & Log In" captures the
current frame, encodes the face (via InsightFace), and compares it
against every user who has enabled biometric login in Settings
(database.get_biometric_users()). On a match, logs in as that user
(session.set_current_user) and opens the Dashboard — the same end
result as a normal email/password login.

Only users who've explicitly enabled Face ID (Settings > Biometric
Login) are ever compared against, so this can't be used to log in as
someone who hasn't opted in.

Note: this build has no liveness/anti-spoof check — a still photo
held up to the camera can match. If that matters for your use case,
re-add a liveness step (e.g. blink detection) before trusting this
for anything beyond a personal convenience login.

SETUP:
    pip install customtkinter mysql-connector-python opencv-python onnxruntime insightface pillow

Run:
    python face_login_page.py
"""

import customtkinter as ctk
import mysql.connector
from PIL import Image

import database
import session
import face_auth

COLOR_BG = "#0E4B47"
COLOR_ACCENT = "#2FD3B0"
COLOR_ACCENT_SOFT = "#8FE3D1"
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#155953"
COLOR_ENTRY_BG = "#0B3D3A"
COLOR_ERROR = "#FF8A80"
COLOR_SUCCESS = "#8CFFB0"

WINDOW_W, WINDOW_H = 460, 640
PREVIEW_W, PREVIEW_H = 360, 270


class FaceLoginPage(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.cap = None
        self._preview_job = None
        self._last_frame = None

        ctk.set_appearance_mode("dark")
        self.title("AI Diet Chart & Nutrition Calculator — Face ID Login")
        self.configure(fg_color=COLOR_BG)
        self._center_window(WINDOW_W, WINDOW_H)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._start_camera()

    def _center_window(self, w, h):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        card = ctk.CTkFrame(
            self, fg_color=COLOR_BG, corner_radius=20,
            border_width=2, border_color=COLOR_TRACK,
        )
        card.pack(fill="both", expand=True, padx=16, pady=16)

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkButton(
            top_row, text="←  Back to Login", width=120, height=30,
            fg_color="transparent", hover_color=COLOR_TRACK,
            text_color=COLOR_ACCENT_SOFT, font=ctk.CTkFont(size=12),
            command=self._go_back,
        ).pack(side="left")

        ctk.CTkLabel(
            card, text="🧬  Face ID Login",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(10, 2))
        ctk.CTkLabel(
            card, text="Look at the camera, then tap Scan & Log In",
            font=ctk.CTkFont(size=12), text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 14))

        self.preview_label = ctk.CTkLabel(
            card, text="Starting camera...", fg_color=COLOR_ENTRY_BG,
            text_color=COLOR_ACCENT_SOFT,
            width=PREVIEW_W, height=PREVIEW_H, corner_radius=12,
        )
        self.preview_label.pack(padx=20)

        self.status_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=12), text_color=COLOR_ERROR,
            wraplength=380, justify="center",
        )
        self.status_label.pack(pady=(12, 6))

        self.scan_btn = ctk.CTkButton(
            card, text="Scan & Log In", height=42, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._handle_scan,
        )
        self.scan_btn.pack(fill="x", padx=40, pady=(4, 10))

        ctk.CTkButton(
            card, text="Use Email & Password Instead",
            fg_color="transparent", hover=False,
            text_color=COLOR_ACCENT, font=ctk.CTkFont(size=12, underline=True),
            width=20, command=self._go_back,
        ).pack(pady=(0, 16))

    # ------------------------------------------------------------ camera
    def _start_camera(self):
        if not face_auth.dependencies_available():
            self.preview_label.configure(text="Camera unavailable", image=None)
            self.status_label.configure(text=face_auth.dependencies_error_message())
            self.scan_btn.configure(state="disabled")
            return
        try:
            self.cap = face_auth.open_camera()
        except RuntimeError as e:
            self.preview_label.configure(text="Camera unavailable", image=None)
            self.status_label.configure(text=str(e))
            self.scan_btn.configure(state="disabled")
            return
        self._update_preview()

    def _update_preview(self):
        if self.cap is None:
            return
        try:
            ok, frame = self.cap.read()
            if ok:
                self._last_frame = frame
                rgb = face_auth.frame_to_rgb(frame)
                img = Image.fromarray(rgb).resize((PREVIEW_W, PREVIEW_H))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(PREVIEW_W, PREVIEW_H))
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img
        finally:
            self._preview_job = self.after(30, self._update_preview)

    # ------------------------------------------------------------- scan
    def _handle_scan(self):
        if self._last_frame is None:
            self.status_label.configure(
                text_color=COLOR_ERROR, text="Camera isn't ready yet — try again in a moment.",
            )
            return

        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.status_label.configure(text_color=COLOR_ACCENT_SOFT, text="")
        self.update_idletasks()

        try:
            encoding = face_auth.encode_face(self._last_frame)
        except RuntimeError as e:
            self.status_label.configure(text_color=COLOR_ERROR, text=str(e))
            self.scan_btn.configure(state="normal", text="Scan & Log In")
            return

        try:
            candidates = database.get_biometric_users()
        except mysql.connector.Error as db_err:
            self.status_label.configure(text_color=COLOR_ERROR, text=f"Database error: {db_err}")
            self.scan_btn.configure(state="normal", text="Scan & Log In")
            return

        matched_email = face_auth.best_match(encoding, candidates)

        if not matched_email:
            self.status_label.configure(
                text_color=COLOR_ERROR,
                text="Face not recognized. Try again, or log in with email and password.",
            )
            self.scan_btn.configure(state="normal", text="Scan & Log In")
            return

        user = database.get_user_by_email(matched_email)
        if not user:
            self.status_label.configure(text_color=COLOR_ERROR, text="Matched account could not be loaded.")
            self.scan_btn.configure(state="normal", text="Scan & Log In")
            return

        self.status_label.configure(
            text_color=COLOR_SUCCESS, text=f"Welcome back, {user['full_name'].split(' ')[0]}!",
        )
        session.set_current_user(user)
        self._release_camera()

        full_user_data = {k: v for k, v in user.items() if k not in ("password_hash", "face_encoding")}
        self.after(500, lambda: self._finish(full_user_data))

    def _finish(self, user_data):
        self.destroy()
        from dashboard import DashboardPage
        DashboardPage(user_data=user_data).mainloop()

    # ------------------------------------------------------------- teardown
    def _release_camera(self):
        if self._preview_job:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        face_auth.release_camera(self.cap)
        self.cap = None

    def _go_back(self):
        self._release_camera()
        self.destroy()
        from login_page import LoginPage
        LoginPage().mainloop()

    def _on_close(self):
        self._release_camera()
        self.destroy()


if __name__ == "__main__":
    app = FaceLoginPage()
    app.mainloop()