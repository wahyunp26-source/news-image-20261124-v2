#!/usr/bin/env python3
"""Build-time asset generator for news-image-20261124 v2.

Renders Liberation glyph atlases with PIL and packs them (plus a hand-drawn
dotted world-map land grid) into assets_blob.py as zlib+base64 single lines.
Run ONCE here in the builder session; the entry itself (main.py) is pure
stdlib and only decodes the blob at runtime. Never re-emit the blob by hand.
"""
import base64
import io
import json
import zlib

from PIL import Image, ImageDraw, ImageFont

OUT = "/home/hatch/workspace/makefun/news-image-20261124-v2-entry/assets_blob.py"
LIB = "/usr/share/fonts/truetype/liberation/"

# (name, ttf file, pixel size)
FONTS = [
    ("serif_b72", "LiberationSerif-Bold.ttf", 72),
    ("serif_b58", "LiberationSerif-Bold.ttf", 58),
    ("serif_b26", "LiberationSerif-Bold.ttf", 26),
    ("serif_b24", "LiberationSerif-Bold.ttf", 24),
    ("serif_b22", "LiberationSerif-Bold.ttf", 22),
    ("serif_b19", "LiberationSerif-Bold.ttf", 19),
    ("serif_b16", "LiberationSerif-Bold.ttf", 16),
    ("serif_r13", "LiberationSerif-Regular.ttf", 13),
    ("serif_r11", "LiberationSerif-Regular.ttf", 11),
    ("serif_i15", "LiberationSerif-Italic.ttf", 15),
    ("sans_b13", "LiberationSans-Bold.ttf", 13),
    ("sans_b11", "LiberationSans-Bold.ttf", 11),
    ("sans_b10", "LiberationSans-Bold.ttf", 10),
    ("sans_b9", "LiberationSans-Bold.ttf", 9),
    ("sans_r10", "LiberationSans-Regular.ttf", 10),
    ("sans_r9", "LiberationSans-Regular.ttf", 9),
]

CHARS = [chr(c) for c in range(32, 127)]
CHARS += ["\u2013", "\u2014", "\u2018", "\u2019", "\u201c", "\u201d",
          "\u2022", "\u2026", "\u00d7", "\u2212", "\u00e9", "\u00a0", "\u00b7"]


def render_atlas(name, path, size):
    font = ImageFont.truetype(path, size)
    # measure every glyph first
    cells = {}
    for ch in CHARS:
        bbox = ImageDraw.Draw(Image.new("L", (8, 8))).textbbox((0, 0), ch, font=font)
        adv = font.getlength(ch)
        if ch == " ":
            cells[ch] = (0, 0, 0, 0, adv, 0, 0)
            continue
        l, t, r, b = bbox
        cells[ch] = (l, t, r - l, b - t, adv, l, t)
    # pack into rows: cell height = max glyph height + 2
    maxh = max(c[3] for c in cells.values()) + 2
    per_row_w = 1024
    x, y = 0, 0
    placements = {}
    for ch in CHARS:
        _l, _t, w, h, _a, _ox, _oy = cells[ch]
        if w == 0:
            continue
        if x + w + 2 > per_row_w:
            x = 0
            y += maxh
        placements[ch] = (x + 1, y + 1)
        x += w + 2
    total_h = y + maxh
    img = Image.new("L", (per_row_w, total_h), 0)
    dr = ImageDraw.Draw(img)
    metrics = {}
    for ch in CHARS:
        l, t, w, h, adv, ox, oy = cells[ch]
        if w == 0:
            metrics[ord(ch)] = [0, 0, 0, 0, round(adv, 2), 0, 0]
            continue
        px, py = placements[ch]
        dr.text((px - ox, py - oy), ch, font=font, fill=255)
        metrics[ord(ch)] = [px, py, w, h, round(adv, 2), ox, oy]
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), metrics, (per_row_w, total_h)


# Hand-drawn land grid: 96 cols (lon -180..180) x 48 rows (lat ~86..-58).
# Built from explicit continent segments below; '#' = land, '.' = sea.
# Authored from a world map by eye; pins + labels carry the meaning.
MAP_SEGS = {
    0: [],
    1: [(34, 40)],
    2: [(33, 41)],
    3: [(4, 8), (59, 95)],
    4: [(3, 12), (33, 41), (59, 95)],
    5: [(3, 16), (33, 41), (59, 95)],
    6: [(4, 22), (50, 55), (59, 94)],
    7: [(4, 26), (50, 55), (59, 94)],
    8: [(5, 28), (46, 47), (50, 55), (60, 94)],
    9: [(5, 29), (46, 47), (51, 55), (60, 93)],
    10: [(6, 30), (47, 57), (60, 92), (88, 89)],
    11: [(8, 31), (47, 58), (60, 91), (88, 90)],
    12: [(9, 31), (47, 58), (60, 90)],
    13: [(10, 31), (47, 58), (61, 89)],
    14: [(11, 31), (44, 60), (62, 88)],
    15: [(12, 30), (46, 49), (44, 60), (63, 86)],
    16: [(13, 28), (44, 60), (65, 85)],
    17: [(14, 24), (44, 60), (66, 84)],
    18: [(15, 23), (44, 59), (67, 78)],
    19: [(17, 24), (44, 59), (68, 77)],
    20: [(19, 25), (45, 59), (68, 76)],
    21: [(20, 25), (45, 59), (69, 76)],
    22: [(21, 25), (46, 58), (70, 76)],
    23: [(22, 25), (47, 58), (71, 77)],
    24: [(24, 26), (27, 36), (48, 58), (72, 78)],
    25: [(26, 36), (48, 57), (72, 80)],
    26: [(26, 37), (48, 57), (72, 82)],
    27: [(26, 37), (49, 57), (73, 81)],
    28: [(27, 37), (49, 57)],
    29: [(27, 36), (50, 56), (78, 88)],
    30: [(28, 36), (50, 56), (78, 88)],
    31: [(28, 35), (50, 55), (79, 88)],
    32: [(28, 35), (51, 55), (79, 88)],
    33: [(28, 34), (51, 55), (79, 87)],
    34: [(29, 34), (52, 55), (80, 87)],
    35: [(29, 33), (52, 54), (80, 86)],
    36: [(30, 33), (81, 86)],
    37: [(30, 33), (82, 85), (91, 92)],
    38: [(30, 32), (85, 85)],
    39: [(30, 32), (91, 92)],
    40: [(30, 32)],
    41: [(31, 32)],
    42: [(31, 32)],
    43: [(31, 32)],
    44: [(31, 32)],
    45: [(31, 32)],
    46: [],
    47: [],
}
MAP_ROWS = []
for _r in range(48):
    _row = ['.'] * 96
    for _a, _b in MAP_SEGS[_r]:
        for _c in range(_a, _b + 1):
            _row[_c] = '#'
    MAP_ROWS.append(''.join(_row))
def main():
    parts = []
    total_png = 0
    for name, fname, size in FONTS:
        png, metrics, (w, h) = render_atlas(name, LIB + fname, size)
        total_png += len(png)
        payload = json.dumps(
            {"w": w, "h": h, "m": metrics}, separators=(",", ":")
        ).encode() + b"\x00" + png
        comp = zlib.compress(payload, 9)
        b64 = base64.b64encode(comp).decode()
        parts.append((name, b64))
        print(f"{name}: atlas {w}x{h} png={len(png)}B b64={len(b64)}")
    lines = []
    lines.append("# Generated by gen_assets.py (build time, PIL). Do not edit by hand.")
    lines.append("# Each value is one line: base64(zlib(json-metrics + NUL + atlas-PNG)).")
    lines.append("BLOB = {")
    for name, b64 in parts:
        lines.append(f'    "{name}": "{b64}",')
    lines.append("}")
    lines.append("MAP_ROWS = [")
    for row in MAP_ROWS:
        lines.append(f'    "{row}",')
    lines.append("]")
    lines.append("")
    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print(f"wrote {OUT}: {len(lines)} lines, png total {total_png}B")


if __name__ == "__main__":
    main()
