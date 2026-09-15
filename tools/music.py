"""Compose the tune and emit it as ACME data.

Original piece, written for this program: big beat.  The idiom is the point -
fast breakbeat drums, a funk bass with octave pops, short stabs that sound
sampled, and a breakdown that drops the kit and builds it back.

    voice 1   the bass - square wave, E minor pentatonic, octave pops, with
              explicit note-offs so it is rhythmic rather than a drone
    voice 2   the stabs - narrow pulse, quick decay.  Stabs flagged with bit 7
              are SID chords: the player arpeggiates a minor triad through
              the note at one step per frame, which is how a single voice
              on this chip has always faked a chord.  In the breakdown the
              same voice holds long notes instead.
    voice 3   the kit - kick (triangle pitch-swept), snare and hat (noise),
              one hit per step, laid out as a breakbeat

Structure, 16 bars at 125 BPM, looping every 30.7 s:

    bars  1-4   drums and bass, the groove on its own
    bars  5-8   stabs come in
    bars  9-12  breakdown: kit drops to hats, then nothing, stabs hold long
                notes that climb, and a snare roll pulls it back
    bars 13-16  everything, with a fill at the end
"""
PAL = 985248.4
STEP_FRAMES = 6                 # 6 frames a step -> 125 BPM in 16ths
BARS = 16
SEQLEN = BARS * 16              # 256 steps
NTABLE = 72                     # note table entries (room for the arp above)

HOLD, OFF = 0, 1
HAT, SNARE, KICK = 2, 3, 4      # drum codes; every pitched note is >= 8
ARP = 0x80                      # voice 2: bit 7 = arpeggiate a minor triad

NOTES = "C C# D D# E F F# G G# A A# B".split()
FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}


def idx(name):
    """'E2' -> sequence byte.  Index 8 = C1, so no pitched note can ever
    collide with a drum code (those are all < 8)."""
    for n in range(len(name)):
        if name[n].isdigit():
            pitch, octave = name[:n], int(name[n:])
            break
    return 8 + (octave - 1) * 12 + NOTES.index(FLATS.get(pitch, pitch))


def sidfreq(i):
    hz = 32.703195 * 2 ** ((i - 8) / 12.0)
    return min(0xFFFF, int(round(hz * 16777216.0 / PAL)))


# --- the parts -------------------------------------------------------------
# bass: a two-bar riff, E minor pentatonic, with the octave pop on step 4
BASS = [
    {0: 'E2', 2: OFF, 3: 'E2', 4: 'E3', 5: OFF, 6: 'G2', 7: OFF, 8: 'E2',
     9: OFF, 10: 'A2', 11: 'A2', 12: 'G2', 13: OFF, 14: 'E2', 15: OFF},
    {0: 'E2', 2: OFF, 3: 'E2', 4: 'E3', 5: OFF, 6: 'G2', 7: OFF, 8: 'D2',
     9: OFF, 10: 'D2', 11: 'E2', 12: 'G2', 13: OFF, 14: 'B1', 15: OFF},
]

# stabs: a two-bar phrase.  A tuple marks a chord (minor triad on that root);
# minor triads on E, A and B all sit inside E natural minor.
STABS = [
    {0: ('E4',), 1: OFF, 3: ('E4',), 4: OFF, 6: 'G4', 7: OFF, 8: ('A4',),
     9: OFF, 10: 'G4', 11: OFF, 12: ('E4',), 13: OFF},
    {0: ('B4',), 1: OFF, 2: ('B4',), 3: OFF, 6: 'D5', 7: OFF, 8: ('A4',),
     9: OFF, 10: 'G4', 11: OFF, 12: ('E4',), 14: OFF},
]
# breakdown: one long chord a bar, climbing
BREAKDOWN = [('E4',), ('G4',), ('A4',), ('B4',)]

# the kit: a breakbeat, one hit per step
BEAT = {0: KICK, 2: HAT, 4: SNARE, 6: HAT, 7: KICK, 8: HAT, 10: KICK,
        11: HAT, 12: SNARE, 14: HAT, 15: KICK}
FILL = {**BEAT, 12: SNARE, 13: SNARE, 14: SNARE, 15: SNARE}
HATS_ONLY = {st: HAT for st in range(0, 16, 2)}
ROLL = {st: SNARE for st in range(8, 16)}       # eight snares into the drop


def code(x):
    """Map a part entry to a sequence byte."""
    if x == OFF or x == HOLD:
        return x
    if isinstance(x, tuple):
        return ARP | idx(x[0])
    return idx(x)


def sequences():
    s1, s2, s3 = [], [], []
    for bar in range(BARS):
        bass = BASS[bar % 2]
        if bar < 4:
            stabs, kit = {}, BEAT
        elif bar < 8:
            stabs, kit = STABS[bar % 2], (FILL if bar == 7 else BEAT)
        elif bar < 12:
            stabs = {0: BREAKDOWN[bar - 8]}
            kit = {8: HATS_ONLY, 9: HATS_ONLY, 10: {}, 11: ROLL}[bar]
        else:
            stabs, kit = STABS[bar % 2], (FILL if bar == 15 else BEAT)
        for st in range(16):
            s1.append(code(bass.get(st, HOLD)))
            s2.append(code(stabs.get(st, HOLD)))
            s3.append(kit.get(st, HOLD))
    assert len(s1) == len(s2) == len(s3) == SEQLEN
    return s1, s2, s3


def emit():
    lo, hi = [], []
    for i in range(NTABLE):
        f = sidfreq(i) if i >= 8 else 0
        lo.append(f & 0xFF)
        hi.append(f >> 8)
    s1, s2, s3 = sequences()

    def rows(name, data, comment=None, per=16):
        out = ([comment] if comment else []) + ["%s:" % name]
        for i in range(0, len(data), per):
            out.append("        !byte " +
                       ",".join("$%02x" % b for b in data[i:i+per]))
        return "\n".join(out)

    txt = ["; note frequencies, PAL.  index 8 = C1, 20 = C2, 32 = C3 ...",
           rows("freqlo", lo), rows("freqhi", hi), "",
           "; $00 = hold, $01 = off, $02 = hat, $03 = snare, $04 = kick,",
           "; $08 and above = note index; on voice 2 bit 7 = chord arpeggio",
           rows("seq1", s1, "; bass"),
           rows("seq2", s2, "; stabs"),
           rows("seq3", s3, "; kit")]
    return "\n".join(txt) + "\n"


if __name__ == "__main__":
    open("musicdata.inc", "w").write(emit())
    s1, s2, s3 = sequences()
    print("%d steps at %d frames = %.1f s per loop, %.0f BPM"
          % (SEQLEN, STEP_FRAMES, SEQLEN * STEP_FRAMES / 50.0,
             60.0 / (STEP_FRAMES / 50.0 * 4)))
    print("bass %d   stabs %d (of which chords %d)   kick %d  snare %d  hat %d"
          % (sum(1 for n in s1 if n >= 8), sum(1 for n in s2 if n >= 8),
             sum(1 for n in s2 if n & ARP), s3.count(KICK), s3.count(SNARE),
             s3.count(HAT)))
