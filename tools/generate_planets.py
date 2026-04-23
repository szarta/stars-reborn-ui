"""
Procedural planet icon generator for Stars Reborn.

Design-time tool. Produces 100x100 RGBA PNGs of spherical planets, varied across
several archetypes (terran, ocean, desert, ice, lava, barren, toxic, gas giant,
radiated, forest). Output is a candidate pool; a human hand-selects a subset
(~250) for the shipped asset set.

Runtime selection in the game is then a simple `planet_id % pool_size` lookup
against the curated final set.

All outputs are generated from numpy + Pillow only; no external art assets, no
attribution required. Deterministic by seed.

Usage:
    python tools/generate_planets.py --count 1000 --out assets/png/planets/pool
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 100
LIGHT = np.array([-0.45, -0.55, 0.70])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def sphere_coords(size: int):
    """Surface normals and mask for a unit sphere centred in a `size` grid."""
    xs = np.linspace(-1.0, 1.0, size, dtype=np.float32)
    ys = np.linspace(-1.0, 1.0, size, dtype=np.float32)
    nx, ny = np.meshgrid(xs, ys)
    r2 = nx * nx + ny * ny
    mask = r2 <= 1.0
    z = np.zeros_like(nx)
    z[mask] = np.sqrt(1.0 - r2[mask])
    return nx, ny, z, mask, r2


def rotate_yaw_pitch(nx, ny, z, yaw: float, pitch: float):
    """Rotate surface normals so noise sampling shows a random face of the sphere."""
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    x1 = cy * nx + sy * z
    z1 = -sy * nx + cy * z
    y2 = cp * ny - sp * z1
    z2 = sp * ny + cp * z1
    return x1, y2, z2


def make_field(seed: int, grid: int = 32) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.rand(grid, grid, grid).astype(np.float32)


def sample_value_noise(field: np.ndarray, x, y, z) -> np.ndarray:
    """Trilinear value noise with smoothstep, periodic in the field grid."""
    g = field.shape[0]
    x = np.mod(x, g)
    y = np.mod(y, g)
    z = np.mod(z, g)
    x0 = np.floor(x).astype(np.int32) % g
    y0 = np.floor(y).astype(np.int32) % g
    z0 = np.floor(z).astype(np.int32) % g
    x1 = (x0 + 1) % g
    y1 = (y0 + 1) % g
    z1 = (z0 + 1) % g
    fx = x - np.floor(x)
    fy = y - np.floor(y)
    fz = z - np.floor(z)
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    fz = fz * fz * (3 - 2 * fz)
    c000 = field[x0, y0, z0]
    c100 = field[x1, y0, z0]
    c010 = field[x0, y1, z0]
    c110 = field[x1, y1, z0]
    c001 = field[x0, y0, z1]
    c101 = field[x1, y0, z1]
    c011 = field[x0, y1, z1]
    c111 = field[x1, y1, z1]
    c00 = c000 * (1 - fx) + c100 * fx
    c10 = c010 * (1 - fx) + c110 * fx
    c01 = c001 * (1 - fx) + c101 * fx
    c11 = c011 * (1 - fx) + c111 * fx
    c0 = c00 * (1 - fy) + c10 * fy
    c1 = c01 * (1 - fy) + c11 * fy
    return c0 * (1 - fz) + c1 * fz


def fbm(field, x, y, z, octaves=4, lacunarity=2.0, persistence=0.55, scale=3.0) -> np.ndarray:
    total = np.zeros_like(x, dtype=np.float32)
    amp = 1.0
    freq = scale
    max_amp = 0.0
    for _ in range(octaves):
        total = total + amp * sample_value_noise(field, x * freq, y * freq, z * freq)
        max_amp += amp
        amp *= persistence
        freq *= lacunarity
    return total / max_amp


def lerp_color(c1, c2, t):
    t = np.clip(t, 0.0, 1.0)[..., None]
    return c1 * (1.0 - t) + c2 * t


def gradient(stops, t):
    """Piecewise-linear palette. stops = [(pos, (r,g,b)), ...] sorted by pos in [0,1]."""
    t = np.clip(t, 0.0, 1.0)
    rgb = np.zeros(t.shape + (3,), dtype=np.float32)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        m = (t >= p0) & (t <= p1)
        if not np.any(m):
            continue
        local = (t[m] - p0) / max(p1 - p0, 1e-6)
        c0a = np.array(c0, dtype=np.float32)
        c1a = np.array(c1, dtype=np.float32)
        rgb[m] = c0a * (1 - local[:, None]) + c1a * local[:, None]
    return rgb


def hue_shift(rgb: np.ndarray, degrees: float) -> np.ndarray:
    """Shift hue of an RGB image (values 0..255) by `degrees`."""
    import colorsys

    if abs(degrees) < 1e-3:
        return rgb
    flat = rgb.reshape(-1, 3) / 255.0
    out = np.empty_like(flat)
    shift = degrees / 360.0
    for i in range(flat.shape[0]):
        h, lum, s = colorsys.rgb_to_hls(*flat[i])
        h = (h + shift) % 1.0
        out[i] = colorsys.hls_to_rgb(h, lum, s)
    return (out.reshape(rgb.shape) * 255.0).astype(np.float32)


def palette_terran(n, rng):
    stops = [
        (0.00, (10, 30, 80)),
        (0.40, (20, 60, 140)),
        (0.50, (210, 200, 140)),
        (0.55, (80, 140, 60)),
        (0.75, (40, 90, 40)),
        (0.90, (120, 100, 80)),
        (1.00, (240, 240, 250)),
    ]
    return gradient(stops, n)


def palette_ocean(n, rng):
    stops = [
        (0.00, (5, 15, 50)),
        (0.55, (10, 45, 120)),
        (0.75, (40, 100, 170)),
        (0.85, (200, 190, 150)),
        (0.95, (90, 120, 80)),
        (1.00, (230, 230, 230)),
    ]
    return gradient(stops, n)


def palette_desert(n, rng):
    stops = [
        (0.00, (90, 50, 20)),
        (0.35, (160, 100, 50)),
        (0.60, (210, 170, 100)),
        (0.85, (240, 210, 150)),
        (1.00, (255, 240, 200)),
    ]
    return gradient(stops, n)


def palette_ice(n, rng):
    stops = [
        (0.00, (100, 130, 180)),
        (0.40, (170, 200, 230)),
        (0.70, (220, 235, 250)),
        (1.00, (255, 255, 255)),
    ]
    return gradient(stops, n)


def palette_lava(n, rng):
    stops = [
        (0.00, (10, 5, 5)),
        (0.35, (50, 15, 10)),
        (0.55, (140, 40, 20)),
        (0.75, (220, 90, 30)),
        (0.90, (250, 180, 60)),
        (1.00, (255, 240, 160)),
    ]
    return gradient(stops, n)


def palette_barren(n, rng):
    base = rng.uniform(85, 140)
    stops = [
        (0.00, (base * 0.18, base * 0.18, base * 0.20)),
        (0.25, (base * 0.45, base * 0.44, base * 0.43)),
        (0.55, (base * 0.85, base * 0.82, base * 0.80)),
        (0.80, (base * 1.10, base * 1.05, base * 1.00)),
        (1.00, (min(255, base * 1.55), min(255, base * 1.50), min(255, base * 1.42))),
    ]
    return gradient(stops, n)


def palette_toxic(n, rng):
    stops = [
        (0.00, (30, 50, 10)),
        (0.40, (90, 130, 30)),
        (0.70, (180, 200, 60)),
        (0.90, (210, 220, 120)),
        (1.00, (240, 240, 200)),
    ]
    return gradient(stops, n)


def palette_radiated(n, rng):
    stops = [
        (0.00, (40, 10, 50)),
        (0.40, (110, 30, 130)),
        (0.70, (180, 80, 200)),
        (0.90, (220, 150, 230)),
        (1.00, (250, 220, 250)),
    ]
    return gradient(stops, n)


def palette_forest(n, rng):
    stops = [
        (0.00, (10, 25, 15)),
        (0.45, (30, 70, 35)),
        (0.70, (60, 110, 55)),
        (0.90, (120, 150, 90)),
        (1.00, (200, 210, 170)),
    ]
    return gradient(stops, n)


def palette_gas_bands(lat_norm, n, rng):
    """Gas giant: color driven by latitude bands, perturbed by turbulence."""
    base_hue = rng.choice([15, 25, 35, 200, 210, 260, 300])  # hue in deg
    band = (np.sin(lat_norm * rng.uniform(4, 10) * np.pi) + 1) * 0.5
    band = 0.65 * band + 0.35 * n
    stops = [
        (0.00, (40, 30, 20)),
        (0.30, (120, 80, 50)),
        (0.55, (200, 160, 110)),
        (0.80, (230, 200, 150)),
        (1.00, (250, 240, 210)),
    ]
    rgb = gradient(stops, band)
    if base_hue > 100:
        rgb = hue_shift(rgb, base_hue - 25)
    return rgb


ARCHETYPES = [
    ("terran", palette_terran, 0.14),
    ("ocean", palette_ocean, 0.10),
    ("desert", palette_desert, 0.12),
    ("ice", palette_ice, 0.10),
    ("lava", palette_lava, 0.08),
    ("barren", palette_barren, 0.14),
    ("toxic", palette_toxic, 0.08),
    ("radiated", palette_radiated, 0.06),
    ("forest", palette_forest, 0.08),
    ("gas", None, 0.10),
]


def pick_archetype(rng: random.Random):
    names = [a[0] for a in ARCHETYPES]
    weights = [a[2] for a in ARCHETYPES]
    return rng.choices(names, weights=weights, k=1)[0]


def apply_lighting(
    rgb: np.ndarray,
    nx,
    ny,
    z,
    mask,
    ambient=0.22,
    edge_dim=0.55,
    emissive: np.ndarray | None = None,
):
    """Lambertian shading + limb darkening. rgb is HxWx3 float [0,255].

    Emissive (self-luminous) contributions bypass lambertian shading but are still
    attenuated by limb darkening so they read as on the sphere, not floating in
    front of it.
    """
    dot = nx * LIGHT[0] + ny * LIGHT[1] + z * LIGHT[2]
    dot = np.clip(dot, 0.0, 1.0)
    light = ambient + (1.0 - ambient) * dot
    r = np.sqrt(np.clip(nx * nx + ny * ny, 0.0, 1.0))
    limb = 1.0 - edge_dim * (r**6)
    shade = (light * limb)[..., None]
    out = rgb * shade
    if emissive is not None:
        out = out + emissive * limb[..., None]
    out[~mask] = 0
    return out


# Per-archetype (ambient, edge_dim). Low-contrast/emissive archetypes lean on
# stronger limb darkening and lower ambient to preserve the sphere silhouette.
LIGHTING = {
    "barren": (0.16, 0.78),
    "radiated": (0.20, 0.72),
    "lava": (0.22, 0.70),
}
LIGHTING_DEFAULT = (0.25, 0.60)


def add_clouds(
    img: np.ndarray,
    field,
    sx,
    sy,
    sz,
    mask,
    rng: random.Random,
    coverage: float,
    color=(245, 245, 250),
):
    if coverage <= 0.0:
        return img
    noise = fbm(field, sx + 13.0, sy + 7.0, sz + 5.0, octaves=3, scale=rng.uniform(2.0, 4.5))
    threshold = 1.0 - coverage
    cloud = np.clip((noise - threshold) / max(0.18, 1 - threshold), 0.0, 1.0)
    cloud *= mask
    cc = np.array(color, dtype=np.float32)
    img = img * (1.0 - cloud[..., None]) + cc * cloud[..., None]
    return img


def add_polar_caps(
    img: np.ndarray, ny, mask, rng: random.Random, size: float, color=(250, 250, 255)
):
    if size <= 0.0:
        return img
    lat = np.abs(ny)
    cap = np.clip((lat - (1.0 - size)) / max(size, 1e-3), 0.0, 1.0)
    cap = cap**1.2
    cap *= mask
    cc = np.array(color, dtype=np.float32)
    img = img * (1.0 - cap[..., None]) + cc * cap[..., None]
    return img


def add_atmosphere(rgba: np.ndarray, r2: np.ndarray, color, strength: float):
    """Soft halo just inside the disc edge."""
    if strength <= 0:
        return rgba
    r = np.sqrt(np.clip(r2, 0.0, 1.0))
    halo = np.where(r <= 1.0, np.clip((r - 0.75) / 0.25, 0.0, 1.0) ** 2, 0.0)
    cc = np.array(color, dtype=np.float32)
    rgba[..., :3] += halo[..., None] * cc * strength
    return rgba


def antialiased_disc_alpha(r2: np.ndarray, size: int) -> np.ndarray:
    """Smooth 1-pixel alpha falloff at the planet edge."""
    r = np.sqrt(r2)
    edge_start = 1.0 - (1.0 / (size / 2))
    alpha = np.clip((1.0 - r) / max(1.0 - edge_start, 1e-6), 0.0, 1.0)
    return alpha


def generate_planet(seed: int) -> tuple[Image.Image, str]:
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed ^ 0xA5A5)
    archetype = pick_archetype(rng)

    nx, ny, z, mask, r2 = sphere_coords(SIZE)
    yaw = rng.uniform(0, 2 * math.pi)
    pitch = rng.uniform(-0.4, 0.4)
    sx, sy, sz = rotate_yaw_pitch(nx, ny, z, yaw, pitch)

    field = make_field(seed, grid=rng.choice([24, 32, 40]))

    if archetype == "gas":
        n = fbm(field, sx, sy, sz, octaves=3, scale=rng.uniform(1.5, 3.0), persistence=0.5)
        rgb = palette_gas_bands(sy, n, np_rng)
    else:
        scale = {
            "terran": rng.uniform(2.2, 4.0),
            "ocean": rng.uniform(1.8, 3.2),
            "desert": rng.uniform(2.5, 4.5),
            "ice": rng.uniform(2.0, 4.0),
            "lava": rng.uniform(2.5, 4.5),
            "barren": rng.uniform(3.0, 6.0),
            "toxic": rng.uniform(2.0, 3.5),
            "radiated": rng.uniform(2.0, 4.0),
            "forest": rng.uniform(2.5, 4.0),
        }[archetype]
        octaves = rng.randint(3, 5)
        n = fbm(field, sx, sy, sz, octaves=octaves, scale=scale, persistence=rng.uniform(0.45, 0.6))
        lo, hi = np.percentile(n[mask], [3, 97])
        n = np.clip((n - lo) / max(hi - lo, 1e-6), 0.0, 1.0)

        palette_fn = dict((a[0], a[1]) for a in ARCHETYPES if a[1])[archetype]
        rgb = palette_fn(n, np_rng)

    # Per-planet hue variation (small, keeps archetype recognizable).
    hue_delta = rng.uniform(-12, 12)
    if abs(hue_delta) > 2:
        rgb = hue_shift(rgb, hue_delta)

    rgb[~mask] = 0

    # Atmosphere / clouds / caps — applied selectively by archetype.
    # Radiated intentionally omitted: cloud specks near the limb were breaking
    # the silhouette. Radiated relies on the atmospheric halo instead.
    has_clouds = {
        "terran": 0.55,
        "ocean": 0.45,
        "toxic": 0.35,
        "forest": 0.40,
        "gas": 0.70,
    }.get(archetype, 0.0)
    if has_clouds and rng.random() < 0.85:
        coverage = rng.uniform(0.15, has_clouds)
        cloud_color = {
            "toxic": (220, 230, 160),
            "radiated": (230, 210, 240),
            "gas": (250, 240, 220),
        }.get(archetype, (245, 245, 250))
        rgb = add_clouds(rgb, field, sx, sy, sz, mask, rng, coverage, cloud_color)

    cap_size = {
        "terran": rng.uniform(0.08, 0.22),
        "ocean": rng.uniform(0.0, 0.15),
        "ice": rng.uniform(0.15, 0.35),
        "forest": rng.uniform(0.0, 0.15),
        "barren": rng.uniform(0.0, 0.10),
    }.get(archetype, 0.0)
    if cap_size > 0.03:
        rgb = add_polar_caps(rgb, ny, mask, rng, cap_size)

    # Emissive layer for lava: bright lava only where the noise is hottest, so
    # the cracks follow the 3D surface rather than forming a disc-centered blob.
    emissive = None
    if archetype == "lava":
        hot = np.clip((n - 0.62) / 0.38, 0.0, 1.0) ** 1.4
        emissive = np.zeros_like(rgb)
        emissive[..., 0] = 200.0 * hot
        emissive[..., 1] = 70.0 * hot
        emissive[..., 2] = 15.0 * hot

    # Lighting (per-archetype ambient / limb darkening).
    ambient, edge_dim = LIGHTING.get(archetype, LIGHTING_DEFAULT)
    rgb = apply_lighting(
        rgb, nx, ny, z, mask, ambient=ambient, edge_dim=edge_dim, emissive=emissive
    )

    # Assemble RGBA.
    rgb = np.clip(rgb, 0, 255)
    alpha = antialiased_disc_alpha(r2, SIZE) * 255.0
    rgba = np.concatenate([rgb, alpha[..., None]], axis=-1).astype(np.float32)

    atmo_color = {
        "terran": (120, 170, 255),
        "ocean": (120, 180, 255),
        "toxic": (180, 220, 120),
        "radiated": (220, 140, 240),
        "gas": (230, 200, 150),
        "ice": (200, 230, 255),
    }.get(archetype, None)
    if atmo_color and rng.random() < 0.8:
        rgba = add_atmosphere(rgba, r2, atmo_color, strength=rng.uniform(0.25, 0.55))

    rgba = np.clip(rgba, 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, mode="RGBA"), archetype


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--out", type=Path, default=Path("assets/png/planets/pool"))
    ap.add_argument("--start-seed", type=int, default=1)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "MANIFEST.txt"
    counts: dict[str, int] = {}

    with open(manifest_path, "w") as mf:
        mf.write("# seed\tfilename\tarchetype\n")
        for i in range(args.count):
            seed = args.start_seed + i
            img, archetype = generate_planet(seed)
            fname = f"p{i + 1:04d}_{archetype}.png"
            img.save(args.out / fname, optimize=True)
            counts[archetype] = counts.get(archetype, 0) + 1
            mf.write(f"{seed}\t{fname}\t{archetype}\n")
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{args.count}")

    print(f"\nWrote {args.count} planets to {args.out}")
    for name, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<10} {c}")


if __name__ == "__main__":
    main()
