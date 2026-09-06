import random
import tkinter as tk
import tkinter.font as tkfont

from . import theme

GRID_COLOR = "#0a2138"
RING_COLOR_DIM = "#153f5c"
RING_COLOR_BRIGHT = "#2f7fa8"
BRACKET_LEN = 26
BRACKET_MARGIN = 14
GRID_STEP = 44
NUM_BLIPS = 14


class HudBackground(tk.Canvas):
    """Decorative animated sci-fi HUD framing (grid, breathing rings, corner
    brackets, rotating sweep, blinking data points) drawn behind the UI panels."""

    def __init__(self, parent):
        super().__init__(parent, highlightthickness=0, bg=theme.BG, bd=0)
        self._angle = 0.0
        self._ring_phase = 0.0
        self._ring_direction = 1
        self._blips = []
        self.bind("<Configure>", lambda e: self._redraw())
        self.after(40, self._animate)

    def _redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        self._draw_grid(w, h)
        self._ensure_blips(w, h)
        self._draw_blips()
        self._draw_rings(w, h)
        self._draw_corner_brackets(w, h)
        self._draw_sweep(w, h)
        self._draw_title()

    def _draw_title(self):
        bold_font = tkfont.Font(family=theme.FONT_FAMILY, size=22, weight="bold")
        self.create_text(28, 40, text="JARVIS", fill=theme.ACCENT, anchor="w", font=bold_font)
        offset = bold_font.measure("JARVIS")
        normal_font = tkfont.Font(family=theme.FONT_FAMILY, size=22)
        self.create_text(28 + offset, 40, text="  Voice Control", fill=theme.TEXT, anchor="w", font=normal_font)

    def _draw_grid(self, w, h):
        for x in range(0, w, GRID_STEP):
            self.create_line(x, 0, x, h, fill=GRID_COLOR, width=1, tags="grid")
        for y in range(0, h, GRID_STEP):
            self.create_line(0, y, w, y, fill=GRID_COLOR, width=1, tags="grid")

    def _ensure_blips(self, w, h):
        if self._blips:
            return
        cols = max(1, w // GRID_STEP)
        rows = max(1, h // GRID_STEP)
        for _ in range(NUM_BLIPS):
            gx = random.randint(0, cols) * GRID_STEP
            gy = random.randint(0, rows) * GRID_STEP
            self._blips.append({"x": gx, "y": gy, "phase": random.random(), "speed": random.uniform(0.02, 0.05)})

    def _draw_blips(self):
        self.delete("blip")
        for blip in self._blips:
            brightness = abs((blip["phase"] % 2.0) - 1.0)
            if brightness < 0.35:
                continue
            color = theme.lerp_color(GRID_COLOR, theme.ACCENT, brightness)
            r = 2 + brightness * 1.5
            x, y = blip["x"], blip["y"]
            self.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="", tags="blip")

    def _draw_rings(self, w, h):
        cx, cy = w - 70, h - 70
        color = theme.lerp_color(RING_COLOR_DIM, RING_COLOR_BRIGHT, self._ring_phase)
        for r in (32, 56, 82):
            self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=1, tags="ring")

    def _draw_corner_brackets(self, w, h):
        m, l = BRACKET_MARGIN, BRACKET_LEN
        corners = [
            ((m, m), (1, 1)),
            ((w - m, m), (-1, 1)),
            ((m, h - m), (1, -1)),
            ((w - m, h - m), (-1, -1)),
        ]
        for (x, y), (dx, dy) in corners:
            self.create_line(x, y, x + dx * l, y, fill=theme.ACCENT, width=2, tags="bracket")
            self.create_line(x, y, x, y + dy * l, fill=theme.ACCENT, width=2, tags="bracket")

    def _draw_sweep(self, w, h):
        cx, cy = w - 70, h - 70
        r = 82
        self.create_arc(cx - r, cy - r, cx + r, cy + r, start=self._angle, extent=55,
                         style="arc", outline=theme.ACCENT, width=2, tags="sweep")

    def _animate(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w > 2 and h > 2:
            self._angle = (self._angle + 2) % 360
            self._ring_phase += 0.03 * self._ring_direction
            if self._ring_phase >= 1.0:
                self._ring_phase, self._ring_direction = 1.0, -1
            elif self._ring_phase <= 0.0:
                self._ring_phase, self._ring_direction = 0.0, 1
            for blip in self._blips:
                blip["phase"] += blip["speed"]

            self.delete("sweep")
            self.delete("ring")
            self._draw_rings(w, h)
            self._draw_sweep(w, h)
            self._draw_blips()
        self.after(40, self._animate)
