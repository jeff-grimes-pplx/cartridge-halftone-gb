#!/usr/bin/env python3
"""Chain the per-plate solver solutions into one full-campaign input script.

Each solver solution was found from a synthesised save that starts its plate directly.  Every plate
starts from an identical game state (level_load resets hearts, ink phase, the RNG seed and all
entities), so the per-plate inputs can be spliced into one continuous run: for plate N the macro
inputs are shifted so that their first frame lands 3 frames after the first PLAY frame of plate N in
the chained run (exactly the solver's own root convention).  The chain is grown one plate at a time
with the real SameBoy runner, reading the PLAY entry frame from the trace; nothing is assumed.

Usage:
    campaign.py --solutions DIR --plates 8 --out DIR [--rom ROM]
Writes DIR/campaign_input.txt plus one trace per growth step.
"""
import argparse, csv, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
BIN = os.environ.get('A5_BIN', '/tmp/a5-tools/bin')
BOOT = os.environ.get('A5_BOOT', '/tmp/a5-tools/SameBoy/build/bin/tester/dmg_boot.bin')
sys.path.insert(0, HERE)
from playtest import probes  # noqa: E402


def parse_solution(path):
    """Return (root_frame, [(rel_frame, mask)], macro_names) for a solver solution file."""
    root = None
    events = []
    macros = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            m = re.match(r'# HALFTONE scripted playthrough: prefix \((\d+) frames\)', line)
            if m:
                root = int(m.group(1))
            m = re.match(r'# macro: (.*) \((\d+) frames\)', line)
            if m:
                macros.append((m.group(1), int(m.group(2))))
            continue
        f, mask = line.split()
        f = int(f); mask = int(mask)
        if root is not None and f >= root:
            events.append((f - root, mask))
    if root is None:
        raise SystemExit(f'{path}: no root frame in header')
    return root, events, macros


def run_trace(rom, script, frames, out, sram_in=None, until=None, extra=None):
    os.makedirs(out, exist_ok=True)
    noi = os.path.splitext(rom)[0] + '.noi'
    P = probes(noi)
    trace = os.path.join(out, 'trace.csv'); summary = os.path.join(out, 'summary.json')
    cmd = [os.path.join(BIN, 'sameboy_runner'), '--boot', BOOT, '--input', script, '--origin', 'probe:g_frame',
           '--frames', str(frames), '--trace', trace, '--summary', summary]
    for w in ['g_frame:2', 'g_state', 'g_level', 'g_px:2', 'g_py:2', 'g_hearts', 'g_sorts', 'g_phase', 'g_ly_end', 'g_lag',
              'g_boss_hp', 'g_ending_reached', 'g_deaths:2']:
        name, _, ln = w.partition(':')
        cmd += ['--probe', f'{name}=0x{P[name]:04X}' + (f':{ln}' if ln else '')]
    if sram_in:
        cmd += ['--sram-in', sram_in]
    if until:
        cmd += ['--until', until, '--until-grace', '90']
    if extra:
        cmd += extra
    cmd.append(rom)
    open(os.path.join(out, 'cmd.txt'), 'w').write(' '.join(cmd) + '\n')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        print(r.stdout, r.stderr); raise SystemExit(f'runner exit {r.returncode}')
    rows = [row for row in csv.DictReader(open(trace)) if int(row['frame']) >= 0]
    return rows, json.load(open(summary)) if os.path.exists(summary) else {}


def first_play_frame(rows, level):
    for row in rows:
        if int(row['g_state']) == 3 and int(row['g_level']) == level:
            return int(row['frame'])
    return None


def write_script(path, events, header):
    last = None
    with open(path, 'w') as f:
        f.write(header)
        for fr, mask in sorted(events):
            if mask != last:
                f.write(f'{fr} {mask}\n'); last = mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(SRC, 'build', 'HALFTONE.gb'))
    ap.add_argument('--solutions', default='/tmp/a5-work/solve')
    ap.add_argument('--plates', type=int, default=8)
    ap.add_argument('--out', default='/tmp/a5-work/campaign')
    ap.add_argument('--start-frame', type=int, default=60, help='frame of the START press on the title')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    # title: press START (NEW GAME is selected when no save exists)
    events = [(0, 0), (args.start_frame, 128), (args.start_frame + 3, 0)]
    header = '# HALFTONE full-campaign input script: title START, then the per-plate solver macros spliced at each plate\'s PLAY entry\n'
    script = os.path.join(args.out, 'campaign_input.txt')
    log = []
    end_frame = args.start_frame + 3
    for plate in range(1, args.plates + 1):
        root, sol_events, macros = parse_solution(os.path.join(args.solutions, f'plate{plate}', 'solution.txt'))
        write_script(script, events, header)
        rows, _ = run_trace(args.rom, script, end_frame + 1200, os.path.join(args.out, f'step{plate}'))
        f_play = first_play_frame(rows, plate - 1)
        if f_play is None:
            last = rows[-1]
            raise SystemExit(f'plate {plate}: PLAY never reached (last state {last["g_state"]} level {last["g_level"]} at frame {last["frame"]})')
        splice = f_play + 3
        if splice < end_frame:
            raise SystemExit(f'plate {plate}: PLAY at {f_play} but the previous plate inputs end at {end_frame}')
        sol_len = max(fr for fr, _ in sol_events)
        for fr, mask in sol_events:
            events.append((splice + fr, mask))
        end_frame = splice + sol_len
        log.append({'plate': plate, 'play_frame': f_play, 'splice_frame': splice, 'solution_root': root, 'macros': len(macros),
                    'solution_frames': sol_len, 'macro_list': [m for m, _ in macros]})
        print(f'plate {plate}: PLAY at frame {f_play}, inputs spliced at {splice} (+{sol_len} frames, {len(macros)} macros)')
    write_script(script, events, header)
    json.dump(log, open(os.path.join(args.out, 'splice_log.json'), 'w'), indent=1)
    print(f'script: {script} (ends at frame {end_frame})')


if __name__ == '__main__':
    main()
