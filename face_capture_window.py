"""
face_capture_window.py
-------------------------
AI Diet Chart & Nutrition Calculator — Face Capture Popup
Healthcare-themed, built with CustomTkinter.

A small CTkToplevel with a live webcam preview and a Capture button.
Used by settings_page.py's "Enable Biometric" flow: shows the current
user's camera feed, lets them capture a single clean frame, encodes
the face (via face_auth.encode_face), and hands the resulting
512-dimension embedding back to the caller through `on_captured`.

This window doesn't touch the database itself — the caller decides
what to do with the encoding (Settings stores it via
database.enable_biometric()).

Note: this build has no liveness/anti-spoof check — a still photo
held up to the camera can be registered as a face. If that matters
for your use case, re-add a liveness step (e.g. blink detection)
before relying on this for anything beyond a personal convenience login.

Run standalone for a quick test:
    pip install customtkinter opencv-python onnxruntime insightface pillow
    python face_capture_window.py
"""

import customtkinter as ctk
from PIL import Image

import face_auth

COLOR_BG = "#0E4B47"
COLOR_TRACK = "#1E6B64"
COLOR_ACCENT = "#2FD3B0"
COLOR_ACCENT_SOFT = "#8FE3D1"
COLOR_WHITE = "#F5FBFA"
COLOR_ENTRY_BG = "#0B3D3A"
COLOR_ERROR = "#FF8A80"

PREVIEW_W, PREVIEW_H = 360, 270


class FaceCaptureWindow(ctk.CTkToplevel):
    def __init__(self, master, on_captured, title="Register Your Face"):
        super().__init__(master)

        # on_captured(encoding: np.ndarray) — called once a clean,
        # single-face frame has been captured and encoded.
        self.on_captured = on_captured
        self.cap = None
        self._preview_job = None
        self._last_frame = None

        self.title(title)
        self.configure(fg_color=COLOR_BG)
        self.geometry("420x500")
        self.resizable(False, False)
        self.transient(master)
        self.after(50, self.grab_set)  # grab after the window is actually mapped
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._build_ui(title)
        self._start_camera()

    def _build_ui(self, title):
        card = ctk.CTkFrame(
            self, fg_color=COLOR_BG, corner_radius=16,
            border_width=2, border_color=COLOR_TRACK,
        )
        card.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            card, text=f"🧬  {title}", font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(14, 4))
        ctk.CTkLabel(
            card, text="Center your face in the frame, in good lighting, then tap Capture.",
            font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT_SOFT,
            wraplength=340, justify="center",
        ).pack(pady=(0, 10))

        self.preview_label = ctk.CTkLabel(
            card, text="Starting camera...", fg_color=COLOR_ENTRY_BG,
            text_color=COLOR_ACCENT_SOFT,
            width=PREVIEW_W, height=PREVIEW_H, corner_radius=10,
        )
        self.preview_label.pack(padx=14)

        self.status_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR,
            wraplength=340, justify="center",
        )
        self.status_label.pack(pady=(8, 4))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(pady=(6, 14))
        self.capture_btn = ctk.CTkButton(
            btn_row, text="📸  Capture", width=150, height=36, corner_radius=10,
            fg_color=COLOR_ACCENT, hover_color="#26B79A", text_color="#0B3D3A",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_capture,
        )
        self.capture_btn.pack(side="left", padx=6)
        ctk.CTkButton(
            btn_row, text="Cancel", width=100, height=36, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=COLOR_TRACK,
            hover_color=COLOR_TRACK, text_color=COLOR_ACCENT_SOFT,
            font=ctk.CTkFont(size=12), command=self._close,
        ).pack(side="left", padx=6)

    # ------------------------------------------------------------ camera
    def _start_camera(self):
        if not face_auth.dependencies_available():
            self.status_label.configure(text=face_auth.dependencies_error_message())
            self.capture_btn.configure(state="disabled")
            return
        try:
            self.cap = face_auth.open_camera()
        except RuntimeError as e:
            self.status_label.configure(text=str(e))
            self.capture_btn.configure(state="disabled")
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

    # ------------------------------------------------------------- capture
    def _handle_capture(self):
        if self._last_frame is None:
            self.status_label.configure(
                text_color=COLOR_ERROR, text="Camera isn't ready yet — try again in a moment.",
            )
            return

        self.capture_btn.configure(state="disabled", text="Processing...")
        self.status_label.configure(text_color=COLOR_ACCENT_SOFT, text="")
        self.update_idletasks()

        try:
            encoding = face_auth.encode_face(self._last_frame)
        except RuntimeError as e:
            self.status_label.configure(text_color=COLOR_ERROR, text=str(e))
            self.capture_btn.configure(state="normal", text="📸  Capture")
            return

        self._close()
        if self.on_captured:
            self.on_captured(encoding)

    def _close(self):
        if self._preview_job:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        face_auth.release_camera(self.cap)
        self.cap = None
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Face Capture Test")
    root.geometry("300x200")
    root.configure(fg_color=COLOR_BG)

    def _handle(encoding):
        print(f"Captured an encoding of length {len(encoding)}")

    ctk.CTkButton(
        root, text="Open Capture", command=lambda: FaceCaptureWindow(root, _handle),
    ).pack(pady=80)
    root.mainloop()