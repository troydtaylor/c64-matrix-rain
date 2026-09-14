"""Compose the tune and emit it as ACME data.

Original piece: D natural minor, 125 BPM, 16 bars in two sections, looping
every 30.7 seconds.

    voice 1   triangle bass
    voice 2   pulse arpeggio, pulse width sweeping
    voice 3   section A: drums.  section B: lead melody with vibrato, with
              the kick and snare punching through it.

Voice 3 used to be pinned to the noise waveform because the rain read its
oscillator for random numbers.  The rain now has its own PRNG, so this voice
can play pitched notes - which is what the whole B section is made of, and
what lets the kick be a real pitch-swept drum instead of a burst of noise.
"""
PAL = 985248.4
STEP_FRAMES = 6                 # frames per 16th -> 125 BPM at 50 Hz
BARS = 16
SEQLEN = BARS * 16              # 256 steps

HOLD, OFF = 0, 1
HAT, SNARE, KICK = 2, 3, 4      # voice 3 drum codes; lead notes are all >= 8

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
SECTION_A = ['Dm', 'Dm', 'Bb', 'C', 'Dm', 'Dm', 'Gm', 'Am']
SECTION_B = ['F', 'C', 'Dm', 'Bb', 'F', 'C', 'Gm', 'Am']
CHORDS = SECTION_A + SECTION_B

ROOT  = {'Dm': 'D2', 'Bb': 'Bb1', 'C': 'C2', 'Gm': 'G1', 'Am': 'A1', 'F': 'F1'}
FIFTH = {'Dm': 'A2', 'Bb': 'F2', 'C': 'G2', 'Gm': 'D2', 'Am': 'E2', 'F': 'C2'}

# section A: close arpeggio that sits under everything
ARP_A = {
    'Dm': ['D3', 'A3', 'F3', 'A3', 'D4', 'A3', 'F3', 'A3'],
    'Bb': ['Bb2', 'F3', 'D3', 'F3', 'Bb3', 'F3', 'D3', 'F3'],
    'C':  ['C3', 'G3', 'E3', 'G3', 'C4', 'G3', 'E3', 'G3'],
    'Gm': ['G2', 'D3', 'Bb2', 'D3', 'G3', 'D3', 'Bb2', 'D3'],
    'Am': ['A2', 'E3', 'C3', 'E3', 'A3', 'E3', 'C3', 'E3'],
    'F':  ['F2', 'C3', 'A2', 'C3', 'F3', 'C3', 'A2', 'C3'],
}
# section B: opens out into two octaves so the lead has something to ride on
ARP_B = {
    'Dm': ['D3', 'F3', 'A3', 'D4', 'F4', 'D4', 'A3', 'F3'],
    'Bb': ['Bb2', 'D3', 'F3', 'Bb3', 'D4', 'Bb3', 'F3', 'D3'],
    'C':  ['C3', 'E3', 'G3', 'C4', 'E4', 'C4', 'G3', 'E3'],
    'Gm': ['G2', 'Bb2', 'D3', 'G3', 'Bb3', 'G3', 'D3', 'Bb2'],
    'Am': ['A2', 'C3', 'E3', 'A3', 'C4', 'A3', 'E3', 'C3'],
    'F':  ['F2', 'A2', 'C3', 'F3', 'A3', 'F3', 'C3', 'A2'],
}
# the lead: four quarter notes a bar, on the chord tones
LEAD = [
    ['F4', 'A4', 'C5', 'A4'],     # F
    ['G4', 'E4', 'G4', 'C5'],     # C
    ['D5', 'C5', 'A4', 'F4'],     # Dm
    ['D5', 'Bb4', 'F4', 'D4'],    # Bb
    ['A4', 'C5', 'F5', 'C5'],     # F
    ['E5', 'C5', 'G4', 'E4'],     # C
    ['D5', 'Bb4', 'G4', 'D4'],    # Gm
    ['C5', 'A4', 'E4', 'A4'],     # Am
]


def sequences():
    s1, s2, s3 = [], [], []
    for bar, ch in enumerate(CHORDS):
        inB = bar >= 8
        for st in range(16):
            # --- bass ---
            if st == 0 or st == 6:
                s1.append(idx(ROOT[ch]))
            elif st == 10:
                s1.append(idx(FIFTH[ch]))
            elif inB and st == 12:
                s1.append(idx(ROOT[ch]) + 12)     # octave lift in section B
            elif st == 15:
                s1.append(OFF)
            else:
                s1.append(HOLD)

            # --- arpeggio ---
            s2.append(idx((ARP_B if inB else ARP_A)[ch][st % 8]))

            # --- voice 3 ---
            if not inB:
                # section A: a straight kit
                s3.append({0: KICK, 4: SNARE, 8: KICK, 12: SNARE,
                           2: HAT, 6: HAT, 10: HAT, 14: HAT}.get(st, HOLD))
            else:
                # section B: half-time drums, melody in the gaps
                if st == 0:
                    s3.append(KICK)
                elif st == 8:
                    s3.append(SNARE)
                elif st in (2, 6, 10, 14):
                    s3.append(idx(LEAD[bar - 8][{2: 0, 6: 1, 10: 2, 14: 3}[st]]))
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
           "; $00 = hold, $01 = off, $02+ = note index.  On voice 3, $02 is a",
           "; hat, $03 a snare and $04 a kick; every lead note is >= $08.",
           rows("seq1", s1, "; bass"),
           rows("seq2", s2, "; arpeggio"),
           rows("seq3", s3, "; drums (bars 1-8) and lead (bars 9-16)")]
    return "\n".join(txt) + "\n"


if __name__ == "__main__":
    open("musicdata.inc", "w").write(emit())
    s1, s2, s3 = sequences()
    print("%d steps, %.1f s per loop, %d bytes of sequence"
          % (SEQLEN, SEQLEN * STEP_FRAMES / 50.0, 3 * SEQLEN))
    print("lead notes: %d   drum hits: %d   arp notes: %d"
          % (sum(1 for n in s3 if n >= 8),
             sum(1 for n in s3 if n in (HAT, SNARE, KICK)),
             sum(1 for n in s2 if n > 1)))
