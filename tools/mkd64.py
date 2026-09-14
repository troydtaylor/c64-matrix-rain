"""Build a standard 35-track .d64 disk image containing one or more PRG files.

No external tools: writes the BAM, the directory sector and the linked data
blocks by hand, then reads the whole thing back to prove it round-trips.
"""
import sys

SPT = [0]*36                       # sectors per track, 1-based
for t in range(1, 36):
    SPT[t] = 21 if t <= 17 else 19 if t <= 24 else 18 if t <= 30 else 17
TOTAL = sum(SPT[1:])               # 683
IMAGE = TOTAL * 256                # 174848

def offset(t, s):
    return (sum(SPT[1:t]) + s) * 256

def petscii(name):
    return name.upper().encode('ascii')[:16].ljust(16, b'\xa0')


class D64:
    def __init__(self, title="MATRIX RAIN", disk_id="25"):
        self.img = bytearray(IMAGE)
        self.free = {t: list(range(SPT[t])) for t in range(1, 36)}
        self.free[18] = [s for s in range(SPT[18]) if s not in (0, 1)]
        self.entries = []
        self.title, self.disk_id = title, disk_id
        self.next = (17, 0)        # start files just outside the directory

    def alloc(self):
        t, s = self.next
        for _ in range(TOTAL):
            if s in self.free[t]:
                self.free[t].remove(s)
                # interleave 10, the classic 1541 file interleave
                ns = (s + 10) % SPT[t]
                self.next = (t, ns)
                return t, s
            s = (s + 1) % SPT[t]
            if s == 0:
                t = t + 1 if t != 17 else 19   # skip the directory track
                if t > 35:
                    t = 1
        raise RuntimeError("disk full")

    def add(self, name, data):
        chunks = [data[i:i+254] for i in range(0, len(data), 254)]
        blocks = [self.alloc() for _ in chunks]
        first = blocks[0]
        for i, (t, s) in enumerate(blocks):
            o = offset(t, s)
            if i + 1 < len(blocks):
                self.img[o], self.img[o+1] = blocks[i+1]
            else:
                self.img[o], self.img[o+1] = 0, len(chunks[i]) + 1
            self.img[o+2:o+2+len(chunks[i])] = chunks[i]
        self.entries.append((name, first, len(blocks)))

    def finish(self):
        b = offset(18, 0)
        self.img[b+0], self.img[b+1] = 18, 1          # first directory sector
        self.img[b+2], self.img[b+3] = 0x41, 0x00     # DOS version 'A'
        for t in range(1, 36):
            e = b + 4 + (t-1)*4
            bits = 0
            for s in self.free[t]:
                bits |= 1 << s
            self.img[e] = len(self.free[t])
            self.img[e+1] = bits & 0xff
            self.img[e+2] = (bits >> 8) & 0xff
            self.img[e+3] = (bits >> 16) & 0xff
        self.img[b+0x90:b+0xa0] = petscii(self.title)
        self.img[b+0xa0] = self.img[b+0xa1] = 0xa0
        self.img[b+0xa2:b+0xa4] = self.disk_id.encode()
        self.img[b+0xa4] = 0xa0
        self.img[b+0xa5:b+0xa7] = b"2A"
        self.img[b+0xa7:b+0xab] = b"\xa0"*4

        d = offset(18, 1)
        self.img[d], self.img[d+1] = 0, 0xff          # last directory sector
        for i, (name, (ft, fs), nblk) in enumerate(self.entries):
            e = d + i*32
            self.img[e+2] = 0x82                     # closed PRG
            self.img[e+3], self.img[e+4] = ft, fs
            self.img[e+5:e+21] = petscii(name)
            self.img[e+30] = nblk & 0xff
            self.img[e+31] = (nblk >> 8) & 0xff
        return bytes(self.img)


def read_back(img):
    """Parse the image the way a 1541 would, and return {name: bytes}."""
    out, t, s = {}, img[offset(18, 0)], img[offset(18, 0)+1]
    while t:
        d = offset(t, s)
        for i in range(8):
            e = d + i*32
            if img[e+2] & 0x0f != 2:
                continue
            name = img[e+5:e+21].rstrip(b'\xa0').decode('latin1')
            ft, fs, data = img[e+3], img[e+4], bytearray()
            while ft:
                o = offset(ft, fs)
                nt, ns = img[o], img[o+1]
                data += img[o+2:o+2+(254 if nt else ns-1)]
                ft, fs = nt, ns
            out[name] = bytes(data)
        t, s = img[d], img[d+1]
    return out


if __name__ == "__main__":
    files = [(sys.argv[i], sys.argv[i+1]) for i in range(2, len(sys.argv), 2)]
    d = D64()
    for name, path in files:
        d.add(name, open(path, 'rb').read())
    img = d.finish()
    open(sys.argv[1], 'wb').write(img)

    # --- verify -----------------------------------------------------------
    back = read_back(img)
    ok = True
    for name, path in files:
        want = open(path, 'rb').read()
        got = back.get(name.upper())
        state = "OK" if got == want else "MISMATCH"
        ok &= got == want
        print("  %-16s %5d bytes  %s" % (name.upper(), len(want), state))
    b = offset(18, 0)
    free = sum(img[b+4+(t-1)*4] for t in range(1, 36) if t != 18)
    print("  image %d bytes, %d blocks free, round-trip %s"
          % (len(img), free, "OK" if ok else "FAILED"))
    sys.exit(0 if ok else 1)
