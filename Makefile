ACME   ?= acme
PYTHON ?= python3

SRC      := src/matrix.asm
DEPS     := $(SRC) src/fontdata.inc src/music.inc src/musicdata.inc
BUILD    := build
DIST     := dist

VARIANTS := matrix matrix-silent matrix-amber matrix-ice matrix-rom
PRGS     := $(addprefix $(BUILD)/,$(addsuffix .prg,$(VARIANTS)))

FLAGS_matrix        :=
FLAGS_matrix-silent := -DMUSIC=0
FLAGS_matrix-amber  := -DPALETTE=1
FLAGS_matrix-ice    := -DPALETTE=2
FLAGS_matrix-rom    := -DFONT=0

.PHONY: all disk verify font music sid audio clean
all: disk
disk: $(DIST)/matrix.d64

$(BUILD) $(DIST):
	mkdir -p $@

# One .prg per build option combination.  -I src lets !source find the
# includes no matter which directory make was started from.
$(BUILD)/%.prg: $(DEPS) | $(BUILD)
	$(ACME) -I src $(FLAGS_$*) -f cbm -l $(BUILD)/$*.sym -o $@ $(SRC)

$(BUILD)/kstub.bin: tools/kstub.asm | $(BUILD)
	$(ACME) -o $@ tools/kstub.asm

$(DIST)/matrix.d64: $(PRGS) tools/mkd64.py | $(DIST)
	$(PYTHON) tools/mkd64.py $@ \
	    $(foreach v,$(VARIANTS),$(v) $(BUILD)/$(v).prg)

# Run every build through a 6502 simulator and check the rain's invariants:
# no holes in a trail, exactly one white head per column, brightness never
# increasing as you go up a trail, and the per-frame cycle budget.
verify: $(PRGS) $(BUILD)/kstub.bin
	@for v in $(VARIANTS); do \
	    printf '%-16s ' $$v; \
	    $(PYTHON) tools/sim.py $(BUILD)/$$v.prg 300 $(BUILD)/$$v-preview.png \
	        | grep -E 'invariant|CPU load' | tr '\n' ' '; echo; \
	done

# Regenerate the glyph set and the tune from their generators.
font:
	cd src && $(PYTHON) ../tools/mkfont.py
	mv src/fontsheet.png docs/fontsheet.png

music:
	cd src && $(PYTHON) ../tools/music.py

# The tune on its own, as a .sid, plus an mp3 rendered from it.
sid: $(DIST)/tune.sid
$(DIST)/tune.sid: src/psid.asm src/music.inc src/musicdata.inc | $(DIST)
	$(ACME) -I src -o $(BUILD)/tune.bin src/psid.asm
	$(PYTHON) tools/mksid.py $(BUILD)/tune.bin $@

audio: $(DIST)/tune.sid
	sidplayfp -w$(BUILD)/tune.wav -t35 $(DIST)/tune.sid
	ffmpeg -y -loglevel error -i $(BUILD)/tune.wav -ss 1.99 -t 31 \
	    -af "afade=t=out:st=29:d=2" -codec:a libmp3lame -b:a 160k \
	    $(DIST)/matrix-tune.mp3

clean:
	rm -rf $(BUILD)
