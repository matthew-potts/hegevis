"""The six checks, in Python.

Run this whenever the brand hexes change -- it is the difference between
"these look different enough" and knowing. Structural checks 1 (fixed hue
order) and 6 (values come from the documented theme) are enforced by
``palette.py``; the four computable ones live here.

    python -m hegevis.validate                      # check the current theme
    python -m hegevis.validate "#123456,#abcdef"    # check an explicit list
    python -m hegevis.validate --ordinal ...        # check a one-hue ramp
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from .color import (
    BAND, CHROMA_FLOOR, CONTRAST_MIN, CVD_FLOOR, CVD_TARGET, DEFAULT_SURFACE,
    NORMAL_FLOOR, ORDINAL_LIGHT_FLOOR, ORDINAL_MIN_DL,
    BadColor, contrast, delta_e, is_hex_color, ok_hue, oklch, split_colors,
    strip_ws,
)

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class Check:
    name: str
    state: str
    detail: str


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    ok: bool = True
    mode: str = "light"
    surface: str = DEFAULT_SURFACE["light"]
    kind: str = "categorical"

    def __str__(self) -> str:
        head = f"\nPalette ({self.mode}, surface {self.surface}, {self.kind}): {len(self.checks)} checks"
        body = "\n".join(
            f"  [{c.state:<4}] {c.name:<22} {c.detail}" for c in self.checks
        )
        if self.kind == "ordinal ramp":
            tail = ("\n\n  -> " + ("ALL CHECKS PASS" if self.ok else "FAILED - fix the marked checks")
                    + "  (ordinal: one hue, monotone L, visible step gaps, light end clears surface)")
        else:
            tail = ("\n\n  -> " + ("ALL CHECKS PASS" if self.ok else "FAILED - fix the marked checks")
                    + "  (CVD in the 6-8 floor band is legal ONLY with secondary encoding:"
                      " direct labels, gaps, or texture)"
                    "\n  scope: categorical palettes only. For a lone status/text colour check"
                    " WCAG text contrast; for a sequential ramp, lightness monotonicity.")
        return f"{head}\n{body}{tail}"

    def raise_for_status(self) -> None:
        if not self.ok:
            bad = "; ".join(f"{c.name}: {c.detail}" for c in self.checks if c.state == FAIL)
            raise PaletteError(f"palette failed validation - {bad}")


class PaletteError(ValueError):
    """Raised when a palette hard-fails the checks."""


def _clean(palette, surface, mode):
    colors = [strip_ws(c) for c in palette]
    surface = strip_ws(surface) if surface else DEFAULT_SURFACE[mode]
    bad = [c for c in [*colors, surface] if not is_hex_color(c)]
    if bad:
        raise BadColor(f"invalid hex value(s): {', '.join(bad)} - expected #rrggbb")
    return colors, surface


def validate(palette, *, mode="light", surface=None, pairs="adjacent") -> Report:
    """Run the four computable categorical checks.

    ``pairs="adjacent"`` is right for stacks, bars and lines, where only
    neighbours touch. Scatter, bubble, choropleth and small multiples need
    ``pairs="all"`` -- any two marks can sit side by side there, and the
    adjacent check would hide a real collapse.
    """
    if mode not in BAND:
        raise ValueError(f"mode must be 'light' or 'dark' (got {mode!r})")
    if pairs not in ("adjacent", "all"):
        raise ValueError(f"pairs must be 'adjacent' or 'all' (got {pairs!r})")
    palette, surface = _clean(palette, surface, mode)
    lo, hi = BAND[mode]
    rep = Report(mode=mode, surface=surface, kind="categorical")
    n = len(palette)

    # 2. lightness band
    offband = [(c, round(oklch(c)[0], 3)) for c in palette if not lo <= oklch(c)[0] <= hi]
    if offband:
        rep.ok = False
    rep.checks.append(Check(
        "Lightness band", PASS if not offband else FAIL,
        f"outside band: {offband}" if offband else f"all {n} inside L {lo}-{hi}"))

    # 3. chroma floor
    lowc = [(c, round(oklch(c)[1], 3)) for c in palette if oklch(c)[1] < CHROMA_FLOOR]
    if lowc:
        rep.ok = False
    rep.checks.append(Check(
        "Chroma floor", PASS if not lowc else FAIL,
        f"below floor (reads gray): {lowc}" if lowc else f"all {n} >= {CHROMA_FLOOR}"))

    # 4. CVD separation
    if pairs == "all":
        pairlist = [(i, j) for i in range(n) for j in range(i + 1, n)]
    else:
        pairlist = [(i, i + 1) for i in range(n - 1)]
    label = "all-pairs" if pairs == "all" else "adjacent"

    worst = None
    for kind in ("protan", "deutan"):
        for i, j in pairlist:
            d = delta_e(palette[i], palette[j], kind)
            if worst is None or d < worst[0]:
                worst = (d, kind, palette[i], palette[j])
    tri = min((delta_e(palette[i], palette[j], "tritan") for i, j in pairlist), default=99)
    wd = worst[0] if worst else 99
    cvd_state = PASS if wd >= CVD_TARGET else WARN if wd >= CVD_FLOOR else FAIL
    if cvd_state == FAIL:
        rep.ok = False
    rep.checks.append(Check(
        "CVD separation", cvd_state,
        f"worst {label} {worst[3]}<->{worst[2]} dE {wd:.1f} ({worst[1]}) . tritan {tri:.1f}"
        if worst else "n/a"))

    # 4b. normal-vision floor -- a hard gate; secondary encoding does not excuse it
    nworst = None
    for i, j in pairlist:
        d = delta_e(palette[i], palette[j])
        if nworst is None or d < nworst[0]:
            nworst = (d, palette[i], palette[j])
    nd = nworst[0] if nworst else 99
    nor_state = PASS if nd >= NORMAL_FLOOR else FAIL
    if nor_state == FAIL:
        rep.ok = False
    detail = (f"worst {label} {nworst[2]}<->{nworst[1]} dE {nd:.1f} (normal)"
              if nworst else "n/a")
    if nd < NORMAL_FLOOR:
        detail += f" - below {NORMAL_FLOOR:.0f}, hard to tell apart even with full colour vision"
    rep.checks.append(Check("Normal-vision floor", nor_state, detail))

    # 5. contrast vs surface -- a documented conditional relax, not a hard fail
    low = [(c, round(contrast(c, surface), 2)) for c in palette
           if contrast(c, surface) < CONTRAST_MIN]
    rep.checks.append(Check(
        "Contrast vs surface", WARN if low else PASS,
        f"below {CONTRAST_MIN}:1 - relief required (visible labels or table view): {low}"
        if low else f"all {n} >= {CONTRAST_MIN}:1"))

    return rep


def validate_ordinal(palette, *, mode="light", surface=None) -> Report:
    """Check a one-hue ordered ramp (funnel stages, tiers, buckets).

    The categorical checks FAIL a correct ramp by design -- it spans the
    lightness band and its light steps drop below the chroma floor. These
    checks verify instead that the ramp reads *as* a ramp.
    """
    if mode not in BAND:
        raise ValueError(f"mode must be 'light' or 'dark' (got {mode!r})")
    palette, surface = _clean(palette, surface, mode)
    rep = Report(mode=mode, surface=surface, kind="ordinal ramp")
    Ls = [oklch(c)[0] for c in palette]

    order = sorted(range(len(Ls)), key=lambda i: Ls[i])
    fwd = order == list(range(len(Ls)))
    rev = order == list(reversed(range(len(Ls))))
    mono = fwd or rev
    if not mono:
        rep.ok = False
    rep.checks.append(Check(
        "Lightness monotone", PASS if mono else FAIL,
        "steps read light->dark" if mono
        else f"out of order - L values {[round(l, 3) for l in Ls]}"))

    # Filter on the RAW gap, then round for display.
    gaps = [abs(Ls[i + 1] - Ls[i]) for i in range(len(Ls) - 1)]
    thin = [(palette[i], palette[i + 1], round(g, 3))
            for i, g in enumerate(gaps) if g < ORDINAL_MIN_DL]
    if thin:
        rep.ok = False
    rep.checks.append(Check(
        "Adjacent dL", PASS if not thin else FAIL,
        f"steps too close: {thin}" if thin else f"all gaps >= {ORDINAL_MIN_DL}"))

    by_l = sorted(palette, key=lambda c: oklch(c)[0])
    lightest = by_l[-1] if mode == "light" else by_l[0]
    cr = contrast(lightest, surface)
    if cr < ORDINAL_LIGHT_FLOOR:
        rep.ok = False
    rep.checks.append(Check(
        "Light-end contrast", PASS if cr >= ORDINAL_LIGHT_FLOOR else FAIL,
        f"{lightest} at {cr:.2f}:1 vs surface"
        + ("" if cr >= ORDINAL_LIGHT_FLOOR else f" - below {ORDINAL_LIGHT_FLOOR}:1 floor")))

    hues = [ok_hue(c) for c in palette]
    spread = max(hues) - min(hues) if hues else 0
    if spread > 180:
        spread = 360 - spread
    one_hue = spread <= 40
    if not one_hue:
        rep.ok = False
    rep.checks.append(Check(
        "Single hue", PASS if one_hue else FAIL,
        f"hue spread {spread:.0f}deg" + ("" if one_hue else " - >40deg, not a one-hue ramp")))

    return rep


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="hegevis-validate",
        description="Validate a categorical palette or ordinal ramp against the house checks.")
    p.add_argument("palette", nargs="?",
                   help="comma-separated hex list; omit to check the current theme")
    p.add_argument("--mode", choices=["light", "dark"], default="light")
    p.add_argument("--surface", default=None)
    p.add_argument("--pairs", choices=["adjacent", "all"], default="adjacent",
                   help="'all' for scatter/bubble/map/small-multiples")
    p.add_argument("--ordinal", action="store_true", help="check a one-hue ramp instead")
    args = p.parse_args(argv)

    if args.palette:
        colors = split_colors(args.palette)
    else:
        from .theme import get_theme
        theme = get_theme()
        if args.ordinal:
            # The full ramp intentionally reaches paler than the ordinal floor:
            # in a continuous heatmap "near zero" is allowed to recede toward
            # the surface. Check the steps the package would actually hand out
            # for discrete ordered marks, which is what --ordinal is about.
            from .palette import Palette
            colors = Palette(theme).ordinal(min(5, len(theme.sequential)))
            print("(checking the ordinal steps drawn from the theme ramp; the "
                  "full ramp reaches paler by design)", file=sys.stderr)
        else:
            colors = list(theme.series)
        if args.surface is None:
            # Contrast is only meaningful against the ground the chart actually
            # prints on -- not the built-in default.
            args.surface = theme.surface
        print(f"(checking the current theme: {theme.name}, surface {args.surface})",
              file=sys.stderr)
    if not colors:
        p.error("empty palette")

    try:
        rep = (validate_ordinal(colors, mode=args.mode, surface=args.surface)
               if args.ordinal
               else validate(colors, mode=args.mode, surface=args.surface, pairs=args.pairs))
    except BadColor as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(rep)
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
