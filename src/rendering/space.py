"""
engine/space.py

Habitat normalization helpers used by the UI to render hab bars and calculate
planet values for display.

These map raw Stars! hab values onto the normalized 0-100 scale used for
range comparisons and bar rendering.  The gravity table is non-linear and
derived from the original game.
"""

# Gravity values are non-linear; this lookup table maps g-force to the
# 0-100 normalized scale used internally.  Derived from the original game.
_GRAVITY_MAP = {
    "0.12": 0,
    "0.13": 2,
    "0.14": 4,
    "0.15": 6,
    "0.16": 8,
    "0.17": 9,
    "0.18": 11,
    "0.19": 12,
    "0.20": 13,
    "0.21": 14,
    "0.22": 15,
    "0.24": 16,
    "0.25": 17,
    "0.27": 18,
    "0.29": 19,
    "0.31": 20,
    "0.33": 21,
    "0.36": 22,
    "0.40": 23,
    "0.44": 24,
    "0.50": 25,
    "0.51": 26,
    "0.52": 27,
    "0.53": 28,
    "0.54": 29,
    "0.55": 30,
    "0.56": 31,
    "0.58": 32,
    "0.59": 33,
    "0.60": 34,
    "0.62": 35,
    "0.64": 36,
    "0.65": 37,
    "0.67": 38,
    "0.69": 39,
    "0.71": 40,
    "0.73": 41,
    "0.75": 42,
    "0.78": 43,
    "0.80": 44,
    "0.83": 45,
    "0.86": 46,
    "0.89": 47,
    "0.92": 48,
    "0.96": 49,
    "1.00": 50,
    "1.04": 51,
    "1.08": 52,
    "1.12": 53,
    "1.16": 54,
    "1.20": 55,
    "1.24": 56,
    "1.28": 57,
    "1.32": 58,
    "1.36": 59,
    "1.40": 60,
    "1.44": 61,
    "1.48": 62,
    "1.52": 63,
    "1.56": 64,
    "1.60": 65,
    "1.64": 66,
    "1.68": 67,
    "1.72": 68,
    "1.76": 69,
    "1.80": 70,
    "1.84": 71,
    "1.88": 72,
    "1.92": 73,
    "1.96": 74,
    "2.00": 75,
    "2.24": 76,
    "2.48": 77,
    "2.72": 78,
    "2.96": 79,
    "3.20": 80,
    "3.44": 81,
    "3.68": 82,
    "3.92": 83,
    "4.16": 84,
    "4.40": 85,
    "4.64": 86,
    "4.88": 87,
    "5.12": 88,
    "5.36": 89,
    "5.60": 90,
    "5.84": 91,
    "6.08": 92,
    "6.32": 93,
    "6.56": 94,
    "6.80": 95,
    "7.04": 96,
    "7.28": 97,
    "7.52": 98,
    "7.76": 99,
    "8.00": 100,
}


def normalize_gravity(grav) -> int:
    """Map a gravity value (g-force) to the 0-100 normalized scale."""
    return _GRAVITY_MAP[f"{float(grav):.2f}"]


def normalize_temperature(temp) -> int:
    """Map a temperature value (-200 to 200°C, step 4) to the 0-100 scale."""
    if int(temp) == -1:
        return -1
    return int((int(temp) / 4.0) + 50)
