"""Record the screen saver running, with its music, as an MP4.

The program runs in the same 6502 simulator make verify uses, writing to real
screen and colour RAM; each frame is rendered through the character set the
program itself built at boot, in the Pepto PAL palette.  The audio is the SID
player rendered through reSID.  Both advance one step per frame from the same
counter, so sound and picture are locked by construction.

    python3 tools/mkvideo.py build/matrix.prg build/tune.wav dist/matrix.mp4 [seconds]
"""
import os
import re
import subprocess
import sys

import numpy as np
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakerom

PAL = [(0, 0, 0), (255, 255, 255), (104, 55, 43), (112, 164, 178),
       (111, 61, 134), (88, 141, 67), (53, 40, 121), (184, 199, 111),
       (111, 79, 37), (67, 57, 0), (154, 103, 89), (68, 68, 68),
       (108, 108, 108), (154, 210, 132), (108, 94, 181), (149, 149, 149)]
FPS = 50                       # PAL
LEAD_IN = 2.0                  # silence sidplayfp writes before the tune
BORDER_X, BORDER_Y = 32, 36    # the visible PAL border around the 320x200


def boot(prg_path):
    prg = open(prg_path, 'rb').read()
    load = prg[0] | (prg[1] << 8)
    mem = ObservableMemory()
    mpu = MPU(memory=mem)
    for i, b in enumerate(prg[2:]):
        mem[load + i] = b
    stub = open(os.path.join(os.path.dirname(prg_path), 'kstub.bin'), 'rb').read()
    for i, b in enumerate(stub):
        mem[0xE544 + i] = b
    rom = fakerom.build()
    mem[0x01] = 0x37

    def io_read(addr):
        if (mem[0x01] & 0x04) == 0:
            return rom[addr - 0xD000]
        if addr == 0xD012:
            return 0xFA
        if addr == 0xDC01:
            return 0xFF
        return None
    mem.subscribe_to_read(range(0xD000, 0xE000), io_read)

    sym = os.path.splitext(prg_path)[0] + '.sym'
    mainloop = int(re.search(r'^\s*mainloop\s*=\s*\$([0-9a-f]+)',
                             open(sym).read(), re.M).group(1), 16)
    mpu.pc = 0x080D
    return mpu, mem, mainloop


def run_to(mpu, addr):
    for _ in range(2000000):
        mpu.step()
        if mpu.pc == addr:
            return
    raise SystemExit('runaway')


def render(mem, glyphs, pal):
    ram = mem._subject
    screen = np.array(ram[0x0400:0x07E8], dtype=np.uint8).reshape(25, 40)
    colour = (np.array(ram[0xD800:0xDBE8], dtype=np.uint8) & 0x0F).reshape(25, 40)
    bits = glyphs[screen]                                   # 25,40,8,8
    bits = bits.transpose(0, 2, 1, 3).reshape(200, 320)     # rows of pixels
    rgb = pal[colour]                                       # 25,40,3
    rgb = np.repeat(np.repeat(rgb, 8, axis=0), 8, axis=1)   # 200,320,3
    frame = np.where(bits[..., None], rgb, 0).astype(np.uint8)
    out = np.zeros((200 + 2 * BORDER_Y, 320 + 2 * BORDER_X, 3), np.uint8)
    out[BORDER_Y:BORDER_Y + 200, BORDER_X:BORDER_X + 320] = frame
    return out


def main(prg, wav, mp4, seconds):
    mpu, mem, mainloop = boot(prg)
    run_to(mpu, mainloop)                       # boot: charset, PRNG, music init

    # the character set the program built, as 256 8x8 bitmaps
    cs = np.array(mem._subject[0x3000:0x3800], dtype=np.uint8).reshape(256, 8)
    glyphs = ((cs[:, :, None] >> np.arange(7, -1, -1)) & 1).astype(bool)
    pal = np.array(PAL, dtype=np.uint8)

    h, w = 200 + 2 * BORDER_Y, 320 + 2 * BORDER_X
    ff = subprocess.Popen([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (w, h),
        '-r', str(FPS), '-i', 'pipe:0',
        '-ss', str(LEAD_IN), '-i', wav,
        '-t', str(seconds),
        '-vf', 'scale=%d:%d:flags=neighbor' % (w * 3, h * 3),
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-shortest', mp4], stdin=subprocess.PIPE)

    frames = int(seconds * FPS)
    for f in range(frames):
        ff.stdin.write(render(mem, glyphs, pal).tobytes())
        mpu.step()                              # leave mainloop ...
        run_to(mpu, mainloop)                   # ... one full frame
        if f % 250 == 0:
            print("  %d / %d frames" % (f, frames), flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote %s: %d frames at %d fps with audio" % (mp4, frames, FPS))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3],
         float(sys.argv[4]) if len(sys.argv) > 4 else 62.0)
