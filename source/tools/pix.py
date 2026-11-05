"""Shared pixel helpers for the HALFTONE asset pipeline.

Pixel art is authored as ASCII grids:
  '.' = colour 0 (paper / transparent for sprites)
  '-' = colour 1 (pale ink)
  '+' = colour 2 (dark grey, phase-neutral)
  '#' = colour 3 (black ink)
Tiles are converted to the Game Boy 2bpp planar format (16 bytes per 8x8 tile).
"""
from __future__ import annotations
import struct, zlib

CH = {'.': 0, '-': 1, '+': 2, '#': 3}


def grid(s: str) -> list[list[int]]:
    rows = [r for r in s.strip('\n').split('\n')]
    rows = [r.rstrip() for r in rows if r.strip('\n') != '']
    w = max(len(r) for r in rows)
    out = []
    for r in rows:
        r = r.ljust(w, '.')
        out.append([CH[c] for c in r])
    return out


def check(g, w, h, name=''):
    assert len(g) == h, f'{name}: height {len(g)} != {h}'
    for row in g:
        assert len(row) == w, f'{name}: width {len(row)} != {w}'


def sub(g, x, y, w=8, h=8):
    return [row[x:x + w] for row in g[y:y + h]]


def tile_bytes(t) -> bytes:
    """8x8 grid of 0..3 -> 16 bytes GB 2bpp."""
    out = bytearray()
    for row in t:
        lo = hi = 0
        for px in row:
            lo = (lo << 1) | (px & 1)
            hi = (hi << 1) | ((px >> 1) & 1)
        out += bytes((lo, hi))
    return bytes(out)


def hflip(t):
    return [list(reversed(r)) for r in t]


def vflip(t):
    return [list(r) for r in reversed(t)]


def c_array(name, data: bytes, per_line=16, const=True, bank_pragma=None):
    lines = []
    lines.append(f'const unsigned char {name}[{len(data)}] = {{')
    for i in range(0, len(data), per_line):
        chunk = data[i:i + per_line]
        lines.append('    ' + ','.join(f'0x{b:02X}' for b in chunk) + ',')
    lines.append('};')
    return '\n'.join(lines) + '\n'


# --- tiny PNG writer (no PIL dependency) -------------------------------------
SHADES = [(0xF4, 0xF1, 0xE6), (0xB4, 0xB0, 0xA3), (0x56, 0x55, 0x50), (0x12, 0x12, 0x12)]


def write_png(path, pixels, scale=1, palette=SHADES):
    """pixels: 2D list of 0..3 values. Writes an RGB PNG scaled by integer."""
    h = len(pixels)
    w = len(pixels[0])
    raw = bytearray()
    for y in range(h):
        row = pixels[y]
        line = bytearray()
        for x in range(w):
            r, g, b = palette[row[x]]
            line += bytes((r, g, b)) * scale
        for _ in range(scale):
            raw += b'\x00' + line

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w * scale, h * scale, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)
