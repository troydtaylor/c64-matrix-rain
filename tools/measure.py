"""Count how many rows the rain actually advances per frame, old build vs new."""
import sys, random
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory
import fakerom

MAINLOOP = 0x0834
CHARROM = fakerom.build()


def measure(path, row_addr, speed_addr, frames=600, seed=1234):
    random.seed(seed)
    prg = open(path, 'rb').read()
    load = prg[0] | (prg[1] << 8)
    mem = ObservableMemory(); mpu = MPU(memory=mem)
    for i, b in enumerate(prg[2:]):
        mem[load+i] = b
    for i, b in enumerate(open('kstub.bin', 'rb').read()):
        mem[0xE544+i] = b
    mem[0x01] = 0x37

    def io(a):
        if (mem[0x01] & 0x04) == 0:
            return CHARROM[a - 0xD000]
        if a == 0xD012: return 0xFA
        if a == 0xD41B: return random.randint(0, 255)
        if a == 0xDC01: return 0xFF
        return None
    mem.subscribe_to_read(range(0xD000, 0xE000), io)
    mpu.pc = 0x080D
    while mpu.pc != MAINLOOP:
        mpu.step()

    steps = 0
    prev = [mem[row_addr+c] for c in range(40)]
    for _ in range(frames):
        mpu.step()
        while mpu.pc != MAINLOOP:
            mpu.step()
        cur = [mem[row_addr+c] for c in range(40)]
        steps += sum(1 for a, b in zip(prev, cur) if a != b)
        prev = cur
    speeds = [mem[speed_addr+c] for c in range(40)]
    return steps/frames, speeds


a, sa = measure(sys.argv[1], int(sys.argv[3], 16), int(sys.argv[4], 16))
b, sb = measure(sys.argv[2], int(sys.argv[5], 16), int(sys.argv[6], 16))
print("%-18s %.3f rows advanced per frame   speeds %s"
      % (sys.argv[1], a, sorted(set(sa))))
print("%-18s %.3f rows advanced per frame   speeds %s"
      % (sys.argv[2], b, sorted(set(sb))))
print("new speed is %.1f%% of the old  ->  %.1f%% slower" % (100*b/a, 100*(1-b/a)))
