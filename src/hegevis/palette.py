"""Assigning colour by the job it does.

Four jobs, four rules:

* **categorical** - identity (which country, which bloc). Fixed slot order,
  assigned in sequence, never cycled.
* **sequential** - magnitude. One hue, light to dark.
* **diverging** - polarity (surplus/deficit, above/below trend). Two opposite
  hues around a neutral grey midpoint.
* **status** - reserved meanings, never borrowed for "series 5".

The one rule worth internalising: **colour follows the entity, not its rank.**
A reader who learned "China is orange" in one chart must not find China blue in
the next because it moved up the ranking, or because a filter dropped a series
above it. :class:`Palette` keeps a registry so that cannot happen.
"""

from __future__ import annotations

import warnings
from itertools import permutations

from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm

from .color import CVD_TARGET, NORMAL_FLOOR, contrast, delta_e, oklch
from .theme import Theme, get_theme

MAX_SERIES = 8
MAX_ARRANGEMENTS = 40_320  # 8!, the most we will brute-force before going greedy
SOFT_CAP = 6  # past this, a legend alone stops carrying identity
ORDINAL_LIGHT_FLOOR = 2.0


class TooManySeries(ValueError):
    """More series than the palette has slots.

    Never solved by generating another hue -- a ninth colour is
    indistinguishable from an existing one under colour-vision deficiency.
    Fold the tail into "Other", facet into small multiples, or use emphasis.
    """


class Palette:
    """Colour assignment for one theme, with a stable entity registry."""

    def __init__(self, theme: Theme | None = None):
        self.theme = theme or get_theme()
        if not self.theme.series:
            raise ValueError("theme defines no categorical series colours")
        # name -> slot index. Seeded from the theme's [entities] table so the
        # recurring actors are pinned across every article in the publication.
        self._assigned: dict[str, int] = dict(self.theme.entities)
        self._validate_pins()

    def _validate_pins(self) -> None:
        n = len(self.theme.series)
        bad = {k: v for k, v in self._assigned.items() if not 0 <= v < n}
        if bad:
            raise ValueError(
                f"[entities] pins a slot outside 0-{n - 1}: {bad}. "
                "Slots are 0-indexed into color.series."
            )

    # -- categorical ---------------------------------------------------------
    def slot(self, i: int) -> str:
        """The i-th categorical colour (0-indexed), never wrapping."""
        if not 0 <= i < len(self.theme.series):
            raise TooManySeries(
                f"slot {i} does not exist - the palette has {len(self.theme.series)}. "
                "Fold the tail into 'Other', facet, or use emphasis()."
            )
        return self.theme.series[i]

    def pin(self, name: str, slot: int) -> None:
        """Pin an entity to a slot for this session (theme file is permanent)."""
        self._assigned[name] = slot
        self._validate_pins()

    # -- adjacency safety ----------------------------------------------------
    def _pair_table(self):
        """Cached pairwise separation between slots, so arranging is table lookups.

        The palette's fixed order is validated for *adjacent* pairs. Pinning an
        entity to a slot permutes that order, which can put two slots side by
        side that were never checked together -- so the pairs actually used
        have to be scored per chart, not assumed.
        """
        if getattr(self, "_pairs_cache", None) is None:
            cols = self.theme.series
            n = len(cols)
            cvd = [[0.0] * n for _ in range(n)]
            nor = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    d = min(delta_e(cols[i], cols[j], "protan"),
                            delta_e(cols[i], cols[j], "deutan"))
                    e = delta_e(cols[i], cols[j])
                    cvd[i][j] = cvd[j][i] = d
                    nor[i][j] = nor[j][i] = e
            self._pairs_cache = (cvd, nor)
        return self._pairs_cache

    def _adjacency_score(self, slots) -> float:
        """Worst adjacent pair in this arrangement, as a fraction of the gates.

        1.0 means every neighbouring pair clears both the CVD target and the
        normal-vision floor; below 1.0 something is tighter than the standard.
        """
        cvd, nor = self._pair_table()
        if len(slots) < 2:
            return 1.0
        return min(
            min(cvd[a][b] / CVD_TARGET, nor[a][b] / NORMAL_FLOOR)
            for a, b in zip(slots, slots[1:])
        )

    def _arrange(self, fixed: dict[int, int], n_names: int, free: list[int]) -> list[int]:
        """Choose slots for the unfixed positions, best adjacency first.

        Ties break toward the lowest slot numbers, so a chart with nothing
        pinned still comes out in the palette's canonical order.
        """
        open_positions = [i for i in range(n_names) if i not in fixed]
        if not open_positions:
            return [fixed[i] for i in range(n_names)]

        k = len(open_positions)
        n_perms = 1
        for i in range(k):
            n_perms *= len(free) - i
        candidates = (permutations(free, k) if n_perms <= MAX_ARRANGEMENTS
                      else [tuple(free[:k])])

        best, best_key = None, None
        for combo in candidates:
            slots = [fixed.get(i) for i in range(n_names)]
            for pos, slot in zip(open_positions, combo):
                slots[pos] = slot
            # Clamped at 1.0: clearing the gates is the goal, not maximising
            # separation. Chasing extra distance would quietly abandon the
            # house order -- slot 1 must stay the house's first colour.
            clamped = min(self._adjacency_score(slots), 1.0)
            key = (round(clamped, 6), tuple(-x for x in slots))
            if best_key is None or key > best_key:
                best, best_key = slots, key
        return best

    def for_series(self, names) -> dict[str, str]:
        """Map series names to colours, stably.

        Slots are remembered across charts, so an entity that appears in three
        figures of the same article keeps one colour throughout, and dropping a
        series never repaints the survivors.

        Remembered slots are honoured per chart rather than reserved globally:
        two unrelated charts in one script both get to start at slot 1, and
        only a genuine clash *within a single chart* pushes a series to the
        next free slot. Anything pinned in the theme's ``[entities]`` table
        always wins the clash, which is what makes the recurring actors --
        China, the US, the EU -- fixed across the whole publication.
        """
        names = list(names)
        if len(names) > MAX_SERIES:
            raise TooManySeries(
                f"{len(names)} series, but the palette has {MAX_SERIES} slots. "
                "A generated 9th hue is indistinguishable under CVD. "
                "Use fold_other(), facet into small multiples, or emphasis()."
            )
        if len(names) > SOFT_CAP:
            warnings.warn(
                f"{len(names)} series is past the soft cap of {SOFT_CAP} - consider "
                "small multiples or folding the tail into 'Other'.",
                stacklevel=2,
            )

        n_slots = len(self.theme.series)
        fixed: dict[int, int] = {}
        taken: set[int] = set()

        # Pinned entities claim their slot first -- they outrank everything.
        for i, name in enumerate(names):
            if name in self.theme.entities:
                slot = self.theme.entities[name]
                fixed[i] = slot
                taken.add(slot)

        # Then anything this session has already coloured, if still free here.
        for i, name in enumerate(names):
            if i in fixed:
                continue
            slot = self._assigned.get(name)
            if slot is not None and slot not in taken:
                fixed[i] = slot
                taken.add(slot)

        free = [i for i in range(n_slots) if i not in taken]
        if len(free) < len(names) - len(fixed):
            raise TooManySeries(
                f"{len(names)} series need distinct colours but only {n_slots} "
                "slots exist. Fold the tail into 'Other' or facet."
            )

        slots = self._arrange(fixed, len(names), free)
        resolved = {name: slot for name, slot in zip(names, slots)}

        for name, slot in resolved.items():
            # Remember it, but never overwrite an earlier remembered slot: the
            # first colour an entity wore is the one readers learned.
            self._assigned.setdefault(name, slot)

        # Even the best arrangement can be forced into a tight pair by pinning.
        # Say so rather than shipping two series a reader cannot separate.
        score = self._adjacency_score(slots)
        if score < 1.0:
            cvd, nor = self._pair_table()
            worst = min(zip(slots, slots[1:]),
                        key=lambda ab: min(cvd[ab[0]][ab[1]] / CVD_TARGET,
                                           nor[ab[0]][ab[1]] / NORMAL_FLOOR))
            a, b = worst
            warnings.warn(
                f"colours for {names!r} put {self.theme.series[a]} next to "
                f"{self.theme.series[b]} (CVD dE {cvd[a][b]:.1f}, normal dE "
                f"{nor[a][b]:.1f}). Pinned entities have forced a tight pair - "
                "reorder the series, drop one, or re-pin in the theme.",
                stacklevel=2,
            )

        return {name: self.theme.series[resolved[name]] for name in names}

    def emphasis(self, names, focus) -> dict[str, str]:
        """One series in colour, the rest in the de-emphasis grey.

        The most underused form in the method, and usually the honest answer
        when the story is "this one moved" rather than "here are eight series".
        """
        names = list(names)
        focus = [focus] if isinstance(focus, str) else list(focus)
        missing = [f for f in focus if f not in names]
        if missing:
            raise ValueError(f"focus series not present in names: {missing}")
        lead = self.for_series(focus)
        return {n: lead[n] if n in lead else self.theme.neutral for n in names}

    # -- sequential ----------------------------------------------------------
    @property
    def ramp(self) -> tuple[str, ...]:
        if not self.theme.sequential:
            raise ValueError("theme defines no sequential ramp")
        return self.theme.sequential

    def sequential_cmap(self, name: str = "hegevis_seq") -> LinearSegmentedColormap:
        """Continuous one-hue colormap for magnitude (heatmaps, shading)."""
        return LinearSegmentedColormap.from_list(name, list(self.ramp))

    def ordinal(self, n: int) -> list[str]:
        """``n`` discrete steps for an ORDERED category (tiers, buckets, bands).

        Drops steps too pale to read as a mark on the surface, then samples
        evenly across what is left, so the ramp still reads as a ramp.
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        usable = [c for c in self.ramp if contrast(c, self.theme.surface) >= ORDINAL_LIGHT_FLOOR]
        if not usable:
            raise ValueError("no step in the sequential ramp clears the light-end floor")
        if n > len(usable):
            warnings.warn(
                f"{n} ordinal steps requested but only {len(usable)} in the ramp clear "
                f"the {ORDINAL_LIGHT_FLOOR}:1 light-end floor - steps will repeat. "
                "Use fewer bins.",
                stacklevel=2,
            )
            return [usable[min(int(i * len(usable) / n), len(usable) - 1)] for i in range(n)]
        if n == 1:
            return [usable[len(usable) // 2]]
        step = (len(usable) - 1) / (n - 1)
        return [usable[round(i * step)] for i in range(n)]

    # -- diverging -----------------------------------------------------------
    def diverging_cmap(self, name: str = "hegevis_div") -> LinearSegmentedColormap:
        d = self.theme.diverging
        missing = {"low", "mid", "high"} - set(d)
        if missing:
            raise ValueError(f"theme.diverging is missing {sorted(missing)}")
        return LinearSegmentedColormap.from_list(name, [d["low"], d["mid"], d["high"]])

    def diverging_norm(self, vmin: float, vmax: float, center: float = 0.0):
        """Normalise so ``center`` lands on the neutral midpoint.

        Falls back to a plain :class:`Normalize` when the data sits entirely on
        one side of the centre, which ``TwoSlopeNorm`` rejects.
        """
        if vmin < center < vmax:
            return TwoSlopeNorm(vcenter=center, vmin=vmin, vmax=vmax)
        return Normalize(vmin=min(vmin, center), vmax=max(vmax, center))

    def diverging_colors(self, values, center: float = 0.0) -> list[str]:
        """Per-value colours for a diverging bar chart."""
        vals = list(values)
        if not vals:
            return []
        cmap = self.diverging_cmap()
        norm = self.diverging_norm(min(vals), max(vals), center)
        from matplotlib.colors import to_hex
        return [to_hex(cmap(norm(v))) for v in vals]

    # -- status --------------------------------------------------------------
    def status(self, role: str) -> str:
        try:
            return self.theme.status[role]
        except KeyError:
            raise ValueError(
                f"unknown status role {role!r} - have {sorted(self.theme.status)}"
            ) from None

    # -- ink -----------------------------------------------------------------
    def label_ink(self, background: str) -> str:
        """Ink or white for a label set INSIDE a coloured fill, by luminance.

        The one place text may sit on a series colour -- and only when the
        contrast is picked, not assumed.
        """
        return self.theme.ink if contrast(self.theme.ink, background) >= contrast(
            "#ffffff", background) else "#ffffff"

    def needs_relief(self) -> list[str]:
        """Slots below 3:1 on the surface, which oblige visible direct labels."""
        return [c for c in self.theme.series if contrast(c, self.theme.surface) < 3.0]


def fold_other(pairs, keep: int = SOFT_CAP, other: str = "Other"):
    """Keep the ``keep`` largest entries, sum the tail into a single row.

    The sanctioned answer to "too many series" -- never a ninth hue.
    Accepts and returns ``[(name, value), ...]`` in descending order.
    """
    items = sorted(pairs, key=lambda kv: kv[1], reverse=True)
    if len(items) <= keep:
        return items
    head, tail = items[:keep], items[keep:]
    return [*head, (other, sum(v for _, v in tail))]


# -- the session palette -------------------------------------------------------
# Entity stability only means something if every chart in a script shares one
# registry -- otherwise each figure starts assigning slots from scratch and the
# second chart repaints what the first one established.
_default: Palette | None = None


def default_palette(theme: Theme | None = None) -> Palette:
    """The shared palette for this session, created on first use."""
    global _default
    if _default is None or (theme is not None and _default.theme is not theme):
        _default = Palette(theme)
    return _default


def reset_palette() -> None:
    """Forget every session assignment. Called when the theme is reloaded."""
    global _default
    _default = None
