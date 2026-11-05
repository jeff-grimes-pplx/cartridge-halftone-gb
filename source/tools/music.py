"""HALFTONE original soundtrack, composed as hUGEDriver pattern data.

The tracker format: 64-row patterns per channel, each cell = (note, instrument, effect).
Rows are sixteenth notes (4 rows per beat, 16 rows per bar, 4 bars per pattern).
`tempo` is ticks (frames) per row: 7 -> 128.6 BPM, 6 -> 150 BPM, 5 -> 180 BPM, 8 -> 112.5 BPM.

Channels: 1 pulse (lead), 2 pulse (harmony/arpeggio), 3 wave (bass), 4 noise (drums).
Run: python3 tools/music.py <outdir>  -> music.c / music.h
"""
import sys, os

NOTE_NAMES = ['C', 'Cs', 'D', 'Ds', 'E', 'F', 'Fs', 'G', 'Gs', 'A', 'As', 'B']
FLAT = {'Db': 'Cs', 'Eb': 'Ds', 'Gb': 'Fs', 'Ab': 'Gs', 'Bb': 'As'}
EMPTY = 90  # ___


def n(name):
    """'E5' -> hUGE note index (C_3 = 0 .. B_8 = 71)."""
    if name in ('R', '-', '.'):
        return EMPTY
    if name[:2] in FLAT:
        name = FLAT[name[:2]] + name[2:]
    pitch = name[:-1]
    octv = int(name[-1])
    idx = (octv - 3) * 12 + NOTE_NAMES.index(pitch)
    assert 0 <= idx < 72, name
    return idx


def tr(idx, semis):
    return EMPTY if idx == EMPTY else idx + semis


class Pattern:
    def __init__(self):
        self.cells = [[EMPTY, 0, 0] for _ in range(64)]

    def put(self, row, note=EMPTY, instr=0, fx=0):
        c = self.cells[row]
        if note != EMPTY:
            c[0] = note
        if instr:
            c[1] = instr
        if fx:
            c[2] = fx

    def c_rows(self):
        return ',\n'.join(f'    DN({c[0]},{c[1]},0x{c[2]:03X})' for c in self.cells)


def seq(pattern, text, instr, start=0, fx=0, cut=None):
    """Write a note sequence. text: 'E5:4 R:2 G5:2 ...' (note:rows). Returns next row.
    cut: if set, add a note-cut effect E0x after `cut` ticks on every note (staccato)."""
    row = start
    for tok in text.split():
        name, dur = tok.split(':')
        dur = int(dur)
        note = n(name)
        if note != EMPTY:
            pattern.put(row, note, instr, (0xE00 | cut) if cut else fx)
        row += dur
    assert row <= 64, f'sequence overflow ({row})'
    return row


def drums(pattern, text, kick=('C5', 1), snare=('D6', 2), hat=('G7', 3)):
    """text: 64 chars, one per row: k kick, s snare, h hat, . rest, K kick+hat."""
    text = text.replace(' ', '').replace('|', '')
    assert len(text) == 64, len(text)
    for i, ch in enumerate(text):
        if ch == 'k' or ch == 'K':
            pattern.put(i, n(kick[0]), kick[1])
        elif ch == 's':
            pattern.put(i, n(snare[0]), snare[1])
        elif ch == 'h':
            pattern.put(i, n(hat[0]), hat[1])


def bass(pattern, roots, instr=1, rhythm='x.x.x.xx' * 8, octave_note=None):
    """roots: list of 4 chord roots (one per bar, e.g. 'A3'); rhythm: 64 chars, x = hit, o = octave up."""
    rhythm = rhythm.replace(' ', '').replace('|', '')
    assert len(rhythm) == 64
    for i, ch in enumerate(rhythm):
        root = n(roots[i // 16])
        if ch == 'x':
            pattern.put(i, root, instr)
        elif ch == 'o':
            pattern.put(i, root + 12, instr)
        elif ch == 'f':
            pattern.put(i, root + 7, instr)


def arps(pattern, chords, instr=2, rhythm='x...x...x...x...' * 4, vol=None):
    """chords: list of 4 (root, kind) with kind in 'maj','min','dim','sus','maj7','min7'; plays an
    arpeggio effect (0xy) so one channel sounds like a chord."""
    kinds = {'maj': 0x47, 'min': 0x37, 'dim': 0x36, 'sus': 0x57, 'maj7': 0x4B, 'min7': 0x3A, 'pow': 0x70}
    rhythm = rhythm.replace(' ', '').replace('|', '')
    assert len(rhythm) == 64
    for i, ch in enumerate(rhythm):
        if ch == 'x':
            root, kind = chords[i // 16]
            pattern.put(i, n(root), instr, 0x000 | kinds[kind])


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
# duty: {sweep NR10, len_duty NR11, envelope NR12, subpattern, highmask}
DUTY_INSTR = [
    (0x00, 0x80, 0xC6, 0, 0x80),  # 1 LEAD   50% duty, vol 12, slow decay
    (0x00, 0x40, 0x92, 0, 0x80),  # 2 ARP    25% duty, vol 9, medium decay
    (0x00, 0x00, 0xF1, 0, 0x80),  # 3 PLUCK  12.5% duty, vol 15, fast decay
    (0x00, 0x80, 0x70, 0, 0x80),  # 4 PAD    50% duty, vol 7, sustained
    (0x00, 0x40, 0xB3, 0, 0x80),  # 5 LEAD2  25% duty, vol 11, decay 3
    (0x00, 0xC0, 0xA2, 0, 0x80),  # 6 HARM   75% duty (sounds like 25% but softer phase)
]
# wave: {length, volume NR32, waveform, subpattern, highmask}
WAVE_INSTR = [
    (0, 0x20, 0, 0, 0x80),  # 1 BASS   100% triangle-ish
    (0, 0x40, 1, 0, 0x80),  # 2 SOFT   50% sine-ish
    (0, 0x20, 2, 0, 0x80),  # 3 SAW    100% saw
]
# noise: {envelope NR42, subpattern, highmask, 0, 0}
NOISE_INSTR = [
    (0xF1, 0, 0, 0, 0),  # 1 KICK
    (0xC2, 0, 0, 0, 0),  # 2 SNARE
    (0x61, 0, 0, 0, 0),  # 3 HAT
    (0xA3, 0, 0, 0, 0),  # 4 CRASH-ish
]


def wave_tri():
    s = list(range(0, 16)) + list(range(15, -1, -1))
    return s


def wave_sine():
    import math
    return [int(round(7.5 + 7.5 * math.sin(2 * math.pi * i / 32))) for i in range(32)]


def wave_saw():
    return [i // 2 for i in range(32)]


def pack_wave(samples):
    assert len(samples) == 32
    out = []
    for i in range(0, 32, 2):
        out.append((samples[i] << 4) | samples[i + 1])
    return out


WAVES = [wave_tri(), wave_sine(), wave_saw()] + [[0] * 32] * 13

# ---------------------------------------------------------------------------
# Songs
# ---------------------------------------------------------------------------
SONGS = []


class Song:
    def __init__(self, name, tempo):
        self.name = name
        self.tempo = tempo
        self.ch = [[], [], [], []]  # lists of Pattern per channel (orders)

    def add(self, p1, p2, p3, p4):
        self.ch[0].append(p1); self.ch[1].append(p2); self.ch[2].append(p3); self.ch[3].append(p4)


# ---- TITLE: "Two Inks" (A minor, 128 BPM) ----------------------------------
def song_title():
    s = Song('song_title', 7)
    # Pattern A: intro - bass and drums establish the groove, arps shimmer
    for variant in range(2):
        p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
        if variant == 0:
            seq(p1, 'R:16 E5:2 R:2 A5:4 C6:2 B5:2 A5:4 '              # bar 2
                    'G5:4 E5:4 R:8 '                                   # bar 3
                    'D5:2 E5:2 G5:4 A5:8', 1)                           # bar 4
        else:
            seq(p1, 'E5:2 R:2 A5:4 C6:2 B5:2 A5:4 '
                    'E6:4 D6:2 C6:2 B5:8 '
                    'C6:2 B5:2 A5:4 G5:2 A5:2 E5:4 '
                    'D5:4 E5:4 A4:8', 1)
        arps(p2, [('A4', 'min'), ('F4', 'maj'), ('C5', 'maj'), ('G4', 'maj')],
             rhythm='x.x.x.x.x.x.x.x.' * 4)
        bass(p3, ['A3', 'F3', 'C4', 'G3'], rhythm='x..x..x.x..x..o.' * 4)
        drums(p4, 'K.h.s.h.K.h.s.hh' * 4)
        s.add(p1, p2, p3, p4)
    # Pattern B: answer phrase over Am F E7 Am
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'A5:4 G5:2 A5:2 C6:4 A5:4 '
            'F5:4 E5:2 F5:2 A5:4 F5:4 '
            'E5:2 Gs5:2 B5:4 E6:4 B5:2 Gs5:2 '
            'A5:8 R:8', 1)
    arps(p2, [('A4', 'min'), ('F4', 'maj'), ('E4', 'maj'), ('A4', 'min')],
         rhythm='x.x.x.x.x.x.x.x.' * 3 + 'x.......x.......')
    bass(p3, ['A3', 'F3', 'E3', 'A3'], rhythm='x..x..x.x..x..o.' * 3 + 'x...x...x...xoxo')
    drums(p4, 'K.h.s.h.K.h.s.hh' * 3 + 'K.h.s.h.K.hhs.ss')
    s.add(p1, p2, p3, p4)
    return s


# ---- PLATE A: "Margins" (C major, bouncy 150 BPM) --------------------------
def song_plate_a():
    s = Song('song_plate_a', 6)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'G5:2 R:2 E5:2 R:2 G5:2 A5:2 G5:4 '
            'E5:2 R:2 C5:2 R:2 D5:4 E5:4 '
            'F5:2 R:2 A5:2 R:2 G5:2 F5:2 E5:4 '
            'D5:4 G5:4 C5:8', 5, cut=4)
    arps(p2, [('C5', 'maj'), ('A4', 'min'), ('F4', 'maj'), ('G4', 'maj')],
         rhythm='x...x...x...x...' * 4)
    bass(p3, ['C3', 'A3', 'F3', 'G3'], rhythm='x.o.x.o.x.o.x.o.' * 4)
    drums(p4, 'K.h.s.h.K.h.s.h.' * 4)
    s.add(p1, p2, p3, p4)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'E5:2 R:2 G5:2 R:2 C6:2 B5:2 A5:4 '
            'G5:2 R:2 E5:2 R:2 F5:4 G5:4 '
            'A5:2 R:2 C6:2 R:2 B5:2 A5:2 G5:4 '
            'F5:4 D5:4 C5:8', 5, cut=4)
    arps(p2, [('C5', 'maj'), ('E4', 'min'), ('F4', 'maj'), ('G4', 'sus')],
         rhythm='x...x...x...x...' * 3 + 'x...x...x.x.x.x.')
    bass(p3, ['C3', 'E3', 'F3', 'G3'], rhythm='x.o.x.o.x.o.x.o.' * 3 + 'x.o.x.o.x.x.o.o.')
    drums(p4, 'K.h.s.h.K.h.s.h.' * 3 + 'K.h.s.h.K.hss.ss')
    s.add(p1, p2, p3, p4)
    return s


# ---- PLATE B: "Galley" (D minor, driving 150 BPM) --------------------------
def song_plate_b():
    s = Song('song_plate_b', 6)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'D5:2 F5:2 A5:2 F5:2 D5:2 F5:2 A5:2 C6:2 '
            'Bb5:2 A5:2 G5:2 A5:2 F5:4 R:4 '
            'D5:2 F5:2 A5:2 F5:2 D5:2 F5:2 A5:2 D6:2 '
            'C6:2 A5:2 G5:2 E5:2 D5:4 R:4', 1)
    arps(p2, [('D4', 'min'), ('Bb3', 'maj'), ('D4', 'min'), ('A3', 'maj')],
         rhythm='x.x.x.x.x.x.x.x.' * 4)
    bass(p3, ['D3', 'Bb3', 'D3', 'A3'], rhythm='x.x.x.x.x.x.x.x.' * 4)
    drums(p4, 'K.h.s.hhK.h.s.h.' * 4)
    s.add(p1, p2, p3, p4)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'F5:4 G5:2 A5:2 Bb5:4 A5:4 '
            'G5:4 F5:2 E5:2 F5:8 '
            'A5:4 Bb5:2 C6:2 D6:4 C6:4 '
            'Bb5:2 A5:2 G5:2 F5:2 E5:4 Cs5:4', 1)
    arps(p2, [('F4', 'maj'), ('Bb3', 'maj'), ('Gm4' if False else 'G4', 'min'), ('A3', 'maj')],
         rhythm='x.x.x.x.x.x.x.x.' * 4)
    bass(p3, ['F3', 'Bb3', 'G3', 'A3'], rhythm='x.x.x.x.x.x.x.x.' * 3 + 'x.x.x.x.x.x.xxxx')
    drums(p4, 'K.h.s.hhK.h.s.h.' * 3 + 'K.h.s.hhK.hhssss')
    s.add(p1, p2, p3, p4)
    return s


# ---- PLATE C: "Ink Works" (E minor, 128 BPM, swagger) ----------------------
def song_plate_c():
    s = Song('song_plate_c', 7)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'E5:3 G5:1 B5:4 A5:2 G5:2 Fs5:4 '
            'G5:3 E5:1 D5:4 E5:8 '
            'E5:3 G5:1 B5:4 D6:2 C6:2 B5:4 '
            'A5:2 B5:2 G5:4 Fs5:8', 1)
    arps(p2, [('E4', 'min'), ('C4', 'maj'), ('E4', 'min'), ('B3', 'maj')],
         rhythm='x..x..x.x..x..x.' * 4)
    bass(p3, ['E3', 'C3', 'E3', 'B3'], rhythm='x..x..x.x..x..x.' * 4)
    drums(p4, 'K..h..s.K..h..s.' * 4)
    s.add(p1, p2, p3, p4)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'C6:3 B5:1 A5:4 G5:2 Fs5:2 E5:4 '
            'Fs5:3 G5:1 A5:4 B5:8 '
            'C6:3 B5:1 A5:4 G5:2 A5:2 B5:4 '
            'E5:4 Fs5:4 E5:8', 1)
    arps(p2, [('A3', 'min'), ('D4', 'maj'), ('A3', 'min'), ('E4', 'min')],
         rhythm='x..x..x.x..x..x.' * 4)
    bass(p3, ['A3', 'D3', 'A3', 'E3'], rhythm='x..x..x.x..x..x.' * 3 + 'x..x..x.x.x.x.x.')
    drums(p4, 'K..h..s.K..h..s.' * 3 + 'K..h..s.K.s.s.ss')
    s.add(p1, p2, p3, p4)
    return s


# ---- BOSS: "The Smudge" (fast, chromatic, 180 BPM) -------------------------
def song_boss():
    s = Song('song_boss', 5)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'E5:2 E5:2 F5:2 E5:2 G5:2 E5:2 Bb5:2 A5:2 '
            'E5:2 E5:2 F5:2 E5:2 Bb5:2 A5:2 G5:2 F5:2 '
            'E5:2 E5:2 F5:2 E5:2 G5:2 E5:2 Bb5:2 A5:2 '
            'C6:2 Bb5:2 A5:2 G5:2 F5:2 E5:2 Ds5:2 E5:2', 5)
    arps(p2, [('E4', 'dim'), ('E4', 'dim'), ('E4', 'dim'), ('F4', 'min')],
         rhythm='x.x.x.x.x.x.x.x.' * 4)
    bass(p3, ['E3', 'E3', 'E3', 'F3'], rhythm='xx.xxx.xxx.xxx.x' * 4, instr=3)
    drums(p4, 'K.hhs.hhK.hhs.hh' * 4)
    s.add(p1, p2, p3, p4)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'B5:4 Bb5:4 A5:4 Gs5:4 '
            'G5:4 Fs5:4 F5:4 E5:4 '
            'E6:2 R:2 E6:2 R:2 Ds6:2 R:2 D6:2 R:2 '
            'Cs6:2 C6:2 B5:2 Bb5:2 A5:2 Gs5:2 G5:2 Fs5:2', 5)
    arps(p2, [('B3', 'dim'), ('G4', 'min'), ('E4', 'min'), ('B3', 'maj')],
         rhythm='x.x.x.x.x.x.x.x.' * 4)
    bass(p3, ['B3', 'G3', 'E3', 'B3'], rhythm='xx.xxx.xxx.xxx.x' * 4, instr=3)
    drums(p4, 'K.hhs.hhK.hhs.hh' * 3 + 'K.hhs.hhKsKsKsss')
    s.add(p1, p2, p3, p4)
    return s


# ---- ENDING: "Final Page" (F major, slow 112 BPM) --------------------------
def song_ending():
    s = Song('song_ending', 8)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'A5:6 G5:2 F5:8 '
            'G5:6 A5:2 C6:8 '
            'A5:4 G5:2 F5:2 D5:8 '
            'E5:4 F5:4 G5:8', 4)
    arps(p2, [('F4', 'maj'), ('C4', 'maj'), ('D4', 'min'), ('Bb3', 'maj')],
         rhythm='x.......x.......' * 4)
    bass(p3, ['F3', 'C3', 'D3', 'Bb3'], rhythm='x.......f.......' * 4, instr=2)
    drums(p4, '................' * 4)
    s.add(p1, p2, p3, p4)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'A5:6 Bb5:2 C6:8 '
            'D6:6 C6:2 A5:8 '
            'Bb5:4 A5:2 G5:2 F5:8 '
            'G5:4 E5:4 F5:8', 4)
    arps(p2, [('F4', 'maj'), ('A3', 'min'), ('Bb3', 'maj'), ('C4', 'maj')],
         rhythm='x.......x.......' * 3 + 'x.......x...x...')
    bass(p3, ['F3', 'A3', 'Bb3', 'C3'], rhythm='x.......f.......' * 4, instr=2)
    drums(p4, '................' * 4)
    s.add(p1, p2, p3, p4)
    return s


# ---- CLEAR jingle (one pattern, played for ~2.5 s then stopped by the game) -
def song_clear():
    s = Song('song_clear', 5)
    p1, p2, p3, p4 = Pattern(), Pattern(), Pattern(), Pattern()
    seq(p1, 'C5:2 E5:2 G5:2 C6:6 R:2 G5:2 C6:8 R:40', 3)
    seq(p2, 'R:2 C5:2 E5:2 G5:6 R:2 E5:2 E5:8 R:40', 2)
    seq(p3, 'C4:4 C4:4 G3:4 C4:8 R:44', 1)
    drums(p4, 'k...k...k...s...' + '.' * 48)
    s.add(p1, p2, p3, p4)
    return s


def build(outdir):
    os.makedirs(outdir, exist_ok=True)
    songs = [song_title(), song_plate_a(), song_plate_b(), song_plate_c(), song_boss(), song_ending(), song_clear()]
    c = ['/* Generated by tools/music.py - HALFTONE original soundtrack (hUGEDriver format) */',
         '#pragma bank 1', '#include "hUGEDriver.h"', '#include <stddef.h>', '']
    c.append('static const hUGEDutyInstr_t duty_instruments[] = {')
    for d in DUTY_INSTR:
        c.append('    {%d,%d,%d,0,%d},' % (d[0], d[1], d[2], d[4]))
    c.append('};')
    c.append('static const hUGEWaveInstr_t wave_instruments[] = {')
    for w in WAVE_INSTR:
        c.append('    {%d,%d,%d,0,%d},' % (w[0], w[1], w[2], w[4]))
    c.append('};')
    c.append('static const hUGENoiseInstr_t noise_instruments[] = {')
    for nz in NOISE_INSTR:
        c.append('    {%d,0,%d,0,0},' % (nz[0], nz[2]))
    c.append('};')
    c.append('static const unsigned char waves[] = {')
    for w in WAVES:
        c.append('    ' + ','.join(str(b) for b in pack_wave(w)) + ',')
    c.append('};')
    pid = 0
    for s in songs:
        order_names = [[], [], [], []]
        for ch in range(4):
            for p in s.ch[ch]:
                name = f'{s.name}_P{pid}'; pid += 1
                c.append(f'static const unsigned char {name}[] = {{')
                c.append(p.c_rows())
                c.append('};')
                order_names[ch].append(name)
        cnt = len(s.ch[0]) * 2
        c.append(f'static const unsigned char {s.name}_order_cnt = {cnt};')
        for ch in range(4):
            c.append(f'static const unsigned char* const {s.name}_order{ch+1}[] = {{' + ','.join(order_names[ch]) + '};')
        c.append(f'const hUGESong_t {s.name} = {{{s.tempo}, &{s.name}_order_cnt, {s.name}_order1, {s.name}_order2, '
                 f'{s.name}_order3, {s.name}_order4, duty_instruments, wave_instruments, noise_instruments, NULL, waves}};')
        c.append('')
    with open(os.path.join(outdir, 'music.c'), 'w') as f:
        f.write('\n'.join(c) + '\n')
    h = ['/* Generated by tools/music.py */', '#ifndef MUSIC_H', '#define MUSIC_H', '#include "hUGEDriver.h"']
    for i, s in enumerate(songs):
        h.append(f'extern const hUGESong_t {s.name};')
        h.append(f'#define SONG_{s.name[5:].upper()} {i}')
    h.append(f'#define SONG_COUNT {len(songs)}')
    h.append('#endif')
    with open(os.path.join(outdir, 'music.h'), 'w') as f:
        f.write('\n'.join(h) + '\n')
    print(f'{len(songs)} songs, {pid} patterns')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'gen')
