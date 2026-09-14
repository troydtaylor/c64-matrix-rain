"""Compose the tune and emit it as ACME data.

Original piece, written for this program.  The brief was "cinematic" rather
than "chiptune", so it leans on the things that actually carry that feel:

  * a slow tempo - 94 BPM, one step every 8 frames
  * a descending lament bass, D - C - Bb - A, the oldest dramatic device
    there is, with the A taken as a major dominant for the bite of the C#
  * sustained, slow-attack timbres instead of plucky ones
  * a half-time kick and snare rather than a busy kit
  * a driving off-beat ostinato underneath a slow upper line

Voice budget, and why the parts sit where they do:

    voice 1   bass, sustained, never interrupted - the floor of the piece
    voice 2   the ostinato, plus the kick, which takes the two steps where
              the ostinato rests anyway
    voice 3   the upper line, slow attack with vibrato, plus the snare on the
              backbeat; the line re-swells after every snare, which is the
              pulsing-strings effect and is deliberate

That is three voices doing the work of five parts, which is the whole craft
of SID composition.
"""
PAL = 985248.4
STEP_FRAMES = 8                 # 8 frames a step -> 94 BPM in 16ths
BARS = 16
SEQLEN = BARS * 16              # 256 steps

HOLD, OFF = 0, 1
HAT, SNARE, KICK = 2, 3, 4      # drum codes; every pitched note is >= 8

NOTES = "C C# D D# E F F# G G# A A# B".split()
FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}


def idx(name):
    """'D3' -> sequence byte.  Index 2 = C1, so C1..B5 fit in 2..61."""
    for n in range(len(name)):
        if name[n].isdigit():
            pitch, octave = name[:n], int(name[n:])
            break
    return 2 + (octave - 1) * 12 + NOTES.index(FLATS.get(pitch, pitch))


def sidfreq(i):
    hz = 32.703195 * 2 ** ((i - 2) / 12.0)
    return min(0xFFFF, int(round(hz * 16777216.0 / PAL)))


# --- the arrangement -------------------------------------------------------
# A: the lament, twice.  B: the same descent started a fourth higher.
SECTION_A = ['Dm', 'C', 'Bb', 'A', 'Dm', 'C', 'Bb', 'A']
SECTION_B = ['Gm', 'Dm', 'Bb', 'A', 'Gm', 'Dm', 'Bb', 'A']
CHORDS = SECTION_A + SECTION_B

ROOT = {'Dm': 'D2', 'C': 'C2', 'Bb': 'Bb1', 'A': 'A1', 'Gm': 'G1'}
FIFTH = {'Dm': 'A2', 'C': 'G2', 'Bb': 'F2', 'A': 'E2', 'Gm': 'D2'}

# six off-beat notes a bar, outlining the chord
OSTINATO = {
    'Dm': ['A3', 'D4', 'F4', 'D4', 'A3', 'D4'],
    'C':  ['G3', 'C4', 'E4', 'C4', 'G3', 'C4'],
    'Bb': ['F3', 'Bb3', 'D4', 'Bb3', 'F3', 'Bb3'],
    'A':  ['E3', 'A3', 'C#4', 'A3', 'E3', 'A3'],   # major dominant
    'Gm': ['D3', 'G3', 'Bb3', 'G3', 'D3', 'G3'],
}
OSTINATO_STEPS = (2, 4, 6, 10, 12, 14)

# the upper line: two long notes a bar, descending through section A and
# answered higher in section B
UPPER = [
    ['A4', 'F4'], ['G4', 'E4'], ['F4', 'D4'], ['E4', 'C#4'],
    ['D5', 'A4'], ['C5', 'G4'], ['Bb4', 'F4'], ['A4', 'E4'],
    ['D5', 'Bb4'], ['A4', 'D5'], ['F5', 'D5'], ['E5', 'C#5'],
    ['D5', 'G4'], ['F4', 'A4'], ['D5', 'F5'], ['E5', 'A4'],
]


def sequences():
    s1, s2, s3 = [], [], []
    for bar, ch in enumerate(CHORDS):
        for st in range(16):
            # --- voice 1: bass, one long note, a fifth halfway through ---
            if st == 0:
                s1.append(idx(ROOT[ch]))
            elif st == 8:
                s1.append(idx(FIFTH[ch]))
            else:
                s1.append(HOLD)

            # --- voice 2: kick on the beat, ostinato off it ---
            if st in (0, 8):
                s2.append(KICK)
            elif st in OSTINATO_STEPS:
                s2.append(idx(OSTINATO[ch][OSTINATO_STEPS.index(st)]))
            else:
                s2.append(HOLD)

            # --- voice 3: upper line, snare on the backbeat ---
            if st in (4, 12):
                s3.append(SNARE)
            elif st == 0:
                s3.append(idx(UPPER[bar][0]))
            elif st == 8:
                s3.append(idx(UPPER[bar][1]))
            else:
                s3.append(HOLD)
    assert len(s1) == len(s2) == len(s3) == SEQLEN
    return s1, s2, s3


def emit():
    lo, hi = [], []
    for i in range(62):
        f = sidfreq(i) if i >= 2 else 0
        lo.append(f & 0xFF)
        hi.append(f >> 8)
    s1, s2, s3 = sequences()

    def rows(name, data, comment=None, per=16):
        out = ([comment] if comment else []) + ["%s:" % name]
        for i in range(0, len(data), per):
            out.append("        !byte " +
                       ",".join("$%02x" % b for b in data[i:i+per]))
        return "\n".join(out)

    txt = ["; note frequencies, PAL.  index 2 = C1, 14 = C2, 26 = C3 ...",
           rows("freqlo", lo), rows("freqhi", hi), "",
           "; $00 = hold, $01 = off, $03 = snare, $04 = kick,",
           "; $08 and above = note index",
           rows("seq1", s1, "; bass"),
           rows("seq2", s2, "; ostinato and kick"),
           rows("seq3", s3, "; upper line and snare")]
    return "\n".join(txt) + "\n"


if __name__ == "__main__":
    open("musicdata.inc", "w").write(emit())
    s1, s2, s3 = sequences()
    print("%d steps at %d frames = %.1f s per loop, %.0f BPM"
          % (SEQLEN, STEP_FRAMES, SEQLEN * STEP_FRAMES / 50.0,
             60.0 / (STEP_FRAMES / 50.0 * 4)))
    print("bass notes %d   ostinato %d   kicks %d   upper line %d   snares %d"
          % (sum(1 for n in s1 if n >= 8), sum(1 for n in s2 if n >= 8),
             s2.count(KICK), sum(1 for n in s3 if n >= 8), s3.count(SNARE)))
