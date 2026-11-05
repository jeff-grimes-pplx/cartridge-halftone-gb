/* HALFTONE level loader (bank 0, non-banked): expands a plate from bank 2 into WRAM and
 * spawns its objects. Kept out of the banked engine because it switches ROM banks itself.
 */
#include "game.h"
#include <string.h>

uint8_t map[LEVEL_MAX_W * 2 * 16];
uint8_t lvl_w_tiles;
uint16_t cam_x;
Ent ents[MAX_ENTS];
uint8_t sorts_mask;
uint8_t rng_state = 0x5A;
uint8_t meta_ram[META_COUNT * 4];
uint8_t cls_ram[256];

int16_t px, py, pvx, pvy;
uint8_t p_dir, p_ground, p_coyote, p_jbuf, p_anim, p_frame, p_inv, p_flippose, p_hurt_t;
uint8_t cp_x, cp_y;
uint8_t level_pulse, pulse_t, pulse_frac, level_music;
int16_t drawn_min, drawn_max;
uint8_t colq_n, tq_n, hud_dirty;
uint8_t boss_slot;
uint8_t n_plats;
uint8_t plat_idx[MAX_PLATS];
uint8_t ent_hi;

void gfx_tables_to_ram(void) {
    uint8_t b = CURRENT_BANK;
    SWITCH_ROM(2);
    memcpy(meta_ram, gfx_meta_tiles, sizeof(meta_ram));
    memcpy(cls_ram, gfx_tile_class, 256);
    SWITCH_ROM(b);
}

static void ent_init(Ent *e, uint8_t type, int16_t x, uint8_t y, uint8_t phase) {
    e->type = type; e->x = x; e->cx8 = (uint8_t)(x >> 3); e->y = y; e->ox = x; e->oy = y;
    e->fx = 0; e->fy = 0; e->vx = 0; e->vy = 0; e->dx = 0;
    e->phase = phase; e->state = 0; e->timer = 0; e->anim = 0; e->dir = 0;
    e->hp = 0; e->slot = 0xFF;
}

/* bank 2 must be active */
static void expand_map(const LevelDef *L) {
    uint8_t mx, my, w = L->width;
    const uint8_t *src = L->map;
    for (mx = 0; mx < w; mx++) {
        uint8_t *dst = &map[(uint16_t)(mx << 1) << 4];
        for (my = 0; my < 8; my++) {
            const uint8_t *m = &meta_ram[(*src++) << 2];
            dst[my << 1] = m[0];
            dst[(my << 1) + 1] = m[2];
            dst[16 + (my << 1)] = m[1];
            dst[16 + (my << 1) + 1] = m[3];
        }
    }
    lvl_w_tiles = w << 1;
}

/* bank 2 must be active */
static void spawn_level_objects(const LevelDef *L) {
    uint8_t i, n, sort_slot = 0, next = 0;
    memset(ents, 0, sizeof(ents));
    n_plats = 0;
    n = L->nobjs;
    for (i = 0; i < n && next < MAX_ENTS; i++) {
        const LevelObj *o = &L->objs[i];
        int16_t x = (int16_t)o->x << 4;
        uint8_t y = o->y << 4;
        Ent *e = &ents[next];
        switch (o->type) {
        case OBJ_SORT:
            if (!(sorts_mask & (1 << sort_slot))) {
                ent_init(e, ET_SORT, x + 4, y + 2, 2);
                e->slot = sort_slot;
                next++;
            }
            sort_slot++;
            break;
        case OBJ_BLOT:    ent_init(e, ET_BLOT, x, y, o->param); next++; break;
        case OBJ_MOTH:    ent_init(e, ET_MOTH, x, y, o->param); next++; break;
        case OBJ_PRESS:   ent_init(e, ET_PRESS, x, y, 2); next++; break;
        case OBJ_DRIPPER: ent_init(e, ET_DRIPPER, x, y, 2); next++; break;
        case OBJ_PLAT_H:
        case OBJ_PLAT_V:
            if (n_plats < MAX_PLATS) {
                ent_init(e, o->type == OBJ_PLAT_H ? ET_PLAT_H : ET_PLAT_V, x, y, 2);
                plat_idx[n_plats++] = next; next++;
            }
            break;
        case OBJ_BOSS:
            ent_init(e, ET_BOSS, x, y, PH_INK);
            e->hp = BOSS_HP; boss_slot = next; g_boss_hp = BOSS_HP;
            next++;
            break;
        default: break;
        }
    }
    g_sorts_total = sort_slot;
    ent_hi = next;
}

static void place_player(uint8_t mx, uint8_t my) {
    int16_t c, maxc;
    px = PX((int16_t)mx << 4); py = PX(((int16_t)my << 4));
    pvx = 0; pvy = 0; p_ground = 0; p_coyote = 0; p_jbuf = 0; p_inv = 0; p_hurt_t = 0; p_flippose = 0;
    p_dir = 0; p_frame = SPR_P_IDLE0;
    c = (px >> FP) - 72;
    maxc = (int16_t)(lvl_w_tiles << 3) - 160;
    if (c < 0) c = 0;
    if (c > maxc) c = maxc;
    cam_x = (uint16_t)c;
    g_px = px >> FP; g_py = py >> FP;
}

void level_load(uint8_t idx, uint8_t from_checkpoint) {
    const LevelDef *L;
    uint8_t save = CURRENT_BANK;
    g_level = idx;
    gfx_tables_to_ram();
    SWITCH_ROM(2);
    L = &level_defs[idx];
    expand_map(L);
    level_pulse = L->pulse; pulse_t = L->pulse; pulse_frac = 0;
    level_music = L->music;
    if (!from_checkpoint) { cp_x = L->start_x; cp_y = L->start_y; sorts_mask = 0; g_sorts = 0; }
    rng_state = (uint8_t)(0x5A + idx * 17);
    g_boss_hp = 0;
    spawn_level_objects(L);
    SWITCH_ROM(save);
    g_hearts = 3;
    set_phase(PH_INK);
    place_player(cp_x, cp_y);
    drawn_min = drawn_max = -1; colq_n = 0; tq_n = 0; hud_dirty = 0x0F;
}

void level_respawn(void) {
    level_load(g_level, 1);
    g_deaths++;
}
