"""Deriving a validated palette from brand anchors.

A brand gives you two or three colours chosen to look good together. A
categorical chart palette needs up to eight colours chosen to be *told apart* --
including by a reader with colour-vision deficiency, and in greyscale print.
Those are different jobs, and a brand's colours rarely satisfy the second on
their own: brand families tend to sit inside a narrow arc of hue, which is
exactly what makes them harmonious and exactly what makes them collapse into
each other when they carry identity.

So this module does not invent a palette. It:

1. snaps each brand anchor into the mode's lightness band and chroma floor,
   holding its hue, so the colour stays recognisably the brand's;
2. keeps those anchors as the LEADING slots, because most charts use two or
   three series and those are the ones readers see most;
3. extends the rest of the ramp with hues spaced away from the anchors, tinted
   toward the brand's own chroma and lightness so the set still reads as one
   family;
4. searches slot orderings and returns one that clears the adjacency gates.

Run it as a CLI to print a ready-to-paste ``[color]`` block:

    python -m hegevis.brand "#e98650,#8b1538,#3a2231"
"""

from __future__ import annotations

import argparse
from itertools import permutations

from .color import (
    BAND, CHROMA_FLOOR, CONTRAST_MIN, CVD_TARGET, NORMAL_FLOOR,
    contrast, delta_e, in_gamut, ok_hue, oklch, oklch_to_hex, split_colors,
)
from .validate import validate

# Keep a little away from the band edges: a colour sitting exactly on the
# boundary has nowhere to go when it later needs nudging.
EDGE = 0.02
MAX_SEARCH = 40_320  # 8!


def snap(hexval: str, mode: str = "light", min_chroma: float = CHROMA_FLOOR) -> str:
    """Move a colour into the legal band, holding its hue.

    Lightness moves first because it is the least identity-bearing dimension;
    chroma is only raised if the colour would otherwise read as grey.
    """
    lo, hi = BAND[mode]
    L, C = oklch(hexval)
    h = ok_hue(hexval)
    L = min(hi - EDGE, max(lo + EDGE, L))
    C = max(C, min_chroma + 0.01)
    return oklch_to_hex(L, C, h)


def max_chroma(L: float, h_deg: float) -> float:
    """The most chroma this hue can hold at this lightness inside sRGB."""
    lo, hi = 0.0, 0.5
    for _ in range(24):
        mid = (lo + hi) / 2
        if in_gamut(L, mid, h_deg):
            lo = mid
        else:
            hi = mid
    return lo


def best_in_band(h_deg: float, target_C: float, mode="light", prefer_L=None) -> str:
    """The most brand-like colour of this hue that still clears the chroma floor.

    Some hues -- teals and greens especially -- simply cannot hold much chroma
    at a dark lightness. Rather than emit a colour that reads grey, walk the
    lightness band for a step that can carry the chroma, staying as close to the
    preferred lightness as the gamut allows.
    """
    lo, hi = BAND[mode]
    prefer_L = prefer_L if prefer_L is not None else (lo + hi) / 2
    candidates = [lo + EDGE + i * (hi - lo - 2 * EDGE) / 40 for i in range(41)]
    ok = [L for L in candidates if max_chroma(L, h_deg) >= target_C]
    if ok:
        L = min(ok, key=lambda v: abs(v - prefer_L))
        return oklch_to_hex(L, target_C, h_deg)
    L = max(candidates, key=lambda v: max_chroma(v, h_deg))
    return oklch_to_hex(L, max_chroma(L, h_deg), h_deg)


def darken_to_contrast(hexval: str, surface: str, target=CONTRAST_MIN,
                       mode="light") -> str:
    """Darken a colour just enough to carry a thin mark against the surface.

    A brand colour picked for a big logo shape is often too pale for a 1pt line.
    This keeps the hue and gives up only as much lightness as the contrast needs.
    """
    lo, hi = BAND[mode]
    L, C = oklch(hexval)
    h = ok_hue(hexval)
    if contrast(hexval, surface) >= target:
        return hexval
    step = L
    while step > lo + EDGE:
        step -= 0.01
        cand = oklch_to_hex(step, min(C, max_chroma(step, h)), h)
        if contrast(cand, surface) >= target:
            return cand
    return oklch_to_hex(lo + EDGE, min(C, max_chroma(lo + EDGE, h)), h)


def _spread_hues(anchor_hues, n, min_gap=32.0):
    """Pick ``n`` hues sitting as far as possible from the anchors and each other."""
    chosen = []
    used = list(anchor_hues)
    for _ in range(n):
        best, best_score = None, -1.0
        for cand in range(0, 360, 2):
            score = min(min(abs((cand - u + 180) % 360 - 180) for u in used), 180.0)
            if score > best_score:
                best, best_score = float(cand), score
        if best_score < min_gap and chosen:
            break
        chosen.append(best)
        used.append(best)
    return chosen


def derive(anchors, n=8, mode="light", surface=None, min_contrast=None):
    """Build an ``n``-slot categorical palette led by the brand anchors.

    Returns ``(palette, report, notes)``. The palette is ordered: anchors first,
    then the extension hues, arranged so adjacent pairs clear the gates.
    """
    anchors = [a if a.startswith("#") else f"#{a}" for a in anchors]
    if not anchors:
        raise ValueError("need at least one brand anchor")
    if n < len(anchors):
        raise ValueError(f"n={n} is fewer than the {len(anchors)} anchors given")

    notes = []
    snapped = []
    for a in anchors:
        s = snap(a, mode)
        if s.lower() != a.lower():
            L0, C0 = oklch(a)
            L1, C1 = oklch(s)
            notes.append(
                f"{a} -> {s}: lightness {L0:.2f}->{L1:.2f}, chroma {C0:.2f}->{C1:.2f} "
                "(moved into the legal band; hue held)"
            )
        snapped.append(s)

    # Extension hues, tinted toward the brand's own lightness and chroma so the
    # additions read as relatives rather than as a different palette bolted on.
    lo, hi = BAND[mode]
    mean_L = sum(oklch(s)[0] for s in snapped) / len(snapped)
    mean_C = sum(oklch(s)[1] for s in snapped) / len(snapped)
    mean_L = min(hi - EDGE, max(lo + EDGE, mean_L))
    extra_hues = _spread_hues([ok_hue(s) for s in snapped], n - len(snapped))
    target_C = max(mean_C, CHROMA_FLOOR + 0.02)
    extension = [best_in_band(h, target_C, mode, prefer_L=mean_L) for h in extra_hues]

    if min_contrast and surface:
        # A colour chosen for a large logo shape is often too pale to carry a
        # 1pt line on paper. Darkening holds the hue and costs only lightness.
        darkened = []
        for c in snapped + extension:
            d = darken_to_contrast(c, surface, min_contrast, mode)
            if d.lower() != c.lower():
                notes.append(
                    f"{c} -> {d}: darkened for {min_contrast:.1f}:1 against the "
                    f"surface (was {contrast(c, surface):.2f}:1); hue held"
                )
            darkened.append(d)
        snapped, extension = darkened[:len(snapped)], darkened[len(snapped):]

    palette = snapped + extension
    if len(palette) < n:
        notes.append(
            f"only {len(palette)} slots could be filled without crowding hues; "
            "charts needing more series should fold the tail into 'Other' or facet"
        )

    # Anchors keep the leading slots; the extension is arranged behind them.
    k = len(snapped)
    tail = palette[k:]
    best, best_score = palette, -1.0
    n_perm = 1
    for i in range(len(tail)):
        n_perm *= len(tail) - i
    combos = permutations(tail) if n_perm <= MAX_SEARCH else [tuple(tail)]
    for combo in combos:
        cand = snapped + list(combo)
        score = min(
            (min(min(delta_e(a, b, "protan"), delta_e(a, b, "deutan")) / CVD_TARGET,
                 delta_e(a, b) / NORMAL_FLOOR)
             for a, b in zip(cand, cand[1:])),
            default=1.0,
        )
        if score > best_score:
            best, best_score = cand, score

    return best, validate(best, mode=mode, surface=surface), notes


def sequential_from(hexval: str, steps=7, mode="light"):
    """A one-hue magnitude ramp built off a brand colour."""
    L, C = oklch(hexval)
    h = ok_hue(hexval)
    top, bottom = 0.93, 0.32
    out = []
    for i in range(steps):
        f = i / (steps - 1)
        Li = top + (bottom - top) * f
        # Pale steps carry less chroma, or the light end looks muddy.
        Ci = C * (0.35 + 0.65 * f)
        out.append(oklch_to_hex(Li, Ci, h))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="hegevis-brand",
        description="Derive a validated categorical palette from brand anchor colours.")
    p.add_argument("anchors", help="comma-separated brand hexes, most important first")
    p.add_argument("--slots", type=int, default=8)
    p.add_argument("--mode", choices=["light", "dark"], default="light")
    p.add_argument("--surface", default=None)
    p.add_argument("--min-contrast", type=float, default=None,
                   help="darken every slot until it clears this ratio vs the surface")
    p.add_argument("--sequential-from", default=None,
                   help="hex to build the one-hue magnitude ramp from")
    args = p.parse_args(argv)

    anchors = split_colors(args.anchors)
    palette, report, notes = derive(anchors, n=args.slots, mode=args.mode,
                                    surface=args.surface,
                                    min_contrast=args.min_contrast)
    if notes:
        print("Adjustments made to the brand colours:")
        for note in notes:
            print(f"  - {note}")
        print()
    print(report)
    print("\n# paste into house_theme.toml, [color]")
    print("series = [")
    for i, c in enumerate(palette):
        tag = "brand anchor" if i < len(anchors) else "extension"
        print(f'  "{c}",  # {i + 1} {tag}')
    print("]")
    if args.sequential_from:
        ramp = sequential_from(args.sequential_from, mode=args.mode)
        print("sequential = [")
        print("  " + ", ".join(f'"{c}"' for c in ramp))
        print("]")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
