"""Wrap the music player in a PSID header so it can be played as a .sid file."""
import struct, sys

data = open(sys.argv[1], 'rb').read()          # starts with its load address
def pad(s, n=32):
    return s.encode('latin1')[:n-1].ljust(n, b'\0')

hdr  = b'PSID' + struct.pack('>HHHHHHHI', 2, 0x7C, 0x0000, 0x1000, 0x1003, 1, 1, 0)
hdr += pad("Matrix Rain") + pad(sys.argv[3] if len(sys.argv) > 3 else "")
hdr += pad("2026")
hdr += struct.pack('>HBBBB', 0, 0, 0, 0, 0)    # flags, startPage, pageLen, SID2, SID3
assert len(hdr) == 0x7C, len(hdr)
open(sys.argv[2], 'wb').write(hdr + data)
print("wrote %s (%d bytes)" % (sys.argv[2], len(hdr) + len(data)))
