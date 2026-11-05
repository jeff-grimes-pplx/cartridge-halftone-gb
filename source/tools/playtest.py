#!/usr/bin/env python3
"""HALFTONE scripted playtest harness.

Compiles a compact input plan into the runner's `frame mask` script, runs the ROM in the
SameBoy (or mGBA) runner with the game's probe variables attached, and summarises the trace:
state changes, hearts, deaths, level transitions, worst-case CPU/sprite budget.

Plan format (one segment per line, '#' comments):
    <buttons> <frames>      hold these buttons for N frames.  buttons: R L U D A B S(elect) T(start) or '-'
    @<frame>                jump the cursor to an absolute script frame (padding with no input)
Example:
    T 2        # press START on the title
    - 150      # wait through the intro card
    R 40       # run right
    RA 8       # jump while running
    R 60

Usage:
    playtest.py --rom ROM --plan PLAN.txt [--level N] [--emu sameboy|mgba] [--frames N]
                [--png f1,f2,...] [--out DIR] [--until g_ending_reached==1] [--sram-in FILE] [--sram-out FILE]
With --level N a save file for plate N (0-based) is synthesised and loaded so that the title's
CONTINUE entry (selected by default when a save exists) starts that plate.
"""
import argparse, csv, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
TOOLS = os.path.join(os.path.dirname(SRC), 'tools')
BIN = os.environ.get('A5_BIN', '/tmp/a5-tools/bin')
BOOT = os.environ.get('A5_BOOT', '/tmp/a5-tools/SameBoy/build/bin/tester/dmg_boot.bin')

MASK = {'R': 1, 'L': 2, 'U': 4, 'D': 8, 'A': 16, 'B': 32, 'S': 64, 'T': 128}
ST = ['BOOT', 'TITLE', 'INTRO', 'PLAY', 'DEATH', 'CLEAR', 'ENDING', 'PAUSE', 'BOSS_DEAD']
LEVEL_COUNT = 8


def probes(noi):
    """Read the game's debug variables from the linker .noi file."""
    out = {}
    for line in open(noi):
        m = re.match(r'DEF _(g_\w+) 0x([0-9A-Fa-f]+)', line)
        if m:
            out[m.group(1)] = int(m.group(2), 16)
    return out


def compile_plan(path):
    """Return (lines, total_frames) in the runner's `frame mask` format."""
    lines = []
    cur = 0
    last_mask = None
    for raw in open(path):
        s = raw.split('#', 1)[0].strip()
        if not s:
            continue
        if s.startswith('@'):
            target = int(s[1:])
            if target < cur:
                raise SystemExit(f'plan: @{target} is before frame {cur}')
            if last_mask != 0:
                lines.append(f'{cur} 0'); last_mask = 0
            cur = target
            continue
        btn, n = s.split()
        n = int(n)
        mask = 0
        for ch in btn:
            if ch == '-':
                continue
            mask |= MASK[ch]
        if mask != last_mask:
            lines.append(f'{cur} {mask}')
            last_mask = mask
        cur += n
    lines.append(f'{cur} 0')
    return lines, cur


def make_sram(path, plate, complete=0):
    """Synthesise a valid HFT1 save: next plate = `plate` (0-based)."""
    data = bytearray(b"\xff" * 8192)
    s = bytearray(b'HFT1') + bytes([plate]) + bytes(LEVEL_COUNT) + (0).to_bytes(2, 'little') \
        + (0).to_bytes(2, 'little') + (0).to_bytes(2, 'little') + bytes([complete])
    s.append((0x7F + sum(s)) & 0xFF)          # the game seeds its byte checksum with 0x7F
    data[:len(s)] = s
    open(path, 'wb').write(data)


def run(args):
    os.makedirs(args.out, exist_ok=True)
    noi = os.path.splitext(args.rom)[0] + '.noi'
    P = probes(noi)
    if args.script:
        script = args.script
        total = max(int(l.split()[0]) for l in open(script) if l.strip() and not l.startswith('#'))
    else:
        lines, total = compile_plan(args.plan)
        script = os.path.join(args.out, 'input.txt')
        open(script, 'w').write('\n'.join(lines) + '\n')
    frames = args.frames or total + 120
    trace = os.path.join(args.out, 'trace.csv')
    summary = os.path.join(args.out, 'summary.json')
    exe = os.path.join(BIN, 'sameboy_runner' if args.emu == 'sameboy' else 'mgba_runner')
    cmd = [exe, '--input', script, '--origin', 'probe:g_frame', '--frames', str(frames),
           '--trace', trace, '--summary', summary]
    if args.emu == 'sameboy':
        cmd += ['--boot', BOOT]
    want = ['g_frame:2', 'g_state', 'g_level', 'g_px:2', 'g_py:2', 'g_hearts', 'g_sorts', 'g_phase',
            'g_ly_end', 'g_lag', 'g_boss_hp', 'g_ending_reached', 'g_deaths:2']
    for w in want:
        name, _, ln = w.partition(':')
        cmd += ['--probe', f'{name}=0x{P[name]:04X}' + (f':{ln}' if ln else '')]
    if args.until:
        cmd += ['--until', args.until, '--until-grace', str(args.until_grace)]
    sram_in = args.sram_in
    if args.level is not None:
        sram_in = os.path.join(args.out, f'plate{args.level}.sav')
        make_sram(sram_in, args.level)
    if sram_in:
        cmd += ['--sram-in', sram_in]
    if args.sram_out:
        cmd += ['--sram-out', args.sram_out]
    if args.png:
        pngdir = os.path.join(args.out, 'png')
        os.makedirs(pngdir, exist_ok=True)
        cmd += ['--png-dir', pngdir, '--png-frames', args.png, '--png-scale', str(args.png_scale)]
    if args.raw:
        cmd += ['--raw', args.raw]
    cmd.append(args.rom)
    open(os.path.join(args.out, 'cmd.txt'), 'w').write(' '.join(cmd) + '\n')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        print(r.stdout); print(r.stderr)
        raise SystemExit(f'runner exit {r.returncode}')
    return trace, summary, r


def summarise(trace, summary, verbose, every):
    rows = list(csv.DictReader(open(trace)))
    play = [r for r in rows if int(r['frame']) >= 0]
    prev = None
    events = []
    busy_max = 0.0; busy_sum = 0.0; busy_n = 0; oam_max = 0; ly_max = 0; lag_last = 0
    play_frames = 0
    for r in play:
        f = int(r['frame']); st = int(r['g_state']); lv = int(r['g_level'])
        px = int(r['g_px']); py = int(r['g_py']); h = int(r['g_hearts']); ph = int(r['g_phase'])
        key = (st, lv, h)
        if prev is None or key != prev:
            events.append(f'f{f:5d}  {ST[st]:<9} plate {lv + 1}  hearts {h}  phase {"INK" if ph == 0 else "CHALK"}  x={px} y={py}')
            prev = key
        if st == 3:
            play_frames += 1
            b = float(r['busy_pct']); busy_max = max(busy_max, b); busy_sum += b; busy_n += 1
            oam_max = max(oam_max, int(r['oam_max_per_line'])); ly_max = max(ly_max, int(r['g_ly_end']))
        lag_last = int(r['g_lag'])
        if verbose and f % every == 0 and st == 3:
            print(f'  f{f:5d} x={px:4d} y={py:3d} h={h} ph={ph} busy={float(r["busy_pct"]):5.1f} oam/line={r["oam_max_per_line"]} ly_end={r["g_ly_end"]}')
    last = play[-1]
    print('events:')
    for e in events:
        print('  ' + e)
    print(f'end: frame {last["frame"]} state {ST[int(last["g_state"])]} plate {int(last["g_level"]) + 1} x={last["g_px"]} y={last["g_py"]} '
          f'hearts={last["g_hearts"]} sorts={last["g_sorts"]} deaths={last["g_deaths"]} boss_hp={last["g_boss_hp"]} ending={last["g_ending_reached"]}')
    if busy_n:
        print(f'budget during PLAY ({play_frames} frames): busy max {busy_max:.1f}% mean {busy_sum / busy_n:.1f}%, '
              f'oam max/line {oam_max}, ly_end max {ly_max}, lag {lag_last}')
    if os.path.exists(summary):
        s = json.load(open(summary))
        keys = [k for k in ('frames', 'exit_reason', 'until_hit', 'until_frame', 'illegal_opcode', 'sram_resumed') if k in s]
        print('summary: ' + ', '.join(f'{k}={s[k]}' for k in keys))
    return play


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(SRC, 'build', 'HALFTONE.gb'))
    ap.add_argument('--plan')
    ap.add_argument('--script', help='ready-made frame/mask script (e.g. solver output)')
    ap.add_argument('--level', type=int)
    ap.add_argument('--emu', default='sameboy', choices=['sameboy', 'mgba'])
    ap.add_argument('--frames', type=int)
    ap.add_argument('--png')
    ap.add_argument('--png-scale', type=int, default=3)
    ap.add_argument('--out', default='/tmp/a5-work/pt')
    ap.add_argument('--until')
    ap.add_argument('--until-grace', type=int, default=60)
    ap.add_argument('--sram-in')
    ap.add_argument('--sram-out')
    ap.add_argument('--raw')
    ap.add_argument('-v', action='store_true')
    ap.add_argument('--every', type=int, default=10)
    args = ap.parse_args()
    trace, summary, r = run(args)
    summarise(trace, summary, args.v, args.every)


if __name__ == '__main__':
    main()
