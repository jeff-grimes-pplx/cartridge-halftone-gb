/* HALFTONE engine: level streaming, collision, player, entities, boss.
 * Lives in ROM bank 3 (banked calls from main). Level data is expanded by level.c (bank 0).
 *
 * Performance notes (DMG has ~17.5K M-cycles per frame and SDCC's 16-bit code is costly):
 *  - entities keep pixel coordinates (int16 x, uint8 y) plus 1/16 px sub-pixel accumulators,
 *  - the player's hitbox is cached once per frame,
 *  - OAM is written through a pointer and only stale entries are cleared.
 */
#pragma bank 3
#include "game.h"
#include <string.h>

/* streaming */
static uint8_t colq[4];               /* columns queued for drawing at next vblank */
static uint8_t tq_col[8], tq_row[8], tq_tile[8];

/* misc */
static uint8_t clear_t, death_t;
static uint8_t oam_n, oam_prev_n;
static uint8_t *oam_ptr;
static int16_t p_prev_bottom;  /* pixels */

/* player hitbox in pixels, refreshed once per frame */
static int16_t pb_x0, pb_x1;
static uint8_t pb_y0, pb_y1;

static const uint8_t bob_tab[16] = {0, 0, 1, 1, 2, 2, 2, 2, 2, 2, 1, 1, 0, 0, 0, 0};
static const int8_t moth_tab[32] = {0, 1, 2, 3, 4, 5, 6, 6, 7, 7, 7, 6, 6, 5, 4, 3, 2, 1, 0, -1, -2, -3, -4, -5, -6, -6, -7, -7, -7, -6, -6, -5};

/* ------------------------------------------------------------------------ */
uint8_t rng(void) BANKED {
    /* 8-bit LCG + xorshift step, deterministic per level so scripted runs replay. */
    rng_state = (uint8_t)(rng_state * 97u + 29u);
    rng_state ^= (rng_state >> 3);
    return rng_state;
}

/* ------------------------------------------------------------------------ */
/* Tiles                                                                      */
/* ------------------------------------------------------------------------ */
/* tile class at a world pixel position; above/below the map is empty, past the right edge solid */
uint8_t cls_at(int16_t wx, int16_t wy) {
    uint8_t col;
    if (wy < 0 || wy >= 128 || wx < 0) return C_EMPTY;
    col = (uint8_t)(wx >> 3);
    if (col >= lvl_w_tiles) return C_SOLID;
    return cls_ram[map[((uint16_t)col << 4) | (uint8_t)(wy >> 3)]];
}

uint8_t is_solid(uint8_t c) {
    if (c == C_SOLID) return 1;
    if (c == C_INK) return g_phase == PH_INK;
    if (c == C_CHALK) return g_phase == PH_CHALK;
    return 0;
}

uint8_t solid_at(int16_t wx, int16_t wy) {
    return is_solid(cls_at(wx, wy));
}


void queue_tile(uint8_t col, uint8_t row, uint8_t tile) {
    map[((uint16_t)col << 4) | row] = tile;
    if (tq_n < 8) {
        tq_col[tq_n] = col; tq_row[tq_n] = row; tq_tile[tq_n] = tile; tq_n++;
    }
}

void queue_col(uint8_t col) {
    if (colq_n < 4) colq[colq_n++] = col;
}

void draw_col_now(uint8_t col) {
    set_bkg_tiles(col & 31, 0, 1, 16, &map[(uint16_t)col << 4]);
}

/* draw everything visible for the current camera (display should be off) */
void draw_full_screen(void) BANKED {
    uint8_t c0 = (uint8_t)(cam_x >> 3), c;
    colq_n = 0; tq_n = 0;
    oam_prev_n = 40;                 /* next build_oam clears every entry */
    for (c = 0; c <= 20; c++) {
        if (c0 + c < lvl_w_tiles) draw_col_now(c0 + c);
    }
    drawn_min = (int16_t)c0;
    drawn_max = (int16_t)c0 + 20;
    if (drawn_max >= (int16_t)lvl_w_tiles) drawn_max = (int16_t)lvl_w_tiles - 1;
}

/* called right after vsync: apply queued VRAM work */
void vram_flush(void) BANKED {
    uint8_t i;
    for (i = 0; i < colq_n; i++) draw_col_now(colq[i]);
    colq_n = 0;
    for (i = 0; i < tq_n; i++) set_bkg_tile_xy(tq_col[i] & 31, tq_row[i], tq_tile[i]);
    tq_n = 0;
    if (hud_dirty) {
        if (hud_dirty & 1) hud_hearts();
        if (hud_dirty & 2) hud_sorts();
        if (hud_dirty & 4) hud_phase();
        if (hud_dirty & 8) hud_pulse(pulse_frac);
        hud_dirty = 0;
    }
}

void stream_columns(void) {
    int16_t c0 = (int16_t)(cam_x >> 3);
    int16_t want_max = c0 + 20;
    if (want_max >= (int16_t)lvl_w_tiles) want_max = (int16_t)lvl_w_tiles - 1;
    while (drawn_max < want_max) {
        drawn_max++;
        queue_col((uint8_t)drawn_max);
        if (drawn_min < drawn_max - 31) drawn_min = drawn_max - 31;
    }
    while (drawn_min > c0) {
        drawn_min--;
        queue_col((uint8_t)drawn_min);
        if (drawn_max > drawn_min + 31) drawn_max = drawn_min + 31;
    }
}

/* ------------------------------------------------------------------------ */
/* Phase                                                                      */
/* ------------------------------------------------------------------------ */
void set_phase(uint8_t ph) BANKED {
    g_phase = ph;
    hud_dirty |= 4;
}

/* does the player's hitbox overlap a tile that is solid in phase ph? */
uint8_t player_overlaps_phase(uint8_t ph) {
    int16_t x0 = (px >> FP) + HB_X0, x1 = (px >> FP) + HB_X1;
    int16_t y0 = (py >> FP) + HB_Y0, y1 = (py >> FP) + HB_Y1;
    uint8_t want = (ph == PH_INK) ? C_INK : C_CHALK;
    if (cls_at(x0, y0) == want || cls_at(x1, y0) == want || cls_at(x0, y1) == want || cls_at(x1, y1) == want)
        return 1;
    return 0;
}

void spawn(uint8_t type, int16_t x, uint8_t y, uint8_t phase);

void try_flip(uint8_t forced) {
    uint8_t np = g_phase ^ 1;
    if (player_overlaps_phase(np)) {
        if (forced) {
            /* crushed by the pulse: lose all hearts */
            g_hearts = 0; hud_dirty |= 1;
            g_state = ST_DEATH; death_t = 0; sfx(SFX_DIE);
            set_phase(np);
            return;
        }
        sfx(SFX_FLIP_BLOCKED);
        return;
    }
    set_phase(np);
    sfx(SFX_FLIP);
    p_flippose = 8;
    spawn(ET_PUFF, px >> FP, (uint8_t)(py >> FP), 2);
}

/* ------------------------------------------------------------------------ */
/* OAM                                                                           */
/* ------------------------------------------------------------------------ */
/* one 8x16 sprite at screen position (sx, sy); clipped horizontally, sy already on screen */
static void put8(int16_t sx, uint8_t sy, uint8_t tile, uint8_t prop) {
    int16_t ox = sx + 8;
    uint8_t *o;
    /* visible OAM x is 1..167: one unsigned compare covers both off-screen sides */
    if ((uint16_t)(ox - 1) >= 167 || oam_n >= 40) return;
    o = oam_ptr;
    *o++ = sy + 16;
    *o++ = (uint8_t)ox;
    *o++ = tile;
    *o++ = prop;
    oam_ptr = o;
    oam_n++;
}

/* 16x16 frame: tiles base (TL,BL), base+2 (TR,BR) */
static void put16(int16_t sx, uint8_t sy, uint8_t base, uint8_t prop, uint8_t flip) {
    if (flip) {
        put8(sx, sy, base + 2, prop | S_FLIPX);
        put8(sx + 8, sy, base, prop | S_FLIPX);
    } else {
        put8(sx, sy, base, prop);
        put8(sx + 8, sy, base + 2, prop);
    }
}

static void oam_begin(void) {
    oam_n = 0; oam_ptr = (uint8_t *)shadow_OAM;
}

static void oam_end(void) {
    uint8_t i;
    /* hide entries used last frame but not this one */
    for (i = oam_n; i < oam_prev_n; i++) { *oam_ptr = 0; oam_ptr += 4; }
    oam_prev_n = oam_n;
}

static void draw_player(void) {
    if (!(p_inv & 2) || g_state != ST_PLAY) {
        int16_t pyp = py >> FP;
        if (pyp > -16 && pyp < 144) put16((px >> FP) - (int16_t)cam_x, (uint8_t)pyp, p_frame, 0, p_dir);
    }
}

/* ------------------------------------------------------------------------ */
/* Entities                                                                    */
/* ------------------------------------------------------------------------ */
void spawn(uint8_t type, int16_t x, uint8_t y, uint8_t phase) {
    uint8_t i;
    Ent *e = ents;
    for (i = 0; i < MAX_ENTS; i++, e++) {
        if (e->type == ET_NONE) {
            if (i >= ent_hi) ent_hi = i + 1;
            e->type = type; e->x = x; e->cx8 = (uint8_t)(x >> 3); e->y = y; e->ox = x; e->oy = y;
            e->fx = 0; e->fy = 0; e->vx = 0; e->vy = 0; e->dx = 0;
            e->phase = phase; e->state = 0; e->timer = 0; e->anim = 0; e->dir = 0;
            e->hp = 0; e->slot = 0xFF;
            return;
        }
    }
}

/* apply 1/16 px velocities through the sub-pixel accumulators; records the pixel delta */
void ent_move(Ent *e) {
    /* Velocities are 1/16 px per frame and never exceed |98| (press slam), so the sub-pixel sum
       fx + v stays inside int8 and the arithmetic shift can be done in 8 bits.  Bit-identical to
       the 16-bit form: ((int16_t)fx + v) >> 4 and ((int16_t)fx + v) & 15. */
    int8_t v = e->vx;
    if (v) {
        int8_t t = (int8_t)(e->fx + v);
        int8_t d = (int8_t)(t >> 4);
        e->dx = d;
        if (d) { int16_t x = e->x + d; e->x = x; e->cx8 = (uint8_t)(x >> 3); }
        e->fx = (uint8_t)t & 15;
    } else {
        e->dx = 0;
    }
    v = e->vy;
    if (v) {
        int8_t t = (int8_t)(e->fy + v);
        e->y += (int8_t)(t >> 4);
        e->fy = (uint8_t)t & 15;
    }
}

void refresh_player_box(void) {
    int16_t x = px >> FP;
    uint8_t y = (uint8_t)(py >> FP);
    pb_x0 = x + HB_X0; pb_x1 = x + HB_X1; pb_y0 = y + HB_Y0; pb_y1 = y + HB_Y1;
}

/* AABB: player hitbox vs an entity box (pixels) */
uint8_t hit_player(int16_t ex0, uint8_t ey0, int16_t ex1, uint8_t ey1) {
    if (pb_y1 < ey0) return 0;
    if (pb_y0 > ey1) return 0;
    if (pb_x1 < ex0) return 0;
    if (pb_x0 > ex1) return 0;
    return 1;
}

void hurt_player(int16_t from_px) {
    if (p_inv) return;
    if (g_hearts) g_hearts--;
    hud_dirty |= 1;
    if (g_hearts == 0) {
        g_state = ST_DEATH; death_t = 0; sfx(SFX_DIE);
        pvy = -60; pvx = 0;
        return;
    }
    sfx(SFX_HURT);
    p_inv = INVULN; p_hurt_t = 16;
    pvy = -44;
    pvx = ((px >> FP) < from_px) ? -28 : 28;
}

void kill_ent(Ent *e) {
    spawn(ET_PUFF, e->x, e->y, 2);
    e->type = ET_NONE;
}

void stomp_bounce(void) {
    pvy = -52;
    sfx(SFX_STOMP);
    p_ground = 0;
}

/* walker sensing: wall ahead or no floor ahead */
uint8_t blot_blocked(Ent *e) {
    int16_t ahead = e->dir ? (e->x - 1) : (e->x + 16);
    if (ahead < 0) return 1;
    if (solid_at(ahead, e->y + 8)) return 1;          /* wall */
    if (!solid_at(ahead, e->y + 16)) return 1;        /* edge */
    return 0;
}

void update_boss(Ent *e);

/* draw-or-not test shared by all entity cases: on screen horizontally and vertically */
#define ON_SCREEN(sx, sy) ((sx) > -32 && (sx) < 160 && ((sy) < 144 || (sy) >= 240))

/* one pass: update every live entity and write its sprites straight into shadow OAM.
   One small function per entity type keeps SDCC from spilling a dozen locals to the stack
   (the monolithic switch version cost ~270 instructions per entity before any real work). */
static int16_t pxp;                 /* player x in pixels, computed once per frame in update_ents */
#define SCREEN_X(e) ((e)->x - (int16_t)cam_x)
#define PHASE_SOLID(e) (((e)->phase == 2) || ((e)->phase == g_phase))

static void upd_sort(Ent *e) {
    int16_t ex = e->x, sx = ex - (int16_t)cam_x;
    uint8_t ey = e->y;
    if (hit_player(ex, ey, ex + 7, ey + 11)) {
        sorts_mask |= (1 << e->slot);
        g_sorts++; hud_dirty |= 2;
        sfx(SFX_SORT);
        e->type = ET_SPARK; e->timer = 0; e->anim = 0;
        put8(sx, ey, SPR_SPARK0, 0);
        return;
    }
    if (ON_SCREEN(sx, ey)) put8(sx, ey - bob_tab[(e->anim >> 2) & 15], SPR_SORT, 0);
}

static void upd_blot(Ent *e) {
    int16_t ex, sx;
    uint8_t ey, solid = PHASE_SOLID(e);
    if (blot_blocked(e)) e->dir ^= 1;
    e->vx = e->dir ? -8 : 8;
    ent_move(e);
    ex = e->x; ey = e->y; sx = ex - (int16_t)cam_x;
    if (solid && hit_player(ex + 1, ey + 2, ex + 14, ey + 15)) {
        if (pvy > 0 && p_prev_bottom <= (int16_t)ey + 6) { kill_ent(e); stomp_bounce(); return; }
        hurt_player(ex);
    }
    if (ON_SCREEN(sx, ey)) put16(sx, ey, ((e->anim >> 3) & 1) ? SPR_BLOT1 : SPR_BLOT0, solid ? 0 : S_PALETTE, e->dir);
}

static void upd_moth(Ent *e) {
    int16_t ex, sx;
    uint8_t ey, solid = PHASE_SOLID(e);
    e->vx = e->dir ? -12 : 12;
    ent_move(e);
    if (e->x > e->ox + 56) e->dir = 1;
    if (e->x < e->ox - 56) e->dir = 0;
    ex = e->x; sx = ex - (int16_t)cam_x;
    ey = (uint8_t)(e->oy + moth_tab[(e->anim >> 1) & 31]);
    e->y = ey;
    if (solid && hit_player(ex + 2, ey + 2, ex + 13, ey + 11)) {
        if (pvy > 0 && p_prev_bottom <= (int16_t)ey + 6) { kill_ent(e); stomp_bounce(); return; }
        hurt_player(ex);
    }
    if (ON_SCREEN(sx, ey)) put16(sx, ey, ((e->anim >> 2) & 1) ? SPR_MOTH1 : SPR_MOTH0, solid ? 0 : S_PALETTE, e->dir);
}

static void upd_press(Ent *e) {
    int16_t ex = e->x, sx = ex - (int16_t)cam_x;
    uint8_t ey = e->y;
    if (e->state == 0) {                      /* waiting under the ceiling */
        if (pxp + 8 > ex - 12 && pxp + 8 < ex + 28 && pb_y0 > ey) { e->state = 1; e->vy = 8; }
    } else if (e->state == 1) {               /* slamming down */
        if (e->vy < 96) e->vy += 6;
        ent_move(e); ey = e->y;
        if (ey >= 112 || solid_at(ex + 2, ey + 16) || solid_at(ex + 13, ey + 16)) {
            e->y = (uint8_t)(((ey + 16) & ~7) - 16); e->fy = 0; e->vy = 0;
            e->state = 2; e->timer = 36; sfx(SFX_DROP);
        }
    } else if (e->state == 2) {               /* resting */
        if (--e->timer == 0) { e->state = 3; e->vy = -12; }
    } else {                                  /* rising */
        ent_move(e);
        if (e->y <= e->oy) { e->y = e->oy; e->fy = 0; e->vy = 0; e->state = 0; }
    }
    ey = e->y;
    if (hit_player(ex, ey + 2, ex + 15, ey + 14)) hurt_player(ex);
    if (ON_SCREEN(sx, ey)) {
        uint8_t cy = e->oy - 16;                   /* chain from the ceiling to the head */
        while (cy < ey - 2 && cy < 144) { put8(sx + 4, cy, SPR_CHAIN, 0); cy += 16; }
        put16(sx, ey, SPR_PRESS, 0, 0);
    }
}

static void upd_dripper(Ent *e) {
    int16_t ex = e->x, sx = ex - (int16_t)cam_x;
    if (++e->timer >= 100) {
        e->timer = 0;
        spawn(ET_DROP, ex + 4, e->y + 12, PH_INK);
        sfx(SFX_DROP);
    }
    if (ON_SCREEN(sx, e->y)) put16(sx, e->y, SPR_DRIPPER, 0, 0);
}

static void upd_drop(Ent *e) {
    int16_t ex = e->x, sx = ex - (int16_t)cam_x;
    uint8_t ey, solid = PHASE_SOLID(e);
    if (e->vy < 40) e->vy += 3;
    ent_move(e); ey = e->y;
    if (ey >= 128 || cls_at(ex + 3, ey + 10) == C_SOLID || (e->timer++ > 200)) { kill_ent(e); return; }
    if (solid && hit_player(ex + 1, ey + 1, ex + 6, ey + 10)) { hurt_player(ex); kill_ent(e); return; }
    if (ON_SCREEN(sx, ey)) put8(sx, ey, SPR_DROP, solid ? 0 : S_PALETTE);
}

static void upd_plat_h(Ent *e) {                 /* 1 px/frame over 48 px: a 96-frame cycle */
    int16_t sx;
    e->vx = e->dir ? -16 : 16;
    ent_move(e);
    if (e->x >= e->ox + 40) e->dir = 1;
    if (e->x <= e->ox - 8) e->dir = 0;
    sx = e->x - (int16_t)cam_x;
    if (ON_SCREEN(sx, e->y)) put16(sx, e->y, SPR_PLAT, 0, 0);
}

static void upd_plat_v(Ent *e) {
    int16_t sx = e->x - (int16_t)cam_x;
    uint8_t old = e->y;
    e->vy = e->dir ? -16 : 16;
    ent_move(e);
    e->dx = (int8_t)(e->y - old);              /* vertical delta carried to the rider */
    if (e->y >= e->oy + 8) e->dir = 1;
    if (e->y <= e->oy - 40) e->dir = 0;
    if (ON_SCREEN(sx, e->y)) put16(sx, e->y, SPR_PLAT, 0, 0);
}

static void upd_boss(Ent *e) {
    update_boss(e);
    if (e->type == ET_BOSS && !(e->state == 5 && (e->timer & 2))) {
        uint8_t base = (e->state == 4 || e->state == 5) ? SPR_BOSS2 : (((e->anim >> 4) & 1) ? SPR_BOSS1 : SPR_BOSS0);
        uint8_t col, row;
        int16_t sx = e->x - (int16_t)cam_x;
        uint8_t ey = e->y;
        for (row = 0; row < 2; row++)
            for (col = 0; col < 4; col++)
                put8(sx + (col << 3), ey + (row << 4), base + (row << 3) + (col << 1), S_PALETTE);
    }
}

static void upd_puff(Ent *e) {
    int16_t sx;
    if (++e->timer > 14) { e->type = ET_NONE; return; }
    sx = e->x - (int16_t)cam_x;
    if (ON_SCREEN(sx, e->y)) put8(sx + 4, e->y + 2, (e->timer < 7) ? SPR_PUFF0 : SPR_PUFF1, 0);
}

static void upd_spark(Ent *e) {
    int16_t sx;
    e->y -= 1;
    if (++e->timer > 16) { e->type = ET_NONE; return; }
    sx = e->x - (int16_t)cam_x;
    if (ON_SCREEN(sx, e->y)) put8(sx, e->y, (e->timer < 8) ? SPR_SPARK0 : SPR_SPARK1, 0);
}

/* one active entity: advance its animation counter, then simulate and draw by type */
static void update_one(Ent *e) {
    e->anim++;
    switch (e->type) {
    case ET_SORT:    upd_sort(e); break;
    case ET_BLOT:    upd_blot(e); break;
    case ET_MOTH:    upd_moth(e); break;
    case ET_PRESS:   upd_press(e); break;
    case ET_DRIPPER: upd_dripper(e); break;
    case ET_DROP:    upd_drop(e); break;
    case ET_PLAT_H:  upd_plat_h(e); break;
    case ET_PLAT_V:  upd_plat_v(e); break;
    case ET_BOSS:    upd_boss(e); break;
    case ET_PUFF:    upd_puff(e); break;
    case ET_SPARK:   upd_spark(e); break;
    default: break;
    }
}

void update_ents(void) {
    uint8_t i;
    uint8_t cam_c8 = (uint8_t)(cam_x >> 3);
    Ent *e = ents;
    refresh_player_box();
    pxp = px >> FP;
    for (i = ent_hi; i; i--, e++) {
        uint8_t t = e->type;
        if (t == ET_NONE) continue;
        /* freeze anything more than 48 px off either screen edge, except presses, drops and the boss
           (8-bit column test: sx/8 in [-6, 26] <=> cx8 - cam_c8 + 6 in [0, 32]) */
        if ((uint8_t)(e->cx8 - cam_c8 + 6) > 32 && t < ET_PRESS) continue;
        update_one(e);
    }
    /* shrink the active range when the top slots are free */
    while (ent_hi && ents[ent_hi - 1].type == ET_NONE) ent_hi--;
}

/* platform support: snap the player on a platform top if falling onto it */
void platform_support(void) {
    uint8_t i;
    int16_t x0, x1, bottom;
    if (!n_plats || pvy < 0) return;
    x0 = (px >> FP) + HB_X0; x1 = (px >> FP) + HB_X1;
    bottom = (py >> FP) + HB_Y1;
    for (i = 0; i < n_plats; i++) {
        int16_t top;
        Ent *e = &ents[plat_idx[i]];
        if (x1 < e->x || x0 > e->x + 15) continue;
        top = e->y;
        if (bottom >= top - 1 && p_prev_bottom <= top + 3 && bottom <= top + 6) {
            py = PX(top - HB_Y1 - 1);
            pvy = 0; p_ground = 1;
            if (e->type == ET_PLAT_H) px += PX((int16_t)e->dx); else py += PX((int16_t)e->dx);
        }
    }
}

/* ------------------------------------------------------------------------ */
/* Boss: The Smudge (32x32, 5 HP). Hovers, slams, rests (stompable while solid),  */
/* flips its own ink after every hit and rains drops.                            */
/* ------------------------------------------------------------------------ */
void update_boss(Ent *e) {
    int16_t ex = e->x;
    uint8_t ey = e->y;
    uint8_t solid = (e->phase == g_phase);
    uint8_t dmg = BOSS_HP - e->hp;
    switch (e->state) {
    case 0:   /* hover left/right near the top */
        e->vx = (int8_t)(8 + dmg * 3);
        if (e->dir) e->vx = -e->vx;
        e->vy = 0;
        ent_move(e);
        if (e->x > 120) e->dir = 1;
        if (e->x < 8) e->dir = 0;
        e->y = e->oy + bob_tab[(e->anim >> 2) & 15];
        if (++e->timer > (uint8_t)(150 - dmg * 20)) {
            e->timer = 0;
            /* slam when roughly above the player */
            if (ex + 16 > (px >> FP) - 24 && ex + 16 < (px >> FP) + 40) { e->state = 1; e->vx = 0; e->vy = 0; e->fy = 0; }
        }
        break;
    case 1:   /* slam down */
        if (e->vy < 72) e->vy += 5;
        ent_move(e); ey = e->y;
        if (ey >= 80) { e->y = 80; e->fy = 0; e->vy = 0; e->state = 2; e->timer = 80; sfx(SFX_DROP); }
        break;
    case 2:   /* resting on the floor: stompable while solid */
        if (--e->timer == 0) {
            uint8_t k;
            e->state = 3; e->vy = -10;
            for (k = 0; k < 3; k++) spawn(ET_DROP, 16 + (rng() & 127), (uint8_t)(240 - k * 10), e->phase);
        }
        break;
    case 3:   /* rise back */
        ent_move(e);
        if (e->y <= e->oy || e->y > 200) { e->y = e->oy; e->fy = 0; e->vy = 0; e->state = 0; e->timer = 0; }
        break;
    case 4:   /* hurt flash */
        if (--e->timer == 0) { e->state = 3; e->vy = -10; e->phase ^= 1; }
        break;
    case 5:   /* dying */
        e->timer++;
        if (e->timer > 90) { e->type = ET_NONE; g_state = ST_BOSS_DEAD; clear_t = 0; }
        else if ((e->timer & 7) == 0) spawn(ET_PUFF, e->x + (rng() & 15), e->y + (rng() & 15), 2);
        return;
    }
    ex = e->x; ey = e->y;
    solid = (e->phase == g_phase);   /* re-evaluate: the hurt flash flips the boss's ink on its last frame */
    if (e->state != 4 && solid && hit_player(ex + 2, ey + 2, ex + 29, ey + 28)) {
        if (pvy > 0 && p_prev_bottom <= (int16_t)ey + 10 && e->state == 2) {
            e->hp--; g_boss_hp = e->hp;
            stomp_bounce(); sfx(SFX_BOSS_HIT);
            if (e->hp == 0) { e->state = 5; e->timer = 0; music_stop(); }
            else { e->state = 4; e->timer = 30; }
        } else {
            hurt_player(ex + 8);
        }
    }
}

/* ------------------------------------------------------------------------ */
/* Player                                                                      */
/* ------------------------------------------------------------------------ */
void player_update(void) {
    int16_t nx, ny, X, Y;
    uint8_t c;
    int16_t x0, x1, y0, y1;

    p_prev_bottom = (py >> FP) + HB_Y1;

    /* ---- input ---- */
    if (p_hurt_t) {
        p_hurt_t--;
    } else {
        if (joy & J_LEFT) {
            p_dir = 1;
            pvx -= p_ground ? RUN_ACCEL : AIR_ACCEL;
            if (pvx < -RUN_SPEED) pvx = -RUN_SPEED;
        } else if (joy & J_RIGHT) {
            p_dir = 0;
            pvx += p_ground ? RUN_ACCEL : AIR_ACCEL;
            if (pvx > RUN_SPEED) pvx = RUN_SPEED;
        } else {
            if (pvx > FRICTION) pvx -= FRICTION;
            else if (pvx < -FRICTION) pvx += FRICTION;
            else pvx = 0;
        }
        if (joy_pressed & J_A) p_jbuf = JUMP_BUFFER;
        if (p_jbuf && (p_ground || p_coyote)) {
            pvy = JUMP_V; p_ground = 0; p_coyote = 0; p_jbuf = 0;
            sfx(SFX_JUMP);
        }
        if (!(joy & J_A) && pvy < JUMP_CUT) pvy = JUMP_CUT;
        if (joy_pressed & J_B) try_flip(0);
    }
    if (p_jbuf) p_jbuf--;
    if (p_coyote) p_coyote--;
    if (p_inv) p_inv--;
    if (p_flippose) p_flippose--;

    /* ---- gravity ---- */
    pvy += GRAVITY;
    if (pvy > MAX_FALL) pvy = MAX_FALL;

    /* ---- horizontal move + collision ---- */
    nx = px + pvx;
    y0 = (py >> FP) + HB_Y0; y1 = (py >> FP) + HB_Y1;
    if (pvx > 0) {
        X = (nx >> FP) + HB_X1;
        if (solid_at(X, y0) || solid_at(X, (y0 + y1) >> 1) || solid_at(X, y1)) {
            nx = PX((X & ~7) - HB_X1 - 1); pvx = 0;
        }
    } else if (pvx < 0) {
        X = (nx >> FP) + HB_X0;
        if (solid_at(X, y0) || solid_at(X, (y0 + y1) >> 1) || solid_at(X, y1)) {
            nx = PX((X & ~7) + 8 - HB_X0); pvx = 0;
        }
    }
    if (nx < 0) nx = 0;
    px = nx;

    /* ---- vertical move + collision ---- */
    ny = py + pvy;
    x0 = (px >> FP) + HB_X0; x1 = (px >> FP) + HB_X1;
    if (pvy > 0) {
        uint8_t was_ground = p_ground;
        Y = (ny >> FP) + HB_Y1;
        c = 0;
        if (solid_at(x0, Y) || solid_at(x1, Y)) c = 1;
        else if ((cls_at(x0, Y) == C_LEDGE || cls_at(x1, Y) == C_LEDGE) && p_prev_bottom < (Y & ~7)) c = 1;
        if (c) {
            ny = PX((Y & ~7) - HB_Y1 - 1); pvy = 0; p_ground = 1;
        } else {
            p_ground = 0;
            if (was_ground) p_coyote = COYOTE;
        }
    } else if (pvy < 0) {
        Y = (ny >> FP) + HB_Y0;
        if (solid_at(x0, Y) || solid_at(x1, Y)) {
            ny = PX((Y & ~7) + 8 - HB_Y0); pvy = 0;
        }
        p_ground = 0;
    }
    py = ny;
    platform_support();

    /* ---- triggers ---- */
    {
        int16_t cx = (px >> FP) + 8, cy = (py >> FP) + 9, fy = (py >> FP) + HB_Y1;
        uint8_t cc = cls_at(cx, cy), cf = cls_at(cx, fy);
        if (cf == C_SPIKE || cc == C_SPIKE) {
            if (!p_inv) { hurt_player(px >> FP); if (g_state == ST_PLAY) { pvy = -56; pvx = p_dir ? 20 : -20; } }
        } else if (cf == C_DEADLY || cc == C_DEADLY || (py >> FP) > 150) {
            if (g_state == ST_PLAY) { g_hearts = 0; hud_dirty |= 1; g_state = ST_DEATH; death_t = 0; sfx(SFX_DIE); pvy = -60; }
        } else if (cc == C_CHECK) {
            uint8_t col = (uint8_t)(cx >> 3), row = (uint8_t)(cy >> 3);
            uint8_t mx = col >> 1, my = row >> 1;
            /* find the head metatile (the post is below it) */
            if (map[((uint16_t)(mx << 1) << 4) | (my << 1)] == meta_ram[MT_CP_POST * 4]) my--;
            if (map[((uint16_t)(mx << 1) << 4) | (my << 1)] == meta_ram[MT_CP_HEAD * 4]) {
                queue_tile(mx << 1, my << 1, meta_ram[MT_CP_HEAD_ON * 4]);
                queue_tile((mx << 1) + 1, my << 1, meta_ram[MT_CP_HEAD_ON * 4 + 1]);
                queue_tile(mx << 1, (my << 1) + 1, meta_ram[MT_CP_HEAD_ON * 4 + 2]);
                queue_tile((mx << 1) + 1, (my << 1) + 1, meta_ram[MT_CP_HEAD_ON * 4 + 3]);
                cp_x = mx; cp_y = my + 1;
                sfx(SFX_CHECK);
                if (g_hearts < 3) { g_hearts = 3; hud_dirty |= 1; }
            }
        } else if (cc == C_EXIT && g_state == ST_PLAY) {
            g_state = ST_CLEAR; clear_t = 0;
            music_play(6);                  /* clear jingle */
        }
    }

    /* ---- animation ---- */
    if (p_hurt_t) p_frame = SPR_P_HURT;
    else if (p_flippose) p_frame = SPR_P_FLIP;
    else if (!p_ground) p_frame = (pvy < 0) ? SPR_P_JUMP : SPR_P_FALL;
    else if (pvx) {
        p_anim++;
        p_frame = SPR_P_RUN0 + ((p_anim >> 2) & 3) * 4;
    } else {
        p_anim++;
        p_frame = ((p_anim & 63) < 48) ? SPR_P_IDLE0 : SPR_P_IDLE1;
    }

    g_px = px >> FP; g_py = py >> FP;
}

void camera_update(void) {
    int16_t target = (px >> FP) - 72 + (p_dir ? -8 : 8);
    int16_t cx = (int16_t)cam_x;
    int16_t maxc = (int16_t)(lvl_w_tiles << 3) - 160;
    int16_t d;
    if (target > cx + 4) { d = (target - cx) >> 3; cx += d ? d : 1; }
    else if (target < cx - 4) { d = (cx - target) >> 3; cx -= d ? d : 1; }
    if (cx < 0) cx = 0;
    if (cx > maxc) cx = maxc;
    cam_x = (uint16_t)cx;
}

/* ------------------------------------------------------------------------ */
/* Per-frame gameplay                                                           */
/* ------------------------------------------------------------------------ */
void play_frame(void) BANKED {
    oam_begin();
    if (g_state == ST_PLAY) {
        player_update();
        g_prof[5] = DIV_REG;
        draw_player();
        if (g_state == ST_PLAY || g_state == ST_CLEAR || g_state == ST_DEATH) update_ents();
        g_prof[6] = DIV_REG;
        if (level_pulse) {
            if (--pulse_t == 0) { pulse_t = level_pulse; try_flip(1); }
            else if (pulse_t == 30 || pulse_t == 15) sfx(SFX_TICK);
            {
                uint8_t f = (uint8_t)(((uint16_t)pulse_t << 3) / level_pulse);
                if (f != pulse_frac) { pulse_frac = f; hud_dirty |= 8; }
            }
        }
        camera_update();
    } else if (g_state == ST_DEATH) {
        /* fall off screen with the hurt pose */
        pvy += GRAVITY; if (pvy > MAX_FALL) pvy = MAX_FALL;
        py += pvy; p_frame = SPR_P_HURT;
        g_px = px >> FP; g_py = py >> FP;
        draw_player();
        update_ents();
        death_t++;
    } else if (g_state == ST_CLEAR) {
        /* auto-walk into the door */
        clear_t++;
        p_dir = 0;
        if (clear_t < 40) { px += 12; p_anim++; p_frame = SPR_P_RUN0 + ((p_anim >> 2) & 3) * 4; }
        else p_frame = SPR_P_IDLE0;
        g_px = px >> FP; g_py = py >> FP;
        draw_player();
        update_ents();
    } else if (g_state == ST_BOSS_DEAD) {
        clear_t++;
        draw_player();
        update_ents();
    }
    oam_end();
    stream_columns();
}

/* draw only (used right after a level load, before the first play_frame) */
void build_oam(void) BANKED {
    oam_begin();
    draw_player();
    oam_end();
}

uint8_t play_timer(void) BANKED { return (g_state == ST_DEATH) ? death_t : clear_t; }

