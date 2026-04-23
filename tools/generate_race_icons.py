"""
Race icon generator for Stars Reborn (race wizard).

Produces 32 distinct 32x32 race icons (scaled up by --size, default 128) that
evoke the silhouettes of the original Stars! race icons without copying them
pixel-for-pixel. Each icon is described by a bespoke draw_NN function; shapes
are rendered on a supersampled canvas (4x) and downsampled with LANCZOS for
smooth edges.

Usage:
    python tools/generate_race_icons.py --out assets/png/race_icons --size 128
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 4  # supersample factor


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def pts(S: int, *coords) -> list[tuple[float, float]]:
    """Scale a list of (x, y) fractional coords in [0,1] to canvas pixels."""
    return [(x * S, y * S) for (x, y) in coords]


def fill_bg(img: Image.Image, color):
    ImageDraw.Draw(img).rectangle([(0, 0), img.size], fill=color)


def grad_rect(size: int, top_color, bottom_color, y0=0.0, y1=1.0) -> Image.Image:
    """Vertical gradient between two RGB colors across fractional y range."""
    arr = np.zeros((size, size, 3), dtype=np.float32)
    ys = np.linspace(0, 1, size)
    t = np.clip((ys - y0) / max(y1 - y0, 1e-6), 0, 1)
    c0 = np.array(top_color, dtype=np.float32)
    c1 = np.array(bottom_color, dtype=np.float32)
    row = c0[None, :] * (1 - t[:, None]) + c1[None, :] * t[:, None]
    arr[:] = row[:, None, :]
    return Image.fromarray(arr.astype(np.uint8), mode="RGB")


# --------------------------------------------------------------------------
# Icon draw functions
# --------------------------------------------------------------------------


def draw_01_dove(S: int) -> Image.Image:
    """Blue bg, white dove in flight."""
    img = Image.new("RGB", (S, S), (45, 90, 180))
    d = ImageDraw.Draw(img)
    # Body (tilted ellipse via polygon)
    body = [
        (0.28, 0.58),
        (0.40, 0.50),
        (0.60, 0.48),
        (0.72, 0.55),
        (0.70, 0.63),
        (0.55, 0.68),
        (0.35, 0.66),
    ]
    d.polygon(pts(S, *body), fill="white")
    # Head
    d.ellipse(pts(S, (0.66, 0.42), (0.80, 0.56)), fill="white")
    # Beak
    d.polygon(pts(S, (0.78, 0.47), (0.88, 0.49), (0.78, 0.52)), fill=(240, 180, 80))
    # Upper wing (raised)
    upper = [
        (0.32, 0.52),
        (0.42, 0.25),
        (0.55, 0.22),
        (0.62, 0.32),
        (0.60, 0.45),
        (0.48, 0.50),
    ]
    d.polygon(pts(S, *upper), fill="white")
    # Lower wing (trailing)
    lower = [
        (0.30, 0.60),
        (0.18, 0.72),
        (0.12, 0.82),
        (0.28, 0.78),
        (0.42, 0.68),
    ]
    d.polygon(pts(S, *lower), fill="white")
    # Tail
    tail = [(0.30, 0.58), (0.18, 0.55), (0.22, 0.65), (0.32, 0.64)]
    d.polygon(pts(S, *tail), fill="white")
    # Olive branch hint
    d.line(pts(S, (0.88, 0.50), (0.96, 0.48)), fill=(120, 200, 100), width=max(1, S // 60))
    return img


def draw_02_yinyang(S: int) -> Image.Image:
    """Blue bg, yin-yang symbol."""
    img = Image.new("RGB", (S, S), (60, 110, 200))
    d = ImageDraw.Draw(img)
    cx, cy, r = 0.5, 0.5, 0.38
    # White full disc
    d.ellipse(pts(S, (cx - r, cy - r), (cx + r, cy + r)), fill="white")
    # Black right half (pieslice)
    d.pieslice(pts(S, (cx - r, cy - r), (cx + r, cy + r)), start=-90, end=90, fill="black")
    # S-curve: small black disc in upper half of white side's boundary
    sr = r / 2
    d.ellipse(pts(S, (cx - sr, cy - r), (cx + sr, cy)), fill="black")
    # small white disc in lower half of black side's boundary
    d.ellipse(pts(S, (cx - sr, cy), (cx + sr, cy + r)), fill="white")
    # Dots
    dr = r / 6
    d.ellipse(pts(S, (cx - dr, cy - sr - dr), (cx + dr, cy - sr + dr)), fill="white")
    d.ellipse(pts(S, (cx - dr, cy + sr - dr), (cx + dr, cy + sr + dr)), fill="black")
    return img


def draw_03_insect(S: int) -> Image.Image:
    """Black bg, green alien insect outline (line art)."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    g = (70, 220, 90)
    w = max(2, S // 45)
    # Head
    d.ellipse(pts(S, (0.42, 0.12), (0.58, 0.28)), outline=g, width=w)
    # Antennae
    d.line(pts(S, (0.46, 0.14), (0.38, 0.02)), fill=g, width=w)
    d.line(pts(S, (0.54, 0.14), (0.62, 0.02)), fill=g, width=w)
    # Thorax
    d.ellipse(pts(S, (0.40, 0.28), (0.60, 0.48)), outline=g, width=w)
    # Abdomen (elongated)
    d.ellipse(pts(S, (0.38, 0.48), (0.62, 0.82)), outline=g, width=w)
    # Legs (3 pairs from thorax)
    for ly, curve in [(0.32, 0.12), (0.38, 0.15), (0.44, 0.18)]:
        d.line(pts(S, (0.40, ly), (0.16, ly + curve)), fill=g, width=w)
        d.line(pts(S, (0.16, ly + curve), (0.10, ly + curve + 0.06)), fill=g, width=w)
        d.line(pts(S, (0.60, ly), (0.84, ly + curve)), fill=g, width=w)
        d.line(pts(S, (0.84, ly + curve), (0.90, ly + curve + 0.06)), fill=g, width=w)
    return img


def draw_04_skull_bones_black(S: int) -> Image.Image:
    """Black bg, white skull and bones."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    # Crossed bones behind
    for a, b in [((0.12, 0.82), (0.88, 0.22)), ((0.12, 0.22), (0.88, 0.82))]:
        # shaft
        d.line(pts(S, a, b), fill="white", width=max(3, S // 25))
        # knobs at each end (approx dumbbell)
        for x, y in (a, b):
            r = 0.06
            d.ellipse(pts(S, (x - r, y - r), (x + r, y + r)), fill="white")
    # Skull (cranium)
    d.ellipse(pts(S, (0.22, 0.16), (0.78, 0.66)), fill="white")
    # Jaw
    d.rectangle(pts(S, (0.34, 0.58), (0.66, 0.72)), fill="white")
    d.ellipse(pts(S, (0.30, 0.56), (0.70, 0.78)), fill="white")
    # Eye sockets
    d.ellipse(pts(S, (0.30, 0.32), (0.44, 0.50)), fill="black")
    d.ellipse(pts(S, (0.56, 0.32), (0.70, 0.50)), fill="black")
    # Nose
    d.polygon(pts(S, (0.50, 0.48), (0.46, 0.58), (0.54, 0.58)), fill="black")
    # Teeth gap
    d.rectangle(pts(S, (0.38, 0.66), (0.62, 0.72)), fill="black")
    for i in range(4):
        x0 = 0.38 + 0.06 * i
        d.rectangle(pts(S, (x0 + 0.005, 0.66), (x0 + 0.055, 0.72)), fill="white")
    return img


def draw_05_dna(S: int) -> Image.Image:
    """Black bg, DNA double helix (light + dark green)."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    dark = (30, 130, 40)
    light = (120, 230, 110)
    w = max(2, S // 40)
    # Two sine-wave strands
    n = 80
    ys = np.linspace(0.08, 0.92, n)
    amp = 0.22
    freq = 2.0  # cycles across height
    a = 0.5 + amp * np.sin(ys * freq * 2 * np.pi)
    b = 0.5 + amp * np.sin(ys * freq * 2 * np.pi + np.pi)
    for i in range(n - 1):
        d.line(pts(S, (a[i], ys[i]), (a[i + 1], ys[i + 1])), fill=light, width=w)
        d.line(pts(S, (b[i], ys[i]), (b[i + 1], ys[i + 1])), fill=dark, width=w)
    # Rungs at crossings (every N samples)
    for i in range(0, n, 8):
        color = dark if i % 16 == 0 else light
        d.line(pts(S, (a[i], ys[i]), (b[i], ys[i])), fill=color, width=max(1, w - 1))
    return img


def draw_06_mountain_water(S: int) -> Image.Image:
    """White bg, black mountain outline over blue water."""
    img = Image.new("RGB", (S, S), "white")
    d = ImageDraw.Draw(img)
    # Water band
    d.rectangle(pts(S, (0.0, 0.70), (1.0, 1.0)), fill=(70, 140, 220))
    # Water ripples
    for y in (0.78, 0.86, 0.94):
        d.line(pts(S, (0.10, y), (0.30, y)), fill=(180, 210, 240), width=max(1, S // 80))
        d.line(
            pts(S, (0.55, y - 0.02), (0.75, y - 0.02)), fill=(180, 210, 240), width=max(1, S // 80)
        )
    # Mountain (two peaks) — outline
    peak = [
        (0.06, 0.75),
        (0.28, 0.28),
        (0.40, 0.55),
        (0.58, 0.14),
        (0.82, 0.52),
        (0.94, 0.75),
    ]
    d.polygon(pts(S, *peak), fill="black")
    # Snow caps
    d.polygon(pts(S, (0.24, 0.34), (0.28, 0.28), (0.34, 0.40), (0.30, 0.42)), fill="white")
    d.polygon(pts(S, (0.54, 0.20), (0.58, 0.14), (0.66, 0.28), (0.60, 0.30)), fill="white")
    return img


def draw_07_infinity(S: int) -> Image.Image:
    """Black bg, thick red infinity sign."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    red = (220, 30, 40)
    w = max(4, S // 10)
    # Two overlapping circles drawn as outlines (thick) form an infinity
    r = 0.20
    for cx in (0.32, 0.68):
        d.ellipse(pts(S, (cx - r, 0.5 - r), (cx + r, 0.5 + r)), outline=red, width=w)
    # Bridge the overlap to reinforce figure-8 read
    d.line(pts(S, (0.46, 0.42), (0.54, 0.58)), fill=red, width=w)
    d.line(pts(S, (0.46, 0.58), (0.54, 0.42)), fill=red, width=w)
    return img


def draw_08_slanted_lines(S: int) -> Image.Image:
    """Black bg, slanted red lines of various thicknesses."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    red = (210, 30, 40)
    # Parallel diagonals going \
    specs = [
        (0.00, 0.35, 0.45, 0.00, 7),
        (0.15, 0.55, 0.70, 0.00, 3),
        (0.30, 0.80, 0.95, 0.20, 9),
        (0.05, 0.95, 0.60, 0.35, 5),
        (0.50, 1.00, 1.00, 0.50, 4),
        (0.68, 0.92, 1.00, 0.60, 2),
    ]
    for x0, y0, x1, y1, th in specs:
        d.line(pts(S, (x0, y0), (x1, y1)), fill=red, width=max(1, th * S // 80))
    return img


def draw_09_butterfly(S: int) -> Image.Image:
    """White bg, black butterfly outline (filled silhouette)."""
    img = Image.new("RGB", (S, S), "white")
    d = ImageDraw.Draw(img)
    # Body
    d.ellipse(pts(S, (0.48, 0.22), (0.52, 0.80)), fill="black")
    # Head
    d.ellipse(pts(S, (0.46, 0.16), (0.54, 0.26)), fill="black")
    # Antennae
    w = max(1, S // 80)
    d.line(pts(S, (0.50, 0.17), (0.42, 0.05)), fill="black", width=w)
    d.line(pts(S, (0.50, 0.17), (0.58, 0.05)), fill="black", width=w)
    # Upper wings (large, rounded) — left then right (mirror)
    upper_L = [(0.50, 0.28), (0.30, 0.10), (0.08, 0.18), (0.06, 0.40), (0.22, 0.52), (0.44, 0.48)]
    upper_R = [(0.50, 0.28), (0.70, 0.10), (0.92, 0.18), (0.94, 0.40), (0.78, 0.52), (0.56, 0.48)]
    d.polygon(pts(S, *upper_L), fill="black")
    d.polygon(pts(S, *upper_R), fill="black")
    # Lower wings (smaller)
    lower_L = [(0.50, 0.56), (0.30, 0.66), (0.18, 0.86), (0.38, 0.88), (0.48, 0.76)]
    lower_R = [(0.50, 0.56), (0.70, 0.66), (0.82, 0.86), (0.62, 0.88), (0.52, 0.76)]
    d.polygon(pts(S, *lower_L), fill="black")
    d.polygon(pts(S, *lower_R), fill="black")
    # Wing spots (white) — upper wing eye
    d.ellipse(pts(S, (0.16, 0.28), (0.26, 0.38)), fill="white")
    d.ellipse(pts(S, (0.74, 0.28), (0.84, 0.38)), fill="white")
    return img


def draw_10_triangles(S: int) -> Image.Image:
    """Yellow bg, 2 diagonal triangles pointing in different directions."""
    img = Image.new("RGB", (S, S), (240, 210, 60))
    d = ImageDraw.Draw(img)
    # Upper-left triangle pointing up-left
    t1 = [(0.10, 0.10), (0.44, 0.14), (0.14, 0.48)]
    d.polygon(pts(S, *t1), fill="black")
    # Lower-right triangle pointing down-right
    t2 = [(0.90, 0.90), (0.56, 0.86), (0.86, 0.52)]
    d.polygon(pts(S, *t2), fill="black")
    return img


def draw_11_duck(S: int) -> Image.Image:
    """Black bg, yellow rubber duck."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    yellow = (250, 220, 60)
    # Body
    d.ellipse(pts(S, (0.18, 0.48), (0.82, 0.86)), fill=yellow)
    # Breast hump (raise the front)
    d.ellipse(pts(S, (0.12, 0.54), (0.40, 0.82)), fill=yellow)
    # Tail flip
    d.polygon(pts(S, (0.78, 0.56), (0.92, 0.48), (0.84, 0.64)), fill=yellow)
    # Head
    d.ellipse(pts(S, (0.18, 0.18), (0.54, 0.54)), fill=yellow)
    # Beak
    d.polygon(pts(S, (0.12, 0.34), (0.02, 0.38), (0.10, 0.44)), fill=(240, 140, 40))
    d.polygon(pts(S, (0.12, 0.38), (0.02, 0.42), (0.12, 0.46)), fill=(230, 110, 30))
    # Eye
    d.ellipse(pts(S, (0.36, 0.28), (0.44, 0.36)), fill="black")
    d.ellipse(pts(S, (0.38, 0.30), (0.42, 0.34)), fill="white")
    return img


def draw_12_hand_circle(S: int) -> Image.Image:
    """Black bg, green hand outline with circle around it."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    g = (80, 220, 100)
    w = max(2, S // 45)
    # Circle
    d.ellipse(pts(S, (0.06, 0.06), (0.94, 0.94)), outline=g, width=w)
    # Palm
    d.rounded_rectangle(pts(S, (0.34, 0.48), (0.66, 0.84)), radius=S * 0.04, outline=g, width=w)
    # Fingers (4)
    for i, fx in enumerate((0.36, 0.45, 0.54, 0.63)):
        top = 0.22 if i == 1 or i == 2 else 0.26
        d.rounded_rectangle(
            pts(S, (fx, top), (fx + 0.07, 0.50)), radius=S * 0.03, outline=g, width=w
        )
    # Thumb
    d.rounded_rectangle(pts(S, (0.22, 0.50), (0.36, 0.64)), radius=S * 0.03, outline=g, width=w)
    return img


def draw_13_sun_water(S: int) -> Image.Image:
    """Black bg with red sun, fading into blue gradient water below."""
    # Vertical gradient: black top -> blue bottom
    top = (10, 10, 20)
    bot = (30, 60, 150)
    img = grad_rect(S, top, bot, y0=0.35, y1=1.0)
    d = ImageDraw.Draw(img)
    # Sun disc with halo (red -> orange outer)
    cx, cy, r = 0.5, 0.52, 0.22
    # halo
    for i, (col, rr) in enumerate(
        [
            ((180, 40, 20), r * 1.5),
            ((210, 70, 30), r * 1.25),
            ((240, 110, 40), r * 1.10),
        ]
    ):
        d.ellipse(pts(S, (cx - rr, cy - rr), (cx + rr, cy + rr)), fill=col)
    d.ellipse(pts(S, (cx - r, cy - r), (cx + r, cy + r)), fill=(240, 70, 40))
    # Water reflection bands (subtle)
    for y, col in [(0.72, (110, 140, 210)), (0.82, (80, 110, 190)), (0.90, (60, 90, 170))]:
        d.rectangle(pts(S, (0.0, y), (1.0, y + 0.02)), fill=col)
    # Sun reflection on water
    d.polygon(pts(S, (0.44, 0.70), (0.56, 0.70), (0.60, 0.98), (0.40, 0.98)), fill=(240, 140, 80))
    return img


def draw_14_nested_ships(S: int) -> Image.Image:
    """White bg, nested black spaceship outlines."""
    img = Image.new("RGB", (S, S), "white")
    d = ImageDraw.Draw(img)
    w = max(2, S // 40)
    # Outer ship (stylized arrow / fighter)
    outer = [
        (0.50, 0.05),
        (0.68, 0.30),
        (0.95, 0.85),
        (0.72, 0.72),
        (0.60, 0.95),
        (0.50, 0.80),
        (0.40, 0.95),
        (0.28, 0.72),
        (0.05, 0.85),
        (0.32, 0.30),
    ]
    d.polygon(pts(S, *outer), outline="black", width=w)
    # Inner ship (smaller, same shape)
    cx, cy = 0.50, 0.50
    inner = [(cx + (x - cx) * 0.50, cy + (y - cy) * 0.50) for (x, y) in outer]
    d.polygon(pts(S, *inner), outline="black", width=w)
    return img


def draw_15_raven(S: int) -> Image.Image:
    """Red bg, black raven silhouette (perched/flying)."""
    img = Image.new("RGB", (S, S), (180, 30, 30))
    d = ImageDraw.Draw(img)
    # Body
    d.ellipse(pts(S, (0.32, 0.40), (0.70, 0.72)), fill="black")
    # Neck + head
    d.ellipse(pts(S, (0.56, 0.22), (0.76, 0.46)), fill="black")
    # Beak
    d.polygon(pts(S, (0.70, 0.30), (0.92, 0.26), (0.74, 0.36)), fill="black")
    # Folded wing
    wing = [(0.32, 0.42), (0.20, 0.52), (0.12, 0.72), (0.40, 0.62), (0.48, 0.50)]
    d.polygon(pts(S, *wing), fill="black")
    # Tail
    tail = [(0.32, 0.62), (0.20, 0.80), (0.38, 0.76), (0.44, 0.68)]
    d.polygon(pts(S, *tail), fill="black")
    # Legs
    w = max(1, S // 50)
    d.line(pts(S, (0.50, 0.70), (0.46, 0.90)), fill="black", width=w)
    d.line(pts(S, (0.58, 0.70), (0.60, 0.90)), fill="black", width=w)
    # Eye glint
    d.ellipse(pts(S, (0.66, 0.30), (0.70, 0.34)), fill=(220, 220, 220))
    return img


def draw_16_circle_diamonds(S: int) -> Image.Image:
    """Black bg, red filled circle with 3 diamond cutouts."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    red = (210, 40, 45)
    d.ellipse(pts(S, (0.12, 0.12), (0.88, 0.88)), fill=red)
    # 3 diamond cutouts in triangular arrangement
    positions = [(0.50, 0.30), (0.32, 0.62), (0.68, 0.62)]
    dr = 0.10
    for cx, cy in positions:
        diamond = [(cx, cy - dr), (cx + dr, cy), (cx, cy + dr), (cx - dr, cy)]
        d.polygon(pts(S, *diamond), fill="black")
    return img


def draw_17_triangle_cut(S: int) -> Image.Image:
    """Black bg, white triangle with smaller black triangle cut from bottom center."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    # Outer upward triangle
    d.polygon(pts(S, (0.50, 0.08), (0.92, 0.88), (0.08, 0.88)), fill="white")
    # Inner inverted (pointing down) triangle cut at bottom
    d.polygon(pts(S, (0.36, 0.88), (0.64, 0.88), (0.50, 0.58)), fill="black")
    return img


def draw_18_pyramid_eye(S: int) -> Image.Image:
    """Black bg, 2-shade pyramid; darker face carries the eye."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    light = (215, 185, 120)
    dark = (140, 115, 70)
    # Light face (left)
    d.polygon(pts(S, (0.50, 0.12), (0.50, 0.86), (0.08, 0.86)), fill=light)
    # Dark face (right)
    d.polygon(pts(S, (0.50, 0.12), (0.92, 0.86), (0.50, 0.86)), fill=dark)
    # Eye on dark face
    # Eye almond shape
    ex, ey = 0.64, 0.52
    d.polygon(
        pts(S, (ex - 0.13, ey), (ex, ey - 0.08), (ex + 0.13, ey), (ex, ey + 0.08)), fill="white"
    )
    d.ellipse(pts(S, (ex - 0.05, ey - 0.05), (ex + 0.05, ey + 0.05)), fill=(30, 60, 130))
    d.ellipse(pts(S, (ex - 0.02, ey - 0.02), (ex + 0.02, ey + 0.02)), fill="black")
    return img


def draw_19_four_rects(S: int) -> Image.Image:
    """White bg, 4 distinct rectangular shapes — one per quadrant."""
    img = Image.new("RGB", (S, S), "white")
    d = ImageDraw.Draw(img)
    # Upper-left: tall thin solid
    d.rectangle(pts(S, (0.14, 0.10), (0.24, 0.44)), fill="black")
    # Upper-right: wide short outline
    d.rectangle(pts(S, (0.56, 0.12), (0.90, 0.24)), outline="black", width=max(2, S // 50))
    # Lower-left: square with diagonal
    d.rectangle(pts(S, (0.10, 0.58), (0.40, 0.88)), outline="black", width=max(2, S // 50))
    d.line(pts(S, (0.10, 0.58), (0.40, 0.88)), fill="black", width=max(2, S // 70))
    # Lower-right: filled wide rectangle
    d.rectangle(pts(S, (0.54, 0.62), (0.90, 0.86)), fill="black")
    return img


def draw_20_skull_bones_white(S: int) -> Image.Image:
    """White bg, black skull + crossbones outline."""
    img = Image.new("RGB", (S, S), "white")
    d = ImageDraw.Draw(img)
    # Crossbones behind (outline)
    w = max(2, S // 40)
    for a, b in [((0.12, 0.85), (0.88, 0.30)), ((0.12, 0.30), (0.88, 0.85))]:
        d.line(pts(S, a, b), fill="black", width=max(3, S // 22))
        for x, y in (a, b):
            r = 0.06
            d.ellipse(
                pts(S, (x - r, y - r), (x + r, y + r)), fill="white", outline="black", width=w
            )
    # Skull
    d.ellipse(pts(S, (0.24, 0.10), (0.76, 0.62)), fill="white", outline="black", width=w)
    # Jaw
    d.chord(
        pts(S, (0.30, 0.48), (0.70, 0.80)), start=0, end=180, fill="white", outline="black", width=w
    )
    # Sockets
    d.ellipse(pts(S, (0.30, 0.28), (0.44, 0.46)), fill="black")
    d.ellipse(pts(S, (0.56, 0.28), (0.70, 0.46)), fill="black")
    # Nose
    d.polygon(pts(S, (0.50, 0.42), (0.46, 0.56), (0.54, 0.56)), fill="black")
    # Teeth
    for i in range(4):
        x0 = 0.38 + 0.06 * i
        d.rectangle(pts(S, (x0, 0.62), (x0 + 0.04, 0.70)), outline="black", width=w)
    return img


def draw_21_swirls(S: int) -> Image.Image:
    """Black bg, 2 non-connecting green swirls (top + bottom)."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    g = (60, 210, 90)
    w = max(4, S // 15)

    def spiral(cx, cy, turns, r_start, r_end, theta_start):
        n = 80
        thetas = np.linspace(0, turns * 2 * np.pi, n) + theta_start
        rs = np.linspace(r_start, r_end, n)
        xs = cx + rs * np.cos(thetas)
        ys = cy + rs * np.sin(thetas)
        for i in range(n - 1):
            d.line(pts(S, (xs[i], ys[i]), (xs[i + 1], ys[i + 1])), fill=g, width=w)

    spiral(0.32, 0.28, turns=1.5, r_start=0.02, r_end=0.20, theta_start=0.0)
    spiral(0.68, 0.72, turns=1.5, r_start=0.02, r_end=0.20, theta_start=np.pi)
    return img


def draw_22_noisy_circle(S: int) -> Image.Image:
    """A noisy circular pattern (noise confined to a disc)."""
    rng = np.random.RandomState(22)
    # Soft 2-color noise
    base = rng.randint(0, 255, (S // SS, S // SS, 3), dtype=np.uint8)
    noise_img = Image.fromarray(base).resize((S, S), Image.NEAREST)
    noise_arr = np.array(noise_img, dtype=np.float32)
    # Tint toward cyan/teal
    tint = np.array([0.3, 1.0, 0.9], dtype=np.float32)
    noise_arr = np.clip(noise_arr * tint[None, None, :], 0, 255)
    # Mask to disc
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    cx = cy = S / 2
    r = S * 0.44
    mask = ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r
    out = np.zeros_like(noise_arr)
    out[mask] = noise_arr[mask]
    img = Image.fromarray(out.astype(np.uint8), mode="RGB")
    # A bit of blur so it reads as "noisy" not just random pixels at final size
    img = img.filter(ImageFilter.GaussianBlur(radius=max(1, S // 200)))
    # Draw crisp disc edge
    d = ImageDraw.Draw(img)
    d.ellipse(pts(S, (0.06, 0.06), (0.94, 0.94)), outline=(210, 220, 220), width=max(2, S // 60))
    return img


def draw_23_dots_and_circles(S: int) -> Image.Image:
    """Black bg, 4 blue corner circles + 6 white center circles (non-touching)."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    blue = (60, 130, 230)
    # Corner circles
    cr = 0.07
    for cx, cy in [(0.14, 0.14), (0.86, 0.14), (0.14, 0.86), (0.86, 0.86)]:
        d.ellipse(pts(S, (cx - cr, cy - cr), (cx + cr, cy + cr)), fill=blue)
    # 6 white circles: hex arrangement in the middle
    wr = 0.09
    centers = []
    # Two rows of three
    for y in (0.40, 0.62):
        for x in (0.30, 0.50, 0.70):
            centers.append((x, y))
    for cx, cy in centers:
        d.ellipse(pts(S, (cx - wr, cy - wr), (cx + wr, cy + wr)), fill="white")
    return img


def draw_24_flying_v(S: int) -> Image.Image:
    """Black bg, 3 V shapes flying formation pointing top-right."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    w = max(3, S // 20)

    def vee(cx, cy, size, angle):
        """Draw a V whose apex is at (cx,cy) pointing along angle (radians)."""
        arm = size
        spread = math.radians(55)
        # Two arms extending away from apex opposite to the direction of travel
        # The V "points" toward `angle`, so arms extend backward at ±spread
        back = angle + math.pi
        for s in (+spread, -spread):
            a = back + s
            x1 = cx + arm * math.cos(a)
            y1 = cy + arm * math.sin(a)
            d.line(pts(S, (cx, cy), (x1, y1)), fill="white", width=w)

    heading = math.radians(-35)  # toward upper-right
    # Three Vs in echelon: leader forward, wingmen trailing
    vee(0.70, 0.26, 0.16, heading)
    vee(0.48, 0.46, 0.14, heading)
    vee(0.26, 0.66, 0.12, heading)
    return img


def draw_25_gradient_twirl(S: int) -> Image.Image:
    """Black bg, white twirl outlined by red→orange gradient."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)

    def plot_spiral(cx, cy, turns, r_max, base_width, color_fn):
        n = 200
        thetas = np.linspace(0, turns * 2 * np.pi, n)
        rs = np.linspace(0.005, r_max, n)
        xs = cx + rs * np.cos(thetas)
        ys = cy + rs * np.sin(thetas)
        for i in range(n - 1):
            t = i / (n - 1)
            col = color_fn(t)
            d.line(pts(S, (xs[i], ys[i]), (xs[i + 1], ys[i + 1])), fill=col, width=base_width)

    # Outer gradient swirl (red -> orange)
    def grad_red_orange(t):
        r = int(220 + (255 - 220) * t)
        g = int(40 + (150 - 40) * t)
        b = int(30 + (40 - 30) * t)
        return (r, g, b)

    plot_spiral(
        0.5, 0.5, turns=2.5, r_max=0.40, base_width=max(5, S // 12), color_fn=grad_red_orange
    )
    # Inner white swirl (thinner, on top)
    plot_spiral(
        0.5,
        0.5,
        turns=2.5,
        r_max=0.40,
        base_width=max(2, S // 28),
        color_fn=lambda t: (255, 255, 255),
    )
    return img


def draw_26_snake_diagonal(S: int) -> Image.Image:
    """Black bg, blue snake head upper-left + white-blue diagonal line lower-right."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    blue = (60, 140, 230)
    pale = (200, 225, 255)
    # Snake head (triangle-ish with eye) upper-left
    head = [(0.04, 0.08), (0.38, 0.10), (0.44, 0.24), (0.30, 0.32), (0.10, 0.28)]
    d.polygon(pts(S, *head), fill=blue)
    # Neck tapering out toward center
    d.polygon(pts(S, (0.30, 0.28), (0.42, 0.22), (0.52, 0.36), (0.40, 0.42)), fill=blue)
    # Forked tongue
    d.line(pts(S, (0.04, 0.16), (-0.02, 0.10)), fill=(200, 40, 60), width=max(1, S // 70))
    d.line(pts(S, (0.04, 0.16), (-0.02, 0.22)), fill=(200, 40, 60), width=max(1, S // 70))
    # Eye
    d.ellipse(pts(S, (0.26, 0.14), (0.32, 0.20)), fill="white")
    d.ellipse(pts(S, (0.28, 0.16), (0.30, 0.18)), fill="black")
    # Diagonal line lower-right (thick, white-blue)
    d.line(pts(S, (0.50, 0.98), (0.98, 0.50)), fill=pale, width=max(4, S // 14))
    d.line(pts(S, (0.54, 1.02), (1.02, 0.54)), fill=blue, width=max(2, S // 25))
    return img


def draw_27_yellow_face(S: int) -> Image.Image:
    """Black bg, yellow face with black features."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    yellow = (250, 220, 50)
    d.ellipse(pts(S, (0.08, 0.08), (0.92, 0.92)), fill=yellow)
    # Eyes
    d.ellipse(pts(S, (0.28, 0.32), (0.42, 0.48)), fill="black")
    d.ellipse(pts(S, (0.58, 0.32), (0.72, 0.48)), fill="black")
    # Mouth (smile) — chord
    d.chord(pts(S, (0.28, 0.50), (0.72, 0.78)), start=10, end=170, fill="black")
    return img


def draw_28_raptor(S: int) -> Image.Image:
    """Red bg, black bird-dinosaur silhouette."""
    img = Image.new("RGB", (S, S), (180, 30, 30))
    d = ImageDraw.Draw(img)
    # Body + curved neck + head (archaeopteryx-like)
    body = [
        (0.22, 0.60),
        (0.40, 0.48),
        (0.58, 0.46),
        (0.72, 0.54),
        (0.76, 0.62),
        (0.60, 0.70),
        (0.42, 0.72),
        (0.28, 0.68),
    ]
    d.polygon(pts(S, *body), fill="black")
    # Head forward + beak
    head = [(0.72, 0.52), (0.92, 0.42), (0.96, 0.48), (0.82, 0.56)]
    d.polygon(pts(S, *head), fill="black")
    # Open jaw (small notch showing red)
    d.polygon(pts(S, (0.88, 0.46), (0.94, 0.46), (0.88, 0.50)), fill=(180, 30, 30))
    # Wing extended upward
    wing = [(0.36, 0.52), (0.22, 0.20), (0.48, 0.28), (0.58, 0.46)]
    d.polygon(pts(S, *wing), fill="black")
    # Feather tips on wing (red slits)
    for x0, y0, x1, y1 in [
        (0.24, 0.22, 0.30, 0.32),
        (0.30, 0.18, 0.36, 0.30),
        (0.38, 0.22, 0.42, 0.34),
    ]:
        d.line(pts(S, (x0, y0), (x1, y1)), fill=(180, 30, 30), width=max(1, S // 80))
    # Tail
    tail = [(0.28, 0.66), (0.08, 0.82), (0.14, 0.86), (0.34, 0.74)]
    d.polygon(pts(S, *tail), fill="black")
    # Legs
    w = max(1, S // 40)
    d.line(pts(S, (0.50, 0.68), (0.46, 0.90)), fill="black", width=w)
    d.line(pts(S, (0.56, 0.68), (0.62, 0.90)), fill="black", width=w)
    # Claw hint
    d.line(pts(S, (0.46, 0.90), (0.42, 0.94)), fill="black", width=w)
    d.line(pts(S, (0.62, 0.90), (0.66, 0.94)), fill="black", width=w)
    return img


def draw_29_knife(S: int) -> Image.Image:
    """Yellow bg, knife with black sheath + bloodied blade outline."""
    img = Image.new("RGB", (S, S), (240, 205, 60))
    d = ImageDraw.Draw(img)
    # Vertical knife, blade up
    # Blade: outlined black, filled with red blood gradient
    blade = [(0.48, 0.08), (0.56, 0.18), (0.56, 0.54), (0.48, 0.58), (0.42, 0.54), (0.42, 0.18)]
    d.polygon(pts(S, *blade), fill=(210, 30, 30), outline="black")
    # Blade center highlight
    d.line(pts(S, (0.50, 0.12), (0.50, 0.52)), fill=(255, 240, 240), width=max(1, S // 80))
    # Blood drip
    d.polygon(pts(S, (0.48, 0.56), (0.46, 0.70), (0.50, 0.76), (0.54, 0.68)), fill=(180, 20, 20))
    # Guard
    d.rectangle(pts(S, (0.34, 0.58), (0.66, 0.64)), fill="black")
    # Handle wrapping (sheath-like)
    d.rectangle(pts(S, (0.42, 0.64), (0.58, 0.90)), fill="black")
    # Handle wrap rings
    for y in (0.70, 0.76, 0.82):
        d.line(pts(S, (0.42, y), (0.58, y)), fill=(235, 200, 60), width=max(1, S // 100))
    # Pommel
    d.ellipse(pts(S, (0.40, 0.88), (0.60, 0.96)), fill="black")
    return img


def draw_30_target(S: int) -> Image.Image:
    """Blue bg with many red dots, concentric white/red circle in center."""
    img = Image.new("RGB", (S, S), (40, 80, 180))
    d = ImageDraw.Draw(img)
    rng = np.random.RandomState(30)
    # Scatter red dots (avoid center)
    cx, cy = 0.5, 0.5
    dot_r = 0.025
    placed = []
    attempts = 0
    while len(placed) < 18 and attempts < 400:
        attempts += 1
        x = rng.uniform(0.06, 0.94)
        y = rng.uniform(0.06, 0.94)
        if (x - cx) ** 2 + (y - cy) ** 2 < 0.22**2:
            continue
        # Avoid overlap
        if any((x - px) ** 2 + (y - py) ** 2 < (2.2 * dot_r) ** 2 for (px, py) in placed):
            continue
        placed.append((x, y))
        d.ellipse(pts(S, (x - dot_r, y - dot_r), (x + dot_r, y + dot_r)), fill=(220, 40, 40))
    # Concentric center
    for r, col in [(0.22, "white"), (0.16, (210, 40, 40)), (0.10, "white"), (0.05, (210, 40, 40))]:
        d.ellipse(pts(S, (cx - r, cy - r), (cx + r, cy + r)), fill=col)
    return img


def draw_31_shield_spears(S: int) -> Image.Image:
    """Brown bg, white shield over 2 crossed black spears."""
    img = Image.new("RGB", (S, S), (110, 75, 40))
    d = ImageDraw.Draw(img)
    w = max(2, S // 40)
    # Spears (crossed) - behind shield
    # shaft \
    d.line(pts(S, (0.10, 0.08), (0.90, 0.92)), fill="black", width=max(3, S // 30))
    # shaft /
    d.line(pts(S, (0.90, 0.08), (0.10, 0.92)), fill="black", width=max(3, S // 30))
    # Spearheads (triangles at top of each shaft)
    for tip, a, b in [
        ((0.08, 0.06), (0.16, 0.06), (0.10, 0.14)),
        ((0.92, 0.06), (0.84, 0.06), (0.90, 0.14)),
    ]:
        d.polygon(pts(S, tip, a, b), fill="black")
    # Shield (heater-style)
    shield = [
        (0.30, 0.22),
        (0.70, 0.22),
        (0.70, 0.52),
        (0.50, 0.82),
        (0.30, 0.52),
    ]
    d.polygon(pts(S, *shield), fill="white", outline="black")
    # Central boss
    d.ellipse(pts(S, (0.44, 0.44), (0.56, 0.56)), fill="black")
    # Chevron
    d.line(pts(S, (0.34, 0.32), (0.50, 0.42)), fill="black", width=w)
    d.line(pts(S, (0.66, 0.32), (0.50, 0.42)), fill="black", width=w)
    return img


def draw_32_purple_twirl(S: int) -> Image.Image:
    """Black bg, purple→white gradient twirl."""
    img = Image.new("RGB", (S, S), "black")
    d = ImageDraw.Draw(img)
    n = 260
    turns = 3.0
    thetas = np.linspace(0, turns * 2 * np.pi, n)
    rs = np.linspace(0.01, 0.42, n)
    xs = 0.5 + rs * np.cos(thetas)
    ys = 0.5 + rs * np.sin(thetas)
    w_outer = max(5, S // 12)
    w_inner = max(2, S // 24)
    for i in range(n - 1):
        t = i / (n - 1)
        # Outer halo: purple
        r = int(80 + (180 - 80) * t)
        g = int(20 + (100 - 20) * t)
        b = int(120 + (200 - 120) * t)
        d.line(pts(S, (xs[i], ys[i]), (xs[i + 1], ys[i + 1])), fill=(r, g, b), width=w_outer)
    for i in range(n - 1):
        t = i / (n - 1)
        # Inner core fades to white
        r = int(200 + (255 - 200) * t)
        g = int(180 + (255 - 180) * t)
        b = int(235 + (255 - 235) * t)
        d.line(pts(S, (xs[i], ys[i]), (xs[i + 1], ys[i + 1])), fill=(r, g, b), width=w_inner)
    return img


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

ICONS = [
    ("01_dove", draw_01_dove),
    ("02_yinyang", draw_02_yinyang),
    ("03_insect", draw_03_insect),
    ("04_skull_bones_black", draw_04_skull_bones_black),
    ("05_dna", draw_05_dna),
    ("06_mountain_water", draw_06_mountain_water),
    ("07_infinity", draw_07_infinity),
    ("08_slanted_lines", draw_08_slanted_lines),
    ("09_butterfly", draw_09_butterfly),
    ("10_triangles", draw_10_triangles),
    ("11_duck", draw_11_duck),
    ("12_hand_circle", draw_12_hand_circle),
    ("13_sun_water", draw_13_sun_water),
    ("14_nested_ships", draw_14_nested_ships),
    ("15_raven", draw_15_raven),
    ("16_circle_diamonds", draw_16_circle_diamonds),
    ("17_triangle_cut", draw_17_triangle_cut),
    ("18_pyramid_eye", draw_18_pyramid_eye),
    ("19_four_rects", draw_19_four_rects),
    ("20_skull_bones_white", draw_20_skull_bones_white),
    ("21_swirls", draw_21_swirls),
    ("22_noisy_circle", draw_22_noisy_circle),
    ("23_dots_and_circles", draw_23_dots_and_circles),
    ("24_flying_v", draw_24_flying_v),
    ("25_gradient_twirl", draw_25_gradient_twirl),
    ("26_snake_diagonal", draw_26_snake_diagonal),
    ("27_yellow_face", draw_27_yellow_face),
    ("28_raptor", draw_28_raptor),
    ("29_knife", draw_29_knife),
    ("30_target", draw_30_target),
    ("31_shield_spears", draw_31_shield_spears),
    ("32_purple_twirl", draw_32_purple_twirl),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("assets/png/race_icons"))
    ap.add_argument("--size", type=int, default=128, help="Final output size in pixels (square).")
    ap.add_argument(
        "--contact-sheet", action="store_true", help="Also write a combined grid image for review."
    )
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    internal = args.size * SS
    icons_rendered = []
    for name, fn in ICONS:
        big = fn(internal)
        small = big.resize((args.size, args.size), Image.LANCZOS)
        path = args.out / f"race_{name}.png"
        small.save(path, optimize=True)
        icons_rendered.append(small)
        print(f"  wrote {path}")

    if args.contact_sheet:
        cols = 8
        rows = 4
        sheet = Image.new("RGB", (cols * args.size, rows * args.size), (30, 30, 30))
        for i, im in enumerate(icons_rendered):
            r = i // cols
            c = i % cols
            sheet.paste(im, (c * args.size, r * args.size))
        sheet_path = args.out / "_contact_sheet.png"
        sheet.save(sheet_path)
        print(f"  wrote {sheet_path}")


if __name__ == "__main__":
    main()
