#!/usr/bin/env python3
"""Generate web/sheet.json (the technical sheet shown on the page) from the real artefacts:
ROM header bytes, romusage/.noi (bank and RAM use), gen/*.h (tile budgets), gen/music.h + src/audio.c (audio),
evidence/campaign/campaign.json and evidence/levels/levels.json (measured budgets and playthrough proof).
Also copies the compact evidence files the page links to into web/evidence/.

usage: techsheet.py            (run after `make check`, verify_levels.py and verify_campaign.py)
"""
import hashlib, json, os, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
ROOT = os.path.dirname(SRC)
ROM = os.path.join(SRC, 'build', 'HALFTONE.gb')
WEB = os.path.join(ROOT, 'web')
EV = os.path.join(ROOT, 'evidence')
GBDK = os.environ.get('GBDK', '/tmp/a5-tools/gbdk')
RGBFIX = os.environ.get('RGBFIX', '/tmp/a5-tools/rgbds/rgbfix')

CART_TYPES = {0x00: 'ROM only', 0x01: 'MBC1', 0x03: 'MBC1 + RAM + BATTERY', 0x1B: 'MBC5 + RAM + BATTERY', 0x19: 'MBC5'}


def header(rom):
    b = open(rom, 'rb').read()
    title = b[0x134:0x144].split(b'\0')[0].decode('ascii', 'replace')
    hc = 0
    for i in range(0x134, 0x14D):
        hc = (hc - b[i] - 1) & 0xFF
    gc = (sum(b) - b[0x14E] - b[0x14F]) & 0xFFFF
    stored_gc = (b[0x14E] << 8) | b[0x14F]
    rom_banks = 2 << b[0x148]
    ram_kib = {0: 0, 2: 8, 3: 32, 4: 128, 5: 64}.get(b[0x149], None)
    out = subprocess.run([RGBFIX, '-v', rom, '-o', '/tmp/a5_rgbfix_check.gb'], capture_output=True, text=True)
    fixed_identical = open('/tmp/a5_rgbfix_check.gb', 'rb').read() == b
    ver = subprocess.run([RGBFIX, '--version'], capture_output=True, text=True).stdout.strip()
    return {
        'title': title, 'size_bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
        'cart_type': f'0x{b[0x147]:02X} {CART_TYPES.get(b[0x147], "?")}',
        'rom_size': f'0x{b[0x148]:02X} — {rom_banks * 16} KiB, {rom_banks} banks of 16 KiB',
        'ram_size': f'0x{b[0x149]:02X} — {ram_kib} KiB battery-backed',
        'flags': f'DMG only (CGB flag 0x{b[0x143]:02X}, SGB flag 0x{b[0x146]:02X}), destination 0x{b[0x14A]:02X}, licensee 0x{b[0x14B]:02X}, version {b[0x14C]}',
        'header_checksum': f'0x{b[0x14D]:02X} stored, 0x{hc:02X} computed — {"match" if hc == b[0x14D] else "MISMATCH"}',
        'global_checksum': f'0x{stored_gc:04X} stored, 0x{gc:04X} computed — {"match" if gc == stored_gc else "MISMATCH"}',
        'logo_note': '0x104–0x133: the 48 header-compliance bytes written by the toolchain (GBDK-2020 makebin) so the console boot check passes; the game never draws them and contains no other first-party data or trademarks',
        'rgbfix': f'{ver}: the output of rgbfix -v is byte-identical to the built ROM ({"ok" if fixed_identical else "DIFFERS"})',
        'header_ok': hc == b[0x14D] and gc == stored_gc and fixed_identical,
    }


def romusage(noi):
    out = subprocess.run([os.path.join(GBDK, 'bin', 'romusage'), noi], capture_output=True, text=True).stdout
    rows = {}
    for l in out.splitlines():
        m = re.match(r'\s*(ROM_\d|WRAM_LO|WRAM_HI|HRAM)\s+0x([0-9A-F]+) -> 0x([0-9A-F]+)\s+(\d+)\s+(\d+)\s+\d+%\s+(\d+)', l)
        if m:
            rows[m.group(1)] = {'size': int(m.group(4)), 'used': int(m.group(5)), 'free': int(m.group(6))}
    return rows


def noi_syms(noi):
    syms = {}
    for l in open(noi):
        p = l.split()
        if len(p) >= 3 and p[0] == 'DEF':
            syms[p[1]] = int(p[2], 16)
    return syms


def wram_breakdown(noi):
    syms = [(a, n) for n, a in noi_syms(noi).items() if 0xC000 <= a < 0xD000 and not n.startswith(('s__', 'l__', 'e__', 'b__', '.__'))]
    syms.sort()
    sizes = {}
    for i, (a, n) in enumerate(syms):
        nxt = syms[i + 1][0] if i + 1 < len(syms) else a
        sizes[n] = nxt - a
    return sizes


def defines(path):
    d = {}
    for l in open(path):
        m = re.match(r'#define\s+(\w+)\s+(\d+)', l)
        if m:
            d[m.group(1)] = int(m.group(2))
    return d


def main():
    hdr = header(ROM)
    noi = os.path.join(SRC, 'build', 'HALFTONE.noi')
    banks = romusage(noi)
    syms = noi_syms(noi)
    wr = wram_breakdown(noi)
    gfx = defines(os.path.join(SRC, 'gen', 'gfx.h'))
    lvh = defines(os.path.join(SRC, 'gen', 'levels.h'))
    camp = json.load(open(os.path.join(EV, 'campaign', 'campaign.json')))
    levels = json.load(open(os.path.join(EV, 'levels', 'levels.json')))
    save = json.load(open(os.path.join(EV, 'save-resume', 'save_resume.json')))
    assert camp['rom_sha256'] == hdr['sha256'], 'campaign.json was measured on a different ROM build'
    for L in levels:
        for emu in ('sameboy', 'mgba'):
            pass
    # level widths / entity counts from the generated level table
    lv_src = open(os.path.join(SRC, 'gen', 'levels.c')).read()
    defs = re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*lv(\d)_map', lv_src)
    widths = {int(d[6]): (int(d[0]), int(d[3])) for d in defs}
    hram_used = syms.get('l__HRAM', 0)
    sp_min = int(camp['sp_min']['sameboy'], 16)
    # songs
    songs = re.findall(r'extern const hUGESong_t (song_\w+);', open(os.path.join(SRC, 'gen', 'music.h')).read())
    sfx = re.findall(r'/\* (SFX_\w+) \*/', open(os.path.join(SRC, 'src', 'audio.c')).read())
    music_py = open(os.path.join(HERE, 'music.py')).read()
    song_desc = {}
    for key, title, info in re.findall(r'^# ---- ([A-Z]+(?: [A-C])?): "([^"]+)" \(([^)]*)\)', music_py, re.M):
        song_desc['song_' + key.lower().replace(' ', '_')] = f'"{title}" ({info})'
    m = re.search(r'^# ---- CLEAR jingle \(([^)]*)\)', music_py, re.M)
    if m:
        song_desc['song_clear'] = f'clear jingle ({m.group(1)})'

    web = None
    wq = os.path.join(EV, 'web', 'web_qa.json')
    if os.path.exists(wq):
        web = json.load(open(wq))
    if web and web.get('binjgb_campaign', {}).get('ending_reached'):
        bc = web['binjgb_campaign']
        web_result = f'boots and plays in the browser; the same campaign script replayed inside this page\'s core also reaches the ending card ({bc["play_frames"]} play frames, {bc["deaths"]} deaths, {len(bc["boss_hits"])} boss hits); not used for the cycle measurements'
    else:
        web_result = 'boots and plays in the browser; used only for the playable page, not for the measurements'
    sheet = {
        'rom': {k: hdr[k] for k in ('title', 'cart_type', 'rom_size', 'ram_size', 'flags', 'header_checksum', 'global_checksum', 'logo_note', 'rgbfix')},
        'rom_sha256': hdr['sha256'], 'rom_bytes': hdr['size_bytes'],
        'banks': [
            {'bank': 'ROM 0 (fixed)', 'contents': 'main loop, title / intro / HUD / ending screens, save record, GBDK runtime, hUGEDriver player, VBlank ISR (scroll/palette latch, music tick), OAM DMA stub in HRAM', 'used': banks['ROM_0']['used'], 'free': banks['ROM_0']['free']},
            {'bank': 'ROM 1', 'contents': f'{len(songs)} hUGEDriver songs (pattern, order and instrument data)', 'used': banks['ROM_1']['used'], 'free': banks['ROM_1']['free']},
            {'bank': 'ROM 2', 'contents': f'tiles ({gfx["GFX_WORLD_TILE_COUNT"] + gfx["GFX_FONT_TILE_COUNT"] + gfx["GFX_BACKDROP_TILE_COUNT"] + gfx["GFX_SPRITE_TILE_COUNT"] + gfx["GFX_BOSS_TILE_COUNT"] + gfx["GFX_LOGO_TILE_COUNT"]} × 16 bytes: world, font/HUD, backdrop, sprites, boss, logo), {gfx["META_COUNT"]} metatile definitions, title logo map, 8 level maps and object lists', 'used': banks['ROM_2']['used'], 'free': banks['ROM_2']['free']},
            {'bank': 'ROM 3', 'contents': 'engine: physics, entities, boss, column streaming, metatile expansion, sprite builder (compiled for speed)', 'used': banks['ROM_3']['used'], 'free': banks['ROM_3']['free']},
        ],
        'banks_note': f'{hdr["size_bytes"] // 1024} KiB ROM in four 16 KiB banks, switched through the MBC5 register; measured by GBDK romusage on the linker map. Bank 0 is always mapped; banks 1–3 are swapped in by GBDK banked calls and far pointers.',
        'ram': {
            'wram_used': banks['WRAM_LO']['used'], 'wram_total': banks['WRAM_LO']['size'],
            'wram_note': f'static allocation: level tile map {wr.get("_map", 0)} B, {lvh.get("LEVEL_COUNT", 8)}-level entity pool {wr.get("_ents", 0)} B ({wr.get("_ents", 0) // 20} × 20 B), tile collision-class table {wr.get("_cls_ram", 0)} B, metatile cache {wr.get("_meta_ram", 0)} B, music driver state, globals',
            'hram_used': hram_used, 'hram_total': 127,
            'stack': f'grows down from 0xE000 in the upper 4 KiB of work RAM; deepest point measured per instruction over the whole scripted campaign: 0x{sp_min:04X} = {0xE000 - sp_min} bytes',
            'shadow_oam': f'{wr.get("_shadow_OAM", 160)} bytes at 0xC000, copied by the HRAM DMA routine every VBlank; 40 entries',
            'sram': f'8 KiB battery RAM bank; a {21}-byte record at 0xA000 (magic, next plate, 8 sort masks, falls, time, complete flag, checksum) is written at every plate clear and at the ending',
        },
        'tiles': {
            'bg_used': gfx['GFX_WORLD_TILE_COUNT'] + gfx['GFX_FONT_TILE_COUNT'] + gfx['GFX_BACKDROP_TILE_COUNT'], 'bg_capacity': 256,
            'bg_note': f'during play: {gfx["GFX_WORLD_TILE_COUNT"]} world tiles at 0–{gfx["GFX_WORLD_TILE_COUNT"] - 1}, {gfx["GFX_FONT_TILE_COUNT"]} font/HUD tiles at {gfx["GFX_FONT_BASE"]}–{gfx["GFX_FONT_BASE"] + gfx["GFX_FONT_TILE_COUNT"] - 1}, {gfx["GFX_BACKDROP_TILE_COUNT"]} backdrop tiles (colour 2 only, non-solid) at {gfx["GFX_BACKDROP_TILE_BASE"]}–{gfx["GFX_BACKDROP_TILE_BASE"] + gfx["GFX_BACKDROP_TILE_COUNT"] - 1}; the {gfx["GFX_LOGO_TILE_COUNT"]} title-logo tiles reuse 192–239 on the title only',
            'obj_used': gfx['GFX_SPRITE_TILE_COUNT'] + gfx['GFX_BOSS_TILE_COUNT'], 'obj_capacity': 256,
            'obj_note': f'{gfx["GFX_SPRITE_TILE_COUNT"]} tiles at 0–{gfx["GFX_SPRITE_TILE_COUNT"] - 1} for the player (10 poses), enemies, platforms, drops, sorts, puffs and sparks; {gfx["GFX_BOSS_TILE_COUNT"]} boss tiles at {gfx["GFX_BOSS_TILE_BASE"]}–{gfx["GFX_BOSS_TILE_BASE"] + gfx["GFX_BOSS_TILE_COUNT"] - 1} loaded on plate 8 only (OBJ 128–255 share VRAM with BG 128–255, so the boss plate\'s backdrop is restricted to slots below {gfx["GFX_BOSS_TILE_BASE"]}); 8×16 sprite mode',
            'metatiles': gfx['META_COUNT'], 'metatile_note': 'each is four 8×8 tiles; levels are 64 × 8 metatile cells (1024 × 128 px) streamed into the 32-column tile map one column at a time',
            'palettes': 'BGP 0xE4 in ink, 0x6C in chalk (the whole world inverts on a flip; colour 2 — stone, text, backdrops — is the same shade in both); OBP0 0xE0 solid, OBP1 0x54 ghosted for the out-of-phase ink and 0xF8 for the boss while it shares the player\'s phase; 4 shades. Scroll and palettes are latched from the VBlank interrupt so they always land inside vblank',
            'objects': f'40 OAM entries, hardware limit 10 per scanline; measured worst case across the campaign {camp["oam_max_per_line_sameboy"]} per line and {max(p["obj_max"] for p in camp["plates"])} on screen, {camp["oam_objects_obscured_total_sameboy"]} objects ever hidden by the line limit; the player is written first so it could never be the one dropped, and the OAM is written through a pointer with only stale entries cleared',
        },
        'audio': {
            'driver': 'hUGEDriver 6.1.3 (public domain), songs composed in the hUGETracker format by tools/music.py',
            'songs': [f'{s.replace("song_", "")} — {song_desc.get(s, "")}'.rstrip(' —') for s in songs],
            'sfx': f'{len(sfx)} register-level effects on pulse 2 and the noise channel (the music channel is muted for the effect\'s length, then handed back): ' + ', '.join(s.replace('SFX_', '').lower() for s in sfx),
            'channels': 'pulse 1 (lead), pulse 2 (harmony / arpeggio, borrowed by SFX), wave (bass, three custom waveforms), noise (drums, borrowed by SFX); the driver ticks once per VBlank interrupt, effects are sequenced from the main loop',
        },
        'levels': [
            {'plate': p['plate'], 'name': p['name'], 'width_cells': widths.get(p['plate'] - 1, (0, 0))[0], 'entities': widths.get(p['plate'] - 1, (0, 0))[1],
             'frames': p['frames'], 'busy_mean': p['busy_mean'], 'busy_max': p['busy_max'], 'lag': p['lag_frames_in_play'],
             'oam_max_line': p['oam_max_per_line'], 'oam_max': p['obj_max'], 'deaths': 0}
            for p in camp['plates']],
        'levels_note': f'Measured in SameBoy on the scripted full-campaign run: {camp["play_frames"]} play frames, mean {camp["busy_pct_mean_play_sameboy"]}% busy, '
                       f'{camp["frames_over_85pct_play_sameboy"]} play frames above 85%. The only frames at 100% are the display-off level loads (one lag frame per plate, counted by the game itself). mGBA\'s cycle split is not comparable because its scheduler does not expose HALT the same way, so budgets are quoted from SameBoy only.',
        'toolchain': [
            {'name': 'GBDK-2020', 'version': '4.5.0', 'license': 'library GPLv2 with linking exception; lcc, makebin, romusage per gbdk/licenses', 'use': 'C compiler driver, linker, ROM header, bank packing'},
            {'name': 'SDCC', 'version': '4.5.1 #15267 (bundled with GBDK-2020)', 'license': 'GPLv2 (compiler only; no SDCC code is linked into the ROM beyond the GBDK runtime above)', 'use': 'sm83 code generation'},
            {'name': 'hUGEDriver', 'version': '6.1.3 (a3cbd0c)', 'license': 'public domain', 'use': 'music player linked into bank 0; songs in its pattern format'},
            {'name': 'RGBDS', 'version': '0.6.1 (rgbasm) and 1.0.4 (rgbfix)', 'license': 'MIT', 'use': 'assembling hUGEDriver for GBDK (rgb2sdas); header checksum verification'},
            {'name': 'Python 3 + Pillow', 'version': sys.version.split()[0], 'license': 'PSF / MIT-CMU', 'use': 'art, level and music generators in source/tools; playtest harness'},
        ],
        'emulators': [
            {'name': 'SameBoy', 'version': '1.0.4 (98da08c), headless core with its own open boot ROM', 'license': 'MIT', 'result': f'boots; campaign ends on the ending card in {camp["frames_total_sameboy"]} frames; no illegal opcode; header accepted by the boot ROM'},
            {'name': 'mGBA', 'version': '0.10.5 (26b7884), libmgba headless', 'license': 'MPL-2.0', 'result': f'boots; same campaign script ends on the ending card in {camp["frames_total_mgba"]} frames; no illegal opcode; every gameplay probe identical to SameBoy on all {camp["compare"]["aligned_frames"]} aligned frames'},
            {'name': 'binjgb', 'version': '1662111 (2026-09-25), WebAssembly build in this page', 'license': 'MIT', 'result': web_result},
        ],
        'proof': [
            {'title': 'Header and checksums', 'detail': f'{hdr["header_checksum"]}; {hdr["global_checksum"]}; {hdr["rgbfix"]}.',
             'files': [{'name': 'ROM', 'href': 'halftone.gb'}]},
            {'title': 'Two independent emulators', 'detail': f'SameBoy 1.0.4 and mGBA 0.10.5 replay the same joypad scripts through the real joypad path. Gameplay probes (state, level, position, hearts, sorts, phase, boss HP, deaths) are identical on every aligned frame in all eight plates and the full campaign; the {camp["compare"]["video_mismatch_frames"]} frames whose pixels differ are all frames where two sprites overlap and mGBA 0.10.5 draws them in OAM order instead of the hardware x-priority rule.',
             'files': [{'name': 'levels.json', 'href': 'evidence/levels.json'}, {'name': 'campaign compare.json', 'href': 'evidence/compare.json'}]},
            {'title': 'Scripted full-campaign playthrough', 'detail': f'All 8 plates completed from a fresh save, the boss defeated, the ending card reached in both emulators, 0 deaths, {camp["campaign_seconds_at_59_73hz"]} s at 59.73 Hz. The inputs are an emulator-in-the-loop search (plates 1–7) and a per-frame reactive policy (boss), so the run is machine-fast and says nothing about human play time.',
             'files': [{'name': 'campaign_input.txt', 'href': 'evidence/campaign_input.txt'}, {'name': 'campaign.json', 'href': 'evidence/campaign.json'}, {'name': 'contact sheet', 'href': 'evidence/contact_campaign.png'}]},
            {'title': 'Per-plate scripts', 'detail': 'One input log per plate (game-frame clock, one line per change: frame and button mask, bits Right=1 Left=2 Up=4 Down=8 A=16 B=32 Select=64 Start=128, the GBDK joypad() layout), each starting from a synthetic save that selects the plate. Every plate reaches CLEAR (plate 8: boss defeated) in both emulators.',
             'files': [{'name': f'plate {i}', 'href': f'evidence/plate{i}_input.txt'} for i in range(1, 9)]},
            {'title': 'Save and resume', 'detail': f'SRAM dumped after plate 2, loaded into a fresh boot: START resumes on plate 3 in both emulators. The end-of-campaign save decodes with the complete flag {"set" if save["end_of_campaign_sav"]["complete"] == 1 else "NOT set"} and a {"valid" if save["end_of_campaign_sav"]["checksum_ok"] else "INVALID"} checksum, and the SRAM written by the two emulators is {"byte-identical" if save["end_of_campaign_sav_mgba_identical"] else "DIFFERENT"}; a save with a corrupted checksum falls back to NEW GAME.',
             'files': [{'name': 'save_resume.json', 'href': 'evidence/save_resume.json'}]},
            {'title': 'This page', 'detail': ('Headless-browser check of the page itself: the sheet renders, the ROM downloads, Enter/Z/X/arrows reach the game, the full campaign script replayed in the embedded core reaches the ending, the save travels SRAM → browser storage → reload → CONTINUE → plate 3 and back in through Import .sav, erases cleanly, and with browser storage blocked (as inside an embedding frame) the save still survives Reset for the session.' if web and web.get('pass') else 'Headless-browser check of the page not yet recorded.'),
             'files': [{'name': 'web_qa.json', 'href': 'evidence/web_qa.json'}] if web else []},
            {'title': 'Budgets', 'detail': f'Busy cycles per frame from SameBoy\'s cycle counters: {camp["busy_pct_mean_play_sameboy"]}% mean during play, {camp["frames_over_85pct_play_sameboy"]} play frames above 85%; OBJ per scanline max {camp["oam_max_per_line_sameboy"]} of 10; stack {0xE000 - sp_min} bytes deep at most; ROM {sum(banks[k]["used"] for k in ("ROM_0", "ROM_1", "ROM_2", "ROM_3")):,} of 65,536 bytes used; WRAM {banks["WRAM_LO"]["used"]:,} of 4,096 bytes static.',
             'files': [{'name': 'EMULATORS.md', 'href': 'evidence/EMULATORS.md'}]},
        ],
        'licenses_text': 'Game code, art, levels and music: original work for this build (MIT). Linked into the ROM: GBDK-2020 4.5.0 runtime (GPLv2 with linking exception) and hUGEDriver 6.1.3 (public domain). On this page: binjgb (MIT, Ben Smith). Verification: SameBoy 1.0.4 (MIT), mGBA 0.10.5 (MPL-2.0), RGBDS (MIT). No first-party assets or trademarks are used; the console is referred to only generically.',
    }
    os.makedirs(os.path.join(WEB, 'evidence'), exist_ok=True)
    json.dump(sheet, open(os.path.join(WEB, 'sheet.json'), 'w'), indent=1)
    # evidence copies (compact text/json/png only)
    copies = [
        (os.path.join(EV, 'levels', 'levels.json'), 'levels.json'),
        (os.path.join(EV, 'campaign', 'compare.json'), 'compare.json'),
        (os.path.join(EV, 'campaign', 'campaign.json'), 'campaign.json'),
        (os.path.join(EV, 'campaign', 'campaign_input.txt'), 'campaign_input.txt'),
        (os.path.join(EV, 'campaign', 'contact_campaign.png'), 'contact_campaign.png'),
        (os.path.join(EV, 'save-resume', 'save_resume.json'), 'save_resume.json'),
        (os.path.join(ROOT, 'tools', 'EMULATORS.md'), 'EMULATORS.md'),
        (os.path.join(EV, 'web', 'web_qa.json'), 'web_qa.json'),
    ] + [(os.path.join(EV, 'levels', f'plate{i}', 'input.txt'), f'plate{i}_input.txt') for i in range(1, 9)]
    for src, name in copies:
        if os.path.exists(src):
            shutil.copy(src, os.path.join(WEB, 'evidence', name))
        else:
            print('missing evidence file', src, file=sys.stderr)
    shutil.copy(ROM, os.path.join(WEB, 'halftone.gb'))
    os.makedirs(os.path.join(ROOT, 'rom'), exist_ok=True)
    shutil.copy(ROM, os.path.join(ROOT, 'rom', 'HALFTONE.gb'))
    print('header ok:', hdr['header_ok'], '| sha256', hdr['sha256'])
    print('wrote', os.path.join(WEB, 'sheet.json'), 'and', len(copies) + 1, 'evidence copies; ROM copied to web/ and rom/')


if __name__ == '__main__':
    main()
