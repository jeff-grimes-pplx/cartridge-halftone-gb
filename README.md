# Cartridge — *HALFTONE* (Original 64 KiB Game Boy ROM) & Photoreal 3D DMG-01 Hardware Studio

[![Live 3D DMG-01 Studio](https://img.shields.io/badge/Live_App-Cartridge_Halftone_3D_Studio-c2185b?style=for-the-badge)](https://www.perplexity.ai/computer/a/cartridge-IQ5WbniuSzyAfLU.aiY3kA)
[![ROM Size](https://img.shields.io/badge/ROM-65%2C536_Bytes_(64_KiB_MBC1%2BRAM%2BBAT)-1a237e?style=for-the-badge)](./rom/HALFTONE.gb)
[![SM83 Verification](https://img.shields.io/badge/Verification-PyBoy_%2B_SameBoy_%2B_mGBA_%2B_binjgb_PASS-2e7d32?style=for-the-badge)](./evidence/verification_report.json)

**Cartridge** pairs ***HALFTONE***—an original 64 KiB (`65,536`-byte) 1989 Nintendo Game Boy (`DMG-01`, Sharp `LR35902` / `SM83` CPU @ `4.194304 MHz`, `MBC1+RAM+BATTERY` `0x03`) platformer ROM written in C/SM83 assembly (`GBDK-2020`)—with a **Photorealistic PBR 3D DMG-01 Handheld & SM83 Hardware Engineering Studio** running cycle-accurate WebAssembly emulation (`binjgb.wasm`) in the browser.

- **Live Public Web Application**: [https://www.perplexity.ai/computer/a/cartridge-IQ5WbniuSzyAfLU.aiY3kA](https://www.perplexity.ai/computer/a/cartridge-IQ5WbniuSzyAfLU.aiY3kA)
- **Download Playable 64 KiB Game Boy ROM**: [`rom/HALFTONE.gb`](./rom/HALFTONE.gb) (`SHA-256: 45748f2c4249d8a78b15c372d873d03c7c7e2f200825fdcbc504a39944e178b9`)

---

## 1. *HALFTONE* — Original 64 KiB Game Boy ROM

Set inside a 19th-century rotary printing press, you play as a loose lead type slug navigating 8 printing plates (`MARGINS`, `GALLEY`, `INK WORKS`, `BINDERY`, `PULSE`, `ROTARY`, `NEGATIVE`, and the 5-HP boss plate `THE SMUDGE`).

### Core Mechanic — Dual-Ink Polarity Flip (`B` Button)
Every level contains two opposite halftone block types (**Black Ink** and **White Chalk**) alongside solid lead rules:
- Pressing **`B`** (or `X` / `Shift`) executes a **zero-VRAM-copy palette & collision swap**:
  - In **INK** phase (`BGP = 0xE4`, `OBP1 = 0xE0`), Black Ink tiles are solid platforms and White Chalk tiles are ghosted dotted outlines.
  - In **CHALK** phase (`BGP = 0x6C`, `OBP1 = 0x54`), White Chalk tiles become solid platforms and Black Ink tiles ghost out.
- Because the flip rewrites `BGP` / `OBP1` shadow registers applied in the VBlank ISR rather than copying tiles across VRAM, polarity swaps cost **0 scanlines of PPU bandwidth** and **0 gameplay lag frames**.
- **Plate 7 (`NEGATIVE`)** introduces an automatic 90-frame (`1.5s`) polarity pulse timer, forcing rhythm-timed mid-air jumps.
- **Plate 8 (`THE SMUDGE`)** pits you against a 5-HP sentient ink blot whose phase alternates between Ink and Chalk—you must match its current polarity to stomp it without taking damage.

### Cartridge Header & Bank Budget (`65,536` Bytes Total)

| Field | Value | Verification |
| :--- | :--- | :--- |
| **Title (`0x0134..0x0143`)** | `HALFTONE` | ASCII clean |
| **Cartridge Type (`0x0147`)** | `0x03` (`MBC1+RAM+BATTERY`) | 4 ROM banks + 8 KiB battery-backed SRAM |
| **ROM Size (`0x0148`)** | `0x01` (`64 KiB` / `4 × 16 KiB` banks) | Exact `65,536` bytes (`21,490` bytes slack) |
| **RAM Size (`0x0149`)** | `0x02` (`8 KiB` SRAM @ `0xA000..0xBFFF`) | 21-byte `HFT1` struct + `0x7F`-seeded checksum |
| **Nintendo Logo (`0x0104..0x0133`)** | 48-byte canonical bitmap | Verified bit-exact (`0xCE 0xED 0x66 0x66...`) |
| **Header Checksum (`0x014D`)** | `0xE4` | Computed `0xE4 == 0xE4` (**VALID**) |
| **Global Checksum (`0x014E..0x014F`)** | `0x9062` | Computed `0x9062 == 0x9062` (**VALID**) |

| Bank | Used Bytes | Capacity | Utilization | Contents |
| :--- | ---: | ---: | ---: | :--- |
| **Bank 0 (`HOME`)** | `15,436 B` | `16,384 B` | `94.2%` | VBlank ISR, physics, collision, entities, boss AI, HUD, SRAM save (`main.c`, `play.c`) |
| **Bank 1 (`ROMB1`)** | `14,689 B` | `16,384 B` | `89.7%` | 2bpp tile graphics, RLE level maps, title & ending press artwork (`gfx.c`, `levels.c`) |
| **Bank 2 (`ROMB2`)** | `13,901 B` | `16,384 B` | `84.8%` | 4-channel APU tracker driver, 5 original chiptune scores, 10 SFX (`audio.c`) |
| **Bank 3 (`ROMB3`)** | `0 B` | `16,384 B` | `0.0%` | Reserved expansion bank |
| **Total ROM** | **`44,026 B`** | **`65,536 B`** | **`67.2%`** | **`21,490 B` free slack across 64 KiB image** |

---

## 2. Photorealistic PBR 3D DMG-01 Handheld & SM83 Engineering Studio

The web studio (`studio/`) renders a museum-grade 1989 Nintendo Game Boy (`DMG-01`) alongside an uncropped `160×144` LCD viewport and a live hardware debugger:

1. **Photorealistic PBR 3D 1989 DMG-01 Shell (`studio/dmg_3d.js`)**:
   - Procedural multi-frequency injection-molded ABS pebble-grain bump & roughness textures on the warm grey (`#CBC7BC`) front/rear shell halves, complete with authentic bottom-right diagonal speaker corner chamfer and molded speaker slots with internal mesh depth.
   - Dark grey (`#575660`) recessed screen lens bezel with magenta (`#9B1B52`) and navy (`#232B69`) top rules, silkscreened `"DOT MATRIX WITH STEREO SOUND"` typography, and a glowing red `"BATTERY"` LED with subsurface bloom.
   - Deep olive-green reflective STN glass recess casting a drop shadow onto the `160×144` pixel matrix, driven live each frame by the `binjgb` WebAssembly PPU framebuffer.
   - Tactile matte-black cross D-pad with raised directional arrows and center pivot dimple (`±7.5°` physical tilt on press), glossy concave magenta `A` / `B` buttons (`1.6 mm` travel), angled导电-silicone `SELECT` / `START` pills, left-side rotary `CONTRAST` thumbwheel, right-side `VOLUME` wheel, and bottom `PHONES` stereo jack.
   - **Translucent Smoked-Charcoal 3D Game Pak (`HALFTONE — DMG-HT-USA`)** with custom artwork label, gripped pull tab, and an visible internal gold PCB with **Sharp MBC1 mapper IC**, **LH53517 512-Kbit Mask ROM**, **64-Kbit Low-Power SRAM**, and **CR1616 3V lithium coin battery with yellow perimeter insulator**.
2. **4 Camera Presets + Exploded PCB X-Ray View**:
   - `1 · Desk Hero` — Three-quarter studio view with interactive orbit/tilt.
   - `2 · Uncropped LCD` — Head-on macro view of the bezel and `160×144` dot-matrix glass.
   - `3 · Insert Cart` — Rear-angled slot view with interactive **Eject / Seat Cart** mechanical latch animation (`2.6 units` vertical travel + synthesized snap acoustics).
   - `4 · Exploded PCB X-Ray` — Separates the front shell, main green DMG-01 motherboard (`Sharp LR35902 CPU`, `8 KB Work RAM`, `8 KB Video RAM`, `Sharp Audio Amp`), rear shell with **4× AA battery compartment**, and translucent Game Pak in 3D space.
3. **100% Uncropped `160×144` Primary LCD Monitor + Live SM83 / PPU / APU Hardware Inspector (`studio/emu_studio.js`)**:
   - Guaranteed zero-crop `160×144` primary viewport with `5px` authentic STN olive-green glass margin, toggleable sub-pixel grid overlay, and 3 palette modes (`DMG Olive`, `Paper Ink`, `Pocket B&W`).
   - Instant **Plate `1..8` Warp Selector** (synthesizes a valid `HFT1` SRAM save and boots directly into any plate) and **AI Auto-Play Speedrunner** (`Full 8-Plate Campaign` or `Current Plate Loop`).
   - Live **SM83 CPU & WRAM Probes** (`PC`, `SP`, `BGP`, `OBP0`, `OBP1`, `LCDC`, `STAT`, `SCX`, `SCY`, `LY`, `DIV`, `IE/IF`, `g_frame`, `g_state`, `g_px`, `g_py`, `g_hearts`, `g_phase`, `g_ly_end`, `g_lag`), **PPU VRAM Tile Data (`384` tiles)**, **40-Sprite OAM Table**, **4-Channel APU Oscilloscope (`CH1 Pulse Sweep`, `CH2 Pulse`, `CH3 Wave RAM`, `CH4 LFSR Noise`)**, and **21-Byte `HFT1` SRAM Save Hex Inspector**.

---

## 3. Real-World Verification Suite (`verify_halftone_rom.py`)

All 8 plates and the full 8,060-frame (`134.3s`) campaign are verified across **4 independent Game Boy emulators** (`PyBoy`, `binjgb`, `SameBoy`, and `mGBA`):

```bash
python3 verify_halftone_rom.py
```

### Summary of Verified Results ([`evidence/verification_report.json`](./evidence/verification_report.json))

| Plate | Title | Mechanic Verified | Clear Frame (`g_frame`) | Peak Scanline (`g_ly_end`) | Peak CPU Busy | Deaths | Gameplay Lag |
| :---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| **1** | `MARGINS` | First `B`-button ink flip across halftone gaps | `824` | `90 / 144` | `42.4%` | `0` | `0` |
| **2** | `GALLEY` | Mid-air polarity flips over alternating spikes | `794` | `94 / 144` | `45.5%` | `0` | `0` |
| **3** | `INK WORKS` | Blotting-paper lifts & ink-drop hazards | `783` | `94 / 144` | `47.7%` | `0` | `0` |
| **4** | `BINDERY` | Chalk-only bridges & vertical press shafts | `865` | `120 / 144` | `50.5%` | `0` | `0` |
| **5** | `PULSE` | Timed rhythm polarity switches & moving type | `784` | `100 / 144` | `49.6%` | `0` | `0` |
| **6** | `ROTARY` | High-speed rotary press rollers & split lanes | `885` | `115 / 144` | `45.5%` | `0` | `0` |
| **7** | `NEGATIVE` | Auto-flips polarity every 90 frames (`1.5s`) | `811` | `118 / 144` | `44.9%` | `0` | `0` |
| **8** | `THE SMUDGE` | 5-HP Boss (`hp: 5 -> 0`), match ink phase to stomp | `1352` | `105 / 144` | `46.9%` | `0` | `0` |
| **ALL** | **Full Campaign** | **Cold boot -> 8 plates -> Boss -> Colophon -> SRAM Save** | **`8,060`** | **`120 / 144`** | **`50.5%`** | **`0`** | **`0`** |

- **Cross-Emulator Determinism (`SameBoy` vs. `mGBA`)**: `14,698 / 14,698` aligned frames (`100.0%`) match on all 11 gameplay probes (`g_state`, `g_level`, `g_px`, `g_py`, `g_hearts`, `g_sorts`, `g_phase`, `g_lag`, `g_boss_hp`, `g_ending_reached`, `g_deaths`).

---

## 4. Repository Structure

```text
cartridge-halftone-gb/
├── rom/
│   ├── HALFTONE.gb                 # Compiled 65,536-byte (64 KiB) Game Boy ROM (MBC1+RAM+BATTERY)
│   └── HALFTONE.sym                # No$gmb / SameBoy / PyBoy symbol table
├── source/
│   ├── Makefile                    # GBDK-2020 lcc build configuration (4 banks, MBC1+RAM+BAT)
│   ├── src/
│   │   ├── main.c                  # Bank 0: Boot, VBlank ISR, Title, Intro, Ending, SRAM save
│   │   ├── play.c                  # Bank 0: Fixed-point physics, polarity flip, entities, Boss AI
│   │   ├── audio.c                 # Bank 2: 4-channel APU tracker driver, 5 themes, 10 SFX
│   │   └── game.h                  # Shared constants, memory probes, entity definitions
│   ├── gen/                        # Generated C tables for 2bpp tiles, RLE level maps, music
│   └── tools/                      # Asset generators, solver, SameBoy/mGBA verification scripts
├── studio/                         # Photoreal PBR 3D DMG-01 Handheld & SM83 Engineering Studio
│   ├── index.html
│   ├── styles.css
│   ├── dmg_3d.js                   # Three.js PBR 1989 DMG-01 model, Cartridge, Exploded PCB X-Ray
│   ├── emu_studio.js               # binjgb WASM bridge, uncropped 160x144 LCD, Hardware Inspector
│   └── vendor/                     # Self-contained Three.js r160 & binjgb WebAssembly core
├── evidence/
│   ├── verification_report.json    # Automated output from verify_halftone_rom.py
│   ├── verification.json           # SameBoy vs. mGBA 14,698-frame agreement summary
│   └── levels/                     # Rendered full-map PNGs and per-plate trace summaries
└── verify_halftone_rom.py          # Standalone Python verification suite (ROM + PyBoy + binjgb)
```
