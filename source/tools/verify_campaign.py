#!/usr/bin/env python3
"""Replay the chained full-campaign input script in SameBoy and mGBA, prove the ending is reached, and
exercise save/resume through the real SRAM file.

Steps
  1. SameBoy replay of the chained emulator-frame script (campaign.py output) -> frame/g_frame map.
  2. Convert the script to the game-frame clock (to_gframe.py) so both emulators replay it identically.
  3. SameBoy + mGBA replays until g_ending_reached == 1 (traces, summaries, SRAM dumps, key-frame PNGs).
  4. Align the two traces on g_frame: gameplay probes must be identical on every frame; video hashes may
     differ only on frames with an OBJ x-priority overlap (mGBA 0.10.5 draws OAM order, the DMG draws the
     smaller X on top).
  5. Save/resume: dump SRAM after plate 2 is cleared, boot fresh from it, press START, expect PLAY on
     plate 3; boot fresh from the end-of-campaign SRAM, expect PLAY on plate 8 and the complete flag.

usage: verify_campaign.py [--script /tmp/a5-work/campaign8/campaign_input.txt] [--out ../evidence/campaign]
"""
import argparse, csv, json, os, shutil, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
ROOT = os.path.dirname(SRC)
sys.path.insert(0, HERE)
from playtest import probes, ST  # noqa: E402
from to_gframe import convert as to_gframe  # noqa: E402
from verify_levels import runner_cmd, run, compare_by_gframe, contact_sheet  # noqa: E402

LEVEL_NAMES = ['MARGINS', 'GALLEY', 'INK WORKS', 'BINDERY', 'PULSE', 'ROTARY', 'NEGATIVE', 'THE SMUDGE']  # as in gen/levels.c


def plate_stats(rows):
    """Per-plate budget statistics from a SameBoy trace (PLAY frames only)."""
    out = []
    for lv in range(8):
        play = [r for r in rows if int(r['g_state']) == 3 and int(r['g_level']) == lv]
        if not play:
            continue
        busy = [float(r['busy_pct']) for r in play]
        lag0 = int(play[0]['g_lag']); lag1 = int(play[-1]['g_lag'])
        out.append({'plate': lv + 1, 'name': LEVEL_NAMES[lv], 'frames': len(play), 'seconds': round(len(play) / 59.73, 1),
                    'busy_mean': round(sum(busy) / len(busy), 1), 'busy_max': max(busy),
                    'frames_over_85': sum(1 for b in busy if b > 85.0),
                    'oam_max_per_line': max(int(r['oam_max_per_line']) for r in play),
                    'oam_max_line': max((int(r['oam_max_per_line']), int(r['oam_max_line'])) for r in play)[1],
                    'obj_max': max(int(r['obj_visible']) for r in play),
                    'lag_frames_in_play': lag1 - lag0,
                    'hearts_at_end': int(play[-1]['g_hearts']), 'sorts_mask_at_end': int(play[-1]['g_sorts'])})
    return out


def decode_save(path):
    b = open(path, 'rb').read()
    magic = b[0:4].decode('latin1'); plate = b[4]; sorts = list(b[5:13]); deaths = struct.unpack('<H', b[13:15])[0]
    frames = struct.unpack('<H', b[15:17])[0] | (struct.unpack('<H', b[17:19])[0] << 16); complete = b[19]; chk = b[20]
    s = (0x7F + sum(b[0:20])) & 0xFF
    return {'magic': magic, 'plate_next_0based': plate, 'sorts_masks': sorts, 'deaths': deaths, 'frames': frames,
            'seconds': round(frames / 59.73, 1), 'complete': complete, 'checksum': chk, 'checksum_ok': chk == s and magic == 'HFT1'}


def last_row(rows):
    return rows[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(SRC, 'build', 'HALFTONE.gb'))
    ap.add_argument('--script', default='/tmp/a5-work/campaign8/campaign_input.txt')
    ap.add_argument('--splice-log', default='/tmp/a5-work/campaign8/splice_log.json')
    ap.add_argument('--out', default=os.path.join(ROOT, 'evidence', 'campaign'))
    ap.add_argument('--save-out', default=os.path.join(ROOT, 'evidence', 'save-resume'))
    ap.add_argument('--gframe-script', default=None,
                    help='campaign script already in the game-frame clock: replay it directly (steps 1-2 skipped; the '
                         'reference run is then a second SameBoy gframe replay, i.e. a determinism check)')
    args = ap.parse_args()
    P = probes(os.path.splitext(args.rom)[0] + '.noi')
    out = args.out; os.makedirs(out, exist_ok=True); os.makedirs(args.save_out, exist_ok=True)
    script = os.path.join(out, 'campaign_input.txt')
    if args.gframe_script:
        if os.path.abspath(args.gframe_script) != os.path.abspath(script):
            shutil.copy(args.gframe_script, script)
        total = max(int(l.split()[0]) for l in open(script) if l.strip() and not l.startswith('#'))
        frames = total + 900
        ref = os.path.join(out, 'sameboy_gframe_ref')
        ref_rows, ref_sum = run(runner_cmd('sameboy', args.rom, script, frames, ref, P, until='g_ending_reached==1', grace=240, clock='gframe'), ref)
        ref_label = 'sameboy_gframe_ref (second SameBoy gframe replay: determinism check)'
    else:
        solver_script = os.path.join(out, 'campaign_input_solver_frames.txt'); shutil.copy(args.script, solver_script)
        if os.path.exists(args.splice_log):
            shutil.copy(args.splice_log, os.path.join(out, 'splice_log.json'))
        total = max(int(l.split()[0]) for l in open(solver_script) if l.strip() and not l.startswith('#'))
        frames = total + 900                     # boss death (120) + fade + ending card + margin

        # 1. SameBoy, emulator-frame clock
        ref = os.path.join(out, 'sameboy_solverclock')
        ref_rows, ref_sum = run(runner_cmd('sameboy', args.rom, solver_script, frames, ref, P, until='g_ending_reached==1', grace=240), ref)
        # 2. game-frame clock
        to_gframe(solver_script, os.path.join(ref, 'trace.csv'), script)
        ref_label = 'sameboy_solverclock (emulator-frame replay of the solver script)'

    # key frames (SameBoy frame numbers; identical for the gframe replay, checked below)
    def first(pred):
        for r in ref_rows:
            if pred(r):
                return int(r['frame'])
        return None
    keys = {'title': 30}
    for lv in range(8):
        f = first(lambda r, lv=lv: int(r['g_state']) == 3 and int(r['g_level']) == lv)
        if f is not None:
            keys[f'plate{lv + 1}_play'] = f + 90
    hp = None
    for r in ref_rows:
        if int(r['g_level']) != 7 or int(r['g_state']) != 3:
            continue
        v = int(r['g_boss_hp'])
        if hp is None:
            hp = v
        elif v < hp:
            hp = v; keys[f'boss_hit_{5 - hp}'] = int(r['frame']) + 2
    f = first(lambda r: int(r['g_state']) == 8); keys['boss_dead'] = f + 30 if f is not None else None
    f = first(lambda r: int(r['g_ending_reached']) == 1); keys['ending'] = f + 90 if f is not None else None
    keys = {k: v for k, v in keys.items() if v is not None}
    sheet_frames = list(range(0, int(ref_rows[-1]['frame']), 120))
    png_ranges = ','.join(str(f) for f in sorted(set(sheet_frames + list(keys.values()))))

    # 3. both emulators, gframe clock
    traces = {}; sums = {}
    for emu in ('sameboy', 'mgba'):
        o = os.path.join(out, emu)
        rows, summary = run(runner_cmd(emu, args.rom, script, frames, o, P, until='g_ending_reached==1', grace=240,
                                       png=png_ranges if emu == 'sameboy' else None,
                                       sram_out=os.path.join(o, 'end_of_campaign.sav'), clock='gframe'), o)
        traces[emu] = rows; sums[emu] = summary
        last = last_row(rows)
        print(f'{emu:8s}: {len(rows)} frames, end state {ST[int(last["g_state"])]}, level {last["g_level"]}, ending_reached {last["g_ending_reached"]}, '
              f'deaths {last["g_deaths"]}, boss hp {last["g_boss_hp"]}, until={summary.get("until")} @ {summary.get("until_hit_frame")}, illegal={summary.get("illegal_opcode")}')
    # mGBA PNGs at the same game frames (its emulator frame numbers differ by the load-phase offset)
    gmap = {int(r['g_frame']): int(r['frame']) for r in traces['mgba']}
    sbg = {int(r['frame']): int(r['g_frame']) for r in traces['sameboy']}
    mg_frames = sorted({gmap[sbg[f]] for f in keys.values() if f in sbg and sbg[f] in gmap})
    o = os.path.join(out, 'mgba_keyframes')
    run(runner_cmd('mgba', args.rom, script, frames, o, P, until='g_ending_reached==1', grace=240, png=','.join(map(str, mg_frames)), clock='gframe'), o)

    # 4. compare
    same = compare_by_gframe(ref_rows, traces['sameboy'])
    cmp = compare_by_gframe(traces['sameboy'], traces['mgba'])
    json.dump({'sameboy_vs_mgba_by_gframe': cmp, 'sameboy_gframe_vs_reference': same, 'reference_run': ref_label},
              open(os.path.join(out, 'compare.json'), 'w'), indent=1)
    print(f'compare: aligned {cmp["aligned_frames"]}, identical probes {cmp["identical_probe_frames"]}, identical video {cmp["identical_video_frames"]}, '
          f'video mismatches {cmp["video_mismatch_frames"]} (all OBJ x-priority overlaps: {cmp["video_mismatch_all_obj_xprio_overlaps"]}); '
          f'gframe replay reproduces the reference run ({ref_label}): {same["agree"]}')

    # key-frame copies with names + contact sheet
    kdir = os.path.join(out, 'keyframes'); os.makedirs(kdir, exist_ok=True)
    for name, f in keys.items():
        src = os.path.join(out, 'sameboy', 'png', f'frame_{f:06d}.png')
        if os.path.exists(src):
            shutil.copy(src, os.path.join(kdir, f'sameboy_{name}_f{f}.png'))
        g = sbg.get(f)
        if g in gmap:
            srcm = os.path.join(o, 'png', f'frame_{gmap[g]:06d}.png')
            if os.path.exists(srcm):
                shutil.copy(srcm, os.path.join(kdir, f'mgba_{name}_f{gmap[g]}.png'))
    # contact sheet: one frame every 120 (2 s) across the whole campaign
    sheet_dir = os.path.join(out, 'sheet_frames'); os.makedirs(sheet_dir, exist_ok=True)
    for f in sheet_frames:
        src = os.path.join(out, 'sameboy', 'png', f'frame_{f:06d}.png')
        if os.path.exists(src):
            shutil.copy(src, os.path.join(sheet_dir, f'frame_{f:06d}.png'))
    contact_sheet(sheet_dir, os.path.join(out, 'contact_campaign.png'), cols=12, scale=1, max_frames=len(sheet_frames))
    shutil.rmtree(sheet_dir)

    # 5. save / resume
    save = {}
    # (a) mid-campaign: SRAM after plate 2 is cleared (g_level becomes 2 at the clear)
    o = os.path.join(args.save_out, 'sameboy_until_plate3')
    rows, _ = run(runner_cmd('sameboy', args.rom, script, frames, o, P, until='g_level==2', grace=30, sram_out=os.path.join(o, 'after_plate2.sav'), clock='gframe'), o)
    sav = os.path.join(args.save_out, 'after_plate2.sav'); shutil.copy(os.path.join(o, 'after_plate2.sav'), sav)
    save['after_plate2_sav'] = decode_save(sav)
    resume_script = os.path.join(args.save_out, 'resume_input.txt')
    open(resume_script, 'w').write('# fresh boot with the saved SRAM: START on the title (CONTINUE is preselected when a save exists)\n0 0\n60 128\n63 0\n')
    for emu in ('sameboy', 'mgba'):
        o = os.path.join(args.save_out, f'{emu}_resume_plate3')
        rows, summary = run(runner_cmd(emu, args.rom, resume_script, 900, o, P, sram_in=sav, until='g_state==3', grace=5,
                                       png='0,30,60' if emu == 'sameboy' else None), o)
        last = last_row(rows)
        save[f'{emu}_resume_plate3'] = {'end_state': ST[int(last['g_state'])], 'level_0based': int(last['g_level']), 'frame': int(last['frame']),
                                        'ok': int(last['g_state']) == 3 and int(last['g_level']) == 2}
        print(f'resume after plate 2 in {emu}: {save[f"{emu}_resume_plate3"]}')
    # (b) end of campaign SRAM
    endsav = os.path.join(args.save_out, 'end_of_campaign.sav'); shutil.copy(os.path.join(out, 'sameboy', 'end_of_campaign.sav'), endsav)
    save['end_of_campaign_sav'] = decode_save(endsav)
    save['end_of_campaign_sav_mgba_identical'] = open(endsav, 'rb').read() == open(os.path.join(out, 'mgba', 'end_of_campaign.sav'), 'rb').read()
    for emu in ('sameboy', 'mgba'):
        o = os.path.join(args.save_out, f'{emu}_resume_after_ending')
        rows, summary = run(runner_cmd(emu, args.rom, resume_script, 900, o, P, sram_in=endsav, until='g_state==3', grace=5), o)
        last = last_row(rows)
        save[f'{emu}_resume_after_ending'] = {'end_state': ST[int(last['g_state'])], 'level_0based': int(last['g_level']), 'frame': int(last['frame']),
                                              'ok': int(last['g_state']) == 3 and int(last['g_level']) == 7}
        print(f'resume after ending in {emu}: {save[f"{emu}_resume_after_ending"]}')
    # (c) a save must not be accepted when corrupted: flip one byte of the checksum and expect NEW GAME (plate 1)
    bad = bytearray(open(sav, 'rb').read()); bad[20] ^= 0xFF; badp = os.path.join(args.save_out, 'corrupt_checksum.sav'); open(badp, 'wb').write(bad)
    o = os.path.join(args.save_out, 'sameboy_corrupt_save')
    rows, _ = run(runner_cmd('sameboy', args.rom, resume_script, 900, o, P, sram_in=badp, until='g_state==3', grace=5), o)
    last = last_row(rows)
    save['sameboy_corrupt_save_starts_plate1'] = {'end_state': ST[int(last['g_state'])], 'level_0based': int(last['g_level']), 'ok': int(last['g_state']) == 3 and int(last['g_level']) == 0}
    print(f'corrupt save: {save["sameboy_corrupt_save_starts_plate1"]}')
    json.dump(save, open(os.path.join(args.save_out, 'save_resume.json'), 'w'), indent=1)

    # summary
    sb = traces['sameboy']; last = last_row(sb)
    stats = plate_stats(sb)
    play_frames = sum(s['frames'] for s in stats)
    result = {
        'rom': os.path.relpath(args.rom, ROOT), 'rom_sha256': subprocess.check_output(['sha256sum', args.rom]).split()[0].decode(),
        'input_gframe_clock': os.path.relpath(script, ROOT),
        'input_solver_frames': os.path.relpath(solver_script, ROOT) if not args.gframe_script else None,
        'input_source': ('gframe script supplied (--gframe-script): the per-plate solver macros were converted to the game-frame clock on an '
                         'earlier ROM build; the game logic and collision classes are unchanged, so the same script is replayed on this build'
                         if args.gframe_script else 'solver emulator-frame script converted to the game-frame clock on this build'),
        'reference_run': ref_label,
        'frames_total_sameboy': len(sb), 'frames_total_mgba': len(traces['mgba']),
        'ending_reached': {emu: int(last_row(traces[emu])['g_ending_reached']) == 1 for emu in traces},
        'end_state': {emu: ST[int(last_row(traces[emu])['g_state'])] for emu in traces},
        'deaths': {emu: int(last_row(traces[emu])['g_deaths']) for emu in traces},
        'illegal_opcode': {emu: sums[emu].get('illegal_opcode') for emu in sums},
        'campaign_seconds_at_59_73hz': round(len(sb) / 59.73, 1), 'play_frames': play_frames, 'play_seconds': round(play_frames / 59.73, 1),
        'busy_pct_max_sameboy': max(float(r['busy_pct']) for r in sb), 'busy_pct_mean_play_sameboy': round(sum(float(r['busy_pct']) for r in sb if int(r['g_state']) == 3) / max(1, play_frames), 1),
        'frames_over_85pct_play_sameboy': sum(1 for r in sb if int(r['g_state']) == 3 and float(r['busy_pct']) > 85.0),
        'oam_max_per_line_sameboy': max(int(r['oam_max_per_line']) for r in sb), 'oam_objects_obscured_total_sameboy': sums['sameboy'].get('oam_objects_obscured_by_line_limit_total'),
        'sp_min': {emu: sums[emu].get('sp_min') for emu in sums},
        'lag_total': int(last['g_lag']),
        'plates': stats, 'keyframes': keys, 'compare': cmp, 'gframe_replay_reproduces_reference_run': same['agree'], 'save_resume': save,
        'emulators': {emu: sums[emu].get('emulator') for emu in sums},
        'pass': all(int(last_row(traces[e])['g_ending_reached']) == 1 and int(last_row(traces[e])['g_deaths']) == 0 and not sums[e].get('illegal_opcode') for e in traces)
                and cmp['agree'] and same['agree'] and all(v.get('ok') for k, v in save.items() if isinstance(v, dict) and 'ok' in v) and save['end_of_campaign_sav']['complete'] == 1,
    }
    json.dump(result, open(os.path.join(out, 'campaign.json'), 'w'), indent=1)
    print(f'campaign: {"PASS" if result["pass"] else "FAIL"}; {len(sb)} frames = {result["campaign_seconds_at_59_73hz"]} s; play {result["play_seconds"]} s; '
          f'busy max {result["busy_pct_max_sameboy"]}%, >85%: {result["frames_over_85pct_play_sameboy"]} frames; oam max/line {result["oam_max_per_line_sameboy"]}; deaths {result["deaths"]}')
    print('wrote', os.path.join(out, 'campaign.json'))


if __name__ == '__main__':
    main()
