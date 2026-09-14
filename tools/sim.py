import os, re, sys, random
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fakerom

PRG = open(sys.argv[1] if len(sys.argv) > 1 else 'matrix2.prg', 'rb').read()
load = PRG[0] | (PRG[1] << 8)
FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 400

mem = ObservableMemory()
mpu = MPU(memory=mem)
for i, b in enumerate(PRG[2:]):
    mem[load+i] = b

# KERNAL clear-screen stand-in, assembled separately.  Look for it beside the
# .prg first (that is where make puts it), then beside this script.
HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), 'kstub.bin'),
             os.path.join(HERE, 'kstub.bin'), 'kstub.bin'):
    if os.path.exists(cand):
        break
stub = open(cand, 'rb').read()
for i, b in enumerate(stub):
    mem[0xE544+i] = b

CHARROM = fakerom.build()
mem[0x01] = 0x37
keys = {'v': 0xFF}
rom_reads = {'n': 0}


def io_read(addr):
    if (mem[0x01] & 0x04) == 0:            # character ROM banked in
        rom_reads['n'] += 1
        return CHARROM[addr - 0xD000]
    if addr == 0xD012:
        return 0xFA
    if addr == 0xD41B:
        return random.randint(0, 255)
    if addr == 0xDC01:
        return keys['v']
    return None                            # plain RAM (colour RAM lives here)


mem.subscribe_to_read(range(0xD000, 0xE000), io_read)

# mainloop moves when build options change, so read it from the symbol file
# that sits next to the .prg unless an address was given explicitly.
def find_mainloop():
    if len(sys.argv) > 4:
        return int(sys.argv[4], 16)
    sym = os.path.splitext(sys.argv[1])[0] + '.sym'
    m = re.search(r'^\s*mainloop\s*=\s*\$([0-9a-f]+)', open(sym).read(), re.M)
    if not m:
        raise SystemExit('no mainloop symbol in ' + sym)
    return int(m.group(1), 16)

MAINLOOP = find_mainloop()
mpu.pc = 0x080D


def run_to(addr, limit=2000000):
    n = 0
    while mpu.pc != addr:
        mpu.step(); n += 1
        if n > limit:
            raise SystemExit('runaway at $%04X' % mpu.pc)
    return n


boot_cycles = mpu.processorCycles
run_to(MAINLOOP)
print("boot (charset build) took %d cycles = %.2f PAL frames; %d ROM bytes read"
      % (mpu.processorCycles, mpu.processorCycles/19656.0, rom_reads['n']))

cyc = []
for _ in range(FRAMES):
    c0 = mpu.processorCycles
    mpu.step()
    run_to(MAINLOOP)
    cyc.append(mpu.processorCycles - c0)
print("cycles/frame  min %d  avg %d  max %d   (PAL frame = 19656)"
      % (min(cyc), sum(cyc)//len(cyc), max(cyc)))
print("CPU load      avg %.1f%%   worst %.1f%%"
      % (100*sum(cyc)/len(cyc)/19656, 100*max(cyc)/19656))

GLYPHS = 85
# ---- invariants ----------------------------------------------------------
LEVEL = {}                       # (colour, block) -> brightness step


def level(c, col):
    blk = c // GLYPHS
    if col == 0x00: return 9     # erased
    if col == 0x01: return 0     # white head
    if col in (0x0d, 0x07, 0x03): return 1
    return 2 + blk               # body colour, dimmed by dither block


bad = []
for c in range(40):
    cells = [(r, mem[0x0400+r*40+c], mem[0xD800+r*40+c] & 0x0f) for r in range(25)]
    lit = [(r, ch, co) for (r, ch, co) in cells if co != 0]
    if not lit:
        continue
    rows = [r for r, _, _ in lit]
    if rows != list(range(rows[0], rows[-1]+1)):
        bad.append(('gap', c, rows))
    if any(ch > 254 for _, ch, _ in lit):
        bad.append(('char>254', c))
    heads = [r for r, _, co in lit if co == 0x01]
    if len(heads) > 1:
        bad.append(('multi-head', c, heads))
    if heads and heads[0] != rows[-1]:
        bad.append(('head-not-lowest', c, heads, rows))
    levels = [level(ch, co) for _, ch, co in lit][::-1]   # head first, upward
    if any(b < a for a, b in zip(levels, levels[1:])):
        bad.append(('brightness-not-monotonic', c, levels))
print("invariant violations:", bad if bad else "none")

used = sorted({mem[0x0400+i] for i in range(1000) if mem[0xD800+i] & 0x0f})
print("distinct glyph codes on screen: %d  (range %d..%d)"
      % (len(used), min(used), max(used)))
blocks = [sum(1 for i in range(1000)
              if (mem[0xD800+i] & 0x0f) and mem[0x0400+i]//GLYPHS == b)
          for b in range(3)]
print("cells per dither block: full=%d  50%%=%d  25%%=%d" % tuple(blocks))
cols_used = sorted({mem[0xD800+i] & 0x0f for i in range(1000)})
print("colours in use:", ['$%02x' % v for v in cols_used])

# ---- render --------------------------------------------------------------
from PIL import Image
PAL = [(0,0,0),(255,255,255),(104,55,43),(112,164,178),(111,61,134),(88,141,67),
       (53,40,121),(184,199,111),(111,79,37),(67,57,0),(154,103,89),(68,68,68),
       (108,108,108),(154,210,132),(108,94,181),(149,149,149)]
SCALE = 3
img = Image.new("RGB", (40*8*SCALE + 32*SCALE, 25*8*SCALE + 20*SCALE), PAL[0])
px = img.load()
ox = oy = 16*SCALE
for r in range(25):
    for c in range(40):
        ch = mem[0x0400+r*40+c]
        col = PAL[mem[0xD800+r*40+c] & 0x0f]
        base = 0x3000 + ch*8
        for y in range(8):
            bits = mem[base+y]
            for x in range(8):
                if bits & (0x80 >> x):
                    X = ox + (c*8+x)*SCALE
                    Y = oy + (r*8+y)*SCALE
                    for dy in range(SCALE):
                        for dx in range(SCALE):
                            px[X+dx, Y+dy] = col
img.save(sys.argv[3] if len(sys.argv) > 3 else 'preview.png')
print("preview written")
