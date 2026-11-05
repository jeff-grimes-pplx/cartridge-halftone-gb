/* HALFTONE audio: hUGEDriver music (songs in bank 1) + register-level sound effects.
 * Music uses all four channels; SFX borrow CH2 (pulse) and CH4 (noise) and mute the
 * corresponding music channel while they play.
 */
#include "game.h"
#include "hUGEDriver.h"
#include "music.h"

static uint8_t music_on;
static uint8_t cur_song = 0xFF;

/* ---- SFX sequencer -------------------------------------------------------- */
typedef struct {
    uint8_t duty;        /* NR21 duty bits */
    uint8_t env;         /* NR22 */
    uint8_t noise_env;   /* NR42, 0 = no noise */
    uint8_t noise_poly;  /* NR43 */
    uint8_t noise_len;   /* frames the noise lasts before cut */
    const uint16_t *freq; /* per-frame CH2 frequency (11 bit), terminated by 0 */
} Sfx;

static const uint16_t f_jump[]   = {1500, 1620, 1720, 1790, 1840, 1870, 0};
static const uint16_t f_flip[]   = {1100, 1400, 1650, 1780, 1850, 1880, 1900, 1910, 0};
static const uint16_t f_block[]  = {600, 500, 600, 500, 600, 500, 0};
static const uint16_t f_sort[]   = {1750, 1750, 1899, 1899, 1972, 1972, 1972, 0};
static const uint16_t f_hurt[]   = {1600, 1500, 1350, 1150, 950, 800, 700, 0};
static const uint16_t f_stomp[]  = {1200, 1000, 800, 0};
static const uint16_t f_die[]    = {1700, 1650, 1600, 1500, 1400, 1300, 1150, 1000, 850, 700, 600, 500, 400, 300, 0};
static const uint16_t f_menu[]   = {1800, 1850, 0};
static const uint16_t f_check[]  = {1546, 1546, 1750, 1750, 1899, 1899, 1972, 1972, 1972, 0};
static const uint16_t f_tick[]   = {1950, 0};
static const uint16_t f_bosshit[] = {900, 700, 500, 400, 300, 200, 0};
static const uint16_t f_start[]  = {1546, 1546, 1750, 1750, 1899, 1899, 1972, 1972, 2005, 2005, 2005, 2005, 0};
static const uint16_t f_drop[]   = {1300, 1100, 0};
static const uint16_t f_none[]   = {0};

static const Sfx sfx_tab[] = {
    {0, 0, 0, 0, 0, f_none},
    {0x80, 0xA1, 0x00, 0x00, 0, f_jump},      /* SFX_JUMP */
    {0x40, 0xC2, 0x41, 0x55, 3, f_flip},      /* SFX_FLIP */
    {0x00, 0x91, 0x00, 0x00, 0, f_block},     /* SFX_FLIP_BLOCKED */
    {0x80, 0xB1, 0x00, 0x00, 0, f_sort},      /* SFX_SORT */
    {0x40, 0xC1, 0x81, 0x6C, 4, f_hurt},      /* SFX_HURT */
    {0x80, 0xA1, 0xA1, 0x36, 3, f_stomp},     /* SFX_STOMP */
    {0x40, 0xF3, 0xB2, 0x7D, 10, f_die},      /* SFX_DIE */
    {0x80, 0x81, 0x00, 0x00, 0, f_menu},      /* SFX_MENU */
    {0x80, 0xA2, 0x00, 0x00, 0, f_check},     /* SFX_CHECK */
    {0x40, 0x61, 0x00, 0x00, 0, f_tick},      /* SFX_TICK */
    {0x80, 0xE2, 0xD2, 0x7E, 8, f_bosshit},   /* SFX_BOSS_HIT */
    {0x80, 0xC3, 0x00, 0x00, 0, f_start},     /* SFX_START */
    {0x40, 0x71, 0x51, 0x45, 2, f_drop},      /* SFX_DROP */
};

static const uint16_t *sfx_ptr;
static uint8_t sfx_cur, sfx_noise_t;
static uint8_t ch2_muted, ch4_muted;

static void ch2_restore(void) {
    if (ch2_muted) { __critical { hUGE_mute_channel(HT_CH2, HT_CH_PLAY); } ch2_muted = 0; }
    NR22_REG = 0x00; NR24_REG = 0x80;   /* silence */
}
static void ch4_restore(void) {
    if (ch4_muted) { __critical { hUGE_mute_channel(HT_CH4, HT_CH_PLAY); } ch4_muted = 0; }
    NR42_REG = 0x00; NR44_REG = 0x80;
}

void sfx(uint8_t id) {
    const Sfx *s;
    if (id >= sizeof(sfx_tab) / sizeof(sfx_tab[0])) return;
    /* priority: do not let a tick interrupt something more important */
    if (sfx_ptr && id == SFX_TICK) return;
    s = &sfx_tab[id];
    sfx_cur = id;
    sfx_ptr = s->freq;
    if (!ch2_muted) { __critical { hUGE_mute_channel(HT_CH2, HT_CH_MUTE); } ch2_muted = 1; }
    NR21_REG = s->duty;
    NR22_REG = s->env;
    if (s->noise_env) {
        if (!ch4_muted) { __critical { hUGE_mute_channel(HT_CH4, HT_CH_MUTE); } ch4_muted = 1; }
        NR41_REG = 0;
        NR42_REG = s->noise_env;
        NR43_REG = s->noise_poly;
        NR44_REG = 0x80;
        sfx_noise_t = s->noise_len;
    }
    /* first frequency now */
    {
        uint16_t f = *sfx_ptr;
        NR23_REG = (uint8_t)f;
        NR24_REG = 0x80 | (uint8_t)(f >> 8);
        sfx_ptr++;
    }
}

void audio_frame(void) {
    if (sfx_ptr) {
        uint16_t f = *sfx_ptr;
        if (f == 0) {
            sfx_ptr = 0;
            ch2_restore();
        } else {
            NR23_REG = (uint8_t)f;
            NR24_REG = (uint8_t)(f >> 8);
            sfx_ptr++;
        }
    }
    if (sfx_noise_t) {
        if (--sfx_noise_t == 0) ch4_restore();
    }
}

/* ---- music -------------------------------------------------------------- */
static const hUGESong_t *song_addr(uint8_t song) {
    switch (song) {
    case SONG_TITLE: return &song_title;
    case SONG_PLATE_A: return &song_plate_a;
    case SONG_PLATE_B: return &song_plate_b;
    case SONG_PLATE_C: return &song_plate_c;
    case SONG_BOSS: return &song_boss;
    case SONG_ENDING: return &song_ending;
    default: return &song_clear;
    }
}

static void music_isr(void) {
#ifdef NO_MUSIC
    return;
#endif
    if (!music_on) return;
    {
        uint8_t b = CURRENT_BANK;
        SWITCH_ROM(1);
        hUGE_dosound();
        SWITCH_ROM(b);
    }
}

void audio_init(void) {
    NR52_REG = 0x80;
    NR51_REG = 0xFF;
    NR50_REG = 0x77;
    music_on = 0;
    __critical { add_VBL(music_isr); }
}

void music_play(uint8_t song) {
    uint8_t b = CURRENT_BANK;
    if (song == cur_song && music_on) return;
    cur_song = song;
    SWITCH_ROM(1);
    __critical {
        music_on = 0;
        hUGE_init(song_addr(song));
        if (ch2_muted) hUGE_mute_channel(HT_CH2, HT_CH_MUTE);
        if (ch4_muted) hUGE_mute_channel(HT_CH4, HT_CH_MUTE);
        music_on = 1;
    }
    SWITCH_ROM(b);
}

void music_stop(void) {
    __critical { music_on = 0; }
    cur_song = 0xFF;
    NR12_REG = 0; NR14_REG = 0x80;
    NR22_REG = 0; NR24_REG = 0x80;
    NR32_REG = 0; NR30_REG = 0;
    NR42_REG = 0; NR44_REG = 0x80;
}
