"""HALFTONE backdrops: non-solid 16x16 metatiles drawn only in colour 2 (phase-neutral dark grey), so they
look the same in INK and CHALK and never read as ink/chalk material. Distant shapes are drawn as dotted or
dashed outlines (a printed, "halftoned" distance), never as filled dark blocks (those are stone).

The tiles live in BG slots 192..255 (the title logo's slots, reloaded on the title) and are baked into the
level maps by levels.py, so the engine streams them like any other tile: zero runtime cost, class EMPTY.

paint(level_name, w, rows) -> {(x, y): 'BD_NAME'} decides, per plate, which backdrop goes into each empty cell.
"""
import random

W = H = 16
C = 2  # the only colour used


def canvas():
    return [[0] * W for _ in range(H)]


def px(c, x, y):
    if 0 <= x < W and 0 <= y < H:
        c[y][x] = C


def hline(c, y, x0, x1, on=1, off=0, phase=0):
    for x in range(x0, x1 + 1):
        if off == 0 or (x + phase) % (on + off) < on:
            px(c, x, y)


def vline(c, x, y0, y1, on=1, off=0, phase=0):
    for y in range(y0, y1 + 1):
        if off == 0 or (y + phase) % (on + off) < on:
            px(c, x, y)


def dither(c, x0, y0, x1, y1, density):
    """ordered dither: density in {12, 25, 50} percent"""
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if density == 50 and (x + y) % 2 == 0: px(c, x, y)
            elif density == 25 and (x + 2 * y) % 4 == 0: px(c, x, y)
            elif density == 12 and (x % 4 == 0 and y % 4 == 0 or x % 4 == 2 and y % 4 == 2): px(c, x, y)
            elif density == 6 and x % 4 == 0 and y % 4 == 0: px(c, x, y)


BD = {}


def reg(name, c):
    BD[name] = c
    return c


# ---- paper texture and tonal bands -------------------------------------------------------------------
c = canvas(); px(c, 2, 1); px(c, 6, 5); px(c, 10, 1); px(c, 14, 5); px(c, 2, 9); px(c, 6, 13); px(c, 10, 9); px(c, 14, 13)
reg('BD_SPECK_A', c)
for d in (12, 25, 50):
    c = canvas(); dither(c, 0, 0, 15, 15, d); reg(f'BD_DITHER{d}', c)
c = canvas(); dither(c, 0, 0, 15, 7, 50); dither(c, 0, 8, 15, 15, 25); reg('BD_FADE_50_25', c)
c = canvas(); dither(c, 0, 0, 15, 7, 25); dither(c, 0, 8, 15, 15, 12); reg('BD_FADE_25_12', c)
c = canvas(); dither(c, 0, 0, 15, 7, 12); reg('BD_FADE_12_0', c)

# ---- the printed page (MARGINS) ------------------------------------------------------------------------
def greek(c, y, pattern, phase=0):
    """a line of 'text': dashes of the given lengths separated by 1 px, starting at x=phase"""
    x = phase
    for L in pattern:
        hline(c, y, x, x + L - 1); x += L + 1
        if x >= W: break

c = canvas(); greek(c, 3, (4, 2, 5, 3)); greek(c, 11, (2, 6, 3, 4), 1); reg('BD_TEXT_A', c)
c = canvas(); greek(c, 3, (6, 3, 2)); reg('BD_TEXT_END', c)              # paragraph end: one short line
c = canvas(); hline(c, 7, 0, 15, 1, 1); reg('BD_RULE', c)                # dotted horizontal rule
c = canvas(); vline(c, 7, 0, 15, 1, 1); reg('BD_MARGIN', c)              # dotted vertical margin
c = canvas(); hline(c, 2, 2, 7); vline(c, 2, 2, 7); reg('BD_CORNER_TL', c)
c = canvas(); hline(c, 2, 8, 13); vline(c, 13, 2, 7); reg('BD_CORNER_TR', c)

# ---- type cases, shelves and books (GALLEY, BINDERY) ---------------------------------------------------
c = canvas()
for k in (7, 15):
    hline(c, k, 0, 15); vline(c, k, 0, 15)
reg('BD_PIGEON', c)                                                       # 8 px pigeonhole grid
c2 = [row[:] for row in c]
for (ox, oy) in ((0, 0), (8, 8)):
    px(c2, ox + 3, oy + 3); px(c2, ox + 4, oy + 3); px(c2, ox + 3, oy + 4); px(c2, ox + 4, oy + 4)
reg('BD_PIGEON_T', c2)                                                    # ...with a sort left in two holes
c = canvas(); hline(c, 13, 0, 15); hline(c, 14, 0, 15, 1, 1); vline(c, 2, 9, 12); vline(c, 10, 9, 12); reg('BD_SHELF', c)
c = canvas(); hline(c, 14, 0, 15); reg('BD_SHELF_LINE', c)

def books(c, spines, y1=13):
    """hollow books standing on a shelf: (x, width, height) triples"""
    for x, wdt, h in spines:
        top = y1 - h + 1
        vline(c, x, top, y1); vline(c, x + wdt - 1, top, y1); hline(c, top, x, x + wdt - 1)
        if h >= 9: hline(c, top + 3, x + 1, x + wdt - 2, 1, 1)
    hline(c, y1 + 1, 0, 15)

c = canvas(); books(c, ((1, 4, 11), (5, 3, 9), (9, 5, 12))); reg('BD_BOOKS', c)

# ---- pipes and vats (INK WORKS) ------------------------------------------------------------------------
c = canvas(); hline(c, 5, 0, 15); hline(c, 10, 0, 15); hline(c, 7, 0, 15, 1, 3); hline(c, 8, 0, 15, 1, 3, 2); reg('BD_PIPE_H', c)
c = canvas(); vline(c, 5, 0, 15); vline(c, 10, 0, 15); vline(c, 7, 0, 15, 1, 3); vline(c, 8, 0, 15, 1, 3, 2); reg('BD_PIPE_V', c)
c = canvas(); vline(c, 5, 0, 9); vline(c, 10, 0, 9); vline(c, 7, 0, 9, 1, 3); vline(c, 8, 0, 9, 1, 3, 2)
hline(c, 10, 3, 12); hline(c, 11, 4, 11); px(c, 7, 13); px(c, 8, 13); px(c, 7, 14); px(c, 8, 14); reg('BD_PIPE_END', c)
c = canvas(); hline(c, 3, 0, 15); hline(c, 4, 0, 15); hline(c, 15, 1, 14)
for x in (0, 1, 14, 15): vline(c, x, 5, 14)
dither(c, 2, 9, 13, 14, 50); hline(c, 9, 2, 13); reg('BD_VAT', c)             # ink vat, half full

# ---- wheels, belts and rollers (PULSE, ROTARY) ---------------------------------------------------------
def big_wheel(r=14, cx=16, cy=16, spokes=4):
    """32x32 dotted wheel split into 4 metatiles (TL, TR, BL, BR)"""
    import math
    big = [[0] * 32 for _ in range(32)]
    n = int(2 * math.pi * r)
    for k in range(0, n, 2):
        a = 2 * math.pi * k / n
        x = int(round(cx + r * math.cos(a))); y = int(round(cy + r * math.sin(a)))
        if 0 <= x < 32 and 0 <= y < 32: big[y][x] = C
    for k in range(spokes):
        a = math.pi * k / spokes + math.pi / 8
        for t in range(4, r - 1, 2):
            x = int(round(cx + t * math.cos(a))); y = int(round(cy + t * math.sin(a)))
            big[y][x] = C; big[31 - y][31 - x] = C
    for y in range(cy - 3, cy + 3):
        for x in range(cx - 3, cx + 3):
            if (x - cx + 0.5) ** 2 + (y - cy + 0.5) ** 2 <= 9: big[y][x] = C
    parts = {}
    for name, ox, oy in (('TL', 0, 0), ('TR', 16, 0), ('BL', 0, 16), ('BR', 16, 16)):
        parts[name] = [row[ox:ox + 16] for row in big[oy:oy + 16]]
    return parts

for k, v in big_wheel().items():
    reg('BD_WHEEL_' + k, v)
c = canvas(); hline(c, 2, 0, 15, 3, 1); reg('BD_BELT_T', c)                   # line shaft running over the wheels' tops
# (no return line under the wheels: a second dashed line sat in the jump band 17 px above the ledges and could be
#  misread as a thin one-way ledge - independent review v2, issue 2)
c = canvas(); hline(c, 3, 0, 15); hline(c, 12, 0, 15); hline(c, 6, 0, 15, 1, 3, 1); hline(c, 9, 0, 15, 1, 3, 3); vline(c, 4, 4, 11, 1, 1); vline(c, 12, 4, 11, 1, 1); reg('BD_ROLLER', c)

# ---- press frame, windows, lamps -----------------------------------------------------------------------
c = canvas(); vline(c, 6, 0, 15); vline(c, 9, 0, 15); vline(c, 7, 0, 15, 1, 1); vline(c, 8, 0, 15, 1, 1, 1); reg('BD_POST', c)
c = canvas(); hline(c, 6, 0, 15); hline(c, 9, 0, 15); hline(c, 7, 0, 15, 1, 1); hline(c, 8, 0, 15, 1, 1, 1); px(c, 3, 5); px(c, 11, 5); reg('BD_BEAM', c)
c = canvas(); hline(c, 1, 2, 13); hline(c, 14, 2, 13); vline(c, 2, 1, 14); vline(c, 13, 1, 14); vline(c, 7, 2, 13, 1, 1); hline(c, 7, 3, 12, 1, 1)
dither(c, 3, 2, 12, 13, 6); reg('BD_WINDOW', c)
c = canvas(); vline(c, 7, 0, 8, 1, 1); hline(c, 9, 5, 9); hline(c, 10, 4, 10); hline(c, 11, 3, 11); hline(c, 12, 2, 13); px(c, 7, 14); reg('BD_LAMP', c)

# ---- per-plate painters ---------------------------------------------------------------------------------
# Each painter returns the backdrop name for an empty cell, or None. x is the column (0..w-1), y the row (0..7).
# Rows 6-7 are the floor band in every plate; backdrops stop above the floor so pits stay plain paper.

def _rng(seed):
    return random.Random(seed)


def paint_margins(w, rows, R):
    out = {}
    for x in range(w):
        for y in range(8):
            if y == 0 and x in (1, w - 2): out[(x, y)] = 'BD_CORNER_TL' if x == 1 else 'BD_CORNER_TR'
            elif y in (1, 2, 3) and 3 <= x <= w - 4:
                out[(x, y)] = 'BD_TEXT_END' if x % 9 == 8 else ('BD_TEXT_A' if (x + y) % 2 == 0 else 'BD_TEXT_B')
            elif y == 4 and 3 <= x <= w - 4: out[(x, y)] = 'BD_RULE'
            elif y in (1, 2, 3, 4) and x in (1, w - 2): out[(x, y)] = 'BD_MARGIN'
            elif y == 5 and R.random() < 0.25: out[(x, y)] = 'BD_SPECK_A'
    return out


def paint_galley(w, rows, R):
    out = {}
    for x in range(w):
        for y in range(8):
            if y == 0: out[(x, y)] = 'BD_FADE_25_12'
            elif y in (1, 2):
                if x % 11 == 5: out[(x, y)] = 'BD_LAMP' if y == 1 else None
                else: out[(x, y)] = 'BD_PIGEON_T' if (x * 7 + y * 3) % 5 == 0 else 'BD_PIGEON'
            elif y == 3: out[(x, y)] = 'BD_SHELF'
            elif y == 5 and R.random() < 0.25: out[(x, y)] = 'BD_SPECK_A'
    return out


def paint_inkworks(w, rows, R):
    out = {}
    for x in range(w):
        out[(x, 0)] = 'BD_PIPE_H'
        if x % 10 == 4:
            out[(x, 1)] = 'BD_PIPE_V'; out[(x, 2)] = 'BD_PIPE_V'; out[(x, 3)] = 'BD_PIPE_END'; out[(x, 4)] = 'BD_VAT'
        elif x % 10 in (8, 9):
            out[(x, 4)] = 'BD_ROLLER'
        elif x % 10 == 1:
            out[(x, 2)] = 'BD_LAMP'
        if R.random() < 0.25: out[(x, 5)] = 'BD_SPECK_A'
    return out


def paint_bindery(w, rows, R):
    out = {}
    for x in range(w):
        out[(x, 0)] = 'BD_FADE_12_0'
        out[(x, 1)] = 'BD_WINDOW' if x % 13 == 6 else None
        out[(x, 2)] = 'BD_BOOKS' if x % 3 != 1 else 'BD_SHELF_LINE'
        out[(x, 3)] = 'BD_LAMP' if x % 13 == 12 else None
        out[(x, 4)] = 'BD_BOOKS' if x % 3 != 2 else 'BD_SHELF_LINE'
        if R.random() < 0.2: out[(x, 5)] = 'BD_SPECK_A'
    return out


def _wheels(out, w, period, row0, phase=0, belts=True):
    for x in range(phase, w - 1, period):
        out[(x, row0)] = 'BD_WHEEL_TL'; out[(x + 1, row0)] = 'BD_WHEEL_TR'
        out[(x, row0 + 1)] = 'BD_WHEEL_BL'; out[(x + 1, row0 + 1)] = 'BD_WHEEL_BR'
    if belts:
        for x in range(phase, w):
            if out.get((x, row0)) is None: out[(x, row0)] = 'BD_BELT_T'


def paint_pulse(w, rows, R):
    out = {}
    for x in range(w):
        out[(x, 0)] = 'BD_FADE_25_12'
        out[(x, 4)] = 'BD_ROLLER' if x % 7 in (4, 5) else None
    _wheels(out, w, 7, 1, 1)
    return out


def paint_rotary(w, rows, R):
    out = {}
    for x in range(w):
        out[(x, 0)] = 'BD_ROLLER'
        out[(x, 1)] = 'BD_LAMP' if x % 9 == 7 else None
        if R.random() < 0.2: out[(x, 5)] = 'BD_SPECK_A'
    _wheels(out, w, 9, 2, 3)
    return out


def paint_negative(w, rows, R):
    out = {}
    for x in range(w):
        out[(x, 0)] = 'BD_DITHER50'
        out[(x, 1)] = 'BD_FADE_50_25'
        out[(x, 2)] = 'BD_FADE_25_12'
        out[(x, 3)] = 'BD_FADE_12_0'
        if R.random() < 0.2: out[(x, 5)] = 'BD_SPECK_A'
    return out


# The boss plate may only use these backdrops: their tiles are allocated below OBJ/BG slot 208, where the
# boss's sprite tiles live (art.py asserts it). Keep the arena calm so the boss silhouette owns the screen.
BOSS_PLATE_NAMES = {'BD_BEAM', 'BD_POST', 'BD_LAMP', 'BD_RULE', 'BD_SHELF_LINE', 'BD_SPECK_A'}


def paint_boss(w, rows, R):
    out = {}
    for x in range(w):
        out[(x, 0)] = 'BD_BEAM'
        for y in (1, 2, 3, 4, 5):
            out[(x, y)] = 'BD_POST' if x in (0, w - 1) else None
    out[(2, 1)] = 'BD_LAMP'; out[(w - 3, 1)] = 'BD_LAMP'
    for x in range(1, w - 1):
        out[(x, 5)] = 'BD_RULE'
    assert all(v is None or v in BOSS_PLATE_NAMES for v in out.values())
    return out


PAINTERS = {'MARGINS': paint_margins, 'GALLEY': paint_galley, 'INK WORKS': paint_inkworks, 'BINDERY': paint_bindery,
            'PULSE': paint_pulse, 'ROTARY': paint_rotary, 'NEGATIVE': paint_negative, 'THE SMUDGE': paint_boss}


def paint(level_name, w, rows):
    R = _rng(hash(level_name) & 0xFFFF if False else sum(ord(ch) for ch in level_name))
    out = PAINTERS[level_name](w, rows, R)
    return {k: ALIAS.get(v, v) for k, v in out.items() if v}


ALIAS = {'BD_SPECK_B': 'BD_SPECK_A', 'BD_TEXT_B': 'BD_TEXT_A'}
BD_ORDER = list(BD.keys())
