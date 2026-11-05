#!/usr/bin/env python3
"""Run the emulator-in-the-loop solver (plates 1-7) or the reactive boss policy (plate 8) on each plate independently (from a synthesised save that
makes the title's CONTINUE entry start at that plate) and report completability.

Usage: solve_plates.py [--plates 0,1,...] [--out DIR] [--max-nodes N] [--time-limit S] [--jobs 2]
"""
import argparse, os, re, subprocess, sys, concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playtest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
BIN = os.environ.get('A5_BIN', '/tmp/a5-tools/bin')
BOOT = os.environ.get('A5_BOOT', '/tmp/a5-tools/SameBoy/build/bin/tester/dmg_boot.bin')
TIME_BUCKET = {3: 16}                             # plate 4 (BINDERY) has moving platforms (96-frame cycle)
EXTRA = {3: ['--time-mod', '96', '--no-flip']}     # no ink/chalk tiles in plate 4: flipping is never needed


def exit_x(level_index):
    """World x of the exit door's centre minus the player's half width, from the level preview."""
    txt = open(os.path.join(SRC, 'gen', 'levels_preview.txt')).read().split('== ')[1:]
    rows = txt[level_index].split('\n')[1:9]
    for r in rows:
        if 'X' in r:
            return r.index('X') * 16 - 8 + 8   # door centre x == player centre (px + 8)
    return None


def solve_one(plate, args):
    out = os.path.join(args.out, f'plate{plate + 1}')
    os.makedirs(out, exist_ok=True)
    rom = os.path.join(SRC, 'build', 'HALFTONE.gb')
    noi = os.path.join(SRC, 'build', 'HALFTONE.noi')
    sav = os.path.join(out, 'start.sav')
    playtest.make_sram(sav, plate)
    prefix = os.path.join(out, 'prefix.txt')
    open(prefix, 'w').write('0 0\n60 128\n63 0\n')          # START on the title (CONTINUE is preselected with a save)
    if plate == 7:
        # the boss fight is a 150+ frame cycle: a per-frame reactive policy (sameboy_bossbot) instead of macro search
        cmd = [os.path.join(BIN, 'sameboy_bossbot'), '--boot', BOOT, '--noi', noi, '--prefix', prefix, '--level', str(plate),
               '--out', os.path.join(out, 'solution.txt'), '--log', os.path.join(out, 'search.log'), '--sram-in', sav, rom]
    else:
        cmd = [os.path.join(BIN, 'sameboy_solver'), '--boot', BOOT, '--noi', noi, '--prefix', prefix, '--level', str(plate),
               '--out', os.path.join(out, 'solution.txt'), '--log', os.path.join(out, 'search.log'), '--sram-in', sav,
               '--max-nodes', str(args.max_nodes), '--time-limit', str(args.time_limit), '--goal-x', str(exit_x(plate))]
        if plate in TIME_BUCKET:                      # moving platforms: waiting must count as a new state
            cmd += ['--time-bucket', str(TIME_BUCKET[plate])]
        cmd += EXTRA.get(plate, [])
        if args.allow_hurt:
            cmd += ['--allow-hurt']
        cmd.append(rom)
    open(os.path.join(out, 'cmd.txt'), 'w').write(' '.join(cmd) + '\n')
    r = subprocess.run(cmd, capture_output=True, text=True)
    open(os.path.join(out, 'solver.stderr'), 'w').write(r.stderr)
    last = r.stderr.strip().split('\n')[-1] if r.stderr.strip() else ''
    return plate, r.returncode, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plates', default='0,1,2,3,4,5,6,7')
    ap.add_argument('--out', default='/tmp/a5-work/solve')
    ap.add_argument('--max-nodes', type=int, default=3000)
    ap.add_argument('--time-limit', type=int, default=1500)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--allow-hurt', action='store_true')
    args = ap.parse_args()
    plates = [int(p) for p in args.plates.split(',')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for plate, rc, last in ex.map(lambda p: solve_one(p, args), plates):
            print(f'plate {plate + 1}: rc={rc} {last}', flush=True)


if __name__ == '__main__':
    main()
