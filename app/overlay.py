"""On-screen confirmation that Jarvis is listening/working — a small
borderless, always-on-top HUD-style circular indicator (a rotating
segmented ring around a thin bright rim, with a soft glowing bloom),
original geometric design in the spirit of a sci-fi heads-up display.
Drawn with PIL at 3x supersample then downscaled for clean anti-aliased
lines (no jagged pixelation). Transparent center/background, shown
top-left. Stays visible from the wake word until the command has actually
finished (including the spoken response), then collapses inward
("implodes"). Must only be touched via show()/hide(), which marshal onto
the Tkinter main thread via root.after."""

import math
import time
import tkinter as tk

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from . import theme

SIZE = 160
MARGIN = 30
SUPERSAMPLE = 3
BIG = SIZE * SUPERSAMPLE
BIG_CENTER = BIG / 2

ANIMATION_MS = 30
SAFETY_TIMEOUT_MS = 20000  # generous fallback in case on_command_done never fires
IMPLODE_SECONDS = 2.2
FLASH_SECONDS = 0.35  # brief brighter flash when the wake word is heard
TRANSPARENT_KEY = "#ff00ff"  # chroma-key color, made invisible via -transparentcolor
ALPHA_CUTOFF = 6  # below this, a supersampled/anti-aliased edge pixel is forced fully transparent

_KEY_RGB = tuple(int(TRANSPARENT_KEY[i:i + 2], 16) for i in (1, 3, 5))


def _hex_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


_ACCENT = _hex_rgb(theme.ACCENT)
_ACCENT_BRIGHT = _hex_rgb(theme.ACCENT_BRIGHT)
_DIM = _hex_rgb(theme.GLOW_DIM)

# Base (pulse-radius = 1.0) geometry, in "final size" pixel units.
OUTER_RING_R = 46
ARC_RING_R = 37

GLOW_BLUR_RADIUS = SUPERSAMPLE * 5
GLOW_STRENGTH = 0.8  # how strong the soft bloom halo is, relative to the crisp lines


def _flash_color(color, flash: float):
    return tuple(int(c + (255 - c) * flash) for c in color)


def _render_frame(tick: int, scale: float = 1.0, brightness: float = 1.0, flash: float = 0.0) -> Image.Image:
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = BIG_CENTER
    s = SUPERSAMPLE * scale

    pulse = 0.85 + 0.15 * math.sin(tick * 0.07)

    def alpha(v):
        return max(0, min(255, int(v * brightness * pulse)))

    bright_color = _flash_color(_ACCENT_BRIGHT, flash)
    accent_color = _flash_color(_ACCENT, flash)

    # Thin bright outer rim (radius breathes gently, flares outward on flash)
    r = OUTER_RING_R * s * (1 + 0.025 * math.sin(tick * 0.07)) * (1 + 0.15 * flash)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=bright_color + (alpha(255),), width=max(1, int((1.8 + 2 * flash) * SUPERSAMPLE * scale)))

    # Rotating segmented ring (clockwise)
    r = ARC_RING_R * s
    angle = (tick * 2.2) % 360
    for i in range(6):
        start = angle + i * 60
        draw.arc([cx - r, cy - r, cx + r, cy + r], start, start + 32,
                  fill=accent_color + (alpha(235),), width=max(1, int(2.6 * SUPERSAMPLE * scale)))

    # Soft bloom: a blurred copy of the crisp linework, composited underneath
    # it, so the rings look like they're actually glowing. Flash briefly
    # widens and intensifies this bloom for a "flare" effect.
    glow_blur = GLOW_BLUR_RADIUS * (1 + 1.5 * flash)
    glow_strength = min(GLOW_STRENGTH + 0.6 * flash, 1.0)
    glow = img.filter(ImageFilter.GaussianBlur(radius=glow_blur))
    glow_alpha = np.asarray(glow.split()[-1]).astype(np.float32) * glow_strength
    glow.putalpha(Image.fromarray(glow_alpha.astype(np.uint8)))
    img = Image.alpha_composite(glow, img)

    img = img.resize((SIZE, SIZE), Image.LANCZOS)

    arr = np.asarray(img).astype(np.float32)
    rgb, a = arr[..., :3], arr[..., 3]
    out_rgb = np.where(a[..., None] >= ALPHA_CUTOFF, rgb, np.array(_KEY_RGB, dtype=np.float32))
    out = np.empty((SIZE, SIZE, 4), dtype=np.uint8)
    out[..., :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
    out[..., 3] = 255
    return Image.fromarray(out, mode="RGBA")


class WakeOverlay:
    def __init__(self, root):
        self.root = root
        self.window = None
        self.label = None
        self._photo = None
        self._animating = False
        self._imploding = False
        self._implode_start = 0.0
        self._timeout_id = None
        self._tick = 0
        self._flash_start = None

    def show(self):
        self.root.after(0, self._show_impl)

    def hide(self):
        self.root.after(0, self._start_implode)

    def _show_impl(self):
        self._flash_start = time.time()

        if self.window is not None:
            self._imploding = False
            self._reset_safety_timeout()
            return

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{SIZE}x{SIZE}+{MARGIN}+{MARGIN}")
        win.configure(bg=TRANSPARENT_KEY)
        try:
            win.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass

        label = tk.Label(win, bg=TRANSPARENT_KEY, borderwidth=0, highlightthickness=0)
        label.pack(fill="both", expand=True)

        self.window = win
        self.label = label
        self._tick = 0
        self._imploding = False
        self._animating = True
        self._animate()
        self._reset_safety_timeout()

    def _start_implode(self):
        if self.window is None or self._imploding:
            return
        self._imploding = True
        self._implode_start = time.time()
        if self._timeout_id is not None:
            try:
                self.root.after_cancel(self._timeout_id)
            except Exception:
                pass
            self._timeout_id = None

    def _animate(self):
        if not self._animating or self.label is None:
            return

        if self._imploding:
            progress = min((time.time() - self._implode_start) / IMPLODE_SECONDS, 1.0)
            eased = progress ** 2  # accelerating collapse
            if progress >= 1.0:
                self._destroy_window()
                return
            scale = max(1.0 - eased, 0.0)
            brightness = max(1.0 - eased, 0.0)
            frame = _render_frame(self._tick, scale=scale, brightness=brightness)
        else:
            flash = 0.0
            if self._flash_start is not None:
                elapsed = time.time() - self._flash_start
                if elapsed < FLASH_SECONDS:
                    flash = 1.0 - (elapsed / FLASH_SECONDS)
                else:
                    self._flash_start = None
            frame = _render_frame(self._tick, flash=flash)

        self._tick += 1
        self._photo = ImageTk.PhotoImage(frame)
        self.label.configure(image=self._photo)
        self.root.after(ANIMATION_MS, self._animate)

    def _reset_safety_timeout(self):
        if self._timeout_id is not None:
            try:
                self.root.after_cancel(self._timeout_id)
            except Exception:
                pass
        self._timeout_id = self.root.after(SAFETY_TIMEOUT_MS, self._start_implode)

    def _destroy_window(self):
        self._animating = False
        self._imploding = False
        if self._timeout_id is not None:
            try:
                self.root.after_cancel(self._timeout_id)
            except Exception:
                pass
            self._timeout_id = None
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
            self.label = None
            self._photo = None
