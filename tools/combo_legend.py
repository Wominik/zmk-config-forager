#!/usr/bin/env python3
"""Append a legend of all combos to a keymap-drawer SVG.

keymap-drawer draws each combo as a small box with an icon, which is compact
but hard to decipher. This adds a table under the drawing: the same box (same
icon, same colour), the keys to press, and a description.

    python3 tools/combo_legend.py keymap-drawer/overview.svg [more.svg ...]

Where things come from:
  - the boxes and icons: the SVG itself (combos are drawn in keymap order)
  - which keys: key-positions in config/forager-combos.dtsi, named after the
    tap legends of the BASE layer in the SVG
  - descriptions: keymap-drawer/combo-legend.yaml, one "combo_name: text" per
    line - a combo that has no line there fails the run, so a new combo
    cannot silently go undocumented

Needs only the Python standard library. Run by .github/workflows/draw-keymaps.yml
after the SVGs are drawn; running it again on the same file replaces the legend.
"""

import html
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS_DTSI = ROOT / "config" / "forager-keys.dtsi"
COMBOS_DTSI = ROOT / "config" / "forager-combos.dtsi"
DESCRIPTIONS = ROOT / "keymap-drawer" / "combo-legend.yaml"

COLUMNS = 3
MARGIN = 30  # keymap-drawer's outer padding
ROW_H = 28
TITLE_H = 34
KEYS_DX = 34  # from the left edge of the box to the key names
DESC_DX = 100  # ... and to the description
BEGIN, END = "<!-- combo-legend -->", "<!-- /combo-legend -->"
# CSS class of a combo box (its zmk_combos "type") -> what its colour means
LAYER_COLOURS = [("nav", "green: only while NAV is held"), ("num", "orange: only while NUM is held")]


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def read_defines() -> dict[str, int]:
    return {m[1]: int(m[2]) for m in re.finditer(r"^#define\s+(\w+)\s+(\d+)\b", KEYS_DTSI.read_text(), re.M)}


def read_combos() -> list[dict]:
    """Combos in keymap order: name, key positions, layer names (empty = all)."""
    defines = read_defines()
    combos = []
    for name, body in re.findall(r"\b(combo_\w+)\s*\{(.*?)\};", strip_comments(COMBOS_DTSI.read_text()), re.S):
        positions = re.search(r"key-positions\s*=\s*<([^>]*)>", body)
        layers = re.search(r"layers\s*=\s*<([^>]*)>", body)
        combos.append(
            {
                "name": name,
                "positions": [defines[t] if t in defines else int(t) for t in positions[1].split()],
                "layers": layers[1].split() if layers else [],
            }
        )
    return combos


def read_descriptions() -> dict[str, str]:
    out = {}
    for line in DESCRIPTIONS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, text = line.partition(":")
        text = text.strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
            text = text[1:-1]
        out[name.strip()] = text
    return out


def base_key_names(svg: str) -> dict[int, str]:
    start = svg.index('class="layer-BASE"')
    end = svg.find('class="layer-', start + 1)
    names = {}
    for pos, inner in re.findall(r'class="key keypos-(\d+)">(.*?)</g>', svg[start : end if end > 0 else None], re.S):
        tap = re.search(r'<text[^>]*class="key tap"[^>]*>([^<]*)</text>', inner)
        names[int(pos)] = html.unescape(tap[1]) if tap else "?"
    return names


def drawn_combos(svg: str) -> list[dict]:
    """Box and label markup of every combo, in drawing (= keymap) order."""
    out = []
    section = svg[svg.index('class="layer-Combos"') :]
    for cls, index, inner in re.findall(r'<g class="(combo[^"]*?)\s*combopos-(\d+)">(.*?)</g>', section, re.S):
        rect = re.search(r'<rect [^>]*x="([\d.-]+)" y="([\d.-]+)" width="([\d.]+)" height="([\d.]+)"[^>]*/>', inner)
        labels = re.sub(r"<path [^>]*/>", "", inner).replace(rect[0], "").strip()
        out.append(
            {
                "index": int(index),
                "class": cls.strip(),
                "rect": rect[0],
                "x": float(rect[1]),
                "y": float(rect[2]),
                "w": float(rect[3]),
                "h": float(rect[4]),
                "labels": labels,
            }
        )
    return sorted(out, key=lambda c: c["index"])


def add_legend(path: Path) -> None:
    svg = path.read_text()

    # start from the drawing as keymap-drawer made it
    old = re.search(re.escape(BEGIN) + r'<g data-added="(\d+)".*?' + re.escape(END), svg, re.S)
    head = re.search(r'<svg width="(\d+)" height="(\d+)" viewBox="0 0 (\d+) (\d+)"', svg)
    width, height = int(head[1]), int(head[2])
    if old:
        svg = svg.replace(old[0], "")
        height -= int(old[1])

    combos, drawn, texts, keys = read_combos(), drawn_combos(svg), read_descriptions(), base_key_names(svg)
    if len(combos) != len(drawn):
        sys.exit(f"{path}: {len(drawn)} combos drawn but {len(combos)} in {COMBOS_DTSI.name}")
    missing = [c["name"] for c in combos if c["name"] not in texts]
    if missing:
        sys.exit(f"{DESCRIPTIONS.name} has no description for: {', '.join(missing)}")

    rows = math.ceil(len(combos) / COLUMNS)
    col_w = (width - 2 * MARGIN) / COLUMNS
    top = height - MARGIN / 2
    added = int(TITLE_H + rows * ROW_H)
    start = 'style="text-anchor: start;'

    out = [f'{BEGIN}<g data-added="{added}" class="combo-legend">']
    out.append(f'<text x="{MARGIN}" y="{top + 10:.0f}" {start} font-weight: 700;">Combos</text>')
    # colour key for combos that only exist on one layer (zmk_combos "type")
    notes = [text for cls, text in LAYER_COLOURS if any(cls in d["class"].split() for d in drawn)]
    if notes:
        out.append(
            f'<text x="{MARGIN + 66}" y="{top + 10:.0f}" {start} font-size: 12px;">'
            f"{html.escape(', '.join(notes))}</text>"
        )
    for i, (combo, box) in enumerate(zip(combos, drawn)):
        x = MARGIN + (i // rows) * col_w
        y = top + TITLE_H + (i % rows) * ROW_H
        mid = y + box["h"] / 2
        pressed = " + ".join(keys.get(p, "?") for p in combo["positions"])
        text = texts[combo["name"]]
        if combo["layers"] and "BASE" not in combo["layers"]:
            text += f" ({', '.join(combo['layers'])})"
        out.append(
            f'<g transform="translate({x - box["x"]:.1f}, {y - box["y"]:.1f})" class="{box["class"]}">'
            f'{box["rect"]}{box["labels"]}</g>'
        )
        out.append(
            f'<text x="{x + KEYS_DX:.1f}" y="{mid:.1f}" {start} font-size: 12px; font-weight: 700;">'
            f"{html.escape(pressed)}</text>"
        )
        out.append(
            f'<text x="{x + DESC_DX:.1f}" y="{mid:.1f}" {start} font-size: 12px;">{html.escape(text)}</text>'
        )
    out.append(f"</g>{END}")

    new_height = height + added
    svg = svg.replace(head[0], f'<svg width="{width}" height="{new_height}" viewBox="0 0 {width} {new_height}"', 1)
    # an optional footer stays at the very bottom
    svg = re.sub(
        r'(<text x="[^"]*" y=")([\d.]+)(" class="footer")',
        lambda m: f"{m[1]}{float(m[2]) + (0 if old else added)}{m[3]}",
        svg,
    )
    cut = svg.rindex("</svg>")
    path.write_text(svg[:cut] + "\n".join(out) + "\n" + svg[cut:])
    print(f"{path}: legend with {len(combos)} combos")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for arg in sys.argv[1:]:
        add_legend(Path(arg))
