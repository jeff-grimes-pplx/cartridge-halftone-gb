# HALFTONE (A5 Cartridge) — independent cold review

Reviewer: independent agent, 2026-10-15. Nothing in the build folder was modified except this `evidence/review/` folder.
All runs used the prebuilt runners in `/tmp/a5-tools/bin` and the ROM `rom/HALFTONE.gb`.

## Verdict: ACCEPT WITH FIXES

The ROM, the two-emulator receipts, the save/resume path, the budgets, the page and the films all reproduce from a cold start and
match the numbers in `README.md`. The fixes are documentation / tooling consistency items, none change the ROM or the films.

## Check table

| # | Check | Result | Key measured values |
|---|---|---|---|
| 1 | Build reproduces (`make`, `make check` in a copy of `source/`, `build/` and `gen/` deleted first) | PASS | `make` exit 0 in 10.8 s (3 SDCC warnings, see I-7); `build/HALFTONE.gb` sha256 `13f81628…0d65cd` = `rom/HALFTONE.gb` = `web/halftone.gb` (bit-identical, deterministic); `make check` exit 0: rgbfix -v changed nothing, romusage ROM0 9531 / ROM1 11352 / ROM2 9562 / ROM3 11449, WRAM 3085 |
| 2 | Header + trademark strings | PASS | title `HALFTONE`, cart 0x1B, ROM 0x01, RAM 0x02, CGB 0x00, SGB 0x00, dest 0x00, lic 0x33, ver 1; header checksum 0xE4 = computed, global 0x4CB9 = computed; `rgbfix -v` output `cmp`-identical. ROM binary: 0 hits for Nintendo/Game Boy/GAMEBOY/GameBoy. `web/` served files (index.html, app.js, sheet.json, vendor): 0 hits. Hits only in source comments (`game.h:1`, `main.c:2`, `pix.py:8`), SDCC listing banners in `build/*.sym` ("(GameBoy)"), and the copied `web/evidence/EMULATORS.md` ("Game Boy cores") — descriptive, not in the product |
| 3 | Campaign from power-on in both cores | PASS | SameBoy: exit 0, 8263 frames, until hit @8022, illegal_opcode false, pc_in_vram_oam_io 0, sp_min 0xDFB7, oam max/line 8, obscured 0. mGBA: exit 0, 8246 frames, until hit @8005, illegal false, sp_min 0xDFB7, oam 8/0. Both fresh `summary.json` identical to `evidence/campaign/*/summary.json` in every field except `rom` path and `png_frames`. End-of-campaign SRAM sha256 `881176f5…3191` identical across fresh SameBoy, fresh mGBA and all three evidence copies. Fresh SameBoy trace identical to evidence trace in every shade hash and probe |
| 3b | Two-core agreement | PASS (tool caveat, I-1) | Game-frame alignment (my own script, same rule as `source/tools/verify_levels.py::compare_by_gframe`): 8060 aligned frames; gameplay probes (`g_state,g_level,g_px,g_py,g_hearts,g_sorts,g_phase,g_lag,g_boss_hp,g_ending_reached,g_deaths`) identical on 8060/8060; 814 video mismatches, all with `obj_xprio_overlaps>0`, 0 unexplained. `g_ly_end` differs by exactly 1 line on 64 frames (timing probe only). The shipped `tools/compare_traces.py` aligns on emulator frame, reports `agree:false`, first divergence 67, exit 1 |
| 4 | Each plate completable (all 8 replayed in SameBoy with `start.sav`) | PASS | clear frames 846 / 816 / 805 / 888 / 806 / 908 / 834 / 1367 (plate 8 → state 8 BOSS_DEAD) — all equal to `levels.json` `clear_frame`; sorts 7/9/9/9/10/9/11/0 as recorded; 0 deaths; no illegal opcode; `g_level` constant per plate |
| 5 | Save / resume | PASS | `after_plate2.sav` + `resume_input.txt`: SameBoy reaches `g_state==3` at frame 174 with `g_level==2`; mGBA at 172 with `g_level==2`. Record decode (`HFT1`, 21 bytes, chk = 0x7F+sum): after_plate2 → next plate 2, 15 sorts, 1314 frames, complete 0, checksum ok; end_of_campaign (evidence and both fresh dumps) → next plate 7, 54 sorts, 5882 frames (98.5 s = 01:38), complete 1, checksum ok; corrupt_checksum.sav → checksum bad as intended |
| 6 | Budgets from fresh SameBoy trace | PASS | ST_PLAY frames 5882, busy mean 47.0 %, max 84.5 %, 0 frames > 85 %, 0 at 100 %. Per plate (play frames / mean / max / OBJ-line / OBJ): 1: 672/37.6/64.9/5/5 · 2: 642/40.6/67.8/5/8 · 3: 631/42.7/67.0/5/7 · 4: 713/57.0/84.5/8/11 · 5: 632/48.5/71.0/6/6 · 6: 733/54.8/80.7/8/11 · 7: 659/54.4/83.1/6/9 · 8: 1200/42.6/74.4/8/12 — every cell equals README's table. 100 %-busy frames: 186 emulator frames in 17 contiguous display-off runs (6–16 frames each) in states 2/5/8, `g_frame` constant inside each run, `g_lag` final 17 |
| 7 | Browser page (local, headless Chromium) | PASS | `GET /halftone.gb` → 200, 65536 bytes, sha256 matches; status "ready · halftone · 64 KiB"; click "Insert cartridge" → "running", `window.__halftone` exposed, canvas hash changes; Enter (held 120 ms) → plate 1; ArrowRight scrolls; Z flips HUD "I INK"→"C CHALK"; X jumps (see `web_enter_right_z_x.png`). Emulation advanced 6.52 emulated s in ~6.5 s wall. Keymap in `app.js` = arrows, KeyX=A, KeyZ=B, Enter=Start, Shift=Select — matches README and the on-page Controls card. 1280 px: no element overflows, 0 console errors. 390 px: page `scrollWidth` 390 (no horizontal page overflow), the per-plate `table.data` is wider than the viewport (right edge 627 px) but scrolls inside its wrapper as designed; 0 console errors. No marketing copy found (text dump reviewed). Deployed URL: NOT VERIFIABLE — returns HTTP 403 Cloudflare "Performing security verification" challenge to headless Chromium and to curl |
| 8 | Films | PASS | Both: h264 yuv420p 1920×1080, 60/1 fps, 1 stream, 0 audio; 60 s = 3600 frames (counted), 2,555,823 B; 30 s = 1800 frames, 758,961 B. 12 evenly spaced frames each show page intro, title, plates 1/2/4/7, boss, FINAL PAGE card, (60 s) technical sheet. Game area 1120×1008 at (400,36): 7× blocks exact (max intra-block deviation 15/255, mean 0.02); film frame 694 reconstructs SameBoy native frame 264 (paper palette) with max channel error 6 → real emulator output, integer scaled. 0 blank frames (std<3), 0 dark frames (mean<20); 3 hard cuts in 60 s (269, 449, 3122) and 2 in 30 s (39, 149), all at shot boundaries; long static holds are the page/card/ending holds listed in `films.json`. No captions, badges or added text; pointer visible only in the intro (moving to and clicking the button). `films.json` shot table (frame ranges, out_frames, nb_frames, bytes) matches ffprobe |
| 9 | Originality / asset provenance | PASS | Only binaries under `source/`+`web/`: 8 `gen/preview_*.png` (written by `art.py`), `build/HALFTONE.cdb` (SDCC debug), `web/vendor/binjgb.wasm` (+ LICENSE), `web/evidence/contact_campaign.png`. `src/*.c` include only `game.h`, `gen/*.h`, `hUGEDriver.h`, `<string.h>`. Fresh `gen/{gfx,levels,music}.c` sha-identical to shipped. Counts: BG tiles 76+52+48=176, OBJ 88+48=136, META 24, 8 levels, 65 `*` sorts (7/9/9/10/10/9/11/0), 7 `hUGESong_t`, 13 SFX rows. Art (previews + keyframes) is a consistent chunky two-ink style, legible at 160×144; see I-8 for a subjective note |
| 10 | Honesty of README/STATUS/films.json | PASS with notes | No claim of human playtesting (explicitly disclaimed in README, STATUS, CONTRACT, sheet.json); no real-time performance claim (films.json and README disclaim it). All numbers I could check are exact. Items I could not verify or that are overstated are listed below |

## Commands run (abridged; full probe list in `evidence/campaign/sameboy/cmd.txt`)

```sh
# 1 build
cp -r source /tmp/review/source && cd /tmp/review/source && rm -rf build gen && make && make check && sha256sum build/HALFTONE.gb
# 2 header
/tmp/a5-tools/rgbds/rgbfix -v rom/HALFTONE.gb -o /tmp/review/fixed.gb && cmp rom/HALFTONE.gb /tmp/review/fixed.gb
python3 (parse 0x134-0x14F, recompute header/global checksums, regex for Nintendo|Game ?Boy over the ROM bytes)
grep -rniE "nintendo|game ?boy" web source
# 3 campaign (PROBES = the 13 --probe flags from evidence/campaign/sameboy/cmd.txt)
/tmp/a5-tools/bin/sameboy_runner --boot /tmp/a5-tools/SameBoy/build/bin/tester/dmg_boot.bin --input evidence/campaign/campaign_input.txt \
  --origin probe:g_frame --input-clock gframe --frames 8687 $PROBES --until g_ending_reached==1 --until-grace 240 \
  --trace /tmp/review/camp/sb/trace.csv --summary /tmp/review/camp/sb/summary.json --sram-out /tmp/review/camp/sb/end.sav rom/HALFTONE.gb
/tmp/a5-tools/bin/mgba_runner --input evidence/campaign/campaign_input.txt --origin probe:g_frame --input-clock gframe --frames 8687 $PROBES \
  --until g_ending_reached==1 --until-grace 240 --trace /tmp/review/camp/mg/trace.csv --summary /tmp/review/camp/mg/summary.json --sram-out /tmp/review/camp/mg/end.sav rom/HALFTONE.gb
python3 tools/compare_traces.py /tmp/review/camp/sb/trace.csv /tmp/review/camp/mg/trace.csv --json /tmp/review/camp/cmp.json   # exit 1, see I-1
python3 (align both CSVs on g_frame, drop repeated g_frame rows, compare probes + shade_fnv, check obj_xprio_overlaps on mismatches)
# 4 plates (N = 1..8, F = --frames value from evidence/levels/plateN/sameboy/cmd.txt)
/tmp/a5-tools/bin/sameboy_runner --boot … --input evidence/levels/plateN/input.txt --origin probe:g_frame --input-clock gframe --frames F $PROBES \
  --sram-in evidence/levels/plateN/start.sav --trace … --summary … rom/HALFTONE.gb
# 5 save/resume (both runners)
… --input evidence/save-resume/resume_input.txt --origin probe:g_frame --input-clock frame --frames 900 $PROBES \
  --sram-in evidence/save-resume/after_plate2.sav --until g_state==3 --until-grace 5 … rom/HALFTONE.gb
python3 (decode 21-byte record: magic[0:4] plate[4] sorts[5:13] deaths<H[13:15] frames<I[15:19] complete[19] chk[20], chk=(0x7F+sum(b[0:20]))&0xFF)
# 6 budgets: pandas-free python over /tmp/review/camp/sb/trace.csv grouped by g_state==3 and g_level
# 7 web: Playwright (NODE_PATH=/home/user/node_modules) against http://127.0.0.1:8765 at 1280x900 and 390x900; curl -w %{size_download} /halftone.gb
# 8 films
ffprobe -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames,pix_fmt -show_entries format=nb_streams,size films/Cartridge-{60,30}s.mp4
ffprobe -count_frames -select_streams v:0 -show_entries stream=nb_read_frames …
ffmpeg -i … -vf "select=eq(n\,N)" -vframes 1 …   (12 frames each + 694 for the pixel check); ffmpeg … -vf scale=192:108 -pix_fmt gray -f rawvideo (blank/cut scan)
```

## Issues (prioritised)

| ID | Severity | File | Finding | Change |
|---|---|---|---|---|
| I-1 | Medium | `tools/compare_traces.py`, `tools/EMULATORS.md` | EMULATORS.md says `compare_traces.py` "aligns two traces on the game frame counter" and reports overlap-explained mismatches; the shipped script aligns on emulator frame only, has no `obj_xprio_overlaps` logic, and exits 1 (`agree:false`, first divergence 67) on the very traces the receipts are built from. The real logic is `compare_by_gframe` in `source/tools/verify_levels.py`. A reader following EMULATORS.md cannot reproduce `compare.json` | Either port `compare_by_gframe` into `tools/compare_traces.py` (add `--align gframe`), or correct EMULATORS.md/README to point at `source/tools/verify_levels.py`/`verify_campaign.py` |
| I-2 | Medium | `web/index.html` line 103 (`Hardware` row), `web/sheet.json` | "Runs on original DMG hardware via a flash cartridge…" is stated as fact, then disclaimed in the next sentence. README correctly says hardware behaviour is "inferred, not observed" | Reword to "Targets original DMG hardware (MBC5 + 8 KiB battery RAM flash cartridge); not tested on hardware in this build" |
| I-3 | Low | `README.md` "Verification receipts" / "Budgets" | README does not document the SRAM record layout (CONTRACT: "SRAM layout documented"); it exists only in `web/sheet.json` and in code. The review brief assumed README has it | Add one line: 21-byte record at 0xA000 — `HFT1`, next plate, 8 sort masks, falls u16, frames u32, complete, checksum = 0x7F + sum of the first 20 bytes |
| I-4 | Low | `tools/EMULATORS.md` ("CPU accounting") | "both cores agree on the game's own `g_ly_end` and `g_lag` probes" — `g_lag` yes; `g_ly_end` differs by exactly 1 scanline on 64 of 8060 aligned frames (mGBA one line earlier) | Say "g_lag identical; g_ly_end within ±1 line" |
| I-5 | Low | `README.md` Budgets bullet 1 | "The only 100 % frames are the display-off level loads … 17 over the run" reads as 17 frames; measured: 17 load events totalling 186 emulator frames (6–16 each, ~100–270 ms of blank screen), and `frames_without_halt` in summary.json is 169 | Say "17 display-off loads (186 emulator frames total; none inside PLAY)" |
| I-6 | Low | `tools/sameboy_runner.c` (and likely `mgba_runner.c`) | `--png-dir` pointing at a non-existent directory writes nothing but `summary.json` still reports `png_frames: N` and exit 0 (reproduced with `--png-dir /tmp/review/nonexistent_dir --png-frames 10,20` → `png_frames: 2`, no files) | `mkdir -p` the directory or fail/report 0 when `fopen` fails |
| I-7 | Info | `source/src/main.c:223`, `source/src/engine.c:400` | SDCC warnings 110 ("conditional flow changed by optimizer") and 126 ("unreachable code") during `make` | Harmless; optionally silence or note in README's build section |
| I-8 | Info | `web/app.js` keyboard handling | A key tap shorter than one emulated frame (down+up within ~16 ms, as Playwright's `press` does) is not seen by the game; held keys work. Real keyboards produce longer presses, so not a user-facing bug, but automated QA must hold keys (web_qa.mjs apparently does) | Optional: latch a keydown until the next joypad poll |
| I-9 | Info | `web/evidence/EMULATORS.md`, `source/src/*.c` comments, `source/tools/pix.py` | The phrase "Game Boy" appears in descriptive comments and in the EMULATORS.md copy served from `web/evidence/`. Not in the ROM, page HTML, or sheet. If the intent is zero first-party names anywhere served, the served copy of EMULATORS.md is the one hit | Optional: replace with "DMG" in the served copy |
| I-10 | Not verifiable | README/STATUS deployed-URL claims | `https://www.perplexity.ai/computer/a/cartridge-IQ5WbniuSzyAfLU.aiY3kA` returns a Cloudflare bot challenge (HTTP 403) to headless Chromium and curl; "live page checked (status ready, game starts, ROM 200 / 65,536 B)" in STATUS.md could not be re-observed here | None required; state in README that the deployed page needs an authenticated browser session |

Subjective visual note (no action required): levels concentrate content in the lower half of the 160×144 screen and the upper area is
often empty paper; the boss arena is sparse. Art is consistent and legible; HUD rows are tight but readable.

## Artifacts in this folder

`fresh_sameboy_summary.json`, `fresh_mgba_summary.json`, `fresh_compare_traces_output.json` (the shipped tool's output, exit 1),
`make.log`, `make_check.log`, `web_1280_contact.png`, `web_390_contact.png`, `web_title_before_after_Z.png`, `web_enter_right_z_x.png`,
`film60_contact.png`, `film30_contact.png`, `film60_intro_seq.png`, `campaign_keyframes_2x.png`, `art_previews.png`.
