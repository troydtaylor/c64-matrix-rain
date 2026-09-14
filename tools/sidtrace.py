"""Run the music player in a 6502 simulator and read back every note it plays.

Analysing the rendered audio is unreliable for this: the arpeggio's harmonics
land in the same band as the lead and will fool a spectrum peak.  Reading the
frequencies the player actually writes to the SID is ground truth.

    python3 tools/sidtrace.py build/tune.bin [steps]
"""
import math
import sys

from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

PAL = 985248.4
STEP_FRAMES = 6
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
WAVE = {0x10: "tri", 0x20: "saw", 0x40: "pulse", 0x80: "noise"}


def note(freq):
    if freq == 0:
        return "-"
    hz = freq * PAL / 16777216.0
    n = round(12 * math.log2(hz / 440.0)) + 69
    return "%s%d" % (NAMES[n % 12], n // 12 - 1)


def trace(path, steps=256):
    data = open(path, 'rb').read()
    load = data[0] | (data[1] << 8)
    mem = ObservableMemory()
    mpu = MPU(memory=mem)
    for i, b in enumerate(data[2:]):
        mem[load + i] = b

    frame = [0]
    log = []
    mem.subscribe_to_write(range(0xD400, 0xD419),
                           lambda a, v: log.append((frame[0], a, v)))

    def call(addr):
        mpu.pc, mpu.sp = addr, 0xFD
        mem[0x01FE] = mem[0x01FF] = 0xFF        # an RTS lands on $0000
        for _ in range(100000):
            mpu.step()
            if mpu.pc == 0x0000:
                return
        raise SystemExit("player did not return")

    call(load)                                   # init
    log.clear()
    for f in range(steps * STEP_FRAMES):
        frame[0] = f
        call(load + 3)                           # play

    byframe = {}
    for f, a, v in log:
        byframe.setdefault(f, []).append((a, v))

    events = []                                  # (step, voice, wave, freq)
    for f in sorted(byframe):
        regs = dict(byframe[f])
        for voice, (ctrl, flo, fhi) in enumerate(
                ((0xD404, 0xD400, 0xD401),
                 (0xD40B, 0xD407, 0xD408),
                 (0xD412, 0xD40E, 0xD40F))):
            gates = [v for a, v in byframe[f] if a == ctrl and v & 1]
            if gates:
                events.append((f // STEP_FRAMES, voice + 1, gates[0] & 0xF0,
                               regs.get(flo, 0) | (regs.get(fhi, 0) << 8)))
    return events


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "build/tune.bin"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    ev = trace(path, steps)
    for v in (1, 2, 3):
        rows = [e for e in ev if e[1] == v]
        kinds = {}
        for _, _, w, _ in rows:
            kinds[WAVE.get(w, hex(w))] = kinds.get(WAVE.get(w, hex(w)), 0) + 1
        print("voice %d: %3d events  %s" % (v, len(rows), kinds))
    print("\nvoice 3, first 24 events (step / waveform / note):")
    for step, v, w, fr in [e for e in ev if e[1] == 3][:24]:
        print("  step %3d  bar %2d.%02d  %-5s %s"
              % (step, step // 16 + 1, step % 16, WAVE.get(w, hex(w)), note(fr)))
