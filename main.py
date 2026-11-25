#!/usr/bin/env python3
"""Tuesday 24 November 2026 in one picture — news-image-20261124 v2.

Pure Python stdlib. Draws a 1024x1024 newspaper front page (35 stories, all
reported or still developing on Tuesday 24 November 2026) from vector shapes
and glyph atlases embedded in assets_blob.py. Writes exactly one file:
$MAKEFUN_OUTPUT_DIR/entry.png. No network, no time, no randomness: two runs
produce byte-identical output.
"""
import base64
import json
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets_blob

W, H = 1024, 1024

# ---------------------------------------------------------------- PNG codec
def _unfilter(raw, w, h, bpp):
    stride = w * bpp
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out += line
        prev = line
    return out


def decode_png(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    idat = b""
    w = h = None
    bitdepth = ctype = None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bitdepth, ctype = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + ln
    assert bitdepth == 8 and ctype in (0, 2, 6)
    bpp = {0: 1, 2: 3, 6: 4}[ctype]
    raw = _unfilter(zlib.decompress(idat), w, h, bpp)
    return w, h, bpp, raw


def _crc(typ, data):
    return struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def _chunk(typ, data):
    return struct.pack(">I", len(data)) + typ + data + _crc(typ, data)


def encode_png(rgb, w, h):
    # per-row filter pick (0/1/2) by smallest absolute residual sum: deterministic
    rows = []
    prev = bytes(w * 3)
    for y in range(h):
        row = bytes(rgb[y * w * 3:(y + 1) * w * 3])
        best = None
        for f in (0, 1, 2):
            if f == 0:
                fil = row
            elif f == 1:
                fil = bytes([row[i] if i < 3 else (row[i] - row[i - 3]) & 255
                             for i in range(len(row))])
            else:
                fil = bytes([(row[i] - prev[i]) & 255 for i in range(len(row))])
            score = sum(v if v < 128 else 256 - v for v in fil)
            if best is None or score < best[0]:
                best = (score, f, fil)
        rows.append(bytes([best[1]]) + best[2])
        prev = row
    comp = zlib.compress(b"".join(rows), 9)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", comp) + _chunk(b"IEND", b""))


# ------------------------------------------------------------------ canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg * (w * h))

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i:i + 3] = col

    def blend(self, x, y, col, a):
        """Alpha-blend one pixel; a in 0..255."""
        if 0 <= x < self.w and 0 <= y < self.h and a > 0:
            i = self._idx(x, y)
            if a >= 255:
                self.px[i:i + 3] = col
            else:
                for k in range(3):
                    self.px[i + k] = (col[k] * a + self.px[i + k] * (255 - a)) // 255

    def rect(self, x, y, w, h, col):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(col) * (x1 - x0)
        for yy in range(y0, y1):
            i = self._idx(x0, yy)
            self.px[i:i + len(row)] = row

    def hline(self, x, y, w, col):
        self.rect(x, y, w, 1, col)

    def vline(self, x, y, h, col):
        self.rect(x, y, 1, h, col)

    def vgrad(self, x, y, w, h, stops):
        """Vertical gradient; stops = [(pos0..1, (r,g,b)), ...] sorted."""
        if h <= 0:
            return
        for yy in range(h):
            t = yy / max(1, h - 1)
            col = _grad_at(stops, t)
            self.rect(x, y + yy, w, 1, col)

    def hgrad(self, x, y, w, h, stops):
        if w <= 0:
            return
        for xx in range(w):
            t = xx / max(1, w - 1)
            self.rect(x + xx, y, 1, h, _grad_at(stops, t))

    def circle(self, cx, cy, r, col, alpha=255):
        r2 = r * r
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            dx = int((r2 - dy * dy) ** 0.5) if r2 - dy * dy >= 0 else -1
            if dx < 0:
                continue
            if alpha >= 255:
                self.rect(cx - dx, yy, dx * 2 + 1, 1, col)
            else:
                for xx in range(cx - dx, cx + dx + 1):
                    self.blend(xx, yy, col, alpha)

    def ring(self, cx, cy, r, col, thick=2):
        for t in range(thick):
            rr = r - t
            for ang in range(0, 360, 2):
                import math
                x = cx + int(rr * math.cos(ang * math.pi / 180))
                y = cy + int(rr * math.sin(ang * math.pi / 180))
                self.set(x, y, col)

    def disc_glow(self, cx, cy, r, col, steps=5):
        for s in range(steps, 0, -1):
            rr = r * s // steps
            self.circle(cx, cy, rr, col, alpha=28)

    def poly(self, pts, col):
        """Scanline fill of a simple polygon."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for yy in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % n]
                if y1 == y2:
                    continue
                if (y1 <= yy < y2) or (y2 <= yy < y1):
                    xs.append(x1 + (yy - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(int(xs[k]), yy, max(1, int(xs[k + 1]) - int(xs[k])), 1, col)

    def line(self, x1, y1, x2, y2, col, wd=1):
        dx, dy = x2 - x1, y2 - y1
        n = max(abs(dx), abs(dy), 1)
        for i in range(n + 1):
            x = x1 + dx * i // n
            y = y1 + dy * i // n
            if wd <= 1:
                self.set(x, y, col)
            else:
                self.circle(x, y, wd // 2, col)

    def rrect(self, x, y, w, h, r, col):
        self.rect(x + r, y, w - 2 * r, h, col)
        self.rect(x, y + r, w, h - 2 * r, col)
        for cx, cy in ((x + r, y + r), (x + w - r - 1, y + r),
                       (x + r, y + h - r - 1), (x + w - r - 1, y + h - r - 1)):
            self.circle(cx, cy, r, col)


def _grad_at(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            t0, c0 = stops[i - 1]
            t1, c1 = stops[i]
            f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
    return stops[-1][1]


# ------------------------------------------------------------------- fonts
class Font:
    def __init__(self, name):
        raw = zlib.decompress(base64.b64decode(assets_blob.BLOB[name]))
        meta_b, png_b = raw.split(b"\x00", 1)
        meta = json.loads(meta_b.decode())
        self.aw, self.ah = meta["w"], meta["h"]
        self.m = {int(k): v for k, v in meta["m"].items()}
        w, h, bpp, px = decode_png(png_b)
        assert bpp == 1 and w == self.aw and h == self.ah
        self.px = px
        self.stride = w

    def width(self, text):
        return sum(self.m.get(ord(ch), [0, 0, 0, 0, 0, 0, 0])[4] for ch in text)

    def draw(self, cv, x, y, text, col):
        """Draw text with top-left at (x, y); returns width drawn."""
        cx = x
        for ch in text:
            m = self.m.get(ord(ch))
            if m is None:
                m = self.m[63]  # '?'
            gx, gy, gw, gh, adv = m[0], m[1], m[2], m[3], m[4]
            ox, oy = m[5], m[6]
            if gw and gh:
                for yy in range(gh):
                    sy = gy + yy
                    dy = y + yy + oy
                    if dy < 0 or dy >= cv.h:
                        continue
                    for xx in range(gw):
                        a = self.px[sy * self.stride + gx + xx]
                        if a:
                            cv.blend(int(cx) + xx + ox, dy, col, a)
            cx += adv
        return int(cx - x)

    def draw_center(self, cv, cx, y, text, col):
        return self.draw(cv, int(cx - self.width(text) / 2), y, text, col)

    def wrap(self, text, maxw):
        words = text.split(" ")
        lines, cur = [], ""
        for wd in words:
            trial = (cur + " " + wd).strip()
            if self.width(trial) <= maxw or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        return lines


_FONTS = {}


def F(name):
    if name not in _FONTS:
        _FONTS[name] = Font(name)
    return _FONTS[name]

# ----------------------------------------------------------------- palette
CREAM = (244, 238, 222)
PAPER = (250, 246, 235)
INK = (26, 26, 32)
NAVY = (31, 42, 68)
NAVY2 = (24, 33, 54)
RED = (166, 32, 32)
RED2 = (196, 52, 40)
GOLD = (198, 142, 44)
SAGE = (104, 128, 96)
TEAL = (42, 96, 96)
ORANGE = (214, 110, 44)
DARK = (20, 20, 26)
GREY = (110, 104, 92)
RULE = (180, 170, 150)

REGIONS = [
    ("EUROPE", 8, (38, 74, 138)),
    ("MIDDLE EAST", 10, (166, 32, 32)),
    ("AMERICAS", 6, (74, 110, 74)),
    ("ASIA-PACIFIC", 4, (176, 124, 32)),
    ("AFRICA", 3, (120, 84, 48)),
    ("WORLD", 4, (96, 74, 140)),
]

# ---------------------------------------------------------------- stories
# n, place, topic, headline, deck, source, lat, lon, scene, pin dx, pin dy
HEROES = [
    (1, "SANTA CLARA, US", "MARKETS",
     "Nvidia slides 7% as its record rally fades",
     "A day after Huang's return lifted shares 31% in their best day since "
     "2003, the stock slides back.",
     37.35, -121.95, "nvidia", 0, 0),
    (2, "BENGHAZI, LIBYA", "WAR",
     "Ukraine's sea drones sink a Russian warship off Libya",
     "Seven naval drones hit the corvette Merkury at Benghazi; Tripoli "
     "demands answers from Kyiv.",
     32.10, 20.07, "libya", 0, 0),
    (3, "HORMUZ STRAIT", "IRAN WAR",
     "Iran says tankers hit mines as its defiance hardens",
     "Three tankers catch fire in the strait as Tehran rules out talks until "
     "the US meets its seven conditions.",
     26.60, 56.25, "hormuz", 0, 0),
]

MIDS = [
    (4, "BROOKLYN, US", "JUSTICE",
     "Huawei guilty of stealing trade secrets",
     "A Brooklyn jury convicts Huawei of trade-secret conspiracy and bank "
     "fraud.",
     40.65, -73.95, "huawei", 0, 0),
    (5, "RIYADH, SAUDI ARABIA", "WAR",
     "Houthis hit Riyadh's tallest tower again",
     "A strike on the PIF Tower injures 11, the second hit in five days.",
     24.70, 46.70, "riyadh", 0, 0),
    (6, "WARSAW, POLAND", "SECURITY",
     "Poland says Russian drone crossed on purpose",
     "Warsaw calls the incursion deliberate, days after three missiles "
     "landed.",
     52.25, 21.05, "poland", 0, 0),
    (7, "OREGON & VIRGINIA, US", "TECH",
     "Two states sue Musk firms over Grok sex images",
     "The states accuse SpaceX and X over Grok's non-consensual sexual "
     "images.",
     37.54, -77.44, "grok", 0, 0),
    (8, "KHAN YOUNIS, GAZA", "WAR",
     "Three killed in Gaza drone strike",
     "An Israeli drone strike kills three in Khan Younis as a meningitis "
     "warning spreads.",
     31.35, 34.30, "gaza", 0, 0),
    (9, "JAKARTA, INDONESIA", "DISASTER",
     "Factory fire kills 24 in Indonesia",
     "Rescuers search unstable wreckage for 30 missing after a blaze sweeps "
     "a factory.",
     -6.20, 106.80, "factory", 0, 0),
    (10, "KOSHI, NEPAL", "QUAKE",
     "Quake shakes Nepal near China border",
     "A 5.4-magnitude tremor is felt in India and Bhutan; no deaths "
     "reported yet.",
     27.00, 87.00, "quake", 0, 0),
    (11, "PARIS, FRANCE", "BUSINESS",
     "Sanofi agrees to buy Insmed for $41bn",
     "The French drugmaker seals its biggest deal in years with the US "
     "biotech.",
     48.85, 2.35, "sanofi", 0, 0),
    (12, "MEXICO CITY, MEXICO", "CRIME",
     "Mexico will try 'El Chapo Isidro' itself",
     "Mexico will prosecute the captured cartel boss despite a US request.",
     19.40, -99.10, "mexico", 0, 0),
    (13, "ODESA, UKRAINE", "WAR",
     "Odesa's schools go online as power fails",
     "Russian strikes leave the port city without power, heat or water for "
     "a third day.",
     46.50, 30.70, "odesa", 0, 0),
]

# n, place, brief (one line), lat, lon
BRIEFS = [
    (14, "TRIPOLI, LIBYA", "Tripoli demands answers from Kyiv over the Benghazi strike. (Reuters)", 32.90, 13.20),
    (15, "THE HAGUE", "Fourteen nations back the ICJ Rohingya ruling; UK sanctions Myanmar officers. (Reuters)", 52.08, 4.30),
    (16, "TEHRAN, IRAN", "Ghalibaf: no talks with the US until seven conditions are met. (Reuters)", 35.70, 51.40),
    (17, "KYIV, UKRAINE", "Ukraine hits Russian oil plants; Putin vows retaliation. (Reuters)", 50.45, 30.50),
    (18, "ZAPORIZHZHIA, UKRAINE", "Russian strike kills two and wounds dozens overnight. (Reuters)", 47.85, 35.10),
    (19, "SANAA, YEMEN", "Strikes on buses and trucks kill about 26 people. (AP)", 15.35, 44.20),
    (20, "ADEN, YEMEN", "Houthi fighters close to within 60 km of Aden. (Reuters)", 12.80, 45.00),
    (21, "TALLINN, ESTONIA", "Russia warns Estonia of war over its border closure. (Reuters)", 59.40, 24.75),
    (22, "VILLAVICENCIO, COLOMBIA", "Car bomb strikes the governor's office in Villavicencio. (Reuters)", 4.15, -73.60),
    (23, "RAS AL KHAIMAH, UAE", "Bus-truck crash kills 11 people on a highway. (AP)", 25.80, 55.95),
    (24, "SINGAPORE", "US moves to blacklist AI firm Megaspeed over chip diversion. (Reuters)", 1.35, 103.80),
    (25, "BEIJING, CHINA", "China sentences a former official to death for espionage. (Reuters)", 39.90, 116.40),
    (26, "SPACE", "NATO vows space defence over Russian nuclear satellite reports. (Reuters)", 51.50, -0.12),
    (27, "NEW YORK, US", "Guterres urges global safeguards on AI. (UN News)", 40.75, -74.00),
    (28, "ADDIS ABABA, ETHIOPIA", "Amnesty seeks a probe into possible Tigray war crimes. (AP)", 9.00, 38.75),
    (29, "AFRICA", "African Union launches a maternal health roadmap. (AP)", 9.05, 38.85),
    (30, "BAGHDAD, IRAQ", "Iraqi forces seize two drone launch platforms in the south. (Reuters)", 33.30, 44.40),
    (31, "JERUSALEM", "Palestinian women detainees allege threats in Israeli prison. (Reuters)", 31.77, 35.20),
    (32, "GAZA", "Israeli strikes kill seven in Gaza as meningitis spreads. (Al Jazeera)", 31.50, 34.45),
    (33, "FLORIDA, US", "Trump prepares to meet NATO chief Rutte in Florida. (Reuters)", 26.70, -80.05),
    (34, "ANTALYA, TURKEY", "COP31 post-mortems spread blame for the 'worst COP ever'. (Reuters)", 36.90, 30.70),
    (35, "WARSAW, POLAND", "NATO sends an AWACS plane to Poland after the missile landings. (Reuters)", 52.10, 20.90),
]

STATS = [
    ("-7%", "NVIDIA SHARES TUESDAY"),
    ("$41BN", "SANOFI-INSMED DEAL"),
    ("3", "TANKERS HIT IN HORMUZ"),
    ("11", "HURT IN RIYADH STRIKE"),
    ("24", "DEAD IN INDONESIA FIRE"),
    ("5.4", "QUAKE IN NEPAL"),
]

SUBHEAD = ("Nvidia slides after its record rally \u00b7 Huawei guilty in Brooklyn "
           "\u00b7 Houthis strike Riyadh tower again")

# THE DAY IN UTC — the winners' timeline strip (v2 lacked it). Times verified
# 25 Nov: quake 01:32 UTC (NCS 07:02:47 IST); Sanofi deal 05:30 UTC (Sanofi
# release 06:30 Paris); Houthi tower hit Tuesday morning (Riyadh); Huawei
# verdict delivered in US court hours; US markets close 21:00 UTC.
TIMELINE = [
    ("01:32", "Nepal 5.4 quake"),
    ("05:30", "Sanofi's $41bn deal"),
    ("Morning", "Houthi strike hits Riyadh tower"),
    ("Afternoon", "Huawei guilty in Brooklyn"),
    ("21:00", "Nvidia slides 7% at the close"),
]

# kevin's device: a full-width red label bar above each hero illustration.
HERO_BAR = ["NVIDIA SLIDES 7%", "WARSHIP SUNK OFF LIBYA", "TANKERS HIT IN HORMUZ"]

# Status badges (winners' device): outlined chip on the kicker row, status +
# source — this is where each story names its outlet now that decks no
# longer carry inline "(Reuters)" attributions.
BADGE_COL = {"CONFIRMED": (36, 120, 66), "OFFICIAL": (176, 124, 32),
             "CLAIM": (166, 32, 32)}
BADGES = {
    1: ("CONFIRMED", "REUTERS, CNN"), 2: ("CONFIRMED", "CNN, WSJ"),
    3: ("CLAIM", "AL JAZEERA"), 4: ("CONFIRMED", "REUTERS"),
    5: ("CONFIRMED", "REUTERS"), 6: ("OFFICIAL", "WARSAW"),
    7: ("CONFIRMED", "REUTERS"), 8: ("CONFIRMED", "AL JAZEERA"),
    9: ("CONFIRMED", "AP"), 10: ("CONFIRMED", "REUTERS"),
    11: ("CONFIRMED", "REUTERS"), 12: ("CONFIRMED", "REUTERS"),
    13: ("CONFIRMED", "REUTERS"),
}
# Short mid kickers (winners use "4 GAMES", "5 RIYADH" — short enough that
# the badge chip fits on the same row).
MID_SHORT = {4: "BROOKLYN", 5: "RIYADH", 6: "WARSAW", 7: "US \u00b7 TECH",
             8: "GAZA", 9: "JAKARTA", 10: "NEPAL", 11: "PARIS",
             12: "MEXICO", 13: "ODESA"}


# ------------------------------------------------------------------ scenes
def _windows(cv, x, y, w, h, cols, rows, lit, col):
    cw = w // max(1, cols)
    chh = h // max(1, rows)
    for r in range(rows):
        for c in range(cols):
            if (r * cols + c) % 3 == 0:
                cv.rect(x + c * cw + 1, y + r * chh + 1, max(1, cw - 2),
                        max(1, chh - 2), lit)
            else:
                cv.rect(x + c * cw + 1, y + r * chh + 1, max(1, cw - 2),
                        max(1, chh - 2), col)


def _flame(cv, cx, base, w, h, col1=(250, 180, 60), col2=(230, 90, 30)):
    cv.poly([(cx - w // 2, base), (cx - w // 4, base - h * 2 // 3),
             (cx, base - h), (cx + w // 4, base - h * 2 // 3),
             (cx + w // 2, base)], col2)
    cv.poly([(cx - w // 4, base), (cx - w // 8, base - h // 2),
             (cx, base - h * 3 // 4), (cx + w // 8, base - h // 2),
             (cx + w // 4, base)], col1)


def _smoke(cv, cx, cy, n=4):
    for i in range(n):
        r = 5 + i * 3
        cv.circle(cx + i * 4 - 6, cy - i * 9, r, (90, 88, 92), alpha=110)


def scene_nvidia(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (18, 26, 46)), (0.6, (28, 44, 78)), (1.0, (16, 22, 40))])
    # ticker screens along the top
    for i in range(4):
        sx = x + 8 + i * (w // 4)
        cv.rect(sx, y + 8, w // 4 - 10, 16, (10, 14, 26))
        cv.rect(sx + 3, y + 11, (w // 4 - 16) * (3 - i) // 3 + 4, 3, (120, 200, 120) if i % 2 == 0 else (220, 80, 60))
    # big chip
    cx, cy = x + w * 2 // 5, y + h * 3 // 5
    cv.rect(cx - 52, cy - 40, 104, 80, (24, 90, 60))
    cv.rect(cx - 44, cy - 32, 88, 64, (34, 130, 84))
    for i in range(5):
        cv.hline(cx - 52, cy - 30 + i * 15, 104, (20, 70, 46))
        cv.vline(cx - 36 + i * 18, cy - 40, 80, (20, 70, 46))
    for dx, dy in ((-58, -30), (58, -30), (-58, 30), (58, 30)):
        cv.rect(cx + dx - 3, cy + dy - 3, 6, 6, (180, 220, 190))
    # huge red down arrow: shaft on top, triangular head below
    ax, ay = x + w - 78, y + 18
    cv.poly([(ax, ay), (ax + 54, ay), (ax + 54, ay + 34), (ax + 76, ay + 34),
             (ax + 27, ay + 96), (ax - 22, ay + 34), (ax, ay + 34)], (214, 48, 38))
    cv.poly([(ax + 10, ay + 8), (ax + 44, ay + 8), (ax + 44, ay + 34),
             (ax + 60, ay + 34), (ax + 27, ay + 80), (ax - 6, ay + 34),
             (ax + 10, ay + 34)], (238, 90, 70))
    # in-scene label: the drop, written on the arrow head itself
    F("sans_b11").draw(cv, ax + 14, ay + 42, "-7%", (255, 255, 255))
    # floor (the -7% is already in the stat strip and the headline)
    cv.rect(x, y + h - 14, w, 14, (12, 16, 30))


def scene_libya(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (8, 12, 30)), (0.55, (16, 26, 52)), (1.0, (10, 16, 34))])
    for sx, sy in ((12, 12), (60, 22), (150, 10), (230, 26), (280, 14), (40, 34), (190, 30)):
        cv.set(x + sx % w, y + sy, (230, 230, 200))
    cv.disc_glow(x + 120, y + 20, 18, (240, 220, 170))
    cv.circle(x + 120, y + 20, 8, (244, 232, 190))
    # sea
    cv.rect(x, y + h * 2 // 3, w, h // 3, (12, 26, 48))
    for i in range(5):
        cv.hline(x + 10 + i * 52, y + h * 2 // 3 + 8 + i * 7, 34, (60, 100, 140))
    # corvette silhouette, burning
    hx, hy = x + w // 2 - 30, y + h * 2 // 3 - 6
    cv.poly([(hx - 78, hy), (hx - 66, hy - 22), (hx + 66, hy - 22),
             (hx + 84, hy), (hx + 60, hy + 6), (hx - 60, hy + 6)], (30, 32, 38))
    cv.rect(hx - 18, hy - 44, 10, 24, (30, 32, 38))
    cv.rect(hx + 8, hy - 34, 8, 14, (30, 32, 38))
    cv.line(hx - 18, hy - 44, hx + 26, hy - 44, (30, 32, 38), 2)
    _flame(cv, hx - 40, hy - 20, 26, 34)
    _flame(cv, hx + 30, hy - 20, 22, 28)
    _smoke(cv, hx - 30, hy - 52)
    cv.disc_glow(hx - 40, hy - 30, 26, (250, 140, 40))
    # in-scene label: the corvette's name, on the sea below the hull
    F("sans_b9").draw(cv, hx - 30, hy + 8, "MERKURY", (200, 210, 230))
    # drone boats with wakes
    for dx, dy in ((-96, 12), (96, 20)):
        bx, by = hx + dx, hy + 26 + dy // 3
        cv.poly([(bx - 12, by), (bx + 12, by), (bx + 6, by + 5), (bx - 6, by + 5)], (180, 180, 170))
        cv.line(bx - 22, by + 8, bx - 40, by + 12, (120, 160, 200), 1)
        cv.line(bx - 20, by + 10, bx - 36, by + 14, (120, 160, 200), 1)


def scene_hormuz(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (52, 32, 66)), (0.45, (190, 96, 52)),
                          (0.7, (226, 140, 70)), (1.0, (40, 30, 52))])
    # low sun, up-left and small, kept well clear of the burning tanker:
    # its glow no longer touches the flame (they merged into one orange
    # blob in v2). Sun centre (x+78, y+20), flame centre (x+156, y+10..40).
    cv.disc_glow(x + w // 2 - 78, y + 20, 20, (245, 185, 100), steps=3)
    cv.circle(x + w // 2 - 78, y + 20, 10, (245, 195, 115))
    # sea with sun road
    cv.rect(x, y + h * 2 // 3, w, h // 3, (26, 34, 58))
    for i in range(4):
        cv.hline(x + w // 2 - 40 + i * 8, y + h * 2 // 3 + 6 + i * 8, 80 - i * 16, (240, 170, 90))
    # three tankers; middle one burning
    for tx, tw, burn in ((x + 14, 74, False), (x + w // 2 - 52, 104, True),
                         (x + w - 92, 78, False)):
        ty = y + h * 2 // 3 - 8
        cv.poly([(tx, ty), (tx + 8, ty - 18), (tx + tw - 8, ty - 18),
                 (tx + tw, ty), (tx + tw - 4, ty + 8), (tx + 4, ty + 8)], (28, 26, 34))
        cv.rect(tx + tw // 2 - 8, ty - 34, 16, 16, (28, 26, 34))
        cv.rect(tx + tw // 2 + 12, ty - 26, 10, 8, (28, 26, 34))
        if burn:
            # smaller flame + softer glow so it reads as fire, not a second sun
            _flame(cv, tx + tw // 2, ty - 30, 24, 30)
            _smoke(cv, tx + tw // 2, ty - 66, 5)
            cv.disc_glow(tx + tw // 2, ty - 40, 16, (250, 140, 40), steps=3)
        else:
            cv.rect(tx + 10, ty - 12, 8, 6, (240, 200, 120))
    # mines bobbing in the strait
    for mx2, my2 in ((26, h - 22), (120, h - 14), (w - 56, h - 26)):
        cv.circle(x + mx2, y + my2, 4, (20, 20, 24))
        for a in range(0, 360, 60):
            import math
            cv.line(x + mx2, y + my2,
                    x + mx2 + int(7 * math.cos(a * math.pi / 180)),
                    y + my2 + int(7 * math.sin(a * math.pi / 180)), (20, 20, 24), 1)


def scene_huawei(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (196, 186, 158)), (0.6, (214, 204, 178)), (1.0, (150, 138, 112))])
    # courthouse
    cv.rect(x + 18, y + 18, w - 36, 10, (120, 108, 88))
    cv.poly([(x + 10, y + 28), (x + w // 2, y + 2), (x + w - 10, y + 28)], (140, 126, 102))
    for i in range(4):
        cx = x + 30 + i * ((w - 60) // 3)
        cv.rect(cx, y + 28, 10, h - 44, (232, 224, 200))
        cv.rect(cx - 2, y + 26, 14, 4, (232, 224, 200))
        cv.rect(cx - 2, y + h - 18, 14, 4, (232, 224, 200))
    cv.rect(x + 10, y + h - 16, w - 20, 6, (120, 108, 88))
    cv.rect(x + 6, y + h - 10, w - 12, 4, (100, 90, 72))
    # scales of justice on the steps
    sx, sy = x + w // 2, y + h - 26
    cv.vline(sx, sy - 22, 22, (60, 52, 40))
    cv.line(sx - 20, sy - 22, sx + 20, sy - 22, (60, 52, 40), 2)
    cv.poly([(sx - 26, sy - 12), (sx - 14, sy - 12), (sx - 20, sy - 2)], (90, 78, 60))
    cv.poly([(sx + 14, sy - 12), (sx + 26, sy - 12), (sx + 20, sy - 2)], (90, 78, 60))
    # GUILTY stamp, bottom-right (clear of the number circle)
    cv.rrect(x + w - 74, y + h - 24, 66, 18, 3, (166, 32, 32))
    F("sans_b11").draw(cv, x + w - 66, y + h - 19, "GUILTY", (255, 255, 255))


def scene_riyadh(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (12, 16, 36)), (0.55, (30, 34, 66)), (1.0, (14, 16, 30))])
    for sx, sy in ((10, 8), (50, 16), (120, 6), (170, 14)):
        cv.set(x + sx, y + sy, (220, 220, 190))
    # skyline
    base = y + h
    for bx, bw, bh in ((0, 26, 34), (28, 20, 48), (50, 24, 40), (150, 22, 52), (174, 24, 36)):
        cv.rect(x + bx, base - bh, bw, bh, (24, 28, 48))
        _windows(cv, x + bx, base - bh + 4, bw, bh - 8, 2, 3, (240, 200, 110), (16, 18, 32))
    # PIF tower: twisted top, hit by fire
    tx = x + w // 2 - 16
    cv.poly([(tx, base), (tx + 4, y + 16), (tx + 28, y + 16), (tx + 32, base)], (52, 58, 84))
    cv.poly([(tx + 4, y + 16), (tx + 14, y + 2), (tx + 28, y + 16)], (52, 58, 84))
    for wy in range(y + 24, base - 8, 8):
        cv.hline(tx + 5, wy, 22, (240, 200, 110))
    _flame(cv, tx + 16, y + 22, 26, 30)
    _smoke(cv, tx + 16, y + 2, 4)
    cv.disc_glow(tx + 16, y + 22, 24, (250, 150, 50))


def scene_poland(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (40, 60, 96)), (0.55, (120, 130, 170)), (1.0, (210, 190, 160))])
    cv.disc_glow(x + w - 30, y + 18, 18, (250, 220, 150))
    cv.circle(x + w - 30, y + 18, 8, (250, 228, 160))
    # ground + city lights
    cv.rect(x, y + h - 16, w, 16, (52, 56, 60))
    for i in range(9):
        cv.rect(x + 8 + i * 20, y + h - 26, 10, 10, (52, 56, 60))
        cv.set(x + 12 + i * 20, y + h - 22, (240, 200, 110))
    # AWACS plane
    px, py = x + w // 2, y + h // 2 - 6
    cv.poly([(px - 64, py), (px - 52, py - 8), (px + 56, py - 8), (px + 68, py),
             (px + 56, py + 6), (px - 52, py + 6)], (232, 232, 228))
    cv.poly([(px + 30, py - 8), (px + 44, py - 22), (px + 52, py - 8)], (210, 210, 206))
    cv.poly([(px - 40, py + 6), (px - 30, py + 18), (px - 22, py + 6)], (210, 210, 206))
    cv.line(px - 14, py - 22, px + 14, py - 22, (70, 70, 76), 3)
    cv.circle(px - 8, py - 26, 10, (200, 200, 196))
    cv.circle(px - 8, py - 26, 10, (120, 120, 118))
    cv.circle(px - 8, py - 26, 5, (200, 200, 196))
    # radar arcs
    for r in (18, 28):
        cv.ring(px - 8, py - 26, r, (255, 255, 255), 1)
    # in-scene label under the plane
    F("sans_b9").draw(cv, px - 30, py + 22, "NATO AWACS", INK)


def scene_grok(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (40, 22, 62)), (0.6, (66, 32, 88)), (1.0, (26, 16, 40))])
    # laptop with warning
    lx, ly = x + w // 2 - 52, y + h // 2 - 30
    cv.rect(lx, ly, 104, 62, (16, 14, 22))
    cv.rect(lx + 4, ly + 4, 96, 54, (120, 40, 90))
    cv.poly([(lx + 52, ly + 12), (lx + 76, ly + 48), (lx + 28, ly + 48)], (250, 200, 60))
    cv.rect(lx + 50, ly + 26, 4, 12, (40, 22, 62))
    cv.circle(lx + 52, ly + 44, 2, (40, 22, 62))
    cv.rect(lx - 12, ly + 62, 128, 6, (30, 26, 38))
    # gavel
    gx, gy = x + 16, y + h - 30
    cv.line(gx, gy, gx + 34, gy - 16, (150, 110, 60), 4)
    cv.rect(gx + 30, gy - 26, 22, 10, (110, 78, 40))


def scene_gaza(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (96, 74, 66)), (0.5, (168, 120, 84)), (1.0, (60, 52, 48))])
    cv.disc_glow(x + 30, y + 20, 16, (250, 200, 130))
    cv.circle(x + 30, y + 20, 8, (248, 210, 140))
    base = y + h
    # ruined skyline
    for bx, bw, bh, tilt in ((0, 34, 44, 0), (36, 26, 30, -4), (64, 30, 52, 0),
                            (96, 24, 26, 5), (122, 30, 40, 0), (154, 28, 34, 0)):
        cv.poly([(x + bx, base), (x + bx + tilt, base - bh), (x + bx + bw + tilt, base - bh),
                 (x + bx + bw, base)], (58, 52, 48))
        _windows(cv, x + bx + 3, base - bh + 6, bw - 6, bh - 10, 2, 2,
                 (240, 190, 100), (44, 40, 38))
    _smoke(cv, x + w // 2 + 10, y + 30, 4)
    cv.rect(x, base - 8, w, 8, (44, 40, 36))


def scene_factory(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (70, 84, 110)), (0.55, (140, 140, 130)), (1.0, (90, 84, 76))])
    base = y + h
    # sawtooth factory
    cv.rect(x + 14, base - 44, w - 28, 44, (96, 88, 78))
    for i in range(3):
        sx = x + 22 + i * ((w - 60) // 3)
        cv.poly([(sx, base - 44), (sx + 18, base - 62), (sx + 36, base - 44)], (120, 110, 96))
    cv.rect(x + w - 34, base - 70, 10, 70, (80, 74, 66))
    _flame(cv, x + w // 3, base - 42, 34, 40)
    _flame(cv, x + 2 * w // 3, base - 42, 28, 32)
    _smoke(cv, x + w // 2, base - 76, 5)
    cv.disc_glow(x + w // 3, base - 56, 26, (250, 140, 40))
    # water arc from a hose
    for i in range(8):
        t = i / 7
        hx = x + 10 + int(t * (w // 2))
        hy = base - 6 - int(26 * t * (1 - t) * 4) - int(t * 10)
        cv.circle(hx, hy, 2, (120, 180, 230), alpha=200)
    cv.rect(x, base - 6, w, 6, (60, 58, 52))


def scene_quake(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (120, 150, 190)), (0.5, (190, 200, 210)), (1.0, (150, 140, 120))])
    # snow mountains
    cv.poly([(x, y + h), (x + w // 4, y + 14), (x + w // 2, y + h)], (110, 120, 140))
    cv.poly([(x + w // 4 - 12, y + 14), (x + w // 4, y + 14), (x + w // 4 + 12, y + 14),
             (x + w // 4 + 6, y + 30), (x + w // 4 - 6, y + 30)], (245, 245, 250))
    cv.poly([(x + w // 2, y + h), (x + 3 * w // 4, y + 26), (x + w, y + h)], (90, 100, 122))
    cv.poly([(x + 3 * w // 4 - 10, y + 26), (x + 3 * w // 4, y + 26),
             (x + 3 * w // 4 + 10, y + 26), (x + 3 * w // 4 + 5, y + 40),
             (x + 3 * w // 4 - 5, y + 40)], (245, 245, 250))
    # tilted house + dust
    hx, hy = x + w // 2 - 26, y + h - 34
    cv.poly([(hx, hy), (hx + 8, hy - 22), (hx + 48, hy - 22), (hx + 56, hy)], (150, 120, 88))
    cv.poly([(hx + 4, hy - 20), (hx + 28, hy - 32), (hx + 52, hy - 20)], (120, 60, 50))
    for i in range(6):
        cv.circle(x + 20 + i * 8, y + h - 12 - (i % 2) * 4, 4, (170, 160, 140), alpha=140)
    # seismograph zigzag
    pts = [(x + 8, y + 12), (x + 26, y + 12), (x + 34, y + 4), (x + 42, y + 20),
           (x + 50, y + 8), (x + 60, y + 16), (x + 72, y + 6), (x + 84, y + 18),
           (x + 96, y + 12), (x + w - 8, y + 12)]
    for a, b in zip(pts, pts[1:]):
        cv.line(a[0], a[1], b[0], b[1], (166, 32, 32), 2)


def scene_sanofi(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (150, 190, 205)), (0.6, (210, 225, 225)), (1.0, (170, 185, 190))])
    # glass lab building
    bx, by = x + 12, y + h - 52
    cv.rect(bx, by, 64, 52, (52, 84, 104))
    for r in range(4):
        for c in range(4):
            cv.rect(bx + 6 + c * 14, by + 6 + r * 11, 9, 7, (190, 225, 235))
    cv.rect(bx, by - 8, 64, 8, (40, 66, 84))
    # giant capsule
    cx, cy = x + w // 2 + 22, y + h // 2 + 6
    cv.poly([(cx - 34, cy - 10), (cx - 10, cy - 26), (cx + 34, cy + 2), (cx + 10, cy + 18)], (250, 250, 245))
    cv.poly([(cx - 34, cy - 10), (cx - 10, cy - 26), (cx + 8, cy - 12), (cx - 16, cy + 4)], (214, 48, 38))
    cv.circle(cx - 34, cy - 10, 7, (250, 250, 245))
    cv.circle(cx + 34, cy + 2, 7, (250, 250, 245))
    # green up arrow
    ax, ay = x + w - 34, y + 12
    cv.poly([(ax, ay + 26), (ax + 10, ay + 26), (ax + 10, ay + 12), (ax + 20, ay + 12),
             (ax + 10, ay), (ax, ay + 12), (ax - 10, ay + 12)], (34, 130, 70))


def scene_mexico(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (190, 170, 130)), (0.6, (214, 198, 168)), (1.0, (150, 132, 104))])
    # courthouse + bars
    cv.rect(x + 20, y + 22, w - 40, 8, (110, 96, 76))
    cv.poly([(x + 14, y + 30), (x + w // 2, y + 8), (x + w - 14, y + 30)], (130, 114, 90))
    for i in range(4):
        cx = x + 32 + i * ((w - 64) // 3)
        cv.rect(cx, y + 30, 9, h - 46, (232, 222, 196))
    cv.rect(x + 12, y + h - 16, w - 24, 6, (110, 96, 76))
    # bars across the door
    for i in range(5):
        cv.vline(x + w // 2 - 20 + i * 10, y + h - 44, 28, (60, 56, 50))
    # police car, big and legible at 300 px: body + cabin + light bar + door text
    cx, cy = x + w // 2 - 46, y + h - 26
    cv.poly([(cx, cy + 16), (cx + 2, cy + 4), (cx + 16, cy + 2), (cx + 76, cy + 2),
             (cx + 90, cy + 6), (cx + 92, cy + 16)], (32, 36, 48))
    cv.poly([(cx + 22, cy + 2), (cx + 28, cy - 10), (cx + 60, cy - 10),
             (cx + 68, cy + 2)], (44, 48, 62))
    cv.rect(cx + 26, cy - 7, 13, 8, (150, 190, 220))
    cv.rect(cx + 45, cy - 7, 13, 8, (150, 190, 220))
    cv.rect(cx + 40, cy - 15, 8, 5, (214, 48, 38))
    cv.rect(cx + 48, cy - 15, 8, 5, (38, 74, 180))
    cv.circle(cx + 20, cy + 16, 5, (16, 16, 20))
    cv.circle(cx + 72, cy + 16, 5, (16, 16, 20))
    cv.circle(cx + 20, cy + 16, 2, (140, 140, 150))
    cv.circle(cx + 72, cy + 16, 2, (140, 140, 150))
    F("sans_b9").draw(cv, cx + 28, cy + 7, "POLICIA", (255, 255, 255))


def scene_odesa(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, [(0.0, (16, 24, 48)), (0.55, (34, 48, 80)), (1.0, (14, 18, 34))])
    for sx, sy in ((14, 10), (70, 18), (130, 8), (170, 20), (100, 26)):
        cv.set(x + sx, y + sy, (230, 230, 200))
    cv.circle(x + w - 30, y + 16, 8, (240, 228, 190))
    base = y + h
    # dark skyline, few lit windows
    for bx, bw, bh in ((0, 30, 40), (32, 24, 56), (58, 28, 34), (88, 22, 48), (112, 26, 30), (140, 24, 44), (166, 20, 36)):
        cv.rect(x + bx, base - bh, bw, bh, (22, 26, 42))
        for wy in range(base - bh + 5, base - 6, 10):
            if (bx + wy) % 3 == 0:
                cv.rect(x + bx + 5, wy, 5, 6, (240, 200, 110))
    # broken pylon with spark
    px, py = x + w // 2 - 6, base - 66
    cv.line(px, py, px - 12, py + 40, (120, 120, 130), 2)
    cv.line(px, py, px + 12, py + 40, (120, 120, 130), 2)
    cv.line(px - 12, py + 14, px + 12, py + 14, (120, 120, 130), 2)
    cv.line(px - 16, py + 30, px + 16, py + 30, (120, 120, 130), 2)
    cv.disc_glow(px + 14, py + 8, 10, (250, 200, 60))
    cv.circle(px + 14, py + 8, 3, (250, 220, 100))
    # snow dots
    for sx, sy in ((10, 40), (40, 55), (90, 44), (140, 60), (170, 38), (60, 66)):
        cv.set(x + sx, y + sy, (240, 240, 250))


SCENES = {
    "nvidia": scene_nvidia, "libya": scene_libya, "hormuz": scene_hormuz,
    "huawei": scene_huawei, "riyadh": scene_riyadh, "poland": scene_poland,
    "grok": scene_grok, "gaza": scene_gaza, "factory": scene_factory,
    "quake": scene_quake, "sanofi": scene_sanofi, "mexico": scene_mexico,
    "odesa": scene_odesa,
}

# ----------------------------------------------------------------- layout
TAGS = {
    "nvidia": "SLIDES 7%", "libya": "WARSHIP SUNK", "hormuz": "BLOCKADE",
    "huawei": "GUILTY", "riyadh": "TOWER HIT", "poland": "DRONE",
    "grok": "2 STATES SUE", "gaza": "3 KILLED", "factory": "24 DEAD",
    "quake": "5.4 QUAKE", "sanofi": "$41BN DEAL", "mexico": "TRIAL",
    "odesa": "NO POWER",
}


def _tag(cv, x, y, text, font="sans_b9"):
    f = F(font)
    w = int(f.width(text)) + 12
    cv.rect(x, y, w, 15, RED)
    f.draw(cv, x + 6, y + 3, text, (255, 255, 255))
    return w


def _num_circle(cv, x, y, n, r=9, solid=False):
    if solid:
        cv.circle(x, y, r, RED)
    else:
        cv.circle(x, y, r, RED)
        cv.circle(x, y, r, (255, 255, 255))
        cv.circle(x, y, r - 1, RED)
    f = F("sans_b9")
    s = str(n)
    f.draw(cv, x - int(f.width(s) / 2), y - 5, s, (255, 255, 255))


def _badge(cv, x, y, text, col):
    """Small outlined status chip, right edge at x; returns its width."""
    f = F("sans_b9")
    w = int(f.width(text)) + 10
    cv.hline(x - w, y, w, col)
    cv.hline(x - w, y + 11, w, col)
    cv.vline(x - w, y, 12, col)
    cv.vline(x - 1, y, 12, col)
    f.draw(cv, x - w + 5, y + 2, text, col)
    return w


def _kicker(cv, x, y, text, badge=None, right_x=None):
    F("sans_b9").draw(cv, x, y, text, RED)
    if badge is not None:
        status, src = badge
        _badge(cv, right_x, y - 2, "%s \u00b7 %s" % (status, src),
               BADGE_COL[status])


def _headline_deck(cv, x, y, w, headline, deck, hfont, dfont, lh_h, lh_d, max_hl=2, max_dk=3):
    f = F(hfont)
    lines = f.wrap(headline, w)
    yy = y
    for ln in lines[:max_hl]:
        f.draw(cv, x, yy, ln, INK)
        yy += lh_h
    f2 = F(dfont)
    yy += 2
    for ln in f2.wrap(deck, w)[:max_dk]:
        f2.draw(cv, x, yy, ln, (52, 48, 44))
        yy += lh_d
    return yy


def draw_page():
    cv = Canvas(W, H, CREAM)
    # ---- top banner
    cv.rect(0, 0, W, 20, NAVY)
    F("sans_b10").draw(cv, 28, 5, "THE WORLD IN ONE DAY", (244, 238, 222))
    right = "35 STORIES \u00b7 6 REGIONS \u00b7 EVERY ONE DATED TUESDAY 24 NOVEMBER 2026"
    F("sans_b10").draw(cv, W - 28 - int(F("sans_b10").width(right)), 5, right, (244, 238, 222))
    # ---- masthead
    F("serif_b58").draw_center(cv, W // 2, 24, "Tuesday 24 November 2026", INK)
    F("serif_i15").draw_center(cv, W // 2, 86, SUBHEAD, RED)
    cv.hline(28, 110, 968, INK)
    cv.hline(28, 112, 968, INK)
    # ---- timeline: THE DAY IN UTC (the winners' device; v2 lacked it)
    cv.rect(28, 116, 92, 28, RED)
    F("sans_b9").draw_center(cv, 28 + 46, 120, "THE DAY", (255, 255, 255))
    F("sans_b9").draw_center(cv, 28 + 46, 131, "IN UTC", (255, 255, 255))
    bw = (968 - 92) // len(TIMELINE)
    for i, (t, fact) in enumerate(TIMELINE):
        x = 120 + i * bw
        F("sans_b10").draw(cv, x + 6, 118, t, RED)
        F("sans_r9").draw(cv, x + 6, 129, fact, INK)
        if i:
            cv.vline(x, 118, 24, RULE)
    cv.hline(28, 146, 968, RULE)
    # ---- stat strip: THE DAY IN NUMBERS (winners' device; v2's strip had
    # the same six numbers but no label box)
    cv.rect(28, 148, 110, 42, RED)
    F("sans_b9").draw_center(cv, 28 + 55, 152, "THE DAY", (255, 255, 255))
    F("sans_b9").draw_center(cv, 28 + 55, 163, "IN", (255, 255, 255))
    F("sans_b9").draw_center(cv, 28 + 55, 174, "NUMBERS", (255, 255, 255))
    cw = (968 - 110) // 6
    for i, (num, label) in enumerate(STATS):
        x = 138 + i * cw
        F("serif_b26").draw_center(cv, x + cw // 2, 150, num, RED if i % 2 == 0 else NAVY)
        f = F("sans_b9")
        for j, ln in enumerate(f.wrap(label, cw - 12)):
            f.draw_center(cv, x + cw // 2, 178 + j * 11, ln, (70, 64, 56))
        if i:
            cv.vline(x, 150, 40, RULE)
    cv.hline(28, 192, 968, RULE)
    # ---- region bar
    x = 28
    for name, count, col in REGIONS:
        seg_w = int(968 * count / 35)
        cv.rect(x, 196, seg_w, 16, col)
        lab = "%s %d" % (name, count)
        fw = F("sans_b9").width(lab)
        if fw + 8 <= seg_w:
            F("sans_b9").draw(cv, x + (seg_w - int(fw)) // 2, 199, lab, (255, 255, 255))
        x += seg_w
    # ---- heroes (kevin's device: a full-width red label bar above each hero)
    hw = 312
    for i, (n, place, topic, head, deck, _la, _lo, scene, _dx, _dy) in enumerate(HEROES):
        x = 28 + i * (hw + 16)
        y = 238
        cv.rect(x, 218, hw, 20, RED)
        F("sans_b11").draw(cv, x + 8, 223, HERO_BAR[i], (255, 255, 255))
        SCENES[scene](cv, x, y, hw, 104)
        _num_circle(cv, x + hw - 14, y + 14, n)
        _kicker(cv, x, 348, "%d %s \u00b7 %s" % (n, place, topic),
                badge=BADGES[n], right_x=x + hw)
        _headline_deck(cv, x, 362, hw, head, deck, "serif_b22", "serif_r13", 24, 14)
    # ---- mids, two rows of five
    mw = (968 - 4 * 10) // 5
    for row in range(2):
        for col in range(5):
            s = MIDS[row * 5 + col]
            n, place, topic, head, deck, _la, _lo, scene, _dx, _dy = s
            x = 28 + col * (mw + 10)
            y = 460 + row * 136
            SCENES[scene](cv, x, y, mw, 58)
            _tag(cv, x + 3, y + 3, TAGS[scene])
            _num_circle(cv, x + mw - 12, y + 12, n, r=8)
            _kicker(cv, x, 522 + row * 136, "%d %s" % (n, MID_SHORT[n]),
                    badge=BADGES[n], right_x=x + mw)
            _headline_deck(cv, x, 534 + row * 136, mw, head, deck,
                           "serif_b16", "serif_r11", 16, 11)
    # ---- bottom: map + briefs
    y0 = 738
    F("sans_b10").draw(cv, 28, y0, "WHERE IT HAPPENED", INK)
    F("sans_r9").draw(cv, 150, y0 + 1, "pins match story numbers", GREY)
    F("sans_b10").draw(cv, 330, y0, "THE REST OF THE DAY \u2014 22 MORE STORIES", INK)
    mx, my = 28, y0 + 16
    mw2, mh2 = 290, 145
    cv.rect(mx - 4, my - 4, mw2 + 8, mh2 + 8, PAPER)
    pitch_x = mw2 / 96.0
    pitch_y = mh2 / 48.0
    for r, row in enumerate(assets_blob.MAP_ROWS):
        for c, ch in enumerate(row):
            if ch == "#":
                cv.circle(int(mx + (c + 0.5) * pitch_x), int(my + (r + 0.5) * pitch_y),
                          1, SAGE)
    all_stories = list(HEROES) + list(MIDS)
    # Label offsets from each story's true lat/lon point, computed by an
    # offline repulsion relaxation (see /tmp/map_layout2.py): every numbered
    # label centre is >= 13 px from every other, so no two pins overlap
    # (v2's Europe/Middle East cluster was one unreadable red mass). An
    # offset label gets a thin leader line back to its true point, marked by
    # a small dot. Pins without an entry sit exactly on their true point.
    PIN_LABEL = {
        2: (-9, 11), 3: (13, -1), 4: (0, -8), 5: (-4, 14), 6: (-12, 4),
        7: (-6, 0), 8: (-9, 1), 9: (1, 3), 10: (2, 0), 11: (-9, 9),
        13: (-7, 3), 14: (-5, -2), 15: (-1, -12), 16: (15, -6),
        17: (5, -16), 18: (2, -5), 19: (-15, -1), 20: (12, 8),
        21: (-3, -12), 23: (1, 7), 24: (-1, -3), 26: (-8, -3),
        27: (5, 6), 28: (5, 13), 29: (-9, 7), 30: (10, -1), 31: (15, -16),
        32: (5, 7), 33: (1, 3), 34: (7, -2), 35: (0, -6),
    }

    def _pin(px, py, n):
        dx, dy = PIN_LABEL.get(n, (0, 0))
        lx, ly = px + dx, py + dy
        if dx or dy:
            cv.circle(px, py, 2, RED)
            cv.line(px, py, lx, ly, RED, 1)
        _num_circle(cv, lx, ly, n, r=6, solid=True)

    for s in all_stories:
        n, _pl, _tp, _hd, _dk, la, lo, _sc, dx, dy = s
        px = int(mx + (lo + 180) / 360.0 * mw2) + dx
        py = int(my + (86 - la) / 144.0 * mh2) + dy
        _pin(px, py, n)
    for s in BRIEFS:
        n, _pl, _tx, la, lo = s
        px = int(mx + (lo + 180) / 360.0 * mw2)
        py = int(my + (86 - la) / 144.0 * mh2)
        _pin(px, py, n)
    # briefs, single column, one line each
    bx = 330
    by = my
    f = F("sans_r9")
    fb = F("sans_b9")
    for n, place, text, _la, _lo in BRIEFS:
        num = "%d " % n
        fb.draw(cv, bx, by, num, RED)
        nx = bx + int(fb.width(num))
        f.draw(cv, nx, by, "%s: %s" % (place.split(",")[0], text), INK)
        by += 9
    # ---- date check
    dy = 962
    cv.rect(28, dy, 968, 42, (255, 255, 255))
    cv.rect(28, dy, 968, 1, RED)
    cv.rect(28, dy + 41, 968, 1, RED)
    cv.rect(28, dy, 1, 42, RED)
    cv.rect(28 + 967, dy, 1, 42, RED)
    dc = ("DATE CHECK  Wires read up to late Tuesday 24 November 2026 (UTC). "
          "Every story here was reported or still developing on 24 November in "
          "at least one time zone. Left out as other days' news: Nvidia's "
          "reinstatement and 31% jump (23 Nov) \u00b7 the Delta outage (22 Nov) "
          "\u00b7 the COP31 collapse itself (22 Nov) \u00b7 the missiles landing "
          "in Poland (20 Nov).")
    f2 = F("sans_r9")
    fb2 = F("sans_b9")
    fb2.draw(cv, 36, dy + 5, "DATE CHECK", RED)
    tx = 36 + int(fb2.width("DATE CHECK  "))
    lines = f2.wrap(dc.split("DATE CHECK  ", 1)[1], 968 - (tx - 28) - 16)
    for j, ln in enumerate(lines[:2]):
        f2.draw(cv, tx, dy + 5 + j * 11, ln, INK)
    # ---- footer
    F("sans_r9").draw(cv, 28, 1008,
                      "CONFIRMED 2+ outlets \u00b7 OFFICIAL authority's word \u00b7 "
                      "CLAIM one side says \u00b7 Sources: Reuters, AP, CNN, WSJ, Al Jazeera, "
                      "Bloomberg, UN News \u00b7 Drawn illustrations, not photos.",
                      GREY)
    F("sans_b9").draw(cv, W - 28 - int(F("sans_b9").width("TUESDAY 24 NOVEMBER 2026 \u00b7 ONE PAGE")),
                      1008, "TUESDAY 24 NOVEMBER 2026 \u00b7 ONE PAGE", INK)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    cv = draw_page()
    data = encode_png(cv.px, W, H)
    with open(os.path.join(out_dir, "entry.png"), "wb") as fh:
        fh.write(data)
    print("wrote entry.png: %d bytes" % len(data))


if __name__ == "__main__":
    main()
