"""Reader for Ford's POD archive containers (`CONTENT/<locale>/*.ARC`).

``POD BAY`` version 1 packs each 8.3 filename, absolute offset, and 24-bit
length into a 15-byte record. ``BAY POD`` version 2 uses 16-byte records and a
separate filename table. Both store IDICOMP payloads; see `idicomp.py`.
"""
import os
import struct

MAGIC = b'BAY POD'
V1_MAGIC = b'POD BAY'
V1_MARKER = V1_MAGIC + b'\x01\x00'
V2_MARKER = MAGIC + b'\x02\x00'
HEADER = 17
ENTRY = 16
V1_HEADER = 13
V1_ENTRY = 15


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


def _symbol_char(value):
    if 1 <= value <= 10:
        return chr(ord('0') + value - 1)
    if 11 <= value <= 36:
        return chr(ord('A') + value - 11)
    if value == 37:
        return '_'
    raise ValueError(f'unknown symbol {value}')


def _decode_symbols(values):
    chars = []
    padded = False
    for value in values:
        if value == 0:
            padded = True
        elif padded:
            raise ValueError('non-padding symbol after padding')
        else:
            chars.append(_symbol_char(value))
    return ''.join(chars)


def _decode_v1_name(raw):
    stem_bits = int.from_bytes(raw[:6], 'big')
    stem = _decode_symbols(
        (stem_bits >> shift) & 0x3f for shift in range(42, -1, -6)
    )
    if not stem:
        raise ValueError('empty filename stem')

    ext_value = int.from_bytes(raw[6:8], 'big')
    ext_symbols = []
    for place in (38 * 38, 38, 1):
        symbol, ext_value = divmod(ext_value, place)
        ext_symbols.append(symbol)
    ext = _decode_symbols(ext_symbols)
    return f'{stem}.{ext}' if ext else stem


class Archive:
    """An open .ARC. `f` may be any seekable binary file-like object."""

    def __init__(self, f, name='<archive>'):
        self.f = f
        self.name = name
        marker = f.read(9)
        if len(marker) < 9:
            raise ArcError(f'{name}: truncated archive header')
        if marker == V1_MARKER:
            self.version = 1
            self.entries = self._read_v1()
        elif marker == V2_MARKER:
            self.version = 2
            self.entries = self._read_v2()
        elif marker[:7] in (V1_MAGIC, MAGIC):
            raise ArcError(f'{name}: unsupported POD archive marker {marker!r}')
        else:
            raise ArcError(f'{name}: not a Ford POD archive '
                           f'(magic was {marker[:7]!r})')

    def _read_v2(self):
        header = self.f.read(8)
        if len(header) < 8:
            raise ArcError(f'{self.name}: truncated version 2 header')
        count, name_size = struct.unpack('<II', header)
        table = self.f.read(count * ENTRY)
        names = self.f.read(name_size)
        if len(table) < count * ENTRY or len(names) < name_size:
            raise ArcError(f'{self.name}: truncated version 2 header')
        entries = []
        for index in range(count):
            name_offset, name_length, data_offset, data_length = \
                struct.unpack_from('<IIII', table, index * ENTRY)
            name = names[name_offset:name_offset + name_length] \
                .split(b'\0')[0].decode('latin-1')
            entries.append(Entry(name, data_offset, data_length))
        return entries

    def _read_v1(self):
        count_bytes = self.f.read(4)
        if len(count_bytes) < 4:
            raise ArcError(f'{self.name}: truncated version 1 header')
        count = struct.unpack('<I', count_bytes)[0]
        table_size = count * V1_ENTRY
        table_end = V1_HEADER + table_size

        self.f.seek(0, os.SEEK_END)
        archive_size = self.f.tell()
        if table_end > archive_size:
            raise ArcError(f'{self.name}: truncated version 1 record table')
        self.f.seek(V1_HEADER)
        table = self.f.read(table_size)
        if len(table) < table_size:
            raise ArcError(f'{self.name}: truncated version 1 record table')

        entries = []
        names = set()
        expected_offset = table_end
        for index in range(count):
            record = table[index * V1_ENTRY:(index + 1) * V1_ENTRY]
            try:
                name = _decode_v1_name(record[:8])
            except ValueError as error:
                raise ArcError(f'{self.name}: invalid version 1 filename at '
                               f'record {index}: {error}') from error

            key = name.lower()
            if key in names:
                raise ArcError(f'{self.name}: duplicate version 1 filename '
                               f'at record {index} ({name!r})')
            names.add(key)

            data_offset = struct.unpack_from('<I', record, 8)[0]
            data_length = int.from_bytes(record[12:15], 'little')
            data_end = data_offset + data_length
            if data_length == 0 or data_offset < table_end or \
                    data_end > archive_size:
                raise ArcError(f'{self.name}: invalid version 1 payload bounds '
                               f'at record {index} ({name!r})')
            if data_offset != expected_offset:
                raise ArcError(f'{self.name}: non-contiguous version 1 payload '
                               f'at record {index} ({name!r}); expected offset '
                               f'{expected_offset}, got {data_offset}')
            entries.append(Entry(name, data_offset, data_length))
            expected_offset = data_end

        if expected_offset != archive_size:
            raise ArcError(f'{self.name}: trailing data after version 1 payloads')
        return entries

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
