#!/usr/bin/env python3
"""Assemble the two silent films from real emulator output.

Sources
  * SameBoy raw RGB24 frames (160x144) of the verified full-campaign script, captured with
    sameboy_runner --raw --palette paper (frame i of the raw file = trace frame i; the trace of the capture run is
    byte-identical in every gameplay/budget column to evidence/campaign/sameboy/trace.csv).
  * Page frames: tools/film_pages.mjs renders (1920x1080 after clipping a per-frame camera rectangle out of the page at
    device scale 2): pointer-led moves onto the Cartridge card -> screen (then the page's binjgb core stepped one
    emulated frame per output frame for the boot) and onto the technical sheet's Bank layout block.

Scaling: 160x144 -> 1120x1008 is an exact 7x nearest-neighbour scale (ffmpeg scale flags=neighbor), centred on the
page's bezel colour. Output 1920x1080, 60 fps, H.264 yuv420p, no audio stream.

Capture method (disclosed in the handoff): frame-stepped software capture. One emulated frame (59.73 Hz on hardware)
is shown per 60 fps output frame, so gameplay runs 0.45% faster than real time; nothing here measures real-time
performance of any GPU or browser.

usage: python3 source/tools/film.py --raw /tmp/a5-work/film/sameboy/campaign_paper.rgb --pages /tmp/a5-work/film/pages --out films
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

W, H, FRAME = 160, 144, 160 * 144 * 3
SCALE = 7
BG = '0x2a2722'   # --bezel of the page's light theme


def seg_raw(raw, a, b, path):
    """Frames [a, b) of the raw file -> path."""
    with open(raw, 'rb') as f, open(path, 'wb') as o:
        f.seek(a * FRAME)
        o.write(f.read((b - a) * FRAME))
    return b - a


def enc_raw(seg, nframes, out, hold_last=0):
    vf = f'scale={W * SCALE}:{H * SCALE}:flags=neighbor,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color={BG}'
    if hold_last:
        vf += f',tpad=stop_mode=clone:stop_duration={hold_last / 60:.6f}'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '60', '-i', seg,
                    '-vf', vf, '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'rgb24', '-r', '60', out], check=True)
    return nframes + hold_last


def enc_pages(pages_dir, a, b, out):
    """Page PNG frames [a, b) -> out, exactly one PNG per output frame (image2 demuxer, no timestamp resampling)."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '60', '-start_number', str(a), '-i', os.path.join(pages_dir, 'f%05d.png'),
                    '-frames:v', str(b - a), '-vf', 'format=rgb24', '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'rgb24', '-r', '60', out], check=True)
    return b - a


def build(name, shots, args, work):
    parts, total, table = [], 0, []
    for k, s in enumerate(shots):
        out = os.path.join(work, f'{name}_{k:02d}.mkv')
        if s['src'] == 'sameboy':
            seg = os.path.join(work, f'{name}_{k:02d}.rgb')
            n = seg_raw(args.raw, s['a'], s['b'], seg)
            n = enc_raw(seg, n, out, s.get('hold', 0))
            os.remove(seg)
        else:
            n = enc_pages(os.path.join(args.pages, s['src']), s['a'], s['b'], out)
        parts.append(out)
        table.append({'shot': k, 'source': s['src'], 'frames': [s['a'], s['b']], 'hold_last': s.get('hold', 0), 'out_frames': n, 'starts_at_s': round(total / 60, 3), 'what': s['what']})
        total += n
    lst = os.path.join(work, f'{name}.txt')
    with open(lst, 'w') as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    final = os.path.join(args.out, f'{name}.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14',
                    '-pix_fmt', 'yuv420p', '-r', '60', '-movflags', '+faststart', final], check=True)
    probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', final], capture_output=True, text=True).stdout)
    v = [s for s in probe['streams'] if s['codec_type'] == 'video'][0]
    info = {'file': final, 'frames_planned': total, 'width': v['width'], 'height': v['height'], 'fps': v['r_frame_rate'], 'nb_frames': v.get('nb_frames'),
            'duration_s': float(probe['format']['duration']), 'codec': v['codec_name'], 'pix_fmt': v['pix_fmt'], 'audio_streams': len([s for s in probe['streams'] if s['codec_type'] == 'audio']),
            'bytes': int(probe['format']['size']), 'shots': table}
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', required=True)
    ap.add_argument('--pages', required=True)
    ap.add_argument('--out', default='films')
    ap.add_argument('--work', default='/tmp/a5-work/film/work')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    shutil.rmtree(args.work, ignore_errors=True)
    os.makedirs(args.work)
    raw_frames = os.path.getsize(args.raw) // FRAME
    assert raw_frames == 8274, raw_frames

    # trace frame indices (origin = first frame with g_frame != 0; see evidence/campaign/sameboy/trace.csv):
    # TITLE 0-59 (START at 60), INTRO 60-174, PLAY1 175-846, CLEAR 847-1001, PLAY2 1110-1751 (mid-air flips at 1253, 1326,
    # 1405, 1544, 1616), PLAY3 2015-2645, PLAY4 2909-3621, PLAY5 3885-4516, PLAY6 4780-5512, PLAY7 5776-6434, INTRO8 6590-6689,
    # PLAY8 6690-7889 (hits 6885 7135 7378 7604 7799), BOSS_DEAD 7890-8032, ENDING 8033-8273.
    # Page intro: click at 168, in-page boot 168-239 ends on the title at g_frame 66; the title is static at that point
    # (hero idle frame 0, ink phase), so the cut to SameBoy frame 20 (g_frame 21, same image) is seamless.
    sixty = [
        {'src': 'intro', 'a': 0, 'b': 240, 'what': 'page: camera on the Cartridge card (ROM file, SHA-256) -> pointer leads the camera to the screen -> clicks Insert cartridge -> boot -> title (binjgb, one emulated frame per output frame, 4x canvas framed at 7x)'},
        {'src': 'sameboy', 'a': 20, 'b': 174, 'what': 'SameBoy: title, START, plate card MARGINS'},
        {'src': 'sameboy', 'a': 174, 'b': 936, 'what': 'SameBoy: plate 1 MARGINS, complete (672 play frames) + CLEAR'},
        {'src': 'sameboy', 'a': 1200, 'b': 1440, 'what': 'SameBoy: plate 2 GALLEY - three mid-air ink flips over the spike floor (1253 chalk, 1326 ink, 1405 chalk): the pillar under the jump only exists in the other ink'},
        {'src': 'sameboy', 'a': 2060, 'b': 2240, 'what': 'SameBoy: plate 3 INK WORKS (ink pools, drippers, flips at 2076 and 2182)'},
        {'src': 'sameboy', 'a': 2963, 'b': 3143, 'what': 'SameBoy: plate 4 BINDERY (busiest plate: presses, moving platforms)'},
        {'src': 'sameboy', 'a': 3950, 'b': 4095, 'what': 'SameBoy: plate 5 PULSE (the world flips on its own beat)'},
        {'src': 'sameboy', 'a': 4831, 'b': 5011, 'what': 'SameBoy: plate 6 ROTARY'},
        {'src': 'sameboy', 'a': 5826, 'b': 6006, 'what': 'SameBoy: plate 7 NEGATIVE'},
        {'src': 'sameboy', 'a': 6630, 'b': 6690, 'what': 'SameBoy: plate card THE SMUDGE'},
        {'src': 'sameboy', 'a': 6790, 'b': 6965, 'what': 'SameBoy: boss, first hit (6885)'},
        {'src': 'sameboy', 'a': 7530, 'b': 8033, 'what': 'SameBoy: boss, hits 4 and 5 (7604, 7799), boss defeated'},
        {'src': 'sameboy', 'a': 8033, 'b': 8274, 'hold': 60, 'what': 'SameBoy: FINAL PAGE ending card (last frame held 1 s)'},
        {'src': 'sheet', 'a': 0, 'b': 300, 'what': 'page: technical sheet -> pointer leads the camera onto the Bank layout block (ROM 0-3 used / free) -> hold'},
    ]
    thirty = [
        {'src': 'intro', 'a': 60, 'b': 240, 'what': 'page: pointer leads the camera from the Cartridge card to the screen, clicks Insert cartridge -> boot -> title'},
        {'src': 'sameboy', 'a': 20, 'b': 174, 'what': 'SameBoy: title, START, plate card MARGINS'},
        {'src': 'sameboy', 'a': 174, 'b': 384, 'what': 'SameBoy: plate 1 MARGINS, opening'},
        {'src': 'sameboy', 'a': 756, 'b': 936, 'what': 'SameBoy: plate 1 MARGINS, exit + CLEAR'},
        {'src': 'sameboy', 'a': 1200, 'b': 1380, 'what': 'SameBoy: plate 2 GALLEY - mid-air ink flips over the spike floor (1253, 1326)'},
        {'src': 'sameboy', 'a': 5826, 'b': 5976, 'what': 'SameBoy: plate 7 NEGATIVE'},
        {'src': 'sameboy', 'a': 6630, 'b': 6690, 'what': 'SameBoy: plate card THE SMUDGE'},
        {'src': 'sameboy', 'a': 6799, 'b': 6934, 'what': 'SameBoy: boss, first hit'},
        {'src': 'sameboy', 'a': 7730, 'b': 8033, 'what': 'SameBoy: boss, fifth hit, boss defeated'},
        {'src': 'sameboy', 'a': 8033, 'b': 8274, 'hold': 7, 'what': 'SameBoy: FINAL PAGE ending card (last frame held)'},
    ]
    for shots, n in ((sixty, 3600), (thirty, 1800)):
        tot = sum(s['b'] - s['a'] + s.get('hold', 0) for s in shots)
        assert tot == n, (tot, n)
    report = {'capture': 'frame-stepped software capture: one emulated frame per 60 fps output frame (hardware runs 59.73 Hz, so gameplay is 0.45% fast); SameBoy frames are the verified campaign run with --palette paper, scaled 160x144 -> 1120x1008 (7x nearest-neighbour) on the page bezel colour; page frames are headless-Chromium renders of the page at device scale 2 from which a 16:9 camera rectangle is clipped per frame and resized to 1920x1080 (the pointer-led moves onto the Cartridge card, the screen and the Bank layout block), with the page\'s binjgb core stepped one frame per output frame for the boot. The pointer is a DOM element drawn by the page during capture; it leads the two camera moves and clicks Insert cartridge. No real-time GPU or browser performance is measured or implied.',
              'sources': {
                  'rom_sha256': '45748f2c4249d8a78b15c372d873d03c7c7e2f200825fdcbc504a39944e178b9',
                  'game_frames': 'sameboy_runner --input evidence/campaign/campaign_input.txt --origin probe:g_frame --input-clock gframe '
                                 '--frames 8687 --boot <SameBoy>/build/bin/tester/dmg_boot.bin --probe g_frame=0xC0B1:2 --probe g_state=0xC0B3 '
                                 '--probe g_level=0xC0B4 --probe g_px=0xC0B5:2 --probe g_py=0xC0B7:2 --probe g_hearts=0xC0B9 --probe g_sorts=0xC0BA '
                                 '--probe g_phase=0xC0BB --probe g_ly_end=0xC0BD --probe g_lag=0xC0BF --probe g_boss_hp=0xC0C0 '
                                 '--probe g_ending_reached=0xC0C1 --probe g_deaths=0xC0C2:2 --until g_ending_reached==1 --until-grace 240 '
                                 '--palette paper --trace <work>/sameboy/trace.csv --raw <work>/sameboy/campaign_paper.rgb rom/HALFTONE.gb '
                                 '(8274 frames; trace identical to evidence/campaign/sameboy/trace.csv in every probe and frame-hash column)',
                  'page_frames': 'node tools/film_pages.mjs http://127.0.0.1:8765 <work>/pages   (python3 -m http.server 8765 in web/; camera path per frame in <work>/pages/capture_log.json)',
                  'assembly': 'python3 source/tools/film.py --raw <work>/sameboy/campaign_paper.rgb --pages <work>/pages --out films',
                  'encode': 'ffmpeg libx264 crf 14 preset slow yuv420p 60 fps; segments encoded losslessly (ffv1 rgb24) and concatenated by frame count, no timestamp resampling',
              },
              'films': {}}
    report['films']['Cartridge-60s'] = build('Cartridge-60s', sixty, args, args.work)
    report['films']['Cartridge-30s'] = build('Cartridge-30s', thirty, args, args.work)
    with open(os.path.join(args.out, 'films.json'), 'w') as f:
        json.dump(report, f, indent=1)
    for k, v in report['films'].items():
        print(k, v['width'], 'x', v['height'], v['fps'], 'nb_frames', v['nb_frames'], 'dur', v['duration_s'], 'audio', v['audio_streams'], 'bytes', v['bytes'])


if __name__ == '__main__':
    main()
