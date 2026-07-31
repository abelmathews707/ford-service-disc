"""Read an ISO9660 filesystem straight out of a disc image.

Ford shipped these titles as pressed CDs and DVDs, and the images people have
of them are a mix: plain ISOs, CloneCD/Alcohol raw dumps with 2352-byte
sectors, and dumps that also carry the 96-byte subchannel (2448). Rather than
make you convert first, `SectorSource` figures out the layout and presents
plain 2048-byte logical sectors to the reader above it.

Reading the image directly also means no mounting, which on Linux would
otherwise want root.
"""
import struct

#: (stride, offset of user data within each sector) candidates, in the order
#: we try them. 2352/16 is MODE1, 2352/24 is MODE2 FORM1.
_LAYOUTS = [(2048, 0), (2352, 16), (2352, 24), (2448, 16), (2448, 24)]

SECTOR = 2048


class IsoError(Exception):
    pass


class SectorSource:
    """Presents a disc image as a flat array of 2048-byte logical sectors."""

    def __init__(self, f):
        self.f = f
        self.stride, self.data_off = self._detect()

    def _detect(self):
        for stride, off in _LAYOUTS:
            self.f.seek(16 * stride + off)
            if self.f.read(6) == b'\x01CD001':
                return stride, off
        raise IsoError(
            'no ISO9660 volume descriptor found — this does not look like a '
            'CD/DVD image (checked 2048, 2352 and 2448-byte sectors)')

    @property
    def raw(self):
        """True when the image carries sync/header/ECC around each sector."""
        return self.stride != SECTOR

    def sector(self, lba):
        self.f.seek(lba * self.stride + self.data_off)
        d = self.f.read(SECTOR)
        if len(d) < SECTOR:
            d += b'\0' * (SECTOR - len(d))
        return d

    def read(self, lba, length):
        out = bytearray()
        while len(out) < length:
            out += self.sector(lba)
            lba += 1
        return bytes(out[:length])

    def to_iso(self, out, progress=None):
        """Write a plain 2048-byte-sector ISO. Only useful if you want to mount
        it; every other command in this tool reads the image in place."""
        self.f.seek(0, 2)
        total = self.f.tell() // self.stride
        for lba in range(total):
            out.write(self.sector(lba))
            if progress and lba % 8192 == 0:
                progress(lba, total)
        if progress:
            progress(total, total)
        return total


class Entry:
    __slots__ = ('path', 'lba', 'size', 'is_dir')

    def __init__(self, path, lba, size, is_dir):
        self.path, self.lba, self.size, self.is_dir = path, lba, size, is_dir

    def __repr__(self):
        return f'<{"dir " if self.is_dir else "file"} {self.path} {self.size}B>'


class Iso9660:
    """Just enough ISO9660 to find and read the files we care about.

    No Joliet or Rock Ridge: these discs use plain 8.3 uppercase names, and
    the archives we want are at CONTENT/<locale>/<CODE>.ARC.
    """

    def __init__(self, src):
        self.src = src
        pvd = src.sector(16)
        if pvd[:6] != b'\x01CD001':
            raise IsoError('bad primary volume descriptor')
        self.label = pvd[40:72].decode('latin-1').strip() or '(unlabelled)'
        self.system = pvd[8:40].decode('latin-1').strip()
        root = pvd[156:190]
        self._root = (struct.unpack_from('<I', root, 2)[0],
                      struct.unpack_from('<I', root, 10)[0])

    def _records(self, lba, size):
        data = self.src.read(lba, size)
        p = 0
        while p < len(data):
            ln = data[p]
            if ln == 0:
                # records never straddle a sector; skip to the next one
                p = (p // SECTOR + 1) * SECTOR
                if p >= len(data):
                    break
                continue
            rec = data[p:p + ln]
            p += ln
            if len(rec) < 33:
                continue
            name_len = rec[32]
            name = rec[33:33 + name_len]
            if name_len == 1 and name in (b'\x00', b'\x01'):
                continue                      # "." and ".."
            nm = name.decode('latin-1').split(';')[0]
            yield Entry(nm,
                        struct.unpack_from('<I', rec, 2)[0],
                        struct.unpack_from('<I', rec, 10)[0],
                        bool(rec[25] & 0x02))

    def walk(self, max_depth=8):
        """Yield every Entry on the disc, with full paths."""
        stack = [('', self._root[0], self._root[1], 0)]
        while stack:
            prefix, lba, size, depth = stack.pop()
            for e in self._records(lba, size):
                e.path = f'{prefix}/{e.path}' if prefix else e.path
                yield e
                if e.is_dir and depth < max_depth:
                    stack.append((e.path, e.lba, e.size, depth + 1))

    def read_file(self, entry):
        return self.src.read(entry.lba, entry.size)


def open_image(path):
    """Open a disc image and return (Iso9660, file handle)."""
    f = open(path, 'rb')
    try:
        return Iso9660(SectorSource(f)), f
    except Exception:
        f.close()
        raise
