/* HALFTONE - shared declarations. Original Game Boy game built with GBDK-2020. */
#ifndef GAME_H
#define GAME_H
#include <gb/gb.h>
#include <stdint.h>
#include <stdbool.h>
#include "gfx.h"
#include "levels.h"

/* ---- fixed point: positions and speeds are in 1/16 pixel ---------------- */
#define FP 4
#define PX(v) ((int16_t)((v) << FP))

/* ---- phases ----------------------------------------------------------- */
#define PH_INK 0
#define PH_CHALK 1
/* BGP: colour 0 paper(white) 1 pale 2 dark grey 3 black  -> ink phase: 3 solid black, 1 pale */
#define BGP_INK   0xE4   /* 11 10 01 00 */
#define BGP_CHALK 0x6C   /* 01 10 11 00 : colour1 black, colour3 pale */
#define OBP_SOLID 0xE0   /* 11 10 00 00 : 1 white, 2 dark grey, 3 black */
#define OBP_GHOST 0x54   /* 01 01 01 00 : everything pale */
#define OBP_DARK  0xF8   /* 11 11 10 00 : 1 dark grey, 2 black, 3 black (boss solid) */

/* ---- game states ------------------------------------------------------ */
enum { ST_BOOT = 0, ST_TITLE, ST_INTRO, ST_PLAY, ST_DEATH, ST_CLEAR, ST_ENDING, ST_PAUSE, ST_BOSS_DEAD };

/* ---- player ----------------------------------------------------------- */
#define RUN_SPEED 24      /* 1.5 px/frame */
#define RUN_ACCEL 3
#define AIR_ACCEL 2
#define FRICTION 3
#define GRAVITY 4         /* 0.25 px/frame^2 */
#define JUMP_V (-66)      /* 4.125 px/frame  -> 34 px apex */
#define JUMP_CUT (-24)
#define MAX_FALL 64
#define COYOTE 6
#define JUMP_BUFFER 6
#define HB_X0 4
#define HB_X1 11
#define HB_Y0 3
#define HB_Y1 15
#define INVULN 70

/* ---- entities ---------------------------------------------------------- */
#define MAX_ENTS 20
/* order matters: types >= ET_PRESS keep updating while far off screen (see update_ents) */
enum { ET_NONE = 0, ET_SORT, ET_BLOT, ET_MOTH, ET_DRIPPER, ET_PLAT_H, ET_PLAT_V, ET_PUFF, ET_SPARK, ET_CHAIN,
       ET_PRESS, ET_DROP, ET_BOSS };
#define MAX_PLATS 4
typedef struct {
    uint8_t type;
    uint8_t phase;      /* PH_INK / PH_CHALK for phase-bound things, 2 = neutral */
    int16_t x;          /* world x, pixels (top-left of the 16x16 box) */
    uint8_t cx8;        /* x >> 3, kept in step with x (cheap 8-bit culling against the camera) */
    uint8_t y;          /* world y, pixels; >= 144 is off the bottom */
    uint8_t fx, fy;     /* 1/16 px sub-pixel accumulators */
    int8_t vx, vy;      /* 1/16 px per frame */
    int8_t dx;          /* pixel delta moved this frame (platforms carry the rider) */
    int16_t ox;         /* origin x (patrol centre) */
    uint8_t oy;         /* origin y */
    uint8_t state, timer, anim, dir, hp, slot;
} Ent;

/* ---- globals (exported for the emulator harness probes) --------------- */
extern uint16_t g_frame;
extern uint8_t g_state;
extern uint8_t g_level;
extern int16_t g_px, g_py;
extern uint8_t g_hearts, g_sorts, g_phase, g_joy, g_ly_end, g_div_end, g_lag, g_boss_hp, g_ending_reached;
extern uint16_t g_deaths;
extern uint8_t g_vbl_count;
extern uint8_t g_sorts_total;
extern uint16_t g_time_frames_lo, g_time_frames_hi;
extern uint8_t g_prof[8];

extern uint8_t map[LEVEL_MAX_W * 2 * 16];
extern uint8_t lvl_w_tiles;          /* level width in 8px tiles */
extern uint16_t cam_x;               /* pixels */
extern Ent ents[MAX_ENTS];
extern uint8_t joy, joy_prev, joy_pressed;
extern uint8_t sorts_mask;           /* collected sorts in the current level (bit per sort slot) */
extern uint8_t rng_state;
extern uint8_t meta_ram[META_COUNT * 4];
extern uint8_t cls_ram[256];

/* player + level state shared between level.c (bank 0 loader) and engine.c (bank 3) */
extern int16_t px, py, pvx, pvy;
extern uint8_t p_dir, p_ground, p_coyote, p_jbuf, p_anim, p_frame, p_inv, p_flippose, p_hurt_t;
extern uint8_t cp_x, cp_y;           /* respawn point in metatiles */
extern uint8_t level_pulse, pulse_t, pulse_frac, level_music;
extern int16_t drawn_min, drawn_max;   /* tile columns; levels can be 128 columns wide */
extern uint8_t colq_n, tq_n, hud_dirty;
extern uint8_t boss_slot;
extern uint8_t n_plats;
extern uint8_t plat_idx[MAX_PLATS];  /* entity slots holding platforms (platform_support only walks these) */
extern uint8_t ent_hi;               /* highest used entity slot + 1 */
#define BOSS_HP 5

/* level.c (bank 0) */
void gfx_tables_to_ram(void);
void level_load(uint8_t idx, uint8_t from_checkpoint);
void level_respawn(void);

/* engine.c (bank 3, banked calls) */
void play_frame(void) BANKED;
void draw_full_screen(void) BANKED;
void build_oam(void) BANKED;
void set_phase(uint8_t ph) BANKED;
void vram_flush(void) BANKED;
uint8_t play_timer(void) BANKED;
uint8_t rng(void) BANKED;

/* audio.c */
void audio_init(void);
void music_play(uint8_t song);
void music_stop(void);
void sfx(uint8_t id);
void audio_frame(void);
enum { SFX_JUMP = 1, SFX_FLIP, SFX_FLIP_BLOCKED, SFX_SORT, SFX_HURT, SFX_STOMP, SFX_DIE, SFX_MENU, SFX_CHECK, SFX_TICK,
       SFX_BOSS_HIT, SFX_START, SFX_DROP };

/* main.c helpers */
void text_bg(uint8_t x, uint8_t y, const char *s);
void text_win(uint8_t x, uint8_t y, const char *s);
void hud_full(void);
void hud_row_clear(uint8_t row);
void hud_plate_row(void);
void hud_hearts(void);
void hud_sorts(void);
void hud_phase(void);
void hud_pulse(uint8_t frac);
void queue_tile(uint8_t col, uint8_t row, uint8_t tile);
void save_write(void);

#endif
