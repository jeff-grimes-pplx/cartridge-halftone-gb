/* HALFTONE - main loop, screens, HUD, saving.
 * Target: original Game Boy (DMG). Built with GBDK-2020 4.5.0 / SDCC 4.5.1.
 */
#include "game.h"
#include "music.h"
#include "gfx_logo_map.h"
#include <string.h>

/* ---- exported state (read by the emulator harness through the .noi symbols) */
uint16_t g_frame;
uint8_t g_state;
uint8_t g_level;
int16_t g_px, g_py;
uint8_t g_hearts, g_sorts, g_phase, g_joy, g_ly_end, g_div_end, g_lag, g_boss_hp, g_ending_reached;
uint16_t g_deaths;
uint8_t g_vbl_count;
uint8_t g_sorts_total;
uint16_t g_time_frames_lo, g_time_frames_hi;
uint8_t g_prof[8];              /* DIV_REG timestamps at frame checkpoints (profiling) */

uint8_t joy, joy_prev, joy_pressed;

static uint8_t last_vbl;
static uint8_t paused;
static volatile uint8_t vreg_on;                     /* VBL-applied scroll/palette shadows, see vbl_isr */
static volatile uint8_t vreg_scx, vreg_bgp, vreg_obp1;
static uint8_t menu_sel, menu_plate, has_save, title_t, title_phase_t;
static uint8_t state_t;
static uint8_t sorts_total_all;     /* sorts collected over the whole campaign (sum of masks) */

/* ---- SRAM save ------------------------------------------------------------- */
typedef struct {
    uint8_t magic[4];
    uint8_t plate;          /* next plate to play, 0-based */
    uint8_t sorts[LEVEL_COUNT];
    uint16_t deaths;
    uint16_t frames_lo, frames_hi;
    uint8_t complete;
    uint8_t sum;
} SaveData;
static SaveData * const sram = (SaveData *)0xA000;
static uint8_t save_sorts[LEVEL_COUNT];

static uint8_t save_checksum(const SaveData *s) {
    const uint8_t *p = (const uint8_t *)s;
    uint8_t sum = 0x7F, i;
    for (i = 0; i < sizeof(SaveData) - 1; i++) sum += p[i];
    return sum;
}

static uint8_t save_valid(void) {
    uint8_t ok;
    ENABLE_RAM;
    ok = sram->magic[0] == 'H' && sram->magic[1] == 'F' && sram->magic[2] == 'T' && sram->magic[3] == '1'
         && sram->plate < LEVEL_COUNT && sram->sum == save_checksum(sram);
    DISABLE_RAM;
    return ok;
}

void save_write(void) {
    SaveData s;
    uint8_t i;
    s.magic[0] = 'H'; s.magic[1] = 'F'; s.magic[2] = 'T'; s.magic[3] = '1';
    s.plate = g_level;
    for (i = 0; i < LEVEL_COUNT; i++) s.sorts[i] = save_sorts[i];
    s.deaths = g_deaths;
    s.frames_lo = g_time_frames_lo; s.frames_hi = g_time_frames_hi;
    s.complete = g_ending_reached;
    s.sum = save_checksum(&s);
    ENABLE_RAM;
    memcpy(sram, &s, sizeof(SaveData));
    DISABLE_RAM;
}

static void save_load(void) {
    uint8_t i;
    ENABLE_RAM;
    menu_plate = sram->plate;
    for (i = 0; i < LEVEL_COUNT; i++) save_sorts[i] = sram->sorts[i];
    g_deaths = sram->deaths;
    g_time_frames_lo = sram->frames_lo; g_time_frames_hi = sram->frames_hi;
    DISABLE_RAM;
}

/* ---- text ------------------------------------------------------------------- */
static uint8_t glyph(char c) {
    if (c >= 'A' && c <= 'Z') return T_FONT_A + (c - 'A');
    if (c >= 'a' && c <= 'z') return T_FONT_A + (c - 'a');
    if (c >= '0' && c <= '9') return T_FONT_DIGIT0 + (c - '0');
    switch (c) {
    case '.': return T_FONT_DOT;
    case ',': return T_FONT_COMMA;
    case ':': return T_FONT_COLON;
    case '-': return T_FONT_DASH;
    case '!': return T_FONT_BANG;
    case '?': return T_FONT_QMARK;
    case '/': return T_FONT_SLASH;
    case '\'': return T_FONT_APOS;
    case '*': return T_FONT_TIMES;
    case '#': return T_HUD_SORT;
    case '@': return T_HUD_HEART;
    case '~': return T_FONT_MIDDOT;
    default: return T_HUD_SPACE;
    }
}

static uint8_t tbuf[20];

void text_bg(uint8_t x, uint8_t y, const char *s) {
    uint8_t n = 0;
    while (*s && n < 20) tbuf[n++] = glyph(*s++);
    set_bkg_tiles(x, y, n, 1, tbuf);
}

void text_win(uint8_t x, uint8_t y, const char *s) {
    uint8_t n = 0;
    while (*s && n < 20) tbuf[n++] = glyph(*s++);
    set_win_tiles(x, y, n, 1, tbuf);
}

static void num2(char *dst, uint8_t v) {
    dst[0] = '0' + v / 10; dst[1] = '0' + v % 10;
}

/* ---- HUD (window layer, 2 rows at the bottom) ------------------------------- */
void hud_hearts(void) {
    uint8_t i;
    for (i = 0; i < 3; i++) tbuf[i] = (i < g_hearts) ? T_HUD_HEART : T_HUD_HEART_EMPTY;
    set_win_tiles(0, 0, 3, 1, tbuf);
}

void hud_sorts(void) {
    tbuf[0] = T_HUD_SORT; tbuf[1] = T_FONT_TIMES;
    tbuf[2] = T_FONT_DIGIT0 + (g_sorts / 10); tbuf[3] = T_FONT_DIGIT0 + (g_sorts % 10);
    set_win_tiles(4, 0, 4, 1, tbuf);
}

void hud_phase(void) {
    if (g_phase == PH_INK) { tbuf[0] = T_HUD_INKDROP; text_win(15, 0, "INK  "); }
    else { tbuf[0] = T_HUD_CHALKDOT; text_win(15, 0, "CHALK"); }
    set_win_tiles(13, 0, 1, 1, tbuf);
}

void hud_pulse(uint8_t frac) {
    uint8_t i;
    for (i = 0; i < 8; i++) tbuf[i] = (i < frac) ? T_HUD_RULE : T_HUD_SPACE;
    set_win_tiles(12, 1, 8, 1, tbuf);
}

void hud_row_clear(uint8_t row) {
    uint8_t i;
    for (i = 0; i < 20; i++) tbuf[i] = T_HUD_SPACE;
    set_win_tiles(0, row, 20, 1, tbuf);
}

/* HUD row 1: "PLATE N" on the left, the pulse bar (pulse plates only) on the right */
void hud_plate_row(void) {
    char s[8];
    hud_row_clear(1);
    s[0] = 'P'; s[1] = 'L'; s[2] = 'A'; s[3] = 'T'; s[4] = 'E'; s[5] = ' '; s[6] = '1' + g_level; s[7] = 0;
    text_win(0, 1, s);
    if (level_pulse) hud_pulse(pulse_frac);
}

void hud_full(void) {
    hud_row_clear(0);
    hud_hearts(); hud_sorts(); hud_phase();
    hud_plate_row();
}

/* ---- palette fades -------------------------------------------------------------- */
static const uint8_t fade_ink[4] = {BGP_INK, 0x90, 0x40, 0x00};
static const uint8_t fade_chalk[4] = {BGP_CHALK, 0x18, 0x04, 0x00};
static const uint8_t fade_obj[4] = {OBP_SOLID, 0x90, 0x40, 0x00};

static void apply_palettes(uint8_t step) {
    BGP_REG = (g_phase == PH_INK) ? fade_ink[step] : fade_chalk[step];
    OBP0_REG = fade_obj[step];
}

static void fade_out(void) {
    uint8_t s, f;
    vreg_on = 0;
    for (s = 1; s < 4; s++) { for (f = 0; f < 4; f++) { vsync(); g_frame++; } apply_palettes(s); }
    for (f = 0; f < 4; f++) { vsync(); g_frame++; }
}

static void fade_in(void) {
    uint8_t s, f;
    vreg_on = 0;
    for (s = 3; s > 0; s--) { apply_palettes(s); for (f = 0; f < 4; f++) { vsync(); g_frame++; } }
    apply_palettes(0);
}

/* ---- VRAM setup helpers ------------------------------------------------------- */
static void load_world_gfx(void) {
    uint8_t b = CURRENT_BANK;
    SWITCH_ROM(2);
    set_bkg_data(0, GFX_WORLD_TILE_COUNT, gfx_world_tiles);
    set_bkg_data(GFX_FONT_BASE, GFX_FONT_TILE_COUNT, gfx_font_tiles);
    set_sprite_data(0, GFX_SPRITE_TILE_COUNT, gfx_sprite_tiles);
    SWITCH_ROM(b);
}

static void load_boss_gfx(void) {
    uint8_t b = CURRENT_BANK;
    SWITCH_ROM(2);
    set_sprite_data(GFX_BOSS_TILE_BASE, GFX_BOSS_TILE_COUNT, gfx_boss_tiles);
    SWITCH_ROM(b);
}

static void load_logo_gfx(void) {
    uint8_t b = CURRENT_BANK;
    SWITCH_ROM(2);
    set_bkg_data(192, GFX_LOGO_TILE_COUNT, gfx_logo_tiles);
    SWITCH_ROM(b);
}

/* backdrop tiles share the logo's slots: the title reloads the logo, every plate reloads the backdrop */
static void load_backdrop_gfx(void) {
    uint8_t b = CURRENT_BANK;
    SWITCH_ROM(2);
    set_bkg_data(GFX_BACKDROP_TILE_BASE, GFX_BACKDROP_TILE_COUNT, gfx_backdrop_tiles);
    SWITCH_ROM(b);
}

static void clear_bg(void) {
    uint8_t y;
    for (y = 0; y < 20; y++) tbuf[y] = 0;
    for (y = 0; y < 32; y++) { set_bkg_tiles(0, y, 20, 1, tbuf); set_bkg_tiles(20, y, 12, 1, tbuf); }
}

static void hide_all_sprites(void) {
    uint8_t i;
    for (i = 0; i < 40; i++) shadow_OAM[i].y = 0;
}

/* ---- title screen ------------------------------------------------------------- */
static void title_draw_menu(void) {
    char s[20];
    text_bg(6, 11, "NEW GAME");
    if (has_save) {
        text_bg(6, 12, "CONTINUE");
        strcpy(s, "PLATE 1  ");
        s[6] = '1' + menu_plate;
        if (menu_plate + 1 < LEVEL_COUNT || 1) {
            s[7] = ' ';
        }
        text_bg(6, 13, s);
    } else {
        text_bg(6, 12, "        ");
        text_bg(6, 13, "         ");
    }
}

static void title_enter(void) {
    uint8_t L, t, x;
    DISPLAY_OFF;
    HIDE_WIN;
    hide_all_sprites();
    load_world_gfx();
    load_logo_gfx();
    clear_bg();
    /* logo: 8 letters x (2x3 tiles) at rows 1..3, x = 2..17 */
    for (L = 0; L < 8; L++) {
        for (t = 0; t < 6; t++) tbuf[t] = 192 + LOGO_MAP[L][t];
        set_bkg_tiles(2 + L * 2, 1, 2, 1, &tbuf[0]);
        set_bkg_tiles(2 + L * 2, 2, 2, 1, &tbuf[2]);
        set_bkg_tiles(2 + L * 2, 3, 2, 1, &tbuf[4]);
    }
    /* a small scene: stone ground with an ink/chalk bridge, rows 7..9 */
    {
        uint8_t b = CURRENT_BANK;
        const uint8_t *mt;
        SWITCH_ROM(2);
        for (x = 0; x < 20; x += 2) {
            uint8_t m = MT_STONE_TOP;
            if (x >= 6 && x < 10) m = MT_INK;
            else if (x >= 10 && x < 14) m = MT_CHALK;
            mt = &gfx_meta_tiles[m * 4];
            tbuf[0] = mt[0]; tbuf[1] = mt[1]; set_bkg_tiles(x, 8, 2, 1, tbuf);
            tbuf[0] = mt[2]; tbuf[1] = mt[3]; set_bkg_tiles(x, 9, 2, 1, tbuf);
        }
        mt = &gfx_meta_tiles[MT_DECO_SPLAT * 4];
        tbuf[0] = mt[0]; tbuf[1] = mt[1]; set_bkg_tiles(16, 6, 2, 1, tbuf);
        tbuf[0] = mt[2]; tbuf[1] = mt[3]; set_bkg_tiles(16, 7, 2, 1, tbuf);
        SWITCH_ROM(b);
    }
    has_save = save_valid();
    if (has_save) save_load(); else { menu_plate = 0; memset(save_sorts, 0, sizeof(save_sorts)); g_deaths = 0; g_time_frames_lo = g_time_frames_hi = 0; }
    menu_sel = has_save ? 1 : 0;
    title_draw_menu();
    text_bg(1, 15, "A JUMP   B FLIP INK");
    text_bg(5, 17, "2026 ~ 64K");
    g_phase = PH_INK; title_phase_t = 0; title_t = 0;
    SCX_REG = 0; SCY_REG = 0;
    apply_palettes(0);
    OBP1_REG = OBP_GHOST;
    SHOW_BKG; SHOW_SPRITES; SPRITES_8x16;
    DISPLAY_ON;
    music_play(SONG_TITLE);
    g_state = ST_TITLE;
}

static void title_frame(void) {
    title_t++;
    /* the bridge flips on its own so the hook is visible on the title */
    if (++title_phase_t >= 100) { title_phase_t = 0; g_phase ^= 1; apply_palettes(0); }
    if (joy_pressed & (J_UP | J_DOWN)) {
        if (has_save) { menu_sel ^= 1; sfx(SFX_MENU); }
    }
    if (has_save && menu_sel == 1 && (joy_pressed & (J_LEFT | J_RIGHT))) {
        uint8_t maxp;
        ENABLE_RAM; maxp = sram->plate; DISABLE_RAM;
        if (joy_pressed & J_RIGHT) { if (menu_plate < maxp) menu_plate++; }
        else { if (menu_plate > 0) menu_plate--; }
        sfx(SFX_MENU);
        title_draw_menu();
    }
    /* cursor + hero on the bridge */
    shadow_OAM[0].y = 16 + 48; shadow_OAM[0].x = 8 + 24; shadow_OAM[0].tile = SPR_P_IDLE0 + (((title_t & 63) < 48) ? 0 : 4); shadow_OAM[0].prop = 0;
    shadow_OAM[1].y = shadow_OAM[0].y; shadow_OAM[1].x = 8 + 32; shadow_OAM[1].tile = shadow_OAM[0].tile + 2; shadow_OAM[1].prop = 0;
    shadow_OAM[2].y = 16 + (11 + menu_sel) * 8 - 4; shadow_OAM[2].x = 8 + 32; shadow_OAM[2].tile = SPR_CURSOR; shadow_OAM[2].prop = 0;
    if (joy_pressed & (J_START | J_A)) {
        sfx(SFX_START);
        if (menu_sel == 0) {
            memset(save_sorts, 0, sizeof(save_sorts));
            g_deaths = 0; g_time_frames_lo = g_time_frames_hi = 0; g_ending_reached = 0;
            g_level = 0;
        } else {
            g_level = menu_plate;
        }
        g_state = ST_INTRO; state_t = 0;
        music_stop();
    }
}

/* ---- level intro card ----------------------------------------------------------- */
static void intro_enter(void) {
    const char *name;
    char s[20];
    uint8_t b = CURRENT_BANK, n = 0;
    uint8_t x;
    DISPLAY_OFF;
    HIDE_WIN;
    hide_all_sprites();
    clear_bg();
    load_world_gfx();
    strcpy(s, "PLATE 1");
    s[6] = '1' + g_level;
    text_bg(6, 7, s);
    SWITCH_ROM(2);
    name = level_defs[g_level].name;
    while (name[n]) n++;
    x = (uint8_t)((20 - n) >> 1);
    text_bg(x, 9, name);
    SWITCH_ROM(b);
    SCX_REG = 0;
    g_phase = PH_INK; apply_palettes(0);
    DISPLAY_ON;
    state_t = 0;
}

static void play_enter(uint8_t from_checkpoint) {
    DISPLAY_OFF;
    hide_all_sprites();
    level_load(g_level, from_checkpoint);
    load_backdrop_gfx();
    if (g_level == LEVEL_COUNT - 1) load_boss_gfx();   /* OBJ 208..255 alias BG 208..255: boss last, and
                                                            the boss plate's backdrop only uses slots below 208 */
    clear_bg();
    draw_full_screen();
    hud_full();
    move_win(7, 128);
    SHOW_WIN;
    SCX_REG = (uint8_t)cam_x;
    apply_palettes(0);
    OBP1_REG = OBP_GHOST;
    build_oam();
    DISPLAY_ON;
    g_state = ST_PLAY;
    paused = 0;
    vreg_update();
    {
        uint8_t b = CURRENT_BANK, m;
        SWITCH_ROM(2); m = level_defs[g_level].music; SWITCH_ROM(b);
        music_play(m == 3 ? SONG_BOSS : (m == 0 ? SONG_PLATE_A : (m == 1 ? SONG_PLATE_B : SONG_PLATE_C)));
    }
}

/* ---- ending ---------------------------------------------------------------------- */
static void ending_enter(void) {
    char s[20];
    uint16_t secs;
    uint8_t i, total = 0;
    DISPLAY_OFF;
    HIDE_WIN;
    hide_all_sprites();
    clear_bg();
    text_bg(5, 2, "FINAL PAGE");
    for (i = 0; i < 16; i++) tbuf[i] = T_HUD_RULE;
    set_bkg_tiles(2, 3, 16, 1, tbuf);
    text_bg(3, 6, "PLATES     8/8");
    for (i = 0; i < LEVEL_COUNT; i++) {
        uint8_t m = save_sorts[i];
        while (m) { total += m & 1; m >>= 1; }
    }
    strcpy(s, "SORTS     00/00");
    num2(&s[10], total); num2(&s[13], sorts_total_all);
    text_bg(3, 8, s);
    strcpy(s, "FALLS       000");
    s[12] = '0' + (g_deaths / 100) % 10; s[13] = '0' + (g_deaths / 10) % 10; s[14] = '0' + g_deaths % 10;
    text_bg(3, 10, s);
    /* time: frames / 60 (59.73 Hz nominal) */
    secs = (uint16_t)(((uint32_t)g_time_frames_hi * 65536u + g_time_frames_lo) / 60u);
    strcpy(s, "TIME      00:00");
    num2(&s[10], (uint8_t)(secs / 60 > 99 ? 99 : secs / 60)); num2(&s[13], (uint8_t)(secs % 60));
    text_bg(3, 12, s);
    text_bg(6, 15, "THE END");
    SCX_REG = 0;
    g_phase = PH_INK; apply_palettes(0);
    DISPLAY_ON;
    g_state = ST_ENDING; state_t = 0;
    g_ending_reached = 1;
    save_write();
    music_play(SONG_ENDING);
}

/* ---- VBL counter for lag detection -------------------------------------------- */
/* Scroll and palettes for the frame about to be drawn are applied from the VBL interrupt, first in the
   chain right after GBDK's OAM DMA, so they always land inside vblank no matter how long the music tick or
   the main loop's VRAM work takes (a late SCX write would shear the top scanlines by a pixel, and the two
   reference emulators resolve such a mid-scanline write differently).  vreg_on gates it so the title, intro
   and ending keep direct control of the palettes for their fades. */

static void vbl_isr(void) {
    g_vbl_count++;
    if (vreg_on) { SCX_REG = vreg_scx; BGP_REG = vreg_bgp; OBP1_REG = vreg_obp1; }
}

/* shadow registers for the play states; called at the end of a loop iteration (applied at the next vblank) */
static void vreg_update(void) {
    if (g_state == ST_PLAY || g_state == ST_DEATH || g_state == ST_CLEAR || g_state == ST_BOSS_DEAD) {
        vreg_scx = (uint8_t)cam_x;
        vreg_bgp = (g_phase == PH_INK) ? BGP_INK : BGP_CHALK;
        if (g_level == LEVEL_COUNT - 1) {
            /* boss palette: solid dark when it shares the player's phase, ghost otherwise */
            vreg_obp1 = (ents[0].type == ET_BOSS && ents[0].phase == g_phase) ? OBP_DARK : OBP_GHOST;
            if (g_boss_hp == 0 && ents[0].type != ET_BOSS) vreg_obp1 = OBP_GHOST;
        } else {
            vreg_obp1 = OBP_GHOST;
        }
        vreg_on = 1;
    } else {
        vreg_on = 0;
    }
}

/* ---- main -------------------------------------------------------------------------- */
void main(void) {
    uint8_t i;
    const LevelDef *L;
    DISPLAY_OFF;
    SPRITES_8x16;
    __critical { add_VBL(vbl_isr); }     /* before the music tick: registers first */
    audio_init();
    /* total sorts in the campaign (for the ending screen) */
    {
        uint8_t b = CURRENT_BANK, k;
        SWITCH_ROM(2);
        for (i = 0; i < LEVEL_COUNT; i++) {
            L = &level_defs[i];
            for (k = 0; k < L->nobjs; k++) if (L->objs[k].type == OBJ_SORT) sorts_total_all++;
        }
        SWITCH_ROM(b);
    }
    title_enter();
    last_vbl = g_vbl_count;

    while (1) {
        vsync();
        g_prof[0] = DIV_REG;
        g_frame++;
        /* lag detection: more than one vblank passed since the last loop */
        if ((uint8_t)(g_vbl_count - last_vbl) > 1) g_lag++;
        last_vbl = g_vbl_count;

        /* The scroll and palette registers for this frame were applied by vbl_isr at the start of this
           vblank (from the shadows set at the end of the previous iteration).  Now the queued VRAM work
           (streamed columns, checkpoint tiles, HUD); GBDK's tile writers wait for an accessible PPU mode,
           so they are safe even if they spill past vblank. */
        if (g_state == ST_PLAY || g_state == ST_DEATH || g_state == ST_CLEAR || g_state == ST_BOSS_DEAD) {
            vram_flush();
        }

        g_prof[1] = DIV_REG;
        joy_prev = joy;
        joy = joypad();
        joy_pressed = joy & ~joy_prev;
        g_joy = joy;

        switch (g_state) {
        case ST_TITLE:
            title_frame();
            if (g_state == ST_INTRO) { intro_enter(); }
            break;
        case ST_INTRO:
            state_t++;
            if (state_t > 90 || (state_t > 20 && (joy_pressed & (J_START | J_A)))) {
                play_enter(0);
            }
            break;
        case ST_PLAY:
            if (joy_pressed & J_START) {
                paused ^= 1;
                sfx(SFX_MENU);
                if (paused) { hud_row_clear(1); text_win(7, 1, "PAUSED"); }
                else hud_plate_row();
            }
            if (!paused) {
                play_frame();
                if (++g_time_frames_lo == 0) g_time_frames_hi++;
            }
            g_prof[2] = DIV_REG;
            break;
        case ST_DEATH:
            play_frame();
            if (play_timer() > 70) {
                fade_out();
                level_respawn();
                DISPLAY_OFF;
                clear_bg();
                draw_full_screen();
                hud_full();
                SCX_REG = (uint8_t)cam_x;
                build_oam();
                DISPLAY_ON;
                fade_in();
                g_state = ST_PLAY;
            }
            break;
        case ST_CLEAR:
            play_frame();
            if (play_timer() > 130) {
                save_sorts[g_level] = sorts_mask;
                fade_out();
                music_stop();
                g_level++;
                save_write();
                if (g_level >= LEVEL_COUNT) { ending_enter(); }
                else { intro_enter(); g_state = ST_INTRO; }
            }
            break;
        case ST_BOSS_DEAD:
            play_frame();
            if (play_timer() > 120) {
                save_sorts[g_level] = sorts_mask;
                fade_out();
                g_level = LEVEL_COUNT;      /* campaign complete */
                ending_enter();
                g_level = LEVEL_COUNT - 1;
                ENABLE_RAM; sram->plate = LEVEL_COUNT - 1; sram->sum = save_checksum(sram); DISABLE_RAM;
            }
            break;
        case ST_ENDING:
            state_t++;
            if (state_t > 120 && (joy_pressed & (J_START | J_A))) {
                music_stop();
                title_enter();
            }
            break;
        default:
            break;
        }

        audio_frame();
        vreg_update();
        g_prof[4] = DIV_REG;
        g_ly_end = LY_REG;
        g_div_end = DIV_REG;
    }
}
