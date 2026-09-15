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

.PHONY: all disk verify checktune font music sid audio video clean
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

# Read back every note the player writes to the SID, which is ground truth
# for the arrangement in a way that analysing the rendered audio is not.
checktune: $(BUILD)/tune.bin
	$(PYTHON) tools/sidtrace.py $(BUILD)/tune.bin

$(BUILD)/tune.bin: src/psid.asm src/music.inc src/musicdata.inc | $(BUILD)
	$(ACME) -I src -f cbm -o $@ src/psid.asm

# Regenerate the glyph set and the tune from their generators.
font:
	cd src && $(PYTHON) ../tools/mkfont.py
	mv src/fontsheet.png docs/fontsheet.png

music:
	cd src && $(PYTHON) ../tools/music.py

# The tune on its own, as a .sid, plus an mp3 rendered from it.
sid: $(DIST)/tune.sid
$(DIST)/tune.sid: $(BUILD)/tune.bin tools/mksid.py | $(DIST)
	$(PYTHON) tools/mksid.py $(BUILD)/tune.bin $@

$(BUILD)/tune.wav: $(DIST)/tune.sid
	sidplayfp -w$@ -t68 $(DIST)/tune.sid

audio: $(BUILD)/tune.wav
	ffmpeg -y -loglevel error -i $(BUILD)/tune.wav -ss 2.0 -t 62 \
	    -af "afade=t=out:st=60:d=2" -codec:a libmp3lame -b:a 160k \
	    $(DIST)/matrix-tune.mp3

# The screen saver running, with its music: the program in the simulator,
# frame by frame, with the reSID render of the tune.  Plus a short silent
# GIF for the README, which cannot embed video.
video: $(BUILD)/matrix.prg $(BUILD)/kstub.bin $(BUILD)/tune.wav
	$(PYTHON) tools/mkvideo.py $(BUILD)/matrix.prg $(BUILD)/tune.wav \
	    $(DIST)/matrix.mp4 62
	ffmpeg -y -loglevel error -i $(DIST)/matrix.mp4 -t 8 -vf \
	    "fps=25,scale=576:-1:flags=neighbor,split[a][b];[a]palettegen=max_colors=16[p];[b][p]paletteuse=dither=none" \
	    docs/preview.gif

clean:
	rm -rf $(BUILD)
