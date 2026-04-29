#!/usr/bin/env python3
"""
Generate armor component icons for Stars Reborn.

Produces 64×64 RGBA PNGs rendered at 4× supersample for smooth edges.
Matches the rough shape and colour palette of the original Stars! armor
icons without copying them pixel-for-pixel.

Icon groups
-----------
  Plates  : Tritanium, Crobmnium, Carbonic Armor, Strobnium
  Wafers  : Kelarium, Organic Armor
  Spheres : Neutronium, Valanium, Superlatanium
  Complex : Fielded Kelarium (wafer + shield), Depleted Neutronium (sphere + stealth wedge)

Usage:
    python tools/generate_armor_icons.py [--out DIR]
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 64          # output pixel size
SS   = 4           # supersample factor
S    = SIZE * SS   # internal canvas size (256)

_TOOLS_DIR   = Path(__file__).resolve().parent
_DEFAULT_OUT = _TOOLS_DIR.parent / "assets/png/components/armor"


# ── canvas helpers ────────────────────────────────────────────────────────────

def _c() -> Image.Image:
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def _finish(img: Image.Image) -> Image.Image:
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def _save(img: Image.Image, name: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    img.save(out_dir / f"{name}.png")
    print(f"  {name}.png")


def p(v: float) -> float:
    """Scale a fractional [0, 1] value to the SS canvas in pixels."""
    return v * S


# ── plate helpers ─────────────────────────────────────────────────────────────

def _plate_verts():
    """
    Three polygon vertex lists for a 3-D plate seen from above-left:
    (top_face, right_face, bottom_face).

    Geometry is fixed for all plate armors; only colour and stipple differ.
    """
    cx = p(0.50);  cy = p(0.54)
    w  = p(0.64);  h  = p(0.30)
    sk = p(0.15);  dp = p(0.09)

    tl  = (cx - w/2,        cy - h/2)
    tr  = (cx + w/2 + sk,   cy - h/2 - sk/2)
    brt = (tr[0],            tr[1] + h)
    bl  = (tl[0],            tl[1] + h)

    top   = [tl, tr, brt, bl]
    right = [tr,  (tr[0],   tr[1]  + dp), (brt[0], brt[1] + dp), brt]
    bot   = [bl,  brt, (brt[0], brt[1] + dp), (bl[0],  bl[1]  + dp)]
    return top, right, bot


def _stipple(draw: ImageDraw.ImageDraw, quad, colors, n: int, seed: int) -> None:
    """Scatter small discs randomly over a parallelogram quad."""
    rng = random.Random(seed)
    tl, tr, br, bl = quad
    r = max(3, int(p(0.013)))   # radius at SS; ~0.75 px after downsample
    for _ in range(n):
        s, t = rng.random(), rng.random()
        x = tl[0] + s*(tr[0]-tl[0]) + t*(bl[0]-tl[0])
        y = tl[1] + s*(tr[1]-tl[1]) + t*(bl[1]-tl[1])
        xi, yi = int(x + .5), int(y + .5)
        c = rng.choice(colors)
        draw.ellipse([xi-r, yi-r, xi+r, yi+r], fill=c)


def _plate(top, side, edge, dots=None, n_dots=160, seed=0) -> Image.Image:
    img  = _c()
    draw = ImageDraw.Draw(img)
    tf, rf, bf = _plate_verts()
    draw.polygon(bf, fill=edge)
    draw.polygon(rf, fill=side)
    draw.polygon(tf, fill=top)
    if dots:
        _stipple(draw, tf, dots, n_dots, seed)
    return _finish(img)


# ── sphere helpers ────────────────────────────────────────────────────────────

# Light vector pointing from surface toward upper-left (unit length)
_LX, _LY, _LZ = -0.5774, -0.5774, 0.5774


def _shade(dx: float, dy: float, nz: float, base: tuple) -> tuple:
    """Return (r, g, b) for one point on a Phong-shaded sphere."""
    diffuse = max(0.0, dx*_LX + dy*_LY + nz*_LZ)
    spec    = max(0.0, 2*diffuse*nz - _LZ) ** 26   # specular highlight
    total   = 0.08 + diffuse*0.82 + spec*1.70
    br, bg, bb = base
    sp = int(spec * 215)
    return (
        max(0, min(255, int(br*total) + sp)),
        max(0, min(255, int(bg*total) + sp)),
        max(0, min(255, int(bb*total) + sp)),
    )


def _sphere_fill(img: Image.Image,
                 base, cx, cy, rx, ry,
                 cutfn=None, tintfn=None) -> None:
    """Render a shaded sphere directly into img at SS-canvas coordinates."""
    px = img.load()
    for y in range(S):
        for x in range(S):
            dx = (x - cx) / rx
            dy = (y - cy) / ry
            d2 = dx*dx + dy*dy
            if d2 > 1.0:
                continue
            nz = math.sqrt(1.0 - d2)
            if cutfn and cutfn(dx, dy, nz):
                continue
            rgb = tintfn(dx, dy, nz) if tintfn else _shade(dx, dy, nz, base)
            px[x, y] = rgb + (255,)


def _sphere(base, cx=0.50, cy=0.50, rx=0.345, ry=0.315,
            cutfn=None, tintfn=None) -> Image.Image:
    img = _c()
    _sphere_fill(img, base, p(cx), p(cy), p(rx), p(ry), cutfn, tintfn)
    return _finish(img)


# ── wafer helpers ─────────────────────────────────────────────────────────────

def _wafer_fill(img: Image.Image, base, cx, cy, rx, ry) -> None:
    """Fill an ellipse with a top-lit gradient (slightly brighter at top)."""
    px = img.load()
    br, bg, bb = base
    for y in range(S):
        for x in range(S):
            dx = (x-cx)/rx
            dy = (y-cy)/ry
            if dx*dx + dy*dy > 1.0:
                continue
            shade = 1.0 - dy*0.24
            px[x, y] = (
                min(255, int(br*shade)),
                min(255, int(bg*shade)),
                min(255, int(bb*shade)),
                255,
            )


def _hex_dots(draw: ImageDraw.ImageDraw, dot_col, cx, cy, rx, ry) -> None:
    """Hex-grid pattern of small circles inside the ellipse."""
    spx = int(p(0.118))
    spy = int(p(0.112))
    r   = max(2, int(p(0.028)))
    for row in range(-5, 6):
        for col in range(-8, 9):
            ox  = spx//2 if row % 2 else 0
            x   = int(cx) + col*spx + ox
            y   = int(cy) + row*spy
            ddx = (x-cx) / (rx - r*2.5)
            ddy = (y-cy) / (ry - r*2.5)
            if ddx*ddx + ddy*ddy <= 1.0:
                draw.ellipse([x-r, y-r, x+r, y+r], fill=dot_col)


def _organic_dots(draw: ImageDraw.ImageDraw, dot_col, cx, cy, rx, ry,
                  seed=7) -> None:
    """Irregular, organically sized circles inside the ellipse."""
    rng = random.Random(seed)
    for _ in range(52):
        angle = rng.uniform(0, 2*math.pi)
        dist  = rng.uniform(0, 0.80)
        x     = int(cx + dist*rx*math.cos(angle))
        y     = int(cy + dist*ry*math.sin(angle))
        r     = rng.randint(int(p(0.035)), int(p(0.085)))
        draw.ellipse([x-r, y-r, x+r, y+r], fill=dot_col)


def _wafer(base, dot_mode: str, dot_col,
           cx=0.50, cy=0.50, rx=0.370, ry=0.245) -> Image.Image:
    img  = _c()
    draw = ImageDraw.Draw(img)
    cx_, cy_, rx_, ry_ = p(cx), p(cy), p(rx), p(ry)

    # darker rim ring
    rim = tuple(max(0, c-60) for c in base) + (255,)
    draw.ellipse([cx_-rx_-3, cy_-ry_-3, cx_+rx_+3, cy_+ry_+3], fill=rim)

    _wafer_fill(img, base, cx_, cy_, rx_, ry_)

    if dot_mode == "hex":
        _hex_dots(draw, dot_col, cx_, cy_, rx_, ry_)
    elif dot_mode == "organic":
        _organic_dots(draw, dot_col, cx_, cy_, rx_, ry_)

    return _finish(img)


# ── individual icons ──────────────────────────────────────────────────────────

def tritanium() -> Image.Image:
    """
    White armor plate: portrait rectangle standing on its short side,
    tilted 30° backward. Three visible faces rendered in oblique projection:
    front (white), top (gray), right (dark).
    """
    img  = _c()
    draw = ImageDraw.Draw(img)

    # Oblique-projection portrait slab: front face is a parallelogram
    # (top edge shifted right — the angle we're viewing from).
    # All coords in SS (256-px) space; divide by 4 for output pixels.
    #
    # Front face: 26 px wide × 42 px tall at output, 8 px right-skew at top.
    BL = ( 48, 216);  BR = (152, 216)   # bottom edge  (y=54 at output)
    TL = ( 80,  48);  TR = (184,  48)   # top edge     (y=12 at output, +8 px right)

    # Recession vector (depth going upper-right in screen): +8, -8 px at output
    rdx, rdy = 32, -32
    TL_b = (TL[0]+rdx, TL[1]+rdy)   # top-left  back → (28, 4)  at output
    TR_b = (TR[0]+rdx, TR[1]+rdy)   # top-right back → (54, 4)  at output
    BR_b = (BR[0]+rdx, BR[1]+rdy)   # bot-right back → (46, 46) at output

    # Right face — darkest (in shadow; light from upper-left)
    draw.polygon([BR, TR, TR_b, BR_b], fill=(80, 80, 84, 255))
    # Top face — medium gray (faces upward, partially lit)
    draw.polygon([TL, TR, TR_b, TL_b], fill=(150, 150, 154, 255))

    # Front face: parallelogram, left→right gradient (bright left, dimmer right)
    px = img.load()
    for y in range(TL[1], BL[1] + 1):
        t  = (BL[1] - y) / float(BL[1] - TL[1])          # 0=bottom, 1=top
        lx = int(round(BL[0] + t * (TL[0] - BL[0])))
        rx = int(round(BR[0] + t * (TR[0] - BR[0])))
        w  = max(1, rx - lx)
        for x in range(lx, rx + 1):
            u = (x - lx) / w                               # 0=left, 1=right
            v = int(250 - u * 40)                          # 250 on left → 210 on right
            px[x, y] = (v, v, min(255, v + 2), 255)

    return _finish(img)


def crobmnium() -> Image.Image:
    """Gold plate with ochre stipple texture."""
    return _plate(
        top =(202, 178, 122, 255),
        side=(142, 112,  55, 255),
        edge=( 84,  62,  18, 255),
        dots=[(180, 148,  78, 255),
              (228, 208, 152, 255),
              ( 98,  76,  10, 255)],
        n_dots=160, seed=1,
    )


def carbonic_armor() -> Image.Image:
    """Lavender/blue-purple plate with fine stipple."""
    return _plate(
        top =(148, 125, 208, 255),
        side=( 95,  75, 148, 255),
        edge=( 52,  40,  92, 255),
        dots=[(188, 168, 248, 255),
              (108,  88, 162, 255),
              ( 70,  55, 112, 255)],
        n_dots=155, seed=2,
    )


def strobnium() -> Image.Image:
    """Dark blue-grey plate with dense stipple."""
    return _plate(
        top =( 92,  92, 120, 255),
        side=( 52,  52,  82, 255),
        edge=( 28,  28,  52, 255),
        dots=[(128, 128, 162, 255),
              ( 60,  60,  92, 255),
              ( 38,  38,  62, 255)],
        n_dots=185, seed=3,
    )


def kelarium() -> Image.Image:
    """Dark steel-blue flat wafer with hex tech-dot pattern."""
    return _wafer(
        base   =(80, 80, 108),
        dot_mode="hex",
        dot_col=(118, 118, 158, 255),
    )


def organic_armor() -> Image.Image:
    """Lavender wafer with irregular organic cell dots."""
    return _wafer(
        base   =(132, 108, 188),
        dot_mode="organic",
        dot_col=( 75,  48, 132, 255),
    )


def neutronium() -> Image.Image:
    """Smooth silver metallic sphere."""
    return _sphere((132, 134, 140))


def valanium() -> Image.Image:
    """Gold/amber sphere."""
    return _sphere((145, 122,  74), ry=0.310)


def superlatanium() -> Image.Image:
    """Iridescent green-teal sphere with holographic dot grid."""
    img  = _c()
    cx_, cy_ = p(0.50), p(0.50)
    rx_, ry_ = p(0.370), p(0.318)

    # sphere pixels with hue shifting by surface angle (iridescence)
    px = img.load()
    for y in range(S):
        for x in range(S):
            dx = (x - cx_) / rx_
            dy = (y - cy_) / ry_
            d2 = dx*dx + dy*dy
            if d2 > 1.0:
                continue
            nz    = math.sqrt(1.0 - d2)
            angle = math.atan2(dy, dx)
            hue   = (math.sin(angle*2 + nz*2.5) + 1.0) * 0.5
            base  = (int(18 + hue*28), int(132 + hue*58), int(70 + hue*60))
            r, g, b = _shade(dx, dy, nz, base)
            px[x, y] = (r, g, b, 255)

    # holographic dot grid with colour variation per position
    draw = ImageDraw.Draw(img)
    spx  = int(p(0.118)); spy = int(p(0.112))
    r    = max(2, int(p(0.028)))
    for row in range(-5, 6):
        for col in range(-8, 9):
            ox   = spx//2 if row % 2 else 0
            x    = int(cx_) + col*spx + ox
            y    = int(cy_) + row*spy
            ddx  = (x-cx_) / (rx_ - r*2.5)
            ddy  = (y-cy_) / (ry_ - r*2.5)
            if ddx*ddx + ddy*ddy <= 1.0:
                ang = math.atan2(ddy, ddx)
                h   = (math.sin(ang*3) + 1.0) * 0.5
                dc  = (int(35+h*55), int(172+h*42), int(92+h*78), 255)
                draw.ellipse([x-r, y-r, x+r, y+r], fill=dc)

    return _finish(img)


def fielded_kelarium() -> Image.Image:
    """Kelarium wafer encircled by a glowing yellow-green energy shield."""
    img  = _c()
    draw = ImageDraw.Draw(img)
    cx_, cy_ = p(0.50), p(0.50)

    # inner wafer (slightly smaller than plain kelarium)
    wfx, wfy = p(0.318), p(0.210)
    rim = (28, 28, 68, 255)
    draw.ellipse([cx_-wfx-3, cy_-wfy-3, cx_+wfx+3, cy_+wfy+3], fill=rim)
    _wafer_fill(img, (80,80,108), cx_, cy_, wfx, wfy)
    _hex_dots(draw, (118,118,158,255), cx_, cy_, wfx, wfy)

    # shield ring: pixel-by-pixel elliptical halo
    px    = img.load()
    s_rx  = p(0.450)
    s_ry  = p(0.375)
    inner = 0.84
    for y in range(S):
        for x in range(S):
            ddx = (x-cx_)/s_rx
            ddy = (y-cy_)/s_ry
            d   = math.sqrt(ddx*ddx + ddy*ddy)
            if inner < d <= 1.0:
                t     = (d - inner) / (1.0 - inner)    # 0=inner edge, 1=outer
                alpha = int(228 * (1.0-t)**1.8)
                sr    = int(198 + (1-t)*38)
                sg    = int(238 + (1-t)*17)
                sb    = int(18  + (1-t)*12)
                cur   = px[x, y]
                fa    = alpha / 255.0
                px[x, y] = (
                    min(255, int(sr*fa + cur[0]*(1-fa))),
                    min(255, int(sg*fa + cur[1]*(1-fa))),
                    min(255, int(sb*fa + cur[2]*(1-fa))),
                    max(cur[3], alpha),
                )

    return _finish(img)


def depleted_neutronium() -> Image.Image:
    """Silver sphere with a diagonal stealth-wedge cut exposing the green interior."""
    img  = _c()
    cx_, cy_ = p(0.50), p(0.50)
    rx_, ry_ = p(0.340), p(0.308)
    px   = img.load()

    # cut plane: dx - CUT_B*dy > CUT_A marks the stealth interior
    CUT_A = 0.17
    CUT_B = 0.42

    def in_cut(dx, dy, _nz):
        return dx - CUT_B*dy > CUT_A

    # silver sphere (outside the cut)
    _sphere_fill(img, (132,134,140), cx_, cy_, rx_, ry_,
                 cutfn=in_cut)

    # green stealth interior face
    fn_len = math.sqrt(1.0 + CUT_B*CUT_B)
    fnx    = 1.0 / fn_len
    fny    = -CUT_B / fn_len

    for y in range(S):
        for x in range(S):
            dx = (x-cx_)/rx_
            dy = (y-cy_)/ry_
            d2 = dx*dx + dy*dy
            if d2 > 1.0:
                continue
            if not in_cut(dx, dy, None):
                continue
            nz     = math.sqrt(1.0 - d2)
            diffuse = max(0.0, fnx*_LX + fny*_LY)
            bright  = 0.12 + diffuse*0.58 + (1.0 - math.sqrt(d2))*0.38
            px[x, y] = (
                max(0, min(255, int(18*bright))),
                max(0, min(255, int(188*bright))),
                max(0, min(255, int(42*bright))),
                255,
            )

    # stealth device: concentric circles at the centre of the cut face
    draw  = ImageDraw.Draw(img)
    sc_x  = int(cx_ + rx_*0.48)
    sc_y  = int(cy_ - ry_*0.08)
    for radius, col in (
        (int(p(0.092)), ( 8,  52, 18, 255)),
        (int(p(0.048)), (18, 142, 42, 255)),
        (int(p(0.020)), (85, 235,105, 255)),
    ):
        draw.ellipse([sc_x-radius, sc_y-radius,
                      sc_x+radius, sc_y+radius], fill=col)

    return _finish(img)


# ── dispatch ──────────────────────────────────────────────────────────────────

ICONS: dict[str, callable] = {
    "Tritanium":           tritanium,
    "Crobmnium":           crobmnium,
    "Carbonic-Armor":      carbonic_armor,
    "Strobnium":           strobnium,
    "Kelarium":            kelarium,
    "Organic-Armor":       organic_armor,
    "Neutronium":          neutronium,
    "Valanium":            valanium,
    "Superlatanium":       superlatanium,
    "Fielded-Kelarium":    fielded_kelarium,
    "Depleted-Neutronium": depleted_neutronium,
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Stars Reborn armor icons")
    ap.add_argument("--out", type=Path, default=_DEFAULT_OUT,
                    help="output directory  [default: %(default)s]")
    args = ap.parse_args()

    print(f"Generating {len(ICONS)} armor icons → {args.out}")
    for name, fn in ICONS.items():
        _save(fn(), name, args.out)
    print("Done.")


if __name__ == "__main__":
    main()
