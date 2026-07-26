"""
splash_screen.py
-----------------
Modern healthcare-themed splash screen for the
"AI Diet Chart & Nutrition Calculator" project.

Built with CustomTkinter. Shows an animated logo, project title,
a subtitle, and a smooth loading progress bar. After ~3 seconds
it automatically closes and hands off to the Login page.

Usage:
    from splash_screen import SplashScreen

    def on_finish():
        # launch your login window here
        ...

    splash = SplashScreen(on_finish=on_finish)
    splash.mainloop()
"""

import customtkinter as ctk
import math

# ---------------------------------------------------------------------------
# Theme constants — a calm, clinical "healthcare" palette
# ---------------------------------------------------------------------------
COLOR_BG_TOP = "#0B3D3A"        # deep teal (background gradient illusion)
COLOR_BG = "#0E4B47"            # primary background
COLOR_ACCENT = "#2FD3B0"        # mint / medical teal accent
COLOR_ACCENT_SOFT = "#8FE3D1"   # softer mint for secondary text
COLOR_WHITE = "#F5FBFA"
COLOR_TRACK = "#155953"         # progress bar track color

WINDOW_W, WINDOW_H = 480, 560
DURATION_MS = 3000               # total splash duration
TICK_MS = 16                     # ~60fps animation tick


class SplashScreen(ctk.CTk):
    def __init__(self, on_finish=None, duration_ms: int = DURATION_MS):
        super().__init__()

        self.on_finish = on_finish
        self.duration_ms = duration_ms
        self._elapsed = 0
        self._pulse_angle = 0.0
        self._closed = False  # guard against double-close

        # ---- window setup -------------------------------------------------
        ctk.set_appearance_mode("dark")
        self.overrideredirect(True)          # frameless, like a real splash
        self.configure(fg_color=COLOR_BG)
        self._center_window(WINDOW_W, WINDOW_H)
        self.attributes("-topmost", True)

        try:
            self.attributes("-alpha", 0.0)   # start transparent for fade-in
        except Exception:
            pass

        self._build_ui()
        self._fade_in()
        self.after(200, self._start_loading)

    # ------------------------------------------------------------------ UI
    def _center_window(self, w, h):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        outer = ctk.CTkFrame(
            self, fg_color=COLOR_BG, corner_radius=24,
            border_width=2, border_color=COLOR_TRACK
        )
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        # spacer
        ctk.CTkFrame(outer, fg_color="transparent", height=40).pack()

        # ---- animated logo (drawn on canvas: heartbeat + cross motif) ----
        self.logo_canvas = ctk.CTkCanvas(
            outer, width=160, height=160,
            bg=COLOR_BG, highlightthickness=0
        )
        self.logo_canvas.pack(pady=(10, 20))
        self._draw_logo()

        # ---- title ---------------------------------------------------
        ctk.CTkLabel(
            outer,
            text="AI Diet Chart &",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=COLOR_WHITE,
        ).pack(pady=(0, 0))

        ctk.CTkLabel(
            outer,
            text="Nutrition Calculator",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=COLOR_ACCENT,
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            outer,
            text="Smarter meals. Healthier you.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_ACCENT_SOFT,
        ).pack(pady=(0, 40))

        # ---- loading progress bar -------------------------------------
        self.progress = ctk.CTkProgressBar(
            outer,
            width=280,
            height=8,
            corner_radius=8,
            fg_color=COLOR_TRACK,
            progress_color=COLOR_ACCENT,
        )
        self.progress.set(0)
        self.progress.pack(pady=(0, 14))

        self.status_label = ctk.CTkLabel(
            outer,
            text="Loading",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_ACCENT_SOFT,
        )
        self.status_label.pack()

        ctk.CTkLabel(
            outer,
            text="v1.0",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLOR_TRACK,
        ).pack(side="bottom", pady=10)

    def _draw_logo(self):
        """Draws a simple medical-cross-in-a-pulse-ring logo without needing
        an external image file, so the project stays dependency-free."""
        c = self.logo_canvas
        c.delete("all")
        cx, cy, r = 80, 80, 62

        # outer ring
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                       outline=COLOR_ACCENT, width=3)

        # heartbeat / pulse line
        pts = [
            cx - 45, cy,
            cx - 20, cy,
            cx - 10, cy - 25,
            cx, cy + 20,
            cx + 10, cy,
            cx + 45, cy,
        ]
        c.create_line(*pts, fill=COLOR_ACCENT_SOFT, width=3,
                       joinstyle="round", smooth=False)

        # medical cross, centered slightly below
        bar_w, bar_l = 10, 34
        c.create_rectangle(cx - bar_w / 2, cy + 8 - bar_l / 2,
                            cx + bar_w / 2, cy + 8 + bar_l / 2,
                            fill=COLOR_WHITE, outline="")
        c.create_rectangle(cx - bar_l / 2, cy + 8 - bar_w / 2,
                            cx + bar_l / 2, cy + 8 + bar_w / 2,
                            fill=COLOR_WHITE, outline="")

    # ------------------------------------------------------------ animation
    def _fade_in(self, alpha=0.0):
        if self._closed:
            return
        alpha = min(alpha + 0.08, 1.0)
        try:
            self.attributes("-alpha", alpha)
        except Exception:
            pass
        if alpha < 1.0:
            self.after(15, lambda: self._fade_in(alpha))

    def _start_loading(self):
        if self._closed:
            return
        self._tick()

    def _tick(self):
        if self._closed:
            return

        self._elapsed += TICK_MS
        fraction = min(self._elapsed / self.duration_ms, 1.0)

        # ease-out curve for a smoother "settling" feel near the end
        eased = 1 - (1 - fraction) ** 2
        self.progress.set(eased)

        dots = "." * (1 + int(self._elapsed / 400) % 3)
        pct = int(fraction * 100)
        self.status_label.configure(text=f"Loading{dots}  {pct}%")

        # subtle pulsing glow on the ring by re-drawing with varying width
        self._pulse_angle += 0.15
        pulse = 2.5 + 1.5 * abs(math.sin(self._pulse_angle))
        self.logo_canvas.itemconfig(1, width=pulse)  # ring is first item

        if fraction < 1.0:
            self.after(TICK_MS, self._tick)
        else:
            self.status_label.configure(text="Ready!")
            self.after(250, self._finish)

    def _finish(self):
        if self._closed:
            return
        self._fade_out()

    def _fade_out(self, alpha=1.0):
        if self._closed:
            return
        alpha = max(alpha - 0.1, 0.0)
        try:
            self.attributes("-alpha", alpha)
        except Exception:
            pass
        if alpha > 0.0:
            self.after(15, lambda: self._fade_out(alpha))
        else:
            self._safe_close()

    def _safe_close(self):
        """Cancel every pending 'after' callback (including CustomTkinter's
        internal DPI-check job) before destroying the window. This prevents
        the 'invalid command name ... check_dpi_scaling' / '...update'
        errors that happen when a scheduled callback tries to run against
        a window that no longer exists."""
        if self._closed:
            return
        self._closed = True

        try:
            for after_id in self.tk.eval('after info').split():
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass

        if self.on_finish:
            self.on_finish()


if __name__ == "__main__":
    # Standalone run: after the splash finishes, actually open the login page.
    from login_page import LoginPage

    def _open_login():
        login = LoginPage()
        login.mainloop()

    app = SplashScreen(on_finish=_open_login)
    app.mainloop()