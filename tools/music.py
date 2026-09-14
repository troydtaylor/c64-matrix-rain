"""Compose the tune and emit it as ACME data.

Original piece: a slow minor loop - D natural minor, 8 bars, 125 BPM.
Three voices: triangle bass, pulse arpeggio, noise percussion.  The noise
voice never changes frequency (it stays at $FFFF) because the rain program
reads that same oscillator as its random number generator - the drums are
made purely with the envelope gate.
"""
PAL = 985248.4
STEP_FRAMES = 6                 # frames per 16th note -> 125 BPM at 50 Hz
SEQLEN = 128                    # 8 bars of 16

HOLD, OFF = 0, 1
HAT, SNARE = 2, 3

NOTES = "C C# D D# E F F# G G# A A# B".split()
FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}


def idx(name):
    """'D3' -> sequence byte.  Index 2 = C1, so C1..B5 fit in 2..61."""
    for n in range(len(name)):
        if name[n].isdigit():
            pitch, octave = name[:n], int(name[n:])
            break
    pitch = FLATS.get(pitch, pitch)
    return 2 + (octave - 1) * 12 + NOTES.index(pitch)


def hz(i):
    return 32.703195 * 2 ** ((i - 2) / 12.0)


def sidfreq(i):
    return min(0xFFFF, int(round(hz(i) * 16777216.0 / PAL)))


# --- the arrangement -------------------------------------------------------
CHORDS = ['Dm', 'Dm', 'Bb', 'C', 'Dm', 'Dm', 'Gm', 'Am']

ARP = {
    'Dm': ['D3', 'A3', 'F3', 'A3', 'D4', 'A3', 'F3', 'A3'],
    'Bb': ['Bb2', 'F3', 'D3', 'F3', 'Bb3', 'F3', 'D3', 'F3'],
    'C':  ['C3', 'G3', 'E3', 'G3', 'C4', 'G3', 'E3', 'G3'],
    'Gm': ['G2', 'D3', 'Bb2', 'D3', 'G3', 'D3', 'Bb2', 'D3'],
    'Am': ['A2', 'E3', 'C3', 'E3', 'A3', 'E3', 'C3', 'E3'],
}
ROOT = {'Dm': 'D2', 'Bb': 'Bb1', 'C': 'C2', 'Gm': 'G1', 'Am': 'A1'}
FIFTH = {'Dm': 'A2', 'Bb': 'F2', 'C': 'G2', 'Gm': 'D2', 'Am': 'E2'}


def sequences():
    s1, s2, s3 = [], [], []
    for bar, ch in enumerate(CHORDS):
        for st in range(16):
            # bass: root, root, fifth, then let it breathe
            if st == 0 or st == 6:
                s1.append(idx(ROOT[ch]))
            elif st == 10:
                s1.append(idx(FIFTH[ch]))
            elif st == 14:
                s1.append(OFF)
            else:
                s1.append(HOLD)
            # arpeggio: straight 16ths through the chord
            s2.append(idx(ARP[ch][st % 8]))
            # percussion: backbeat, with a fill at the end of the loop
            if st in (4, 12):
                s3.append(SNARE)
            elif st in (0, 2, 6, 8, 10, 14):
                s3.append(HAT)
            elif bar == 7 and st in (13, 15):
                s3.append(SNARE)
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

    def rows(name, data, per=16, comment=None):
        out = ["%s:" % name]
        if comment:
            out.insert(0, comment)
        for i in range(0, len(data), per):
            out.append("        !byte " +
                       ",".join("$%02x" % b for b in data[i:i+per]))
        return "\n".join(out)

    txt = []
    txt.append("; note frequencies, PAL.  index 2 = C1, 14 = C2, 26 = C3 ...")
    txt.append(rows("freqlo", lo))
    txt.append(rows("freqhi", hi))
    txt.append("")
    txt.append("; $00 = hold, $01 = note off, $02+ = note index")
    txt.append("; (voice 3: $02 = hat, $03 = snare - it never changes pitch)")
    txt.append(rows("seq1", s1, 16, "; bass"))
    txt.append(rows("seq2", s2, 16, "; arpeggio"))
    txt.append(rows("seq3", s3, 16, "; percussion"))
    return "\n".join(txt) + "\n"


if __name__ == "__main__":
    open("musicdata.inc", "w").write(emit())
    s1, s2, s3 = sequences()
    print("%d steps, %.2f s per loop, %d bytes of sequence + 124 of note table"
          % (SEQLEN, SEQLEN * STEP_FRAMES / 50.0, 3 * SEQLEN))
    print("bass notes:", sorted({n for n in s1 if n > 1}))
    print("arp range :", min(n for n in s2 if n > 1), "-",
          max(n for n in s2 if n > 1))
