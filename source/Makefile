# HALFTONE - build with GBDK-2020 4.5.0 (SDCC 4.5.1) + hUGEDriver 6.1.3
#
#   make            -> build/HALFTONE.gb (+ .map/.noi/.sym for the harness)
#   make check      -> verify header checksums with rgbfix -v (no bytes may change)
#   make clean
#
# Tool locations can be overridden: make GBDK=/path/to/gbdk HUGE=/path/to/hUGEDriver RGBDS6=/path/to/rgbds-0.6.1
GBDK   ?= /tmp/a5-tools/gbdk
HUGE   ?= /tmp/a5-tools/hUGEDriver
RGBDS6 ?= /tmp/a5-tools/rgbds-0.6.1
RGBFIX ?= /tmp/a5-tools/rgbds/rgbfix
PY     ?= python3

LCC    = $(GBDK)/bin/lcc
BUILD  = build
GEN    = gen
ROM    = $(BUILD)/HALFTONE.gb

# MBC5 + RAM + BATTERY (0x1B), 1 x 8 KiB SRAM bank, 4 x 16 KiB ROM banks (64 KiB), title HALFTONE
CART   = -Wm-yt0x1B -Wm-ya1 -Wl-yo4 -Wm-yn"HALFTONE"
CFLAGS = -Wa-l -Wl-m -Wl-j -debug -I$(GEN) -Isrc -I$(HUGE)/include
# the per-frame engine is compiled for speed with a deeper register-allocation search (slower compile, ~10 s)
OPT    = -Wf--opt-code-size
$(BUILD)/engine.o: OPT = -Wf--opt-code-speed -Wf--max-allocs-per-node3000

SRC    = src/main.c src/engine.c src/audio.c src/level.c
GENC   = $(GEN)/gfx.c $(GEN)/levels.c $(GEN)/music.c
OBJS   = $(patsubst src/%.c,$(BUILD)/%.o,$(SRC)) $(patsubst $(GEN)/%.c,$(BUILD)/%.o,$(GENC)) $(BUILD)/hUGEDriver.o

all: $(ROM)

$(GEN)/gfx.c $(GEN)/gfx.h $(GEN)/gfx_logo_map.h: tools/art.py tools/pix.py tools/backdrop.py
	$(PY) tools/art.py $(GEN)

$(GEN)/levels.c $(GEN)/levels.h: tools/levels.py tools/backdrop.py $(GEN)/gfx.h
	$(PY) tools/levels.py $(GEN)

$(GEN)/music.c $(GEN)/music.h: tools/music.py
	$(PY) tools/music.py $(GEN)

# hUGEDriver is assembled with RGBDS 0.6.1 (object format rev 9, required by rgb2sdas.py) and converted to an SDCC object
$(BUILD)/hUGEDriver.o: $(HUGE)/hUGEDriver.asm
	mkdir -p $(BUILD)
	cd $(HUGE) && $(RGBDS6)/rgbasm -I. -DGBDK -o $(CURDIR)/$(BUILD)/hUGEDriver.obj hUGEDriver.asm
	$(PY) $(HUGE)/tools/rgb2sdas.py -b 0 -o $@ $(BUILD)/hUGEDriver.obj

$(BUILD)/%.o: src/%.c src/game.h $(GEN)/gfx.h $(GEN)/levels.h $(GEN)/music.h $(GEN)/gfx_logo_map.h
	mkdir -p $(BUILD)
	$(LCC) $(CFLAGS) $(OPT) -c -o $@ $<

$(BUILD)/%.o: $(GEN)/%.c $(GEN)/gfx.h $(GEN)/levels.h $(GEN)/music.h
	mkdir -p $(BUILD)
	$(LCC) $(CFLAGS) $(OPT) -c -o $@ $<

$(ROM): $(OBJS)
	$(LCC) $(CFLAGS) $(CART) -o $@ $(OBJS)
	@ls -l $@

check: $(ROM)
	$(RGBFIX) -v $(ROM) -o $(BUILD)/HALFTONE.fixed.gb
	cmp $(ROM) $(BUILD)/HALFTONE.fixed.gb && echo "header checksums valid (rgbfix -v changed nothing)"
	$(GBDK)/bin/romusage $(BUILD)/HALFTONE.map -g || $(GBDK)/bin/romusage $(BUILD)/HALFTONE.noi -g

clean:
	rm -rf $(BUILD) $(GEN)

.PHONY: all check clean
