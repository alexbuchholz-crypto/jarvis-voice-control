BG = "#050c1a"
BG_LIGHT = "#0b1c33"
CARD = "#0e1f3a"
CARD_HOVER = "#14294a"
ACCENT = "#00d4ff"
ACCENT_HOVER = "#00a8cc"
ACCENT_BRIGHT = "#8ff4ff"
GLOW_DIM = "#123a52"
GLOW_OFF = "#16273f"
DANGER = "#ff4d6d"
DANGER_HOVER = "#cc3d57"
TEXT = "#eaf6ff"
TEXT_MUTED = "#5f89a8"
FONT_FAMILY = "Segoe UI"


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def lerp_color(color_a, color_b, t):
    a, b = hex_to_rgb(color_a), hex_to_rgb(color_b)
    return rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))
