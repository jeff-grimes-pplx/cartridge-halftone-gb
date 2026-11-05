#!/usr/bin/env python3
"""Convert an emulator-frame input script to the game's own frame clock.

The solver and the first replays timed inputs in emulator frames counted from the origin.  During a
display-off level load the game's loop is paused while the emulator keeps counting frames, and the
two emulators finish that load one frame apart, so emulator-frame scripts are not portable.  The
game increments `g_frame` once per loop iteration right after vsync, and that iteration is the one
that reads the joypad, so an event applied at emulator frame f is seen by the iteration whose
g_frame equals the trace's g_frame column at row f.  Rewriting every event to that value gives a
script both runners replay identically with `--input-clock gframe`.

usage: to_gframe.py script.txt sameboy_trace.csv out.txt
"""
import csv, sys


def convert(script, trace, out):
    """An event applied at emulator frame f is first observed by the game iteration that starts at or
    after frame f (iterations read the joypad right after they start).  Events inside a display-off
    stall therefore all land on the first iteration after the stall; the last one wins, exactly as the
    game saw it."""
    rows = [(int(r['frame']), int(r['g_frame'])) for r in csv.DictReader(open(trace)) if int(r['frame']) >= 0]
    first_row = {}
    for f, g in rows:
        first_row.setdefault(g, f)
    starts = sorted((f, g) for g, f in first_row.items())

    def observer(f):
        for sf, g in starts:
            if sf >= f:
                return g
        raise SystemExit(f'{script}: frame {f} is beyond the trace ({rows[-1][0]})')

    lines = []
    for line in open(script):
        raw = line.rstrip('\n')
        s = raw.strip()
        if not s or s.startswith('#'):
            lines.append(raw); continue
        f, mask = s.split()[:2]
        lines.append(f'{observer(int(f))} {mask}')
    with open(out, 'w') as fo:
        fo.write('# clock: gframe (times are the game frame counter g_frame; replay with --input-clock gframe)\n')
        fo.write('\n'.join(lines) + '\n')
    return out


if __name__ == '__main__':
    convert(*sys.argv[1:4])
    print('wrote', sys.argv[3])
