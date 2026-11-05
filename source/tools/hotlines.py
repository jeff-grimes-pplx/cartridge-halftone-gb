#!/usr/bin/env python3
"""Attribute sameboy_profiler --dump counts to C source lines using the SDCC .rst listings.
Usage: hotlines.py DUMP build/*.rst [--top N] [--frames F]"""
import sys, re, collections
dump = sys.argv[1]; rsts = [a for a in sys.argv[2:] if a.endswith('.rst')]
top = 40; frames = 1
if '--top' in sys.argv: top = int(sys.argv[sys.argv.index('--top') + 1])
if '--frames' in sys.argv: frames = int(sys.argv[sys.argv.index('--frames') + 1])
addr2line = {}
for rst in rsts:
    cur = None
    for line in open(rst, errors='replace'):
        m = re.match(r'\s*\d+\s+;(src/[\w./]+:\d+):', line)
        if m: cur = m.group(1); continue
        m = re.match(r'\s{4}([0-9A-F]{8}) [0-9A-F]{2}', line)
        if m and cur: addr2line[int(m.group(1), 16)] = cur
counts = collections.Counter(); total = 0; unmapped = 0
for line in open(dump):
    a, n = line.split(); a = int(a, 16); n = int(n)
    total += n
    key = addr2line.get(a)
    if key is None:
        # bank-0 code in the listing has bank 0 prefix; try without bank
        key = addr2line.get(a & 0xFFFF)
    if key is None: unmapped += n; key = '?'
    counts[key] += n
print(f'total {total} instr over {frames} frames = {total/frames:.0f}/frame; unmapped {unmapped}')
for k, n in counts.most_common(top):
    print(f'{n/frames:8.0f}/frame {100*n/total:5.1f}%  {k}')
