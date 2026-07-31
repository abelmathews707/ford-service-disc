"""Reader for Ford's "BAY POD" archive container (`CONTENT/<locale>/*.ARC`).

    offset  size   field
    0       7      "BAY POD"
    7       1      version (2 on every disc seen so far)
    8       1      reserved, 0
    9       4      u32  entry count
    13      4      u32  name-table size
    17      n*16   entries: u32 nameOff, u32 nameLen, u32 dataOff, u32 dataLen
    ...            name table (nameOff is relative to the start of the table)
    ...            entry payloads (dataOff is absolute within the file)

Each payload is IDICOMP-compressed — see `idicomp.py`.
"""
import os
import struct

MAGIC = b'BAY POD'
HEADER = 17
ENTRY = 16


class ArcError(Exception):
    pass


class Entry:
    __slots__ = ('name', 'offset', 'length')

    def __init__(self, name, offset, length):
        self.name, self.offset, self.length = name, offset, length

    @property
    def ext(self):
        return self.name.rsplit('.', 1)[-1].lower() if '.' in self.name else ''

    def __repr__(self):
        return f'<Entry {self.name} @{self.offset} {self.length}B>'


class Archive:
    """An open .ARC. `f` may be any seekable binary file-like object."""

    def __init__(self, f, name='<archive>'):
        self.f = f
        self.name = name
        hdr = f.read(HEADER)
        if hdr[:7] != MAGIC:
            raise ArcError(f'{name}: not a BAY POD archive '
                           f'(magic was {hdr[:7]!r})')
        self.version = hdr[7]
        count, nsize = struct.unpack('<II', hdr[9:17])
        table = f.read(count * ENTRY)
        names = f.read(nsize)
        if len(table) < count * ENTRY or len(names) < nsize:
            raise ArcError(f'{name}: truncated header')
        self.entries = []
        for i in range(count):
            no, nl, do, dl = struct.unpack_from('<IIII', table, i * ENTRY)
            nm = names[no:no + nl].split(b'\0')[0].decode('latin-1')
            self.entries.append(Entry(nm, do, dl))

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def raw(self, entry):
        """The still-compressed payload for one entry."""
        self.f.seek(entry.offset)
        d = self.f.read(entry.length)
        if len(d) != entry.length:
            raise ArcError(f'{self.name}: short read on {entry.name}')
        return d

    def read(self, entry):
        """The decompressed contents of one entry."""
        from .idicomp import unwrap
        data, _ = unwrap(self.raw(entry))
        return data

    def find(self, name):
        low = name.lower()
        for e in self.entries:
            if e.name.lower() == low:
                return e
        return None

    def ext_counts(self):
        counts = {}
        for e in self.entries:
            counts[e.ext or '(none)'] = counts.get(e.ext or '(none)', 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def open_arc(path):
    return Archive(open(path, 'rb'), os.path.basename(path))
