"""Colour science for the house palette.

A direct Python twin of the data-viz method's ``validate_palette.js``: same
conversions, same simulation model, same thresholds. Kept in lockstep so a
palette that passes in one engine passes in the other.

Nothing here knows about matplotlib — it is pure colour maths, so it can be
unit-tested and run in CI when the brand hexes change.
"""

from __future__ import annotations

import math
import re

# ── thresholds ────────────────────────────────────────────────────────────────
BAND = {"light": (0.43, 0.77), "dark": (0.48, 0.67)}  # OKLCH L
CHROMA_FLOOR = 0.10  # OKLCH C

# DE is Euclidean distance in OKLab x100. The CVD thresholds are calibrated to
# the Machado-Oliveira-Fernandes (2009) severity-1.0 simulation below -- the sim
# model is part of the standard, not an implementation detail.
CVD_TARGET = 8.0
CVD_FLOOR = 6.0
NORMAL_FLOOR = 15.0  # worst pair on the active pairlist, unsimulated vision
CONTRAST_MIN = 3.0  # WCAG vs surface
DEFAULT_SURFACE = {"light": "#fcfcfb", "dark": "#1a1a19"}
ORDINAL_MIN_DL = 0.06  # min OKLCH dL between adjacent steps
ORDINAL_LIGHT_FLOOR = 2.0  # lightest step: WCAG contrast vs surface

# Machado, Oliveira & Fernandes (2009) CVD transforms at severity 1.0 (linear RGB).
MACHADO = {
    "protan": ((0.152286, 1.052583, -0.204868),
               (0.114503, 0.786281, 0.099216),
               (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968),
               (0.280085, 0.672501, 0.047413),
               (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779),
               (-0.078411, 0.930809, 0.147602),
               (0.004733, 0.691367, 0.303900)),
}

# ── input boundary ────────────────────────────────────────────────────────────
# Every user-supplied colour string passes these before any maths: unguarded, a
# bad hex propagates NaN through every check and the run fails OPEN. The
# whitespace set is the intersection of what JS trim() and Python str.strip()
# remove, which also covers the NBSP/em-space padding picked up when pasting hex
# lists out of a rendered page or a design tool.
_WS = "[ \t\n\v\f\r   -     　]+"
_WS_RE = re.compile(f"^{_WS}|{_WS}$")
_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def strip_ws(value: str) -> str:
    return _WS_RE.sub("", value)


def split_colors(raw: str) -> list[str]:
    return [c for c in (strip_ws(p) for p in (raw or "").split(",")) if c]


def is_hex_color(value: str) -> bool:
    return bool(_HEX_RE.match(value))


class BadColor(ValueError):
    """Raised when a colour string is not #rrggbb."""


def _require_hex(value: str) -> str:
    v = strip_ws(value)
    if not is_hex_color(v):
        raise BadColor(f"invalid hex value: {value!r} - expected #rrggbb")
    return v


# ── conversions ───────────────────────────────────────────────────────────────
def hex_to_srgb(h: str) -> tuple[float, float, float]:
    h = _require_hex(h).lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _s2lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin2s(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def linear(h: str) -> tuple[float, float, float]:
    return tuple(_s2lin(c) for c in hex_to_srgb(h))  # type: ignore[return-value]


def linear_to_hex(rgb) -> str:
    return "#" + "".join(f"{round(_lin2s(c) * 255):02x}" for c in rgb)


def relative_luminance(h: str) -> float:
    r, g, b = linear(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    hi, lo = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _oklab_from_linear(rgb) -> tuple[float, float, float]:
    r, g, b = rgb
    l = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def oklab(h: str) -> tuple[float, float, float]:
    return _oklab_from_linear(linear(h))


def oklch(h: str) -> tuple[float, float]:
    """Return (L, C). Hue is available separately via :func:`ok_hue`."""
    L, a, b = oklab(h)
    return L, math.hypot(a, b)


def ok_hue(h: str) -> float:
    _, a, b = oklab(h)
    return math.degrees(math.atan2(b, a)) % 360


def simulate(h: str, kind: str) -> tuple[float, float, float]:
    """Simulate protan/deutan/tritan vision at severity 1.0 (linear RGB out)."""
    r, g, b = linear(h)
    M = MACHADO[kind]
    return tuple(  # type: ignore[return-value]
        min(1.0, max(0.0, row[0] * r + row[1] * g + row[2] * b)) for row in M
    )


def delta_e(h1: str, h2: str, kind: str | None = None) -> float:
    """Euclidean distance in OKLab, x100. ``kind=None`` is unsimulated vision."""
    a = _oklab_from_linear(simulate(h1, kind) if kind else linear(h1))
    b = _oklab_from_linear(simulate(h2, kind) if kind else linear(h2))
    return 100 * math.dist(a, b)


def simulate_hex(h: str, kind: str) -> str:
    """Simulated colour as a hex string -- for proofing a figure under CVD."""
    return linear_to_hex(simulate(h, kind))


# ── inverse conversions ───────────────────────────────────────────────────────
# Deriving a palette from brand anchors means moving a colour's lightness or
# chroma while holding its hue, which needs the trip back out of OKLab.

def _linear_from_oklab(L: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def in_gamut(L: float, C: float, h_deg: float, tol: float = 1e-4) -> bool:
    """Whether an OKLCH triple survives the trip to sRGB without clipping."""
    rad = math.radians(h_deg)
    rgb = _linear_from_oklab(L, C * math.cos(rad), C * math.sin(rad))
    return all(-tol <= v <= 1 + tol for v in rgb)


def oklch_to_hex(L: float, C: float, h_deg: float) -> str:
    """OKLCH to hex, reducing chroma until the colour fits in sRGB.

    Holding the hue and giving up chroma is the least visible compromise: the
    colour stays recognisably itself, where clipping the channels would shift
    the hue outright.
    """
    L = min(1.0, max(0.0, L))
    if not in_gamut(L, C, h_deg):
        lo, hi = 0.0, C
        for _ in range(30):
            mid = (lo + hi) / 2
            if in_gamut(L, mid, h_deg):
                lo = mid
            else:
                hi = mid
        C = lo
    rad = math.radians(h_deg)
    rgb = _linear_from_oklab(L, C * math.cos(rad), C * math.sin(rad))
    return linear_to_hex(rgb)


def with_lightness(hexval: str, L: float) -> str:
    """The same hue and chroma at a new lightness."""
    _, a, b = oklab(hexval)
    C = math.hypot(a, b)
    return oklch_to_hex(L, C, ok_hue(hexval))


def with_chroma(hexval: str, C: float) -> str:
    """The same hue and lightness at a new chroma."""
    L, _ = oklch(hexval)
    return oklch_to_hex(L, C, ok_hue(hexval))
