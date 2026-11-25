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
    (1, "SANTA CLARA", "MARKETS",
     "Nvidia slides 7% as its record rally fades",
     "A day after Huang's return lifted shares 31% in their best day since "
     "2003, the stock slides back.",
     37.35, -121.95, "nvidia", 0, 0),
    (2, "BENGHAZI, LIBYA", "WAR",
     "Ukraine's sea drones sink a Russian warship",
     "Seven naval drones hit the corvette Merkury at Benghazi; Tripoli "
     "demands answers from Kyiv.",
     32.10, 20.07, "libya", 0, 0),
    (3, "HORMUZ STRAIT", "IRAN WAR",
     "Iran says tankers hit mines, defiance hardens",
     "Three tankers catch fire in the strait as Tehran rules out talks until "
     "the US meets its seven conditions.",
     26.60, 56.25, "hormuz", 0, 0),
]

MIDS = [
    (4, "BROOKLYN, US", "JUSTICE",
     "Huawei guilty of trade secrets",
     "A Brooklyn jury convicts Huawei of trade-secret conspiracy and bank "
     "fraud.",
     40.65, -73.95, "huawei", 0, 0),
    (5, "RIYADH, SAUDI ARABIA", "WAR",
     "Houthis hit Riyadh tower again",
     "A strike on the PIF Tower injures 11, the second hit in five days.",
     24.70, 46.70, "riyadh", 0, 0),
    (6, "WARSAW, POLAND", "SECURITY",
     "Russian drone crossed on purpose",
     "Warsaw calls the incursion deliberate, days after three missiles "
     "landed.",
     52.25, 21.05, "poland", 0, 0),
    (7, "OREGON & VIRGINIA, US", "TECH",
     "Two states sue Musk over Grok images",
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
    (14, "TRIPOLI, LIBYA", "Tripoli demands answers from Kyiv. (Reuters)", 32.90, 13.20),
    (15, "THE HAGUE", "Fourteen nations back the ICJ ruling. (Reuters)", 52.08, 4.30),
    (16, "TEHRAN, IRAN", "Ghalibaf: no US talks until conditions met. (Reuters)", 35.70, 51.40),
    (17, "KYIV, UKRAINE", "Ukraine hits Russian oil plants. (Reuters)", 50.45, 30.50),
    (18, "ZAPORIZHZHIA, UKRAINE", "Russian strike kills two. (Reuters)", 47.85, 35.10),
    (19, "SANAA, YEMEN", "Strikes kill about 26 in Sanaa. (AP)", 15.35, 44.20),
    (20, "ADEN, YEMEN", "Houthi fighters near Aden, 60 km off. (Reuters)", 12.80, 45.00),
    (21, "TALLINN, ESTONIA", "Russia warns Estonia over border closure. (Reuters)", 59.40, 24.75),
    (22, "VILLAVICENCIO, COLOMBIA", "Car bomb hits governor's office. (Reuters)", 4.15, -73.60),
    (23, "RAS AL KHAIMAH, UAE", "Bus-truck crash kills 11 in UAE. (AP)", 25.80, 55.95),
    (24, "SINGAPORE", "US to blacklist AI firm Megaspeed. (Reuters)", 1.35, 103.80),
    (25, "BEIJING, CHINA", "China sentences ex-official to death. (Reuters)", 39.90, 116.40),
    (26, "SPACE", "NATO vows space defence. (Reuters)", 51.50, -0.12),
    (27, "NEW YORK, US", "Guterres urges global AI safeguards. (UN News)", 40.75, -74.00),
    (28, "ADDIS ABABA, ETHIOPIA", "Amnesty seeks Tigray war-crimes probe. (AP)", 9.00, 38.75),
    (29, "AFRICA", "African Union launches health roadmap. (AP)", 9.05, 38.85),
    (30, "BAGHDAD, IRAQ", "Iraqi forces seize drone platforms. (Reuters)", 33.30, 44.40),
    (31, "JERUSALEM", "Palestinian detainees allege threats. (Reuters)", 31.77, 35.20),
    (32, "GAZA", "Israeli strikes kill seven in Gaza. (Al Jazeera)", 31.50, 34.45),
    (33, "FLORIDA, US", "Trump to meet NATO chief in Florida. (Reuters)", 26.70, -80.05),
    (34, "ANTALYA, TURKEY", "COP31 post-mortems spread blame. (Reuters)", 36.90, 30.70),
    (35, "WARSAW, POLAND", "NATO sends AWACS to Poland. (Reuters)", 52.10, 20.90),
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

# THE DAY IN UTC — 7 beats (beats bagarte's 6 and kevin's 5; superskie19
# also has 7 but only 4 timed). Times verified 25 Nov: quake 01:32 UTC (NCS
# 07:02:47 IST); Sanofi deal 05:30 UTC (release 06:30 Paris); UAE crash toll
# confirmed 07:30 UTC (QNA wire 07:30:37Z); Poland drone crossed overnight
# (late Mon night local, announced Tue morning — the winners use "Overnight"
# for the night leading into the day, same convention); Houthi tower hit
# Tuesday morning Riyadh (sources state the exact hour is not known — kept
# as the phase label, as superskie19 does with "Overnight"/"Asia day");
# Huawei verdict delivered in US court hours (no clock time published —
# phase label); US markets close 21:00 UTC.
TIMELINE = [
    ("Overnight", "Drone enters Poland"),
    ("01:32", "Nepal 5.4 quake"),
    ("05:30", "Sanofi's $41bn deal"),
    ("07:30", "UAE bus crash kills 11"),
    ("Morning", "Houthi hits Riyadh"),
    ("Afternoon", "Huawei guilty"),
    ("21:00", "Nvidia slides 7%"),
]

# kevin's device: a full-width red label bar above each hero illustration.
HERO_BAR = ["NVIDIA SLIDES 7%", "WARSHIP SUNK OFF LIBYA", "TANKERS HIT IN HORMUZ"]

# Status badges (winners' device): outlined chip on the kicker row, status +
# source — this is where each story names its outlet now that decks no
# longer carry inline "(Reuters)" attributions.
BADGE_COL = {"CONFIRMED": (36, 120, 66), "OFFICIAL": (176, 124, 32),
             "CLAIM": (166, 32, 32)}
BADGES = {
    1: ("CONFIRMED", "REUTERS"), 2: ("CONFIRMED", "CNN, WSJ"),
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


def _smoke(cv, cx, cy, n=4, top=None):
    """Smoke rising from (cx, cy). If top is given, no puff ever crosses
    it: puffs are spread between cy and top so a tall column cannot paint
    over the bar or deck text above the scene (the old version did)."""
    for i in range(n):
        r = 4 + i * 2
        if top is None:
            ccy = cy - i * 8
        else:
            span = max(0, cy - (top + r))
            ccy = cy - span * i // max(1, n - 1)
        cv.circle(cx + i * 4 - 6, ccy, r, (90, 88, 92), alpha=110)


def scene_nvidia(cv, x, y, w, h):
    # Trading floor at night: deep navy gradient sky, ticker screens with
    # live candlesticks, a big glowing GPU chip, a falling candlestick chart
    # with a red glow, and desks with lit monitors along the bottom.
    cv.vgrad(x, y, w, h, [(0.0, (18, 28, 54)), (0.5, (26, 42, 76)), (1.0, (20, 30, 56))])
    for sx, sy in ((14, 6), (70, 12), (140, 5), (200, 10), (230, 16)):
        cv.set(x + sx, y + sy, (180, 190, 220))
    # ticker screens along the top: tiny candlesticks inside each screen
    for i in range(4):
        sx = x + 8 + i * (w // 4)
        cv.rect(sx, y + 6, w // 4 - 10, 18, (8, 12, 24))
        cv.rect(sx, y + 6, w // 4 - 10, 2, (60, 80, 120))
        for k in range(5):
            cx2 = sx + 6 + k * 9
            up = (i + k) % 3 != 0
            col = (110, 200, 130) if up else (225, 85, 65)
            cv.rect(cx2, y + 10 + (0 if up else 4), 4, 8, col)
    # big GPU chip, left: glow, body, top highlight, pins, label
    cx, cy = x + 62, y + 66
    cv.disc_glow(cx, cy, 46, (40, 160, 110), steps=3)
    cv.rect(cx - 50, cy - 38, 100, 76, (18, 70, 46))
    cv.rect(cx - 44, cy - 32, 88, 64, (30, 120, 80))
    cv.rect(cx - 44, cy - 32, 88, 6, (70, 190, 130))
    cv.hline(cx - 50, cy - 38, 100, GOLD)
    cv.hline(cx - 50, cy + 37, 100, GOLD)
    cv.vline(cx - 50, cy - 38, 76, GOLD)
    cv.vline(cx + 49, cy - 38, 76, GOLD)
    for i in range(5):
        cv.hline(cx - 44, cy - 22 + i * 14, 88, (20, 70, 46))
        cv.vline(cx - 30 + i * 16, cy - 32, 64, (20, 70, 46))
    for dx, dy in ((-56, -28), (56, -28), (-56, 28), (56, 28)):
        cv.rect(cx + dx - 3, cy + dy - 3, 6, 6, (190, 230, 200))
    F("sans_b9").draw(cv, cx - 14, cy - 6, "NVDA", (210, 240, 220))
    # falling candlestick chart, right: 7 red candles stepping down
    gx, gy, gw, gh = x + 138, y + 32, 100, 52
    cv.rect(gx - 6, gy - 6, gw + 12, gh + 12, (14, 22, 44))
    for i in range(6):
        cv.hline(gx - 4, gy + i * 10, gw + 8, (34, 48, 76))
    cv.disc_glow(gx + gw - 14, gy + gh - 6, 22, (230, 70, 50), steps=3)
    for i in range(7):
        bx = gx + 4 + i * 13
        top = gy + 4 + i * 6
        cv.rect(bx, top, 8, 14, (225, 80, 60))
        cv.vline(bx + 4, top - 4, 22, (225, 80, 60))
    # one bold focal moment: a glowing red trend line over the falling candles
    for i in range(6):
        cv.line(gx + 8 + i * 13, gy + 18 + i * 6, gx + 8 + (i + 1) * 13,
                gy + 18 + (i + 1) * 6, (255, 120, 100), 2)
    cv.disc_glow(gx + gw - 6, gy + 42, 14, (255, 110, 90), steps=2)
    # red down arrow with glow, over the chart's right end
    ax, ay = x + w - 62, y + 22
    cv.disc_glow(ax + 24, ay + 44, 32, (230, 60, 45), steps=3)
    cv.poly([(ax, ay), (ax + 44, ay), (ax + 44, ay + 28), (ax + 62, ay + 28),
             (ax + 22, ay + 82), (ax - 18, ay + 28), (ax, ay + 28)], (214, 48, 38))
    cv.poly([(ax + 8, ay + 6), (ax + 36, ay + 6), (ax + 36, ay + 28),
             (ax + 48, ay + 28), (ax + 22, ay + 68), (ax - 4, ay + 28),
             (ax + 8, ay + 28)], (238, 90, 70))
    F("sans_b11").draw(cv, ax + 12, ay + 36, "-7%", (255, 255, 255))
    # trading desks with lit monitors along the bottom
    cv.rect(x, y + h - 14, w, 14, (10, 14, 28))
    for i in range(6):
        dx = x + 10 + i * 40
        cv.rect(dx, y + h - 26, 22, 12, (16, 22, 40))
        cv.rect(dx + 3, y + h - 24, 16, 6, (90, 170, 120) if i % 2 else (200, 90, 70))


def scene_libya(cv, x, y, w, h):
    # A corvette burning at night off Benghazi: moonlit sky, sea with a
    # moon road, a real hull with bridge, mast and lit portholes, two fires
    # with glow and smoke, drone boats closing in with wakes.
    cv.vgrad(x, y, w, h, [(0.0, (8, 12, 30)), (0.45, (18, 30, 58)), (0.62, (26, 44, 72)), (1.0, (10, 16, 34))])
    for sx, sy in ((12, 12), (60, 22), (150, 10), (230, 26), (40, 34), (190, 30), (110, 6)):
        cv.set(x + sx % w, y + sy, (230, 230, 200))
    # moon with halo, upper left
    cv.disc_glow(x + 44, y + 18, 16, (240, 220, 170))
    cv.circle(x + 44, y + 18, 9, (244, 232, 190))
    cv.circle(x + 41, y + 16, 2, (210, 200, 160))
    cv.circle(x + 47, y + 21, 2, (210, 200, 160))
    # sea with a moon road and wave lines
    cv.rect(x, y + h * 2 // 3, w, h // 3, (12, 26, 48))
    for i in range(4):
        cv.hline(x + 30 + i * 6, y + h * 2 // 3 + 5 + i * 8, 46 - i * 8, (200, 200, 170))
    for i in range(5):
        cv.hline(x + 10 + i * 52, y + h * 2 // 3 + 8 + i * 7, 34, (60, 100, 140))
    # corvette: hull with a lighter top edge, bow, bridge with lit windows,
    # mast with radar bar, funnel, and a wake of foam at the bow
    hx, hy = x + w // 2 - 10, y + h * 2 // 3 - 4
    cv.poly([(hx - 84, hy), (hx - 70, hy - 20), (hx + 70, hy - 20),
             (hx + 88, hy), (hx + 64, hy + 6), (hx - 64, hy + 6)], (54, 60, 76))
    cv.hline(hx - 70, hy - 20, 140, (150, 160, 180))
    cv.rect(hx - 30, hy - 46, 44, 26, (60, 66, 82))
    cv.rect(hx - 30, hy - 46, 44, 3, (160, 170, 190))
    for wx in range(hx - 26, hx + 14, 8):
        cv.rect(wx, hy - 40, 6, 6, (240, 200, 110))
    cv.rect(hx + 22, hy - 38, 8, 18, (36, 40, 52))
    cv.vline(hx - 8, hy - 66, 20, (60, 64, 76))
    cv.line(hx - 20, hy - 66, hx + 4, hy - 66, (60, 64, 76), 3)
    cv.circle(hx - 8, hy - 66, 3, (200, 60, 50))
    for fx in range(4):
        cv.circle(hx - 92 + fx * 6, hy + 4, 2, (200, 220, 240), alpha=180)
    # two fires with glow, smoke and orange reflections on the water
    _flame(cv, hx - 44, hy - 18, 26, 36)
    _flame(cv, hx + 34, hy - 18, 22, 30)
    _smoke(cv, hx - 44, hy - 54, 5, top=y)
    _smoke(cv, hx + 34, hy - 48, 4, top=y)
    cv.disc_glow(hx - 44, hy - 28, 26, (250, 140, 40))
    cv.disc_glow(hx + 34, hy - 28, 22, (250, 140, 40))
    cv.hline(hx - 64, hy + 12, 40, (250, 150, 60))
    cv.hline(hx + 14, hy + 12, 36, (250, 150, 60))
    # the corvette's name, on the sea below the hull
    F("sans_b9").draw(cv, hx - 30, hy + 16, "MERKURY", (200, 210, 230))
    # drone boats with wakes and a red running light
    for dx, dy in ((-104, 10), (104, 18)):
        bx, by = hx + dx, hy + 24 + dy // 3
        cv.poly([(bx - 12, by), (bx + 12, by), (bx + 6, by + 5), (bx - 6, by + 5)], (180, 180, 170))
        cv.set(bx, by - 3, (230, 60, 50))
        cv.line(bx - 22, by + 8, bx - 40, by + 12, (120, 160, 200), 1)
        cv.line(bx - 20, by + 10, bx - 36, by + 14, (120, 160, 200), 1)


def scene_hormuz(cv, x, y, w, h):
    # Sunset over the strait: purple-orange gradient sky with clouds, a low
    # sun with a road of light on the sea, three tankers with real hull
    # detail (bridge, containers, portholes), the middle one burning, mines
    # bobbing, a patrol boat and gulls.
    cv.vgrad(x, y, w, h, [(0.0, (52, 32, 66)), (0.45, (205, 110, 60)),
                          (0.7, (226, 140, 70)), (1.0, (40, 30, 52))])
    # dusk clouds, soft dark ellipses high in the sky
    for cx, cy, cr in ((x + 40, y + 16, 12), (x + 70, y + 14, 9),
                       (x + w - 60, y + 16, 11), (x + w - 30, y + 18, 8)):
        cv.circle(cx, cy, cr, (90, 52, 84), alpha=140)
    # low sun, up-left and small, kept well clear of the burning tanker:
    # its glow no longer touches the flame (they merged into one orange
    # blob in v2). Sun centre (x+78, y+20), flame centre (x+156, y+10..40).
    cv.disc_glow(x + w // 2 - 78, y + 20, 26, (245, 185, 100), steps=3)
    cv.circle(x + w // 2 - 78, y + 20, 12, (245, 195, 115))
    # gulls
    for gx, gy in ((x + 30, y + 34), (x + 44, y + 30), (x + w - 40, y + 36)):
        cv.line(gx - 4, gy, gx, gy - 3, (40, 30, 50), 1)
        cv.line(gx, gy - 3, gx + 4, gy, (40, 30, 50), 1)
    # sea with sun road
    cv.rect(x, y + h * 2 // 3, w, h // 3, (26, 34, 58))
    for i in range(5):
        cv.hline(x + w // 2 - 40 + i * 8, y + h * 2 // 3 + 6 + i * 8, 80 - i * 16, (240, 170, 90))
    # three tankers; middle one burning
    for tx, tw, burn in ((x + 14, 74, False), (x + w // 2 - 52, 104, True),
                         (x + w - 92, 78, False)):
        ty = y + h * 2 // 3 - 8
        cv.poly([(tx, ty), (tx + 8, ty - 18), (tx + tw - 8, ty - 18),
                 (tx + tw, ty), (tx + tw - 4, ty + 8), (tx + 4, ty + 8)], (48, 44, 54))
        cv.hline(tx + 6, ty - 16, tw - 12, (160, 120, 90))
        # bridge tower with lit windows + container stacks
        cv.rect(tx + tw // 2 - 10, ty - 36, 20, 18, (62, 56, 66))
        cv.rect(tx + tw // 2 - 10, ty - 36, 20, 3, (90, 80, 70))
        for wx in range(tx + tw // 2 - 7, tx + tw // 2 + 8, 6):
            cv.rect(wx, ty - 32, 4, 5, (245, 200, 120))
        cv.rect(tx + 8, ty - 12, 14, 10, (120, 70, 60))
        cv.rect(tx + 24, ty - 12, 14, 10, (90, 110, 80))
        for px2 in range(tx + 10, tx + tw - 8, 12):
            cv.set(px2, ty - 4, (200, 170, 110))
        # bow wave
        cv.line(tx - 4, ty + 6, tx - 12, ty + 10, (200, 210, 230), 1)
        cv.line(tx + tw + 4, ty + 6, tx + tw + 12, ty + 10, (200, 210, 230), 1)
        if burn:
            # smaller flame + softer glow so it reads as fire, not a second sun
            _flame(cv, tx + tw // 2, ty - 30, 24, 30)
            _smoke(cv, tx + tw // 2, ty - 30, 5, top=y)
            cv.disc_glow(tx + tw // 2, ty - 40, 16, (250, 140, 40), steps=3)
            cv.hline(tx + tw // 2 - 16, ty + 10, 32, (250, 150, 60))
        else:
            cv.rect(tx + 10, ty - 12, 8, 6, (240, 200, 120))
    # patrol boat, small, foreground right
    bx, by = x + w - 34, y + h - 12
    cv.poly([(bx - 12, by), (bx + 12, by), (bx + 6, by + 4), (bx - 6, by + 4)], (200, 200, 190))
    cv.rect(bx - 4, by - 8, 8, 8, (200, 200, 190))
    cv.set(bx, by - 10, (230, 60, 50))
    # mines bobbing in the strait
    for mx2, my2 in ((26, h - 22), (120, h - 14), (w - 56, h - 26)):
        cv.circle(x + mx2, y + my2, 4, (20, 20, 24))
        for a in range(0, 360, 60):
            import math
            cv.line(x + mx2, y + my2,
                    x + mx2 + int(7 * math.cos(a * math.pi / 180)),
                    y + my2 + int(7 * math.sin(a * math.pi / 180)), (20, 20, 24), 1)


def scene_huawei(cv, x, y, w, h):
    # Brooklyn courthouse in warm morning light: pale sky with a sun glow,
    # a stone facade in two tones, shaded columns with capitals, steps with
    # shadows, a dark door, scales of justice, and two trees. (The GUILTY
    # stamp is gone — the red tag above the scene already says it.)
    cv.vgrad(x, y, w, h, [(0.0, (196, 186, 158)), (0.6, (214, 204, 178)), (1.0, (150, 138, 112))])
    cv.disc_glow(x + w - 22, y + 10, 10, (250, 230, 170), steps=3)
    cv.circle(x + w - 22, y + 10, 6, (250, 236, 190))
    # trees flanking the courthouse
    for tx in (x + 8, x + w - 14):
        cv.vline(tx + 3, y + h - 26, 12, (90, 70, 50))
        cv.circle(tx + 3, y + h - 32, 7, (96, 120, 80))
        cv.circle(tx - 2, y + h - 28, 5, (110, 134, 90))
    # courthouse: pediment with shading, entablature, columns, steps
    cv.rect(x + 18, y + 18, w - 36, 10, (120, 108, 88))
    cv.poly([(x + 10, y + 28), (x + w // 2, y + 2), (x + w - 10, y + 28)], (146, 132, 108))
    cv.poly([(x + w // 2, y + 2), (x + w - 10, y + 28), (x + w // 2, y + 28)], (128, 114, 92))
    cv.circle(x + w // 2, y + 16, 4, (110, 98, 80))
    for i in range(4):
        cx = x + 30 + i * ((w - 60) // 3)
        cv.rect(cx, y + 28, 10, h - 44, (232, 224, 200))
        cv.rect(cx + 6, y + 28, 4, h - 44, (200, 190, 164))
        cv.rect(cx - 2, y + 26, 14, 4, (232, 224, 200))
        cv.rect(cx - 2, y + h - 18, 14, 4, (232, 224, 200))
    # dark door between the middle columns
    cv.rect(x + w // 2 - 9, y + h - 30, 18, 14, (70, 60, 48))
    cv.vline(x + w // 2, y + h - 30, 14, (120, 108, 88))
    # steps with shadows
    cv.rect(x + 10, y + h - 16, w - 20, 6, (120, 108, 88))
    cv.rect(x + 6, y + h - 10, w - 12, 4, (100, 90, 72))
    cv.rect(x + 10, y + h - 16, w - 20, 1, (150, 138, 116))
    # scales of justice on the steps
    sx, sy = x + w // 2, y + h - 26
    cv.vline(sx, sy - 22, 22, (60, 52, 40))
    cv.line(sx - 20, sy - 22, sx + 20, sy - 22, (60, 52, 40), 2)
    cv.poly([(sx - 26, sy - 12), (sx - 14, sy - 12), (sx - 20, sy - 2)], (90, 78, 60))
    cv.poly([(sx + 14, sy - 12), (sx + 26, sy - 12), (sx + 20, sy - 2)], (90, 78, 60))


def scene_riyadh(cv, x, y, w, h):
    # Riyadh at dusk: a purple-orange sunset sky, a skyline with varied lit
    # windows, the twisted PIF tower with glass reflections and a fire at
    # its crown, and a street below with a car and a streetlight.
    cv.vgrad(x, y, w, h, [(0.0, (62, 48, 92)), (0.5, (154, 94, 110)), (0.75, (232, 154, 104)), (1.0, (74, 62, 84))])
    cv.disc_glow(x + w - 26, y + 12, 10, (250, 200, 140), steps=3)
    cv.circle(x + w - 26, y + 12, 6, (250, 214, 160))
    # skyline (width-relative: the old absolute bx values overflowed the
    # narrowed 150 px mid column and painted over the next scene)
    base = y + h
    for fx, fw, bh in ((0.00, 0.16, 30), (0.17, 0.12, 44), (0.31, 0.15, 36),
                       (0.69, 0.13, 48), (0.84, 0.15, 32)):
        bx, bw = int(w * fx), int(w * fw)
        cv.rect(x + bx, base - bh, bw, bh, (24, 28, 48))
        cv.rect(x + bx, base - bh, bw, 2, (70, 76, 100))
        _windows(cv, x + bx, base - bh + 4, bw, bh - 8, 2, 3, (240, 200, 110), (16, 18, 32))
        if fx == 0.69:
            cv.rect(x + bx + bw // 2 - 1, base - bh - 8, 2, 8, (24, 28, 48))
            cv.set(x + bx + bw // 2, base - bh - 9, (230, 60, 50))
    # two extra lit windows on the outer towers
    cv.rect(x + int(w * 0.17) + 6, base - 30, 4, 5, (240, 200, 110))
    cv.rect(x + int(w * 0.69) + 8, base - 36, 4, 5, (240, 200, 110))
    # PIF tower: twisted top, glass facade with vertical light strips, fire
    tx = x + w // 2 - 16
    cv.poly([(tx, base), (tx + 4, y + 16), (tx + 28, y + 16), (tx + 32, base)], (52, 58, 84))
    cv.poly([(tx + 4, y + 16), (tx + 14, y + 2), (tx + 28, y + 16)], (66, 72, 100))
    for wy in range(y + 24, base - 8, 8):
        cv.hline(tx + 5, wy, 22, (240, 200, 110))
    cv.vline(tx + 10, y + 20, base - y - 28, (140, 150, 180))
    cv.vline(tx + 20, y + 20, base - y - 28, (140, 150, 180))
    _flame(cv, tx + 16, y + 30, 26, 24)
    _smoke(cv, tx + 16, y + 6, 3, top=y)
    cv.disc_glow(tx + 16, y + 30, 20, (250, 150, 50))
    # street: a car with headlights and a streetlight
    cv.rect(x, base - 6, w, 6, (30, 28, 36))
    cv.poly([(x + 12, base - 6), (x + 16, base - 12), (x + 30, base - 12), (x + 34, base - 6)], (180, 60, 50))
    cv.circle(x + 17, base - 6, 2, (16, 16, 20))
    cv.circle(x + 29, base - 6, 2, (16, 16, 20))
    cv.set(x + 34, base - 9, (250, 240, 180))
    cv.vline(x + w - 12, base - 18, 12, (60, 60, 66))
    cv.disc_glow(x + w - 12, base - 18, 8, (250, 220, 140), steps=2)


def scene_poland(cv, x, y, w, h):
    # A NATO AWACS over Polish farmland: blue-grey sky with soft clouds and
    # a low sun, green fields with a road, a tree line and two farmhouses,
    # and the white plane with a shaded belly, radar dome and sweep arcs —
    # plus a small dark drone silhouette far behind it.
    cv.vgrad(x, y, w, h, [(0.0, (70, 100, 140)), (0.55, (150, 165, 185)), (0.8, (210, 195, 165)), (1.0, (120, 130, 100))])
    cv.disc_glow(x + w - 30, y + 18, 18, (250, 220, 150))
    cv.circle(x + w - 30, y + 18, 8, (250, 228, 160))
    # soft clouds
    for cx, cy, cr in ((x + 24, y + 10, 10), (x + 40, y + 7, 8), (x + 110, y + 14, 9)):
        cv.circle(cx, cy, cr, (235, 235, 230), alpha=120)
    # farmland: two field tones, a road, a tree line, two farmhouses
    cv.rect(x, y + h - 26, w, 26, (96, 120, 74))
    cv.rect(x, y + h - 26, w // 2, 26, (116, 138, 88))
    cv.poly([(x, y + h), (x + w // 2, y + h - 26), (x + w // 2 + 10, y + h - 26), (x + 16, y + h)], (200, 190, 170))
    for tx in range(x + 8, x + w - 8, 14):
        cv.poly([(tx, y + h - 26), (tx + 4, y + h - 38), (tx + 8, y + h - 26)], (60, 88, 58))
    cv.rect(x + 12, y + h - 34, 12, 8, (200, 180, 150))
    cv.poly([(x + 12, y + h - 34), (x + 18, y + h - 40), (x + 24, y + h - 34)], (150, 60, 50))
    cv.rect(x + w - 30, y + h - 34, 11, 6, (200, 180, 150))
    cv.poly([(x + w - 30, y + h - 34), (x + w - 24, y + h - 40), (x + w - 19, y + h - 34)], (150, 60, 50))
    # small dark drone silhouette far behind the AWACS
    dx0, dy0 = x + 22, y + 26
    cv.line(dx0 - 8, dy0, dx0 + 8, dy0, (50, 50, 56), 2)
    cv.line(dx0, dy0 - 2, dx0, dy0 + 3, (50, 50, 56), 2)
    cv.line(dx0 - 10, dy0 + 6, dx0 - 2, dy0 + 2, (50, 50, 56), 1)
    cv.line(dx0 + 2, dy0 + 2, dx0 + 10, dy0 + 6, (50, 50, 56), 1)
    # AWACS plane, shaded: light top, grey belly, windows, radar dome
    # (scaled x1.25 now the tiles are 185 px wide)
    px, py = x + w // 2, y + h // 2 - 8
    cv.poly([(px - 80, py), (px - 65, py - 10), (px + 70, py - 10), (px + 85, py),
             (px + 70, py + 7), (px - 65, py + 7)], (232, 232, 228))
    cv.poly([(px - 65, py + 2), (px + 70, py + 2), (px + 70, py + 7), (px - 65, py + 7)], (180, 180, 176))
    for wx in range(px - 52, px + 56, 8):
        cv.rect(wx, py - 5, 4, 3, (90, 110, 140))
    cv.poly([(px + 38, py - 10), (px + 55, py - 24), (px + 65, py - 10)], (210, 210, 206))
    cv.poly([(px - 50, py + 7), (px - 38, py + 22), (px - 28, py + 7)], (210, 210, 206))
    cv.line(px - 18, py - 20, px + 18, py - 20, (70, 70, 76), 3)
    # radar dome, kept small so it never rises above the scene: the old
    # sweep rings painted white arcs over the hero deck text above.
    cv.circle(px - 10, py - 17, 8, (200, 200, 196))
    cv.circle(px - 10, py - 17, 8, (120, 120, 118))
    cv.circle(px - 10, py - 17, 4, (200, 200, 196))
    # contrail behind the plane (clamped to this tile's left edge so it
    # never paints into the neighbouring Riyadh tile)
    cv.line(px - 80, py + 2, x + 2, py + 6, (220, 220, 215), 1)
    # gulls
    for gx, gy in ((x + 30, y + 12), (x + 46, y + 9)):
        cv.line(gx - 4, gy, gx, gy - 3, (40, 30, 50), 1)
        cv.line(gx, gy - 3, gx + 4, gy, (40, 30, 50), 1)
    # in-scene label under the plane, on a white pill so it reads
    cv.rrect(px - 38, py + 20, 76, 12, 2, (255, 255, 255))
    F("sans_b9").draw(cv, px - 30, py + 22, "NATO AWACS", INK)


def scene_grok(cv, x, y, w, h):
    """Courtroom, dense (15+ elements): warm wood panels with grain, a
    golden hanging lamp with a pool of light on the bench, scales of
    justice, a document stack, two laptops with glowing screens (X and
    GROK), a gavel + block, and a small flag on the bench. The old version
    read as a flat dark box because every tone was dark purple-brown —
    the lamp and the lighter wood fix that."""
    cv.vgrad(x, y, w, h, [(0.0, (96, 62, 58)), (0.6, (78, 50, 52)), (1.0, (56, 38, 42))])
    # hanging lamp, top-centre: cord, shade, warm glow, light pool
    cv.vline(x + w // 2, y + 2, 8, (40, 30, 30))
    cv.poly([(x + w // 2 - 10, y + 10), (x + w // 2 + 10, y + 10), (x + w // 2 + 6, y + 18), (x + w // 2 - 6, y + 18)], (150, 110, 60))
    cv.disc_glow(x + w // 2, y + 20, 20, (250, 200, 110), steps=4)
    cv.circle(x + w // 2, y + 20, 4, (255, 230, 160))
    # wood wall panels with grain
    for px in (x + 26, x + 50, x + 100, x + 124):
        cv.vline(px, y + 2, 32, (120, 84, 72))
    cv.hline(x, y + 34, w, (120, 84, 72))
    # scales of justice, top-right emblem (clear of the tag and the circle)
    cx = x + 104
    cv.vline(cx, y + 8, 20, (198, 142, 44))
    cv.line(cx - 16, y + 10, cx + 16, y + 10, (198, 142, 44), 2)
    cv.poly([(cx - 16, y + 10), (cx - 22, y + 20), (cx - 10, y + 20)], (150, 106, 32))
    cv.poly([(cx + 16, y + 10), (cx + 10, y + 20), (cx + 22, y + 20)], (150, 106, 32))
    cv.rect(cx - 6, y + 28, 12, 3, (198, 142, 44))
    # judge's bench: wood with grain lines and a top highlight
    cv.rect(x, y + 38, w, h - 38, (120, 80, 52))
    cv.hline(x, y + 38, w, (190, 140, 90))
    cv.hline(x, y + 46, w, (90, 58, 40))
    for gx in range(x + 12, x + w - 8, 22):
        cv.vline(gx, y + 48, h - 48, (100, 66, 44))
    # warm light pool on the bench under the lamp
    cv.disc_glow(x + w // 2, y + 52, 18, (250, 200, 110), steps=3)
    # document stack with a red filed edge
    cv.rect(x + 8, y + 44, 24, 14, (208, 200, 180))
    cv.rect(x + 10, y + 42, 24, 14, (220, 214, 196))
    cv.rect(x + 12, y + 40, 24, 14, (232, 226, 210))
    cv.rect(x + 12, y + 40, 24, 2, RED)
    cv.hline(x + 15, y + 45, 18, (120, 110, 95))
    cv.hline(x + 15, y + 49, 14, (120, 110, 95))
    # laptop X, screen glowing
    cv.rect(x + 46, y + 40, 24, 14, (16, 14, 22))
    cv.rect(x + 48, y + 42, 20, 10, (200, 220, 240))
    F("sans_b11").draw(cv, x + 54, y + 42, "X", (20, 30, 50))
    cv.rect(x + 43, y + 54, 30, 4, (30, 26, 38))
    # laptop GROK, screen glowing
    cv.rect(x + 80, y + 40, 28, 14, (16, 14, 22))
    cv.rect(x + 82, y + 42, 24, 10, (200, 220, 240))
    F("sans_b9").draw(cv, x + 84, y + 43, "GROK", (20, 30, 50))
    cv.rect(x + 77, y + 54, 34, 4, (30, 26, 38))
    # gavel + block
    cv.line(x + 122, y + 58, x + 138, y + 44, (150, 110, 60), 3)
    cv.rect(x + 134, y + 40, 13, 7, (110, 78, 40))
    cv.rect(x + 124, y + 60, 14, 4, (90, 64, 36))


def scene_gaza(cv, x, y, w, h):
    # Khan Younis in a dusty haze: a pale sun behind smoke, a ruined
    # skyline with jagged tops and exposed floors, a few lit windows, two
    # smoke columns with fire glow at their base, and rubble on the street.
    cv.vgrad(x, y, w, h, [(0.0, (150, 120, 100)), (0.5, (190, 150, 110)), (1.0, (110, 96, 82))])
    cv.disc_glow(x + 30, y + 18, 18, (250, 205, 140))
    cv.circle(x + 30, y + 18, 8, (248, 210, 140))
    base = y + h
    # ruined skyline: jagged tops, one building with exposed floors
    for fx, fw, bh, tilt in ((0.00, 0.19, 40, 0), (0.20, 0.14, 28, -4),
                             (0.36, 0.17, 48, 0), (0.54, 0.13, 24, 5),
                             (0.68, 0.17, 36, 0), (0.85, 0.14, 30, 0)):
        bx, bw = int(w * fx), int(w * fw)
        cv.poly([(x + bx, base), (x + bx + tilt, base - bh), (x + bx + bw + tilt, base - bh),
                 (x + bx + bw, base)], (58, 52, 48))
        cv.poly([(x + bx + tilt, base - bh), (x + bx + bw // 2, base - bh - 5),
                 (x + bx + bw + tilt, base - bh)], (70, 62, 56))
        _windows(cv, x + bx + 3, base - bh + 6, bw - 6, bh - 10, 2, 2,
                 (240, 190, 100), (44, 40, 38))
    # exposed floors on the middle ruin: horizontal floor lines
    ex = int(w * 0.36)
    for fy in range(base - 44, base - 8, 8):
        cv.hline(x + ex + 2, fy, int(w * 0.17) - 4, (90, 80, 70))
    # smoke columns with fire glow at the base
    _smoke(cv, x + w // 2 + 10, y + 28, 4, top=y)
    _smoke(cv, x + w - 24, y + 34, 3, top=y)
    # second dust cloud, mid-sky left
    for dcx, dcy, dcr in ((x + 40, y + 40, 10), (x + 54, y + 36, 8), (x + 28, y + 44, 7)):
        cv.circle(dcx, dcy, dcr, (235, 220, 200), alpha=90)
    cv.disc_glow(x + w // 2 + 10, base - 14, 14, (250, 140, 50), steps=3)
    _flame(cv, x + w // 2 + 10, base - 8, 14, 16)
    # a standing minaret at right, one lit window in it
    cv.rect(x + w - 14, base - 58, 8, 58, (70, 62, 56))
    cv.circle(x + w - 10, base - 58, 5, (70, 62, 56))
    cv.rect(x + w - 12, base - 40, 4, 5, (240, 190, 100))
    # rubble on the street
    for rx, rw, rh in ((4, 12, 5), (18, 9, 4), (w - 26, 11, 5), (w - 14, 8, 3),
                       (w // 2 - 8, 10, 4), (w // 2 + 14, 8, 3)):
        cv.poly([(x + rx, base), (x + rx + rw // 2, base - rh), (x + rx + rw, base)], (70, 62, 54))
    for dx in range(0, w, 18):
        cv.set(x + dx, base - 3, (150, 135, 115))
    cv.rect(x, base - 8, w, 8, (44, 40, 36))


def scene_factory(cv, x, y, w, h):
    # A candy factory on fire: grey-blue sky under a big layered smoke
    # plume, a sawtooth factory with brick lines and orange-lit windows, two
    # fires washing the walls with light, a red fire truck with its ladder
    # up, a water arc, and debris on the ground.
    cv.vgrad(x, y, w, h, [(0.0, (70, 84, 110)), (0.55, (140, 140, 130)), (1.0, (90, 84, 76))])
    base = y + h
    # big smoke plume rising and drifting right; puffs are clamped so none
    # crosses the scene top (they painted over the deck text above before)
    for i in range(6):
        pr = 7 + i * 2
        cv.circle(x + w // 2 + i * 7, max(base - 58 - i * 5, y + pr),
                  pr, (110, 108, 104), alpha=130)
    # sawtooth factory with brick lines and fire-lit windows
    cv.rect(x + 14, base - 44, w - 28, 44, (96, 88, 78))
    for i in range(3):
        sx = x + 22 + i * ((w - 60) // 3)
        cv.poly([(sx, base - 44), (sx + 18, base - 62), (sx + 36, base - 44)], (120, 110, 96))
        cv.poly([(sx + 18, base - 62), (sx + 26, base - 62), (sx + 36, base - 44), (sx + 18, base - 44)], (140, 128, 112))
    for by in range(base - 40, base - 8, 8):
        cv.hline(x + 16, by, w - 32, (82, 74, 66))
    for wx in range(x + 22, x + w - 22, 16):
        cv.rect(wx, base - 30, 8, 8, (250, 150, 60))
    cv.rect(x + w - 34, base - 70, 10, 70, (80, 74, 66))
    cv.rect(x + w - 34, base - 70, 10, 4, (110, 100, 88))
    _flame(cv, x + w // 3, base - 42, 34, 40)
    _flame(cv, x + 2 * w // 3, base - 42, 28, 32)
    cv.disc_glow(x + w // 3, base - 56, 18, (250, 140, 40))
    cv.disc_glow(x + 2 * w // 3, base - 52, 16, (250, 140, 40))
    # red fire truck with ladder, bottom-left
    tx, ty = x + 8, base - 14
    cv.rect(tx, ty - 6, 26, 8, (190, 40, 32))
    cv.rect(tx + 18, ty - 12, 10, 6, (190, 40, 32))
    cv.line(tx + 22, ty - 12, tx + 40, ty - 30, (200, 200, 200), 2)
    cv.circle(tx + 6, ty + 2, 3, (16, 16, 20))
    cv.circle(tx + 22, ty + 2, 3, (16, 16, 20))
    cv.set(tx + 20, ty - 14, (250, 220, 80))
    # water arc from a hose
    for i in range(8):
        t = i / 7
        hx = x + 10 + int(t * (w // 2))
        hy = base - 6 - int(26 * t * (1 - t) * 4) - int(t * 10)
        cv.circle(hx, hy, 2, (120, 180, 230), alpha=200)
    # debris + puddle
    for dx, dy in ((w - 30, base - 4), (w - 18, base - 3), (w - 44, base - 5)):
        cv.rect(x + dx, dy, 6, 3, (60, 56, 50))
    cv.rect(x + w // 2 - 10, base - 4, 30, 3, (120, 160, 200))
    cv.rect(x, base - 6, w, 6, (60, 58, 52))


def scene_quake(cv, x, y, w, h):
    # Nepal after the tremor: a pale blue sky, three mountain ranges with
    # shaded slopes and snow caps, a small village at the foot with one
    # tilted house and cracked walls, dust clouds, and a cracked road.
    cv.vgrad(x, y, w, h, [(0.0, (110, 140, 180)), (0.5, (180, 195, 210)), (1.0, (200, 190, 170))])
    cv.disc_glow(x + w - 24, y + 12, 10, (250, 235, 190), steps=3)
    cv.circle(x + w - 24, y + 12, 6, (250, 240, 200))
    # back range, hazy and pale
    cv.poly([(x, y + h), (x + w // 3, y + 22), (x + 2 * w // 3, y + h)], (140, 150, 168))
    cv.poly([(x + w // 3 - 8, y + 22), (x + w // 3, y + 22), (x + w // 3 + 8, y + 22),
             (x + w // 3 + 4, y + 34), (x + w // 3 - 4, y + 34)], (235, 235, 242))
    # mid range: left slope light, right slope shaded, snow caps
    cv.poly([(x, y + h), (x + w // 4, y + 14), (x + w // 2, y + h)], (110, 120, 140))
    cv.poly([(x + w // 4, y + 14), (x + w // 2, y + h), (x + w // 4 + 10, y + h)], (88, 98, 118))
    cv.poly([(x + w // 4 - 12, y + 14), (x + w // 4, y + 14), (x + w // 4 + 12, y + 14),
             (x + w // 4 + 6, y + 30), (x + w // 4 - 6, y + 30)], (245, 245, 250))
    cv.poly([(x + w // 2, y + h), (x + 3 * w // 4, y + 26), (x + w, y + h)], (100, 110, 130))
    cv.poly([(x + 3 * w // 4, y + 26), (x + w, y + h), (x + 3 * w // 4 + 8, y + h)], (80, 90, 110))
    cv.poly([(x + 3 * w // 4 - 10, y + 26), (x + 3 * w // 4, y + 26),
             (x + 3 * w // 4 + 10, y + 26), (x + 3 * w // 4 + 5, y + 40),
             (x + 3 * w // 4 - 5, y + 40)], (245, 245, 250))
    # village at the foot: small houses, one tilted with a cracked wall
    for hx, hw2 in ((x + 8, 18), (x + 30, 16), (x + w - 34, 20), (x + w - 56, 16)):
        cv.rect(hx, y + h - 16, hw2, 10, (200, 180, 150))
        cv.poly([(hx - 1, y + h - 16), (hx + hw2 // 2, y + h - 24), (hx + hw2 + 1, y + h - 16)], (150, 70, 55))
        cv.rect(hx + hw2 // 2 - 2, y + h - 10, 4, 4, (80, 60, 45))
    hx, hy = x + w // 2 - 26, y + h - 34
    cv.poly([(hx, hy), (hx + 8, hy - 22), (hx + 48, hy - 22), (hx + 56, hy)], (150, 120, 88))
    cv.poly([(hx + 4, hy - 20), (hx + 28, hy - 32), (hx + 52, hy - 20)], (120, 60, 50))
    cv.line(hx + 14, hy - 18, hx + 20, hy - 6, (90, 70, 55), 1)
    cv.line(hx + 20, hy - 6, hx + 16, hy, (90, 70, 55), 1)
    # dust clouds at the tilted house
    for i in range(6):
        cv.circle(x + 20 + i * 8, y + h - 12 - (i % 2) * 4, 4, (170, 160, 140), alpha=140)
    # cracked ground
    cv.line(x + 10, y + h - 6, x + 30, y + h - 10, (90, 80, 66), 1)
    cv.line(x + 30, y + h - 10, x + 48, y + h - 6, (90, 80, 66), 1)
    # seismograph zigzag, small, top-left
    pts = [(x + 8, y + 10), (x + 22, y + 10), (x + 28, y + 4), (x + 34, y + 16),
           (x + 40, y + 7), (x + 48, y + 13), (x + 56, y + 6), (x + 64, y + 14),
           (x + 72, y + 10), (x + 84, y + 10)]
    for a, b in zip(pts, pts[1:]):
        cv.line(a[0], a[1], b[0], b[1], (166, 32, 32), 2)


def scene_sanofi(cv, x, y, w, h):
    # A biotech deal in bright daylight: pale blue sky with soft clouds, a
    # glass lab building with two-tone reflections and varied windows, a
    # giant capsule with a highlight and a shadow, a pill bottle with
    # spilled pills, a molecule, and a glowing green up arrow.
    cv.vgrad(x, y, w, h, [(0.0, (150, 190, 205)), (0.6, (210, 225, 225)), (1.0, (170, 185, 190))])
    for cx, cy, cr in ((x + 20, y + 8, 9), (x + 34, y + 6, 7), (x + w - 30, y + 10, 8)):
        cv.circle(cx, cy, cr, (245, 248, 250), alpha=160)
    # glass lab building: two-tone facade, varied windows, roof, antenna
    bx, by = x + 12, y + h - 52
    cv.rect(bx, by, 64, 52, (52, 84, 104))
    cv.rect(bx + 32, by, 32, 52, (40, 68, 88))
    for r in range(4):
        for c in range(4):
            lit = (r + c) % 3 != 0
            cv.rect(bx + 6 + c * 14, by + 6 + r * 11, 9, 7,
                    (190, 225, 235) if lit else (150, 190, 205))
    cv.rect(bx, by - 8, 64, 8, (40, 66, 84))
    cv.vline(bx + 56, by - 16, 8, (60, 80, 100))
    cv.set(bx + 56, by - 17, (230, 60, 50))
    # lawn
    cv.rect(x, y + h - 6, w, 6, (110, 150, 90))
    # giant capsule with highlight and shadow
    cx, cy = x + w // 2 + 22, y + h // 2 + 6
    cv.poly([(cx - 30, cy + 16), (cx + 34, cy + 10), (cx + 34, cy + 16), (cx - 30, cy + 22)], (180, 180, 175))
    cv.poly([(cx - 34, cy - 10), (cx - 10, cy - 26), (cx + 34, cy + 2), (cx + 10, cy + 18)], (250, 250, 245))
    cv.poly([(cx - 34, cy - 10), (cx - 10, cy - 26), (cx + 8, cy - 12), (cx - 16, cy + 4)], (214, 48, 38))
    cv.poly([(cx - 28, cy - 14), (cx - 12, cy - 24), (cx - 2, cy - 16), (cx - 18, cy - 6)], (255, 255, 255))
    cv.circle(cx - 34, cy - 10, 7, (250, 250, 245))
    cv.circle(cx + 34, cy + 2, 7, (250, 250, 245))
    # pill bottle with spilled pills, bottom-right
    cv.rect(x + w - 26, y + h - 24, 12, 18, (240, 235, 220))
    cv.rect(x + w - 26, y + h - 24, 12, 4, (214, 48, 38))
    for px, py in ((x + w - 40, y + h - 8), (x + w - 48, y + h - 5), (x + w - 34, y + h - 5)):
        cv.circle(px, py, 3, (250, 250, 245))
    # green up arrow with glow
    ax, ay = x + w - 34, y + 12
    cv.disc_glow(ax + 5, ay + 14, 14, (60, 180, 100), steps=2)
    cv.poly([(ax, ay + 26), (ax + 10, ay + 26), (ax + 10, ay + 12), (ax + 20, ay + 12),
             (ax + 10, ay), (ax, ay + 12), (ax - 10, ay + 12)], (34, 130, 70))


def scene_mexico(cv, x, y, w, h):
    # Mexico City in warm afternoon light: a pale sky with sun, a
    # courthouse with a shaded pediment and columns, steps, bars across the
    # door, and the POLICIA car with a glowing light bar, a shadow and a
    # street with a lane line — plus a cactus at the edge.
    cv.vgrad(x, y, w, h, [(0.0, (190, 170, 130)), (0.6, (214, 198, 168)), (1.0, (150, 132, 104))])
    cv.disc_glow(x + w - 24, y + 10, 10, (250, 225, 160), steps=3)
    cv.circle(x + w - 24, y + 10, 6, (250, 234, 185))
    # cactus, far left
    cv.rect(x + 6, y + h - 26, 5, 14, (90, 130, 80))
    cv.rect(x + 2, y + h - 20, 4, 5, (90, 130, 80))
    cv.rect(x + 11, y + h - 22, 4, 5, (90, 130, 80))
    # courthouse + bars, shaded
    cv.rect(x + 20, y + 22, w - 40, 8, (110, 96, 76))
    cv.poly([(x + 14, y + 30), (x + w // 2, y + 8), (x + w - 14, y + 30)], (136, 120, 96))
    cv.poly([(x + w // 2, y + 8), (x + w - 14, y + 30), (x + w // 2, y + 30)], (120, 104, 82))
    for i in range(4):
        cx = x + 32 + i * ((w - 64) // 3)
        cv.rect(cx, y + 30, 9, h - 46, (232, 222, 196))
        cv.rect(cx + 6, y + 30, 3, h - 46, (200, 188, 162))
    cv.rect(x + 12, y + h - 16, w - 24, 6, (110, 96, 76))
    cv.rect(x + 12, y + h - 16, w - 24, 1, (150, 136, 112))
    # bars across the door
    for i in range(5):
        cv.vline(x + w // 2 - 20 + i * 10, y + h - 44, 28, (60, 56, 50))
    # street with a lane line
    cv.rect(x, y + h - 8, w, 8, (90, 86, 80))
    for lx in range(x + 4, x + w - 4, 16):
        cv.rect(lx, y + h - 5, 8, 2, (220, 210, 190))
    # police car, big and legible at 300 px: body + cabin + light bar + door text
    cx, cy = x + w // 2 - 46, y + h - 26
    cv.poly([(cx - 30, cy + 20), (cx + 92, cy + 20), (cx + 92, cy + 24), (cx - 30, cy + 24)], (70, 66, 60))
    cv.poly([(cx, cy + 16), (cx + 2, cy + 4), (cx + 16, cy + 2), (cx + 76, cy + 2),
             (cx + 90, cy + 6), (cx + 92, cy + 16)], (32, 36, 48))
    cv.poly([(cx + 22, cy + 2), (cx + 28, cy - 10), (cx + 60, cy - 10),
             (cx + 68, cy + 2)], (44, 48, 62))
    cv.rect(cx + 26, cy - 7, 13, 8, (150, 190, 220))
    cv.rect(cx + 45, cy - 7, 13, 8, (150, 190, 220))
    cv.disc_glow(cx + 44, cy - 15, 10, (220, 60, 50), steps=2)
    cv.disc_glow(cx + 52, cy - 15, 10, (60, 90, 220), steps=2)
    cv.rect(cx + 40, cy - 15, 8, 5, (214, 48, 38))
    cv.rect(cx + 48, cy - 15, 8, 5, (38, 74, 180))
    cv.circle(cx + 20, cy + 16, 5, (16, 16, 20))
    cv.circle(cx + 72, cy + 16, 5, (16, 16, 20))
    cv.circle(cx + 20, cy + 16, 2, (140, 140, 150))
    cv.circle(cx + 72, cy + 16, 2, (140, 140, 150))
    F("sans_b9").draw(cv, cx + 28, cy + 7, "POLICIA", (255, 255, 255))


def scene_odesa(cv, x, y, w, h):
    # Odesa in blackout: a starry night sky with a glowing moon, a dark
    # skyline where almost every window is dark — only a few stay lit, one
    # with a candle — a broken pylon throwing sparks, snow, a car with its
    # headlights on, and the black sea with a ship at the bottom.
    cv.vgrad(x, y, w, h, [(0.0, (26, 36, 64)), (0.55, (46, 62, 98)), (1.0, (20, 26, 44))])
    for sx, sy in ((14, 10), (70, 18), (130, 8), (170, 20), (100, 26)):
        cv.set(x + sx, y + sy, (230, 230, 200))
    cv.disc_glow(x + w - 30, y + 16, 14, (240, 228, 190))
    cv.circle(x + w - 30, y + 16, 8, (240, 228, 190))
    cv.circle(x + w - 33, y + 14, 2, (210, 200, 160))
    base = y + h
    # dark skyline, mostly unlit: only a handful of warm windows survive
    for bx, bw, bh in ((0, 30, 40), (32, 24, 56), (58, 28, 34), (88, 22, 48), (112, 26, 30), (140, 24, 44), (164, 20, 36)):
        cv.rect(x + bx, base - bh, bw, bh, (22, 26, 42))
        cv.rect(x + bx, base - bh, bw, 2, (60, 66, 88))
        for wy in range(base - bh + 5, base - 6, 10):
            if (bx + wy) % 3 == 0:
                cv.rect(x + bx + 5, wy, 5, 6, (240, 200, 110))
    # one window lit by a candle: brighter, with a glow
    cv.disc_glow(x + 100, base - 40, 10, (250, 200, 110), steps=2)
    cv.rect(x + 96, base - 42, 7, 8, (255, 220, 130))
    cv.set(x + 99, base - 38, (255, 240, 180))
    # four more lit windows so the skyline is not one black mass
    for wx, wy in ((x + 66, base - 26), (x + 120, base - 20),
                   (x + 146, base - 30), (x + 170, base - 24)):
        cv.rect(wx, wy, 5, 6, (240, 200, 110))
    # lit church dome at right, silhouetted against the moon
    cv.circle(x + w - 24, base - 52, 10, (30, 34, 52))
    cv.vline(x + w - 24, base - 66, 10, (90, 96, 110))
    cv.hline(x + w - 28, base - 63, 8, (90, 96, 110))
    cv.rect(x + w - 27, base - 50, 5, 6, (240, 200, 110))
    # broken pylon with spark and a sagging wire
    px, py = x + w // 2 - 6, base - 66
    cv.line(px, py, px - 12, py + 40, (120, 120, 130), 2)
    cv.line(px, py, px + 12, py + 40, (120, 120, 130), 2)
    cv.line(px - 12, py + 14, px + 12, py + 14, (120, 120, 130), 2)
    cv.line(px - 16, py + 30, px + 16, py + 30, (120, 120, 130), 2)
    cv.disc_glow(px + 14, py + 8, 10, (250, 200, 60))
    cv.circle(px + 14, py + 8, 3, (250, 220, 100))
    cv.line(px + 12, py + 40, px + 34, py + 52, (90, 90, 100), 1)
    # car with headlights on the street
    cv.poly([(x + 14, base - 6), (x + 18, base - 12), (x + 32, base - 12), (x + 36, base - 6)], (150, 40, 35))
    cv.circle(x + 19, base - 6, 2, (16, 16, 20))
    cv.circle(x + 31, base - 6, 2, (16, 16, 20))
    cv.disc_glow(x + 38, base - 9, 8, (250, 240, 180), steps=2)
    cv.set(x + 38, base - 9, (255, 250, 210))
    # the black sea with a ship silhouette at the very bottom
    cv.rect(x, base - 4, w, 4, (10, 16, 30))
    cv.poly([(x + w - 60, base - 4), (x + w - 56, base - 10), (x + w - 30, base - 10),
             (x + w - 26, base - 4)], (16, 20, 34))
    cv.rect(x + w - 48, base - 16, 10, 6, (16, 20, 34))
    cv.set(x + w - 44, base - 13, (240, 200, 110))
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


def _kicker(cv, x, y, text, badge=None, right_x=None, badge_src=True):
    F("sans_b9").draw(cv, x, y, text, RED)
    if badge is not None:
        status, src = badge
        # Mids use status-only chips (bagarte + kevin both do this on mids);
        # heroes keep status + source (they have the width for it).
        _badge(cv, right_x, y - 2,
               "%s \u00b7 %s" % (status, src) if badge_src else status,
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
    # ---- region bar (the horizontal stats strip is gone: THE DAY IN NUMBERS
    # is now a vertical panel on the right, bagarte's device, cleaner here)
    x = 28
    for name, count, col in REGIONS:
        seg_w = int(968 * count / 35)
        cv.rect(x, 150, seg_w, 16, col)
        lab = "%s %d" % (name, count)
        fw = F("sans_b9").width(lab)
        if fw + 8 <= seg_w:
            F("sans_b9").draw(cv, x + (seg_w - int(fw)) // 2, 153, lab, (255, 255, 255))
        x += seg_w
    # ---- THE DAY IN NUMBERS: vertical panel on the right (bagarte's device,
    # cleaner here — dividers between items, red rule under the header, white
    # numbers on navy, one-line captions). Spans the hero row only, so both
    # mid rows are uniform width.
    px0, pw = 830, 166
    cv.rect(px0, 172, pw, 268, NAVY)
    F("sans_b11").draw_center(cv, px0 + pw // 2, 186, "THE DAY IN NUMBERS", (255, 255, 255))
    cv.rect(px0 + 33, 202, 100, 2, RED2)
    _nf = F("sans_b9")
    for i, (num, label) in enumerate(STATS):
        iy = 214 + i * 36
        F("serif_b26").draw_center(cv, px0 + pw // 2, iy, num, (255, 255, 255))
        for j, ln in enumerate(_nf.wrap(label, pw - 24)):
            _nf.draw_center(cv, px0 + pw // 2, iy + 30 + j * 11, ln, (208, 202, 190))
        if i:
            cv.hline(px0 + 16, iy - 6, pw - 32, (58, 68, 96))
    # ---- heroes (kevin's device: a full-width red label bar above each hero)
    # Narrowed to 252 px so the numbers panel fits on the right (bagarte's
    # layout: heroes + first mid row share the width left of the panel).
    # Scenes are 120 tall now (the strip removal freed 44 px): the Nvidia
    # arrow finally fits inside its scene instead of overflowing it.
    hw = 252
    for i, (n, place, topic, head, deck, _la, _lo, scene, _dx, _dy) in enumerate(HEROES):
        x = 28 + i * (hw + 16)
        y = 194
        cv.rect(x, 172, hw, 20, RED)
        cv.circle(x + 12, 182, 8, (255, 255, 255))
        F("sans_b9").draw_center(cv, x + 12, 179, str(n), RED)
        F("sans_b11").draw(cv, x + 30, 177, HERO_BAR[i], (255, 255, 255))
        cv.rect(x, 192, hw, 2, GOLD)
        SCENES[scene](cv, x, y, hw, 120)
        _kicker(cv, x, 320, "%d %s \u00b7 %s" % (n, place, topic),
                badge=BADGES[n], right_x=x + hw)
        _headline_deck(cv, x, 334, hw, head, deck, "serif_b22", "serif_r13", 24, 14)
    # ---- mids, two rows of five, uniform width (the numbers panel spans
    # only the hero row now, so both rows are full width — bagarte/kevin)
    mw = (968 - 4 * 10) // 5
    for row in range(2):
        cw = mw
        for col in range(5):
            s = MIDS[row * 5 + col]
            n, place, topic, head, deck, _la, _lo, scene, _dx, _dy = s
            x = 28 + col * (cw + 10)
            y = 446 + row * 156
            SCENES[scene](cv, x, y, cw, 66)
            _tag(cv, x + 3, y + 3, TAGS[scene])
            _num_circle(cv, x + cw - 12, y + 12, n, r=8)
            _kicker(cv, x, y + 70, "%d %s" % (n, MID_SHORT[n]),
                    badge=BADGES[n], right_x=x + cw, badge_src=False)
            _headline_deck(cv, x, y + 82, cw, head, deck,
                           "serif_b16", "serif_r11", 16, 11)
    # ---- bottom: map + briefs
    y0 = 754
    F("sans_b10").draw(cv, 28, y0, "WHERE IT HAPPENED", INK)
    F("sans_r9").draw(cv, 150, y0 + 1, "numbered pins = stories 1-13 \u00b7 dots = briefs 14-35", GREY)
    F("sans_b10").draw(cv, 428, y0, "THE REST OF THE DAY \u2014 22 MORE STORIES", INK)
    mx, my = 28, y0 + 16
    # Map is 380x190 now (was 290x145): 31% larger, so the Europe/Middle
    # East cluster gets real room — bagarte's map is crowded in the same
    # place, ours reads cleaner. Aspect kept 2:1 so the dot grid is square.
    mw2, mh2 = 380, 180
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
    # offline repulsion relaxation (see /tmp/map_layout4.py): every numbered
    # label centre is >= 15.3 px from every other (was 14.1), max offset
    # 25.5 px (was 23.1) — the wider spread is what clears the
    # Europe/Middle East cluster. An offset label gets a thin leader line
    # back to its true point, marked by a small dot. Pins without an entry
    # sit exactly on their true point.
    PIN_LABEL = {
        1: (0, 0), 2: (-6, -2), 3: (17, -1), 4: (9, -12), 5: (-3, 7),
        6: (-12, 4), 7: (-11, 6), 8: (-18, 13), 9: (1, 3), 10: (1, 0),
        11: (-5, 9), 12: (0, 0), 13: (-8, 3), 14: (-13, 3), 15: (5, -12),
        16: (12, -1), 17: (7, -15), 18: (3, -3), 19: (-15, 1), 20: (13, 4),
        21: (-1, -12), 22: (0, 0), 23: (3, 5), 24: (-1, -3), 25: (0, 0),
        26: (-5, -4), 27: (0, 2), 28: (-7, 14), 29: (3, 2), 30: (-14, 9),
        31: (18, -18), 32: (15, 1), 33: (2, 4), 34: (6, -1), 35: (3, -5),
    }

    def _pin(px, py, n, r=6):
        dx, dy = PIN_LABEL.get(n, (0, 0))
        lx, ly = px + dx, py + dy
        if dx or dy:
            cv.circle(px, py, 2, RED)
            cv.line(px, py, lx, ly, RED, 1)
        _num_circle(cv, lx, ly, n, r=r, solid=True)

    for s in all_stories:
        n, _pl, _tp, _hd, _dk, la, lo, _sc, dx, dy = s
        px = int(mx + (lo + 180) / 360.0 * mw2) + dx
        py = int(my + (86 - la) / 144.0 * mh2) + dy
        _pin(px, py, n)
    for s in BRIEFS:
        n, _pl, _tx, la, lo = s
        px = int(mx + (lo + 180) / 360.0 * mw2)
        py = int(my + (86 - la) / 144.0 * mh2)
        cv.circle(px, py, 2, RED)
    # briefs, two airy columns with numbered chips (bagarte/kevin's device):
    # items 14-24 in column 1, 25-35 in column 2, 16 px pitch.
    f = F("sans_r9")
    fb = F("sans_b9")
    for k, (n, place, text, _la, _lo) in enumerate(BRIEFS):
        if k < 11:
            bx, by = 428, 770 + k * 16
        else:
            bx, by = 716, 770 + (k - 11) * 16
        cv.rrect(bx, by, 16, 11, 2, RED)
        F("sans_b9").draw_center(cv, bx + 8, by + 1, str(n), (255, 255, 255))
        fb.draw(cv, bx + 20, by + 1, place.split(",")[0] + ":", RED)
        f.draw(cv, bx + 20 + int(fb.width(place.split(",")[0] + ": ")), by + 1, text, INK)
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
