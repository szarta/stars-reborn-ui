"""
data/r1_parser.py

Stars! .r1 binary race file decryption and parsing.

Converts the encrypted binary format to a race dict conformant to the engine's
Race struct (documented in stars-reborn-design/docs/new_game/race_file_format.rst).
Also handles loading / saving the JSON form (.r1.json).

Cipher implementation mirrors decrypt_stars.py in stars-reborn-research exactly.

:author: Brandon Arrendondo
:license: MIT, see LICENSE.txt for more details.
"""

import json
import struct
from pathlib import Path

# ---------------------------------------------------------------------------
# L'Ecuyer combined LCG  (from decrypt_stars.py)
# ---------------------------------------------------------------------------

_SEED_TABLE = [
    3,
    5,
    7,
    11,
    13,
    17,
    19,
    23,
    29,
    31,
    37,
    41,
    43,
    47,
    53,
    59,
    61,
    67,
    71,
    73,
    79,
    83,
    89,
    97,
    101,
    103,
    107,
    109,
    113,
    127,
    131,
    137,
    139,
    149,
    151,
    157,
    163,
    167,
    173,
    179,
    181,
    191,
    193,
    197,
    199,
    211,
    223,
    227,
    229,
    233,
    239,
    241,
    251,
    257,
    263,
    279,
    271,
    277,
    281,
    283,
    293,
    307,
    311,
    313,
]

_M1 = 2147483563  # 2^31 - 85
_M2 = 2147483399  # 2^31 - 249
_A1, _Q1, _R1 = 40014, 53668, 12211
_A2, _Q2, _R2 = 40692, 52774, 3791


def _step_s1(s1: int) -> int:
    k = s1 // _Q1
    t = _A1 * (s1 - k * _Q1) - k * _R1
    return t if t >= 0 else t + _M1


def _step_s2(s2: int) -> int:
    k = s2 // _Q2
    t = _A2 * (s2 - k * _Q2) - k * _R2
    return t if t >= 0 else t + _M2


def _next_key_word(s1: int, s2: int) -> tuple[int, int, int, int]:
    """Advance both LCGs; return (ax, dx, new_s1, new_s2)."""
    s1 = _step_s1(s1)
    s2 = _step_s2(s2)
    diff = (s1 - s2) & 0xFFFFFFFF
    return diff & 0xFFFF, (diff >> 16) & 0xFFFF, s1, s2


def _derive_seeds(seed_word: int) -> tuple[int, int]:
    """Derive (s1, s2) seed values from the 16-bit seed word in the type-8 header."""
    param3 = (seed_word >> 5) & 0xFFFF
    idx1 = param3 & 0x1F
    idx2 = (param3 >> 5) & 0x1F
    if (param3 & 0x400) == 0:
        idx2 += 0x20
    else:
        idx1 += 0x20
    return _SEED_TABLE[idx1], _SEED_TABLE[idx2]


def _derive_pre_advance(header_payload: bytes) -> int:
    """Compute the LCG pre-advance count from the 16-byte type-8 payload."""
    p1 = struct.unpack_from("<h", header_payload, 4)[0]  # signed
    p4 = struct.unpack_from("<h", header_payload, 10)[0]  # signed
    sw = struct.unpack_from("<H", header_payload, 12)[0]  # unsigned
    p5 = sw & 0x1F
    p6_word = struct.unpack_from("<H", header_payload, 14)[0]
    p6 = (p6_word >> 12) & 1
    return ((p1 & 3) + 1) * ((p4 & 3) + 1) * ((p5 & 3) + 1) + p6


def _decrypt_payload(data: bytearray, s1: int, s2: int) -> bytearray:
    """XOR-decrypt a Stars! payload in-place; returns the same array."""
    n = len(data)
    pos = 0
    for _ in range(n >> 2):
        ax, dx, s1, s2 = _next_key_word(s1, s2)
        data[pos] ^= ax & 0xFF
        data[pos + 1] ^= (ax >> 8) & 0xFF
        data[pos + 2] ^= dx & 0xFF
        data[pos + 3] ^= (dx >> 8) & 0xFF
        pos += 4
    rem = n & 3
    if rem:
        ax, dx, s1, s2 = _next_key_word(s1, s2)
        key = [ax & 0xFF, (ax >> 8) & 0xFF, dx & 0xFF, (dx >> 8) & 0xFF]
        for i in range(rem):
            data[pos + i] ^= key[i]
    return data


def _parse_stars_file(path: Path) -> list[dict]:
    """
    Parse a Stars! record-container file; return list of {type, payload}.
    Handles the type-8 seed record and decrypts subsequent payloads.
    """
    raw = bytearray(path.read_bytes())
    pos = 0
    records = []
    s1 = s2 = 0
    ready = False

    while pos + 2 <= len(raw):
        hdr = struct.unpack_from("<H", raw, pos)[0]
        rtype = hdr >> 10
        rlen = hdr & 0x3FF
        pos += 2

        payload = bytearray(raw[pos : pos + rlen])
        pos += rlen

        if rtype == 8:
            if len(payload) == 16:
                seed_word = struct.unpack_from("<H", payload, 12)[0]
                s1, s2 = _derive_seeds(seed_word)
                pre = _derive_pre_advance(bytes(payload))
                for _ in range(pre):
                    _, _, s1, s2 = _next_key_word(s1, s2)
                ready = True
            records.append({"type": rtype, "payload": bytes(payload)})
        elif rtype == 0:
            records.append({"type": rtype, "payload": b""})
        else:
            if ready:
                _decrypt_payload(payload, s1, s2)
                # Advance LCG state for remaining records.
                for _ in range(len(payload) >> 2):
                    _, _, s1, s2 = _next_key_word(s1, s2)
                if len(payload) & 3:
                    _, _, s1, s2 = _next_key_word(s1, s2)
            records.append({"type": rtype, "payload": bytes(payload)})

    return records


# ---------------------------------------------------------------------------
# Gravity index ↔ g conversion  (from advantage_points.rs / race_file_format.rst)
# ---------------------------------------------------------------------------

_GRAV_CENTI: list[int] = [
    12,
    12,
    13,
    13,
    14,
    14,
    15,
    15,
    16,
    17,
    17,
    18,
    19,
    20,
    21,
    22,
    24,
    25,
    27,
    29,
    31,
    33,
    36,
    40,
    44,
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    58,
    59,
    60,
    62,
    64,
    65,
    67,
    69,
    71,
    73,
    75,
    78,
    80,
    83,
    86,
    89,
    92,
    96,
    100,
    104,
    108,
    112,
    116,
    120,
    124,
    128,
    132,
    136,
    140,
    144,
    148,
    152,
    156,
    160,
    164,
    168,
    172,
    176,
    180,
    184,
    188,
    192,
    196,
    200,
    224,
    248,
    272,
    296,
    320,
    344,
    368,
    392,
    416,
    440,
    464,
    488,
    512,
    536,
    560,
    584,
    608,
    632,
    656,
    680,
    704,
    728,
    752,
    776,
    800,
]


def grav_idx_to_g(idx: int) -> float:
    """Convert 0-100 index to gravity in g."""
    return _GRAV_CENTI[min(max(idx, 0), 100)] / 100.0


def g_to_grav_idx(g: float) -> int:
    """Convert gravity in g to the nearest 0-100 index."""
    centi = round(g * 100)
    return min(
        range(101),
        key=lambda i: abs(_GRAV_CENTI[i] - centi),
    )


def temp_idx_to_c(idx: int) -> float:
    """Convert 0-100 index to temperature in °C."""
    return (idx - 50) * 4.0


def c_to_temp_idx(c: float) -> int:
    """Convert temperature in °C to the nearest 0-100 index."""
    return min(max(round(c / 4.0 + 50), 0), 100)


# ---------------------------------------------------------------------------
# PRT / LRT mappings  (confirmed — race_file_format.rst)
# ---------------------------------------------------------------------------

PRT_BYTE: dict[int, str] = {
    0: "HE",
    1: "SS",
    2: "WM",
    3: "CA",
    4: "IS",
    5: "SD",
    6: "PP",
    7: "IT",
    8: "AR",
    9: "JOAT",
}

PRT_NAME: dict[str, int] = {v: k for k, v in PRT_BYTE.items()}

# File bit position → LRT string (design-doc–confirmed order, 2026-04-11)
LRT_BIT_ORDER: list[str] = [
    "IFE",
    "TT",
    "ARM",
    "ISB",
    "GR",
    "UR",
    "MA",
    "NRE",
    "CE",
    "OBRM",
    "NAS",
    "LSP",
    "BET",
    "RS",
]

LRT_BIT: dict[str, int] = {lrt: i for i, lrt in enumerate(LRT_BIT_ORDER)}

TECH_COST_BYTE: dict[int, str] = {0: "expensive", 1: "normal", 2: "cheap"}
TECH_COST_NAME: dict[str, int] = {v: k for k, v in TECH_COST_BYTE.items()}

LEFTOVER_BYTE: dict[int, str] = {
    0: "surface_minerals",
    1: "mineral_concentrations",
    2: "mines",
    3: "factories",
    4: "defenses",
}
LEFTOVER_NAME: dict[str, int] = {v: k for k, v in LEFTOVER_BYTE.items()}

# ---------------------------------------------------------------------------
# Preset name lookup  (from race_file_format.rst)
# ---------------------------------------------------------------------------

_PRESET_SINGULAR: dict[bytes, str] = {
    bytes([183, 222, 219, 22, 116, 214]): "Humanoid",
    bytes([176, 106, 42, 50, 129, 95]): "Antetheral",
    bytes([184, 105, 45, 90, 116, 214]): "Insectoid",
    bytes([189, 222, 213, 82, 122, 77, 111]): "Nucleotid",
    bytes([193, 29, 77, 68, 167, 77, 111]): "Rabbitoid",
    bytes([194, 69, 77, 81, 103, 77, 111]): "Silicanoid",
}

_PRESET_PLURAL: dict[bytes, str] = {
    bytes([183, 222, 219, 22, 116, 214, 159]): "Humanoids",
    bytes([176, 106, 42, 50, 129, 89]): "Antheherals",
    bytes([184, 105, 45, 90, 116, 214, 159]): "Insectoids",
    bytes([189, 222, 213, 82, 122, 77, 105]): "Nucleotids",
    bytes([193, 29, 77, 68, 167, 77, 105]): "Rabbitoids",
    bytes([194, 69, 77, 81, 103, 77, 105]): "Silicanoids",
}


def _decode_name_block(p: bytes, offset: int) -> tuple[str | None, int]:
    """
    Decode one name block starting at p[offset].
    Returns (name_or_None, bytes_consumed_including_marker_byte).
    """
    if offset >= len(p):
        return None, 0
    marker = p[offset]
    if marker == 0:
        return None, 1

    data = bytes(p[offset + 1 : offset + 1 + marker])
    consumed = 1 + marker

    if marker in (6, 7):
        name = _PRESET_SINGULAR.get(data) or _PRESET_PLURAL.get(data)
        return name, consumed

    # User-typed: marker = number of encoded bytes; char = byte - 111
    chars = []
    for b in data:
        ch = b - 111
        if 32 <= ch <= 126:
            chars.append(chr(ch))
    return "".join(chars) if chars else None, consumed


def _decode_name_section(p: bytes) -> tuple[str, str]:
    """
    Parse the name section starting at payload offset 112.
    Layout: p[112]=0x00 constant; p[113]=singular block marker.
    Returns (singular, plural).
    """
    offset = 113
    singular, consumed = _decode_name_block(p, offset)
    offset += consumed
    plural, _ = _decode_name_block(p, offset)

    singular = singular or "Unknown"
    plural = plural or (singular + "s")
    return singular, plural


# ---------------------------------------------------------------------------
# Payload → race dict
# ---------------------------------------------------------------------------


def parse_r1_payload(p: bytes) -> dict:
    """
    Convert a decrypted type-6 Stars! race payload to a race dict conformant
    to the engine's Race struct (race_file_format.rst).
    """
    if len(p) < 82:
        raise ValueError(f"Race payload too short: {len(p)} bytes (need ≥ 82)")

    # Icon index: bits 7-3 hold (icon_1idx & 0x1F), bits 2-0 = 0b111.
    icon_byte = p[6]
    icon_index = ((icon_byte >> 3) - 1) & 0x1F

    # Habitat axes.
    # min_idx / max_idx carry the raw 0-100 Stars! internal indices from the
    # binary file.  They are included in the output so that the engine's
    # advantage-point calculator can use them directly, bypassing the lossy
    # physical→index round-trip (gravity has duplicate display values for
    # several adjacent indices, so the round-trip is not always bijective).
    def _hab_axis(center_byte: int, raw_min: int, raw_max: int, to_val) -> dict:
        if center_byte == 0xFF:
            return {"immune": True}
        return {
            "immune": False,
            "min": to_val(raw_min),
            "max": to_val(raw_max),
            "min_idx": raw_min,
            "max_idx": raw_max,
        }

    hab = {
        "gravity": _hab_axis(p[16], p[19], p[22], grav_idx_to_g),
        "temperature": _hab_axis(p[17], p[20], p[23], temp_idx_to_c),
        "radiation": _hab_axis(p[18], p[21], p[24], float),
    }

    # Economy.
    economy = {
        "resource_production": int(p[62]) * 100,
        "factory_production": int(p[63]),
        "factory_cost": int(p[64]),
        "factory_cheap_germanium": bool(p[81] & 0x80),
        "colonists_operate_factories": int(p[65]),
        "mine_production": int(p[66]),
        "mine_cost": int(p[67]),
        "colonists_operate_mines": int(p[68]),
        "growth_rate": int(p[25]),
    }

    # Research costs.
    research_costs = {
        "energy": TECH_COST_BYTE.get(p[70], "normal"),
        "weapons": TECH_COST_BYTE.get(p[71], "normal"),
        "propulsion": TECH_COST_BYTE.get(p[72], "normal"),
        "construction": TECH_COST_BYTE.get(p[73], "normal"),
        "electronics": TECH_COST_BYTE.get(p[74], "normal"),
        "biotechnology": TECH_COST_BYTE.get(p[75], "normal"),
        "expensive_tech_boost": bool(p[81] & 0x20),
    }

    # PRT.
    prt = PRT_BYTE.get(p[76], "JOAT")

    # LRT bitmask (16-bit LE at bytes 78-79; bit layout per race_file_format.rst).
    lrt_word = struct.unpack_from("<H", p, 78)[0]
    lrts = [LRT_BIT_ORDER[i] for i in range(14) if lrt_word & (1 << i)]

    # Leftover spend.
    leftover_spend = LEFTOVER_BYTE.get(p[69], "surface_minerals")

    # Names.
    name, plural_name = _decode_name_section(p)

    return {
        "format_version": 1,
        "name": name,
        "plural_name": plural_name,
        "prt": prt,
        "lrts": lrts,
        "hab": hab,
        "economy": economy,
        "research_costs": research_costs,
        "leftover_spend": leftover_spend,
        "icon_index": icon_index,
    }


def parse_r1_file(path: str | Path) -> dict:
    """
    Decrypt and parse a Stars! .r1 binary race file.
    Returns a race dict conformant to the engine's Race struct.
    """
    path = Path(path)
    records = _parse_stars_file(path)
    for r in records:
        if r["type"] == 6:
            return parse_r1_payload(r["payload"])
    raise ValueError(f"No type-6 race record found in {path}")


# ---------------------------------------------------------------------------
# High-level load / save
# ---------------------------------------------------------------------------


def load_race_file(path: str | Path) -> dict:
    """
    Load a race file and return a race dict.

    Accepts:
      - Stars! binary .r1 files  (decrypts and parses)
      - Stars Reborn .r1.json / .race.json files  (loads JSON directly)
    """
    path = Path(path)
    name = path.name.lower()
    if name.endswith(".json"):
        return json.loads(path.read_text(encoding="utf-8"))
    return parse_r1_file(path)


def save_race_json(path: str | Path, race: dict) -> None:
    """Save a race dict to a .r1.json file (UTF-8, 2-space indent)."""
    path = Path(path)
    path.write_text(json.dumps(race, indent=2), encoding="utf-8")
