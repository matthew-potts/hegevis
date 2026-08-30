"""Making the licensed house faces available to matplotlib.

The publication is set in **Tiempos Headline** and **Gill Sans**. Both are
commercially licensed, so they are NOT shipped inside the package: the wheel on
an index would be redistributing someone else's type. Instead they are dropped
into ``assets/fonts/`` on each machine that has a licence, and registered with
matplotlib's font manager at import.

That means the same code path works whether the faces are installed system-wide
(the design desk's machines) or sitting in the package directory (an analyst who
was handed the zip), and no analyst has to think about it either way.

If the faces are absent, charts fall back and :mod:`hegevis.rc` warns loudly --
a chart in the wrong face must never ship silently.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from matplotlib import font_manager

FONT_DIR = Path(__file__).parent / "assets" / "fonts"

# AppleDouble sidecars ride along in zips unpacked on a Mac. They are not fonts
# and matplotlib raises on them, so they never reach the font manager.
SUFFIXES = (".otf", ".ttf", ".ttc")


def font_files(directory: Path | None = None) -> list[Path]:
    d = directory or FONT_DIR
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir()
                  if p.suffix.lower() in SUFFIXES and not p.name.startswith("._"))


@lru_cache(maxsize=1)
def register(directory: str | None = None) -> tuple[str, ...]:
    """Add every font in the directory to matplotlib. Returns the families found.

    Cached: registering twice in one session is wasted work, and matplotlib
    keeps its own list, so a second pass would only duplicate entries.
    """
    found: set[str] = set()
    for path in font_files(Path(directory) if directory else None):
        try:
            font_manager.fontManager.addfont(str(path))
            found.add(font_manager.FontProperties(fname=str(path)).get_name())
        except Exception:
            # A corrupt or unreadable file is not worth stopping a chart run
            # for; the missing-face warning in rc.py is what surfaces it.
            continue
    return tuple(sorted(found))


def installed() -> set[str]:
    """Every family matplotlib can currently see, registered or system-wide."""
    return {f.name for f in font_manager.fontManager.ttflist}


def available(families) -> tuple[str | None, list[str]]:
    """First family from ``families`` that is actually present, and the misses."""
    have = installed()
    missing = []
    for fam in families:
        if fam in have:
            return fam, missing
        missing.append(fam)
    return None, missing
