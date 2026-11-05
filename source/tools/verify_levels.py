#!/usr/bin/env python3
"""Replay every per-plate solver solution on the final ROM in two independent emulators and
collect the evidence: input script, per-frame traces, runner summaries, contact sheets and a
SameBoy-vs-mGBA trace comparison.

For plate N the solution is replayed from a synthesised save that starts plate N (the same
convention the solver used).  A plate passes when the trace reaches ST_CLEAR (or ST_BOSS_DEAD for
the last plate) with no death, and both emulators agree frame by frame on the 4-shade frame hash
and on every probe.

Usage: verify_levels.py --solutions DIR --out evidence/levels [--plates 8] [--rom ROM]
"""
import argparse, csv, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
ROOT = os.path.dirname(SRC)
sys.path.insert(0, HERE)
from playtest import probes, make_sram, ST  # noqa: E402
from to_gframe import convert as to_gframe  # noqa: E402

BIN = os.environ.get('A5_BIN', '/tmp/a5-tools/bin')
BOOT = os.environ.get('A5_BOOT', '/tmp/a5-tools/SameBoy/build/bin/tester/dmg_boot.bin')
PROBES = ['g_frame:2', 'g_state', 'g_level', 'g_px:2', 'g_py:2', 'g_hearts', 'g_sorts', 'g_phase', 'g_ly_end', 'g_lag',
          'g_boss_hp', 'g_ending_reached', 'g_deaths:2']


def runner_cmd(emu, rom, script, frames, out, P, sram_in=None, png=None, png_scale=1, until=None, grace=60, raw=None, sram_out=None, clock='frame'):
    cmd = [os.path.join(BIN, 'sameboy_runner' if emu == 'sameboy' else 'mgba_runner'), '--input', script, '--origin', 'probe:g_frame',
           '--input-clock', clock, '--frames', str(frames), '--trace', os.path.join(out, 'trace.csv'), '--summary', os.path.join(out, 'summary.json')]
    if emu == 'sameboy':
        cmd += ['--boot', BOOT]
    for w in PROBES:
        name, _, ln = w.partition(':')
        cmd += ['--probe', f'{name}=0x{P[name]:04X}' + (f':{ln}' if ln else '')]
    if sram_in:
        cmd += ['--sram-in', sram_in]
    if sram_out:
        cmd += ['--sram-out', sram_out]
    if until:
        cmd += ['--until', until, '--until-grace', str(grace)]
    if png:
        os.makedirs(os.path.join(out, 'png'), exist_ok=True)
        cmd += ['--png-dir', os.path.join(out, 'png'), '--png-frames', png, '--png-scale', str(png_scale)]
    if raw:
        cmd += ['--raw', raw]
    cmd.append(rom)
    return cmd


def run(cmd, out):
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'cmd.txt'), 'w').write(' '.join(cmd) + '\n')
    r = subprocess.run(cmd, capture_output=True, text=True)
    open(os.path.join(out, 'runner.log'), 'w').write(r.stdout + r.stderr)
    if r.returncode not in (0, 1):
        raise SystemExit(f'runner failed ({r.returncode}): {" ".join(cmd)}\n{r.stderr[-2000:]}')
    rows = [row for row in csv.DictReader(open(os.path.join(out, 'trace.csv'))) if int(row['frame']) >= 0]
    summary = json.load(open(os.path.join(out, 'summary.json')))
    return rows, summary


def level_stats(rows, level):
    """Steady-state budget during PLAY of `level`, excluding the two frames after the level loads
    (the load hitch is reported separately through the lag counter)."""
    play = []; entry = None; prev = None; lag0 = lag1 = None; oam_line = 0; obj_max = 0
    first_play = None; clear_frame = None; end_state = None
    for r in rows:
        st = int(r['g_state']); lv = int(r['g_level']); f = int(r['frame'])
        if st == 3 and lv == level:
            if prev != (3, lv):
                entry = f
                if first_play is None:
                    first_play = f
            if f - entry >= 2:
                play.append(float(r['busy_pct']))
                oam_line = max(oam_line, int(r['oam_max_per_line'])); obj_max = max(obj_max, int(r['obj_visible']))
                if lag0 is None:
                    lag0 = int(r['g_lag'])
                lag1 = int(r['g_lag'])
        if lv == level and st in (5, 8) and clear_frame is None:
            clear_frame = f
        prev = (st, lv)
    last = rows[-1]
    return {'play_frames': len(play), 'busy_mean': round(sum(play) / len(play), 1) if play else None,
            'busy_max': round(max(play), 1) if play else None, 'oam_max_line': oam_line, 'oam_max': obj_max,
            'lag_delta_during_play': (lag1 - lag0) if lag0 is not None else None, 'first_play_frame': first_play,
            'clear_frame': clear_frame, 'end_state': ST[int(last['g_state'])], 'deaths': int(last['g_deaths']),
            'hearts_end': int(last['g_hearts']), 'sorts': int(last['g_sorts']), 'boss_hp_end': int(last['g_boss_hp'])}


def compare_by_gframe(a_rows, b_rows, probes=('g_state', 'g_level', 'g_px', 'g_py', 'g_hearts', 'g_sorts', 'g_phase', 'g_lag', 'g_boss_hp', 'g_ending_reached', 'g_deaths')):
    """Align two traces on the game's frame counter (rows inside a load stall share a g_frame and are
    skipped) and compare the 4-shade frame hash and the gameplay probes."""
    def by_g(rows):
        seen = {}; dup = set()
        for r in rows:
            g = int(r['g_frame'])
            if g in seen: dup.add(g)
            seen[g] = r
        return {g: r for g, r in seen.items() if g not in dup}
    A, B = by_g(a_rows), by_g(b_rows)
    common = sorted(set(A) & set(B))
    video = sum(1 for g in common if A[g]['shade_fnv'] == B[g]['shade_fnv'])
    probe_ok = sum(1 for g in common if all(A[g][k] == B[g][k] for k in probes))
    first_probe_bad = next((g for g in common if any(A[g][k] != B[g][k] for k in probes)), None)
    video_bad = [g for g in common if A[g]['shade_fnv'] != B[g]['shade_fnv']]
    # Every video mismatch must be a frame where two visible objects overlap with the later OAM entry at the
    # smaller X: the DMG draws the smaller X on top (SameBoy does), mGBA 0.10.5 draws the lower OAM index on top.
    # Frames without such an overlap that still differ would point at the game, so they fail the check.
    xprio = 'obj_xprio_overlaps' in (A[common[0]] if common else {})
    unexplained = [g for g in video_bad if not (xprio and int(A[g]['obj_xprio_overlaps']) > 0)]
    return {'aligned_frames': len(common), 'identical_video_frames': video, 'identical_probe_frames': probe_ok,
            'first_probe_divergence_gframe': first_probe_bad,
            'video_mismatch_frames': len(video_bad), 'video_mismatch_all_obj_xprio_overlaps': xprio and not unexplained,
            'video_mismatch_unexplained_gframes': unexplained[:20],
            'agree': len(common) > 0 and first_probe_bad is None and not unexplained}


def contact_sheet(pngdir, out, cols=6, scale=2, max_frames=24):
    from PIL import Image
    files = sorted(f for f in os.listdir(pngdir) if f.endswith('.png'))
    if not files:
        return None
    step = max(1, len(files) // max_frames)
    files = files[::step][:max_frames]
    tiles = [Image.open(os.path.join(pngdir, f)).convert('RGB') for f in files]
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * h), (24, 24, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * w, (i // cols) * h))
    sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    sheet.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(SRC, 'build', 'HALFTONE.gb'))
    ap.add_argument('--solutions', default='/tmp/a5-work/solve')
    ap.add_argument('--out', default=os.path.join(ROOT, 'evidence', 'levels'))
    ap.add_argument('--plates', type=int, default=8)
    ap.add_argument('--only', type=int, nargs='*')
    ap.add_argument('--gframe-inputs', default=None,
                    help='directory with plateN/input.txt scripts already in the game-frame clock (e.g. a copy of a previous '
                         'evidence/levels); replay those directly instead of converting the solver\'s emulator-frame scripts')
    args = ap.parse_args()
    P = probes(os.path.splitext(args.rom)[0] + '.noi')
    results = []
    for plate in range(1, args.plates + 1):
        if args.only and plate not in args.only:
            continue
        out = os.path.join(args.out, f'plate{plate}')
        os.makedirs(out, exist_ok=True)
        sav = os.path.join(out, 'start.sav'); make_sram(sav, plate - 1)
        script = os.path.join(out, 'input.txt')
        if args.gframe_inputs:
            # the script is already clocked on the game's own frame counter: replay it as is (portable across
            # ROM builds whose display-off load phases differ in length, and across emulators)
            src = os.path.join(args.gframe_inputs, f'plate{plate}', 'input.txt')
            if not os.path.exists(src):
                print(f'plate {plate}: no gframe script'); continue
            if os.path.abspath(src) != os.path.abspath(script):
                shutil.copy(src, script)
            total = max(int(l.split()[0]) for l in open(script) if l.strip() and not l.startswith('#'))
            frames = total + 200
            res = {'plate': plate, 'script_end_frame': total, 'script_source': os.path.relpath(src, ROOT) if src.startswith(ROOT) else src,
                   'script_clock': 'gframe (supplied; solver-clock reference replay skipped)'}
            ref_rows = None
        else:
            sol = os.path.join(args.solutions, f'plate{plate}', 'solution.txt')
            if not os.path.exists(sol):
                print(f'plate {plate}: no solution yet'); continue
            solver_script = os.path.join(out, 'input_solver_frames.txt'); shutil.copy(sol, solver_script)
            total = max(int(l.split()[0]) for l in open(solver_script) if l.strip() and not l.startswith('#'))
            frames = total + 200
            res = {'plate': plate, 'script_end_frame': total, 'script_clock': 'converted from the solver\'s emulator-frame script'}
            # 1. SameBoy replay of the solver's emulator-frame script -> the frame/g_frame map for the conversion
            ref = os.path.join(out, 'sameboy_solverclock')
            ref_rows, _ = run(runner_cmd('sameboy', args.rom, solver_script, frames, ref, P, sram_in=sav), ref)
            to_gframe(solver_script, os.path.join(ref, 'trace.csv'), script)
        # PNG frames every 30 frames during the run for the contact sheet
        png_ranges = ','.join(str(f) for f in range(0, frames, 30))
        res['input'] = os.path.relpath(script, ROOT)
        traces = {}
        for emu in ('sameboy', 'mgba'):
            o = os.path.join(out, emu)
            cmd = runner_cmd(emu, args.rom, script, frames, o, P, sram_in=sav, png=png_ranges if emu == 'sameboy' else None, clock='gframe')
            rows, summary = run(cmd, o)
            traces[emu] = rows
            st = level_stats(rows, plate - 1)
            st['illegal_opcode'] = summary.get('illegal_opcode'); st['frames_run'] = summary.get('frames')
            res[emu] = st
            print(f'plate {plate} {emu:8s}: end {st["end_state"]:9s} clear@{st["clear_frame"]} deaths={st["deaths"]} '
                  f'busy mean {st["busy_mean"]} max {st["busy_max"]} oam/line {st["oam_max_line"]} obj {st["oam_max"]} lag+{st["lag_delta_during_play"]}')
        # the g_frame-clocked SameBoy replay must reproduce the solver-clock run exactly (when one was made)
        if ref_rows is not None:
            same = compare_by_gframe(ref_rows, traces['sameboy'])
            res['gframe_script_reproduces_solver_run'] = same['agree']
        else:
            same = {'agree': None, 'note': 'script supplied in the gframe clock; no solver-clock reference run'}
            res['gframe_script_reproduces_solver_run'] = None
        cmp = compare_by_gframe(traces['sameboy'], traces['mgba'])
        json.dump({'sameboy_vs_mgba_by_gframe': cmp, 'sameboy_gframe_vs_solver_clock': same}, open(os.path.join(out, 'compare.json'), 'w'), indent=1)
        res['compare'] = cmp
        res['emulators_agree'] = cmp['agree']
        print(f'plate {plate}: emulators aligned on g_frame: {cmp["aligned_frames"]} frames, identical video {cmp["identical_video_frames"]}, '
              f'identical probes {cmp["identical_probe_frames"]}, video mismatches {cmp["video_mismatch_frames"]} '
              f'(all OBJ x-priority overlaps: {cmp["video_mismatch_all_obj_xprio_overlaps"]}); gframe script == solver run: {same["agree"]}')
        sheet = contact_sheet(os.path.join(out, 'sameboy', 'png'), os.path.join(out, f'contact_plate{plate}.png'))
        res['contact_sheet'] = os.path.relpath(sheet, ROOT) if sheet else None
        ok = res['sameboy']['clear_frame'] is not None and res['mgba']['clear_frame'] is not None \
            and res['sameboy']['deaths'] == 0 and res['mgba']['deaths'] == 0 and res['emulators_agree'] \
            and res['gframe_script_reproduces_solver_run'] in (True, None)
        res['pass'] = bool(ok)
        print(f'plate {plate}: {"PASS" if ok else "FAIL"} (emulators agree: {res["emulators_agree"]})')
        results.append(res)
        # drop the bulky per-frame PNGs once the contact sheet exists; keep traces
        shutil.rmtree(os.path.join(out, 'sameboy', 'png'), ignore_errors=True)
    json.dump(results, open(os.path.join(args.out, 'levels.json'), 'w'), indent=1)
    print('wrote', os.path.join(args.out, 'levels.json'))


if __name__ == '__main__':
    main()
