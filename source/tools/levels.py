"""HALFTONE level compiler. Levels are authored as ASCII metatile maps (16x16 px cells),
8 rows tall (128 px) and up to 64 columns wide (1024 px). Row 0 is the top.

Terrain:  . empty   # stone (auto top/fill variants)   I ink block   C chalk block
          ^ spikes  = one-way ledge   ~ ink pool surface (fills down automatically)
          S checkpoint (2 tall, char marks the base)   X exit (2 tall, char marks the base)
Decor:    a e (letters)  g gear  s stitch  d drip  c chain  p paper curl  t type  ! splat
Objects:  @ player start  * sort   B blot(ink)  b blot(chalk)  M moth(ink)  m moth(chalk)
          P press   D dripper (ink drops)  h horizontal platform  v vertical platform   O boss
Run: python3 tools/levels.py <outdir>  -> levels.c / levels.h
"""
import sys, os

MT = {}  # metatile ids are taken from art.py's META_ORDER
sys.path.insert(0, os.path.dirname(__file__))
import art
import backdrop
for i, name in enumerate(art.META_ORDER):
    MT[name] = i

OBJ_TYPES = ['NONE', 'SORT', 'BLOT', 'MOTH', 'PRESS', 'DRIPPER', 'PLAT_H', 'PLAT_V', 'BOSS']
OBJ = {n: i for i, n in enumerate(OBJ_TYPES)}

DECO = {'a': 'DECO_LETTER_A', 'e': 'DECO_LETTER_E', 'g': 'DECO_GEAR', 's': 'DECO_STITCH',
        'd': 'DECO_DRIP', 'c': 'DECO_CHAIN', 'p': 'DECO_PAPERCURL', 't': 'DECO_TYPE', '!': 'DECO_SPLAT'}

LEVELS = []


def level(name, music, pulse, rows, song_name=None):
    rows = [r for r in rows.strip('\n').split('\n')]
    w = max(len(r) for r in rows)
    assert len(rows) == 8, f'{name}: need 8 rows, got {len(rows)}'
    assert 10 <= w <= 64, f'{name}: width {w}'
    for i, r in enumerate(rows):
        assert len(r) == w, f'{name}: row {i} has {len(r)} columns, expected {w} (ragged rows hide alignment slips)'
    LEVELS.append(dict(name=name, music=music, pulse=pulse, rows=rows, w=w))


# ---------------------------------------------------------------------------
# Design rules (measured in the emulator): jump apex 32 px, so a two-cell step up is NOT reachable
# and a one-cell step is; a full-speed jump clears a 2-cell gap at equal height and a 3-cell gap
# only when landing lower.  Levels are built with place() so columns cannot slip between rows.

def grid(w):
    return [['.'] * w for _ in range(8)]


def place(g, row, col, text):
    """Write text into row starting at col; '.' in text is transparent."""
    for i, ch in enumerate(text):
        if ch != '.':
            g[row][col + i] = ch


def fill(g, row, c0, c1, ch):
    for c in range(c0, c1 + 1):
        g[row][c] = ch


def emit(name, music, pulse, g):
    level(name, music, pulse, '\n'.join(''.join(r) for r in g))


def pillar(g, c0, c1, ch, top):
    for c in range(c0, c1 + 1):
        for r in range(top, 8):
            g[r][c] = ch


def block(g, c0, c1, top):
    pillar(g, c0, c1, '#', top)


# PLATE 1 - MARGINS. Teaches: run, jump, the ink bridge, the first flip (ink wall), a blot.
g = grid(64)
block(g, 0, 5, 6); fill(g, 7, 6, 7, '#')              # start ground, one-deep trench at 6-7
block(g, 8, 14, 6); fill(g, 7, 15, 16, '#')           # ground, trench 15-16
block(g, 17, 22, 6)
place(g, 5, 19, '##'); place(g, 4, 20, '##')          # two 16 px steps up (sort on top)
fill(g, 7, 23, 24, '#')                               # trench 23-24
block(g, 25, 26, 6)
fill(g, 6, 27, 32, 'I')                               # INK BRIDGE over a real pit (nothing below)
block(g, 33, 36, 6); fill(g, 7, 37, 38, '#')          # trench 37-38
block(g, 39, 46, 6); fill(g, 7, 47, 48, '#')          # blot ground, trench 47-48
block(g, 49, 53, 6)
fill(g, 4, 53, 53, 'I'); fill(g, 5, 53, 53, 'I')      # INK WALL on the stone: flip to chalk to pass
fill(g, 6, 54, 55, 'C'); fill(g, 7, 54, 55, 'C')      # chalk floor over a pit (solid once flipped)
block(g, 56, 63, 6)
place(g, 5, 2, '@')
for (r, c) in [(5, 8), (5, 16), (3, 20), (5, 30), (4, 36), (5, 45), (4, 54)]: place(g, r, c, '*')
place(g, 5, 43, 'B')                                  # ink blot patrolling 39-46
place(g, 5, 34, 'a'); place(g, 5, 58, 'p')             # loose type and a paper curl on the floor
place(g, 5, 60, 'S'); place(g, 5, 62, 'X')
emit('MARGINS', 0, 0, g)

# PLATE 2 - GALLEY. Teaches: ink/chalk pillars, mid-air flips, spikes, the first moth and chalk blot.
# Pattern: stone (top row 6) -1 gap- pillar (top row 5) -2 gap- stone ...
g = grid(64)
fill(g, 7, 0, 63, '^')
block(g, 0, 3, 6); block(g, 6, 7, 6)
pillar(g, 9, 10, 'I', 5); block(g, 13, 14, 6)
pillar(g, 16, 17, 'C', 5); block(g, 20, 21, 6)
pillar(g, 23, 24, 'I', 5); block(g, 27, 28, 6)
pillar(g, 30, 31, 'C', 5); block(g, 34, 41, 6)
pillar(g, 43, 44, 'I', 5); block(g, 47, 48, 6)
pillar(g, 50, 51, 'C', 5); block(g, 54, 63, 6)
place(g, 5, 2, '@')
for (r, c) in [(5, 7), (3, 10), (3, 17), (5, 21), (3, 24), (3, 31), (5, 38), (3, 44), (3, 51)]: place(g, r, c, '*')
place(g, 5, 37, 'b'); place(g, 3, 40, 'm')
place(g, 5, 60, 'S'); place(g, 5, 62, 'X')
emit('GALLEY', 1, 0, g)

# PLATE 3 - INK WORKS. Teaches: deadly ink pools, drippers, a blot on an island, flip-then-jump.
g = grid(64)
fill(g, 6, 0, 63, '~'); fill(g, 7, 0, 63, '~')
block(g, 0, 3, 5)
pillar(g, 6, 7, 'C', 5); pillar(g, 10, 11, 'I', 5)
block(g, 14, 16, 5); pillar(g, 19, 21, 'C', 5)
block(g, 24, 27, 5)                                   # blot island
pillar(g, 30, 31, 'I', 5); pillar(g, 34, 35, 'C', 5)
block(g, 38, 41, 5)                                   # checkpoint island
pillar(g, 44, 46, 'I', 5); pillar(g, 49, 50, 'C', 5); pillar(g, 53, 54, 'I', 5)
block(g, 57, 63, 5)
place(g, 4, 2, '@')
for (r, c) in [(3, 7), (3, 11), (4, 15), (3, 20), (4, 31), (3, 35), (3, 45), (4, 50), (3, 54)]: place(g, r, c, '*')
place(g, 4, 26, 'B')
place(g, 0, 15, 'D'); place(g, 0, 40, 'D'); place(g, 0, 58, 'D')
place(g, 4, 39, 'S'); place(g, 4, 61, 'X')
emit('INK WORKS', 2, 0, g)

# PLATE 4 - BINDERY. Teaches: moving platforms, presses (crushers), stitches, a chalk blot.
g = grid(64)
fill(g, 7, 0, 63, '^')
block(g, 0, 4, 5)
place(g, 5, 7, 'h')                                   # platform rides x 104..152 at the stone's height
block(g, 12, 13, 5)
place(g, 5, 16, 'h')                                  # platform rides x 248..296
block(g, 21, 33, 5)                                   # press hall
place(g, 0, 23, 'P'); place(g, 0, 28, 'P')
block(g, 36, 37, 5)
block(g, 40, 47, 5)                                   # chalk blot ground + lift to a high sort
place(g, 3, 44, 'v')
place(g, 5, 49, 'h')                                  # platform rides x 776..824
block(g, 52, 53, 5)
block(g, 56, 63, 5)
place(g, 4, 2, '@')
for (r, c) in [(3, 8), (3, 13), (3, 17), (4, 25), (4, 31), (4, 37), (4, 46), (0, 44), (3, 50), (4, 58)]: place(g, r, c, '*')
place(g, 4, 42, 'b')
place(g, 3, 1, 's'); place(g, 3, 36, 's'); place(g, 2, 57, 's')
place(g, 4, 60, 'S'); place(g, 4, 62, 'X')
emit('BINDERY', 0, 0, g)

# PLATE 5 - PULSE. The world flips on its own every two seconds; blots of both inks.
g = grid(64)
fill(g, 7, 0, 63, '^')
block(g, 0, 4, 5)
pillar(g, 7, 8, 'I', 5); pillar(g, 11, 12, 'C', 5); pillar(g, 15, 16, 'I', 5)
block(g, 19, 22, 5)
pillar(g, 25, 26, 'C', 5); pillar(g, 29, 30, 'I', 5); pillar(g, 33, 34, 'C', 5)
block(g, 37, 40, 5)
pillar(g, 43, 44, 'I', 5); pillar(g, 47, 48, 'C', 5); pillar(g, 51, 52, 'I', 5)
block(g, 55, 63, 5)
place(g, 4, 2, '@')
place(g, 4, 21, 'B'); place(g, 4, 39, 'b'); place(g, 4, 58, 'B')
for (r, c) in [(3, 8), (3, 12), (3, 16), (4, 22), (3, 26), (3, 30), (3, 34), (3, 44), (3, 48), (3, 52)]: place(g, r, c, '*')
place(g, 4, 38, 'S'); place(g, 4, 61, 'X')
emit('PULSE', 1, 120, g)

# PLATE 6 - ROTARY. Gears, presses, moths and drippers together; the long combination room.
g = grid(64)
fill(g, 7, 0, 63, '^')
block(g, 0, 4, 5)
block(g, 7, 9, 5)                                     # moth island
pillar(g, 12, 14, 'I', 5)
block(g, 17, 20, 5)                                   # blot + press
pillar(g, 23, 23, 'C', 5); pillar(g, 26, 26, 'I', 5) # single-cell pillars: flip between them
block(g, 29, 31, 5)
pillar(g, 34, 36, 'C', 5)
block(g, 39, 42, 5)                                   # checkpoint + press
pillar(g, 45, 47, 'I', 5)
block(g, 50, 52, 5)                                   # dripper island
pillar(g, 55, 56, 'C', 5)
block(g, 59, 63, 5)
place(g, 4, 2, '@')
place(g, 3, 8, 'M'); place(g, 4, 18, 'B'); place(g, 3, 30, 'm'); place(g, 4, 51, 'b')
place(g, 0, 19, 'P'); place(g, 0, 41, 'P')
place(g, 0, 13, 'D'); place(g, 0, 51, 'D')
place(g, 2, 2, 'g'); place(g, 1, 31, 'g'); place(g, 2, 45, 'g')
for (r, c) in [(3, 13), (4, 20), (3, 23), (3, 26), (3, 35), (3, 46), (3, 52), (3, 56), (4, 61)]: place(g, r, c, '*')
place(g, 4, 40, 'S'); place(g, 4, 62, 'X')
emit('ROTARY', 2, 0, g)

# PLATE 7 - NEGATIVE. Faster pulse, few stones, everything at once.
g = grid(64)
fill(g, 7, 0, 63, '^')
block(g, 0, 2, 5)
pillar(g, 5, 6, 'C', 5); pillar(g, 9, 10, 'I', 5); pillar(g, 13, 14, 'C', 5)
block(g, 17, 20, 5)                                   # moth over stone
pillar(g, 23, 24, 'I', 5); pillar(g, 27, 28, 'C', 5)
block(g, 31, 34, 5)                                   # checkpoint 1 + ink blot
pillar(g, 37, 37, 'I', 5); pillar(g, 40, 40, 'C', 5); pillar(g, 43, 43, 'I', 5)
block(g, 46, 48, 5)                                   # checkpoint 2 + chalk blot
pillar(g, 51, 52, 'C', 5); pillar(g, 55, 56, 'I', 5)
block(g, 59, 63, 5)
place(g, 4, 1, '@')
place(g, 3, 18, 'm'); place(g, 4, 33, 'B'); place(g, 4, 47, 'b')
place(g, 0, 10, 'D'); place(g, 0, 28, 'D'); place(g, 0, 40, 'D'); place(g, 0, 55, 'D')
for (r, c) in [(3, 6), (3, 10), (3, 14), (4, 20), (3, 24), (3, 28), (3, 37), (3, 40), (3, 43), (3, 52), (3, 56)]: place(g, r, c, '*')
place(g, 4, 32, 'S'); place(g, 4, 46, 'S'); place(g, 4, 61, 'X')
emit('NEGATIVE', 1, 90, g)

# PLATE 8 - THE SMUDGE. Single fixed screen (10 cells = 160 px) boss arena.
g = grid(10)
fill(g, 7, 0, 9, '#')
pillar(g, 2, 2, 'I', 6); pillar(g, 7, 7, 'C', 6)      # one-cell footstools, one of each ink
place(g, 6, 4, '@'); place(g, 3, 4, 'O')
emit('THE SMUDGE', 3, 0, g)


def compile_level(L):
    rows = L['rows']; w = L['w']
    meta = [[MT['EMPTY']] * 8 for _ in range(w)]  # meta[col][row]
    objs = []
    start = None
    cols_with_pool = set()
    for y in range(8):
        for x in range(w):
            ch = rows[y][x]
            if ch == '.':
                continue
            if ch == '#':
                above = rows[y - 1][x] if y > 0 else '.'
                below = rows[y + 1][x] if y < 7 else '#'
                if above != '#':
                    meta[x][y] = MT['STONE_TOP']
                else:
                    # deep fill when fully surrounded horizontally too
                    left = rows[y][x - 1] if x > 0 else '#'
                    right = rows[y][x + 1] if x < w - 1 else '#'
                    if left == '#' and right == '#' and below == '#':
                        meta[x][y] = MT['STONE_FILL']
                    else:
                        meta[x][y] = MT['STONE']
            elif ch == 'I':
                meta[x][y] = MT['INK']
            elif ch == 'C':
                meta[x][y] = MT['CHALK']
            elif ch == '^':
                meta[x][y] = MT['SPIKES']
            elif ch == '=':
                meta[x][y] = MT['LEDGE']
            elif ch == '~':
                above = rows[y - 1][x] if y > 0 else '.'
                meta[x][y] = MT['POOL'] if above == '~' else MT['POOL_TOP']
            elif ch == 'S':
                meta[x][y] = MT['CP_POST']
                assert y > 0 and rows[y - 1][x] == '.', f"{L['name']}: checkpoint needs empty cell above"
                meta[x][y - 1] = MT['CP_HEAD']
            elif ch == 'X':
                meta[x][y] = MT['EXIT_BOT']
                assert y > 0 and rows[y - 1][x] == '.', f"{L['name']}: exit needs empty cell above"
                meta[x][y - 1] = MT['EXIT_TOP']
            elif ch in DECO:
                meta[x][y] = MT[DECO[ch]]
            elif ch == '@':
                start = (x, y)
            elif ch == '*':
                objs.append((OBJ['SORT'], x, y, 0))
            elif ch == 'B':
                objs.append((OBJ['BLOT'], x, y, 0))
            elif ch == 'b':
                objs.append((OBJ['BLOT'], x, y, 1))
            elif ch == 'M':
                objs.append((OBJ['MOTH'], x, y, 0))
            elif ch == 'm':
                objs.append((OBJ['MOTH'], x, y, 1))
            elif ch == 'P':
                objs.append((OBJ['PRESS'], x, y, 0))
            elif ch == 'D':
                objs.append((OBJ['DRIPPER'], x, y, 0))
            elif ch == 'h':
                objs.append((OBJ['PLAT_H'], x, y, 0))
            elif ch == 'v':
                objs.append((OBJ['PLAT_V'], x, y, 0))
            elif ch == 'O':
                objs.append((OBJ['BOSS'], x, y, 0))
            else:
                raise SystemExit(f"{L['name']}: unknown char {ch!r} at {x},{y}")
    assert start is not None, f"{L['name']}: no start"
    # backdrop: every cell that is still EMPTY (plain paper) may receive a non-solid colour-2 backdrop metatile
    for (bx, by), bname in backdrop.paint(L['name'], w, rows).items():
        if 0 <= bx < w and 0 <= by < 8 and meta[bx][by] == MT['EMPTY']:
            meta[bx][by] = MT[bname]
    assert len(objs) <= 24, f"{L['name']}: too many objects ({len(objs)})"
    # order objects by x so spawn scanning is cheap
    objs.sort(key=lambda o: (o[1], o[2]))
    return meta, objs, start


def build(outdir):
    os.makedirs(outdir, exist_ok=True)
    c = ['/* Generated by tools/levels.py - HALFTONE level data */', '#include <stdint.h>',
         '#include "levels.h"', '#pragma bank 2', '']
    h = ['/* Generated by tools/levels.py */', '#ifndef LEVELS_H', '#define LEVELS_H', '#include <stdint.h>',
         f'#define LEVEL_COUNT {len(LEVELS)}', '#define LEVEL_MAX_W 64',
         'typedef struct { uint8_t type, x, y, param; } LevelObj;',
         'typedef struct { uint8_t width; uint8_t music; uint8_t pulse; uint8_t nobjs; uint8_t start_x, start_y;',
         '  const uint8_t *map; const LevelObj *objs; const char *name; } LevelDef;',
         'extern const LevelDef level_defs[];']
    for i, n in enumerate(OBJ_TYPES):
        h.append(f'#define OBJ_{n} {i}')
    for li, L in enumerate(LEVELS):
        meta, objs, start = compile_level(L)
        flat = bytes(meta[x][y] for x in range(L['w']) for y in range(8))
        c.append(f'static const uint8_t lv{li}_map[{len(flat)}] = {{')
        for x in range(L['w']):
            c.append('    ' + ','.join(str(b) for b in flat[x * 8:(x + 1) * 8]) + ',')
        c.append('};')
        c.append(f'static const LevelObj lv{li}_objs[{max(1, len(objs))}] = {{')
        for o in objs or [(0, 0, 0, 0)]:
            c.append('    {%d,%d,%d,%d},' % o)
        c.append('};')
        c.append(f'static const char lv{li}_name[] = "{L["name"]}";')
    c.append('const LevelDef level_defs[LEVEL_COUNT] = {')
    for li, L in enumerate(LEVELS):
        meta, objs, start = compile_level(L)
        c.append(f'    {{ {L["w"]}, {L["music"]}, {L["pulse"]}, {len(objs)}, {start[0]}, {start[1]}, lv{li}_map, lv{li}_objs, lv{li}_name }},')
    c.append('};')
    h.append('#endif')
    with open(os.path.join(outdir, 'levels.c'), 'w') as f:
        f.write('\n'.join(c) + '\n')
    with open(os.path.join(outdir, 'levels.h'), 'w') as f:
        f.write('\n'.join(h) + '\n')
    total = sum(L['w'] * 8 for L in LEVELS)
    print(f'{len(LEVELS)} levels, {total} map bytes')
    # text preview
    with open(os.path.join(outdir, 'levels_preview.txt'), 'w') as f:
        for L in LEVELS:
            f.write(f"== {L['name']} (w={L['w']}, pulse={L['pulse']})\n")
            f.write('\n'.join(L['rows']) + '\n\n')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'gen')
