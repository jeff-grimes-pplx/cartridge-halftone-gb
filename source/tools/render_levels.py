"""Fast art loop: render every plate (terrain + backdrop metatiles, no sprites) to PNG in the paper palette,
straight from the Python art/level sources, so backdrop composition can be judged without building the ROM.

usage: python3 render_levels.py OUTDIR [scale]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import art
import levels
from pix import grid, write_png

PAPER = [(0xF3, 0xEF, 0xE5), (0xA9, 0xA3, 0x94), (0x5D, 0x59, 0x4F), (0x1A, 0x18, 0x14)]


def render(L, scale):
    meta, objs, start = levels.compile_level(L)
    w = L['w']
    pix = [[0] * (w * 16) for _ in range(8 * 16)]
    grids = {i: grid(art.META[name]) for i, name in enumerate(art.META_ORDER)}
    for x in range(w):
        for y in range(8):
            g = grids[meta[x][y]]
            for yy in range(16):
                row = pix[y * 16 + yy]
                src = g[yy]
                for xx in range(16):
                    row[x * 16 + xx] = src[xx]
    # object markers: a 1-px colour-3 box at each object's cell, start cell marked with a dot
    for (t, ox, oy, p) in objs:
        for k in range(16):
            for (px_, py_) in ((ox * 16 + k, oy * 16), (ox * 16 + k, oy * 16 + 15), (ox * 16, oy * 16 + k), (ox * 16 + 15, oy * 16 + k)):
                if 0 <= px_ < w * 16 and 0 <= py_ < 128:
                    pix[py_][px_] = 3 if (k % 2 == 0) else pix[py_][px_]
    return pix


def main():
    outdir = sys.argv[1]
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    os.makedirs(outdir, exist_ok=True)
    for i, L in enumerate(levels.LEVELS):
        pix = render(L, scale)
        path = os.path.join(outdir, f'plate{i + 1}_{L["name"].replace(" ", "_").lower()}.png')
        write_png(path, pix, scale=scale, palette=PAPER)
        print(path, f'{L["w"] * 16}x128')


if __name__ == '__main__':
    main()
