"""Decoder for IDICOMP, the LZ77 variant Ford used inside .ARC payloads.

Payload layout::

    0   8   "\\x01IDICOMP"
    8   1   version (1)
    9   ..  chunk stream:
              i16 len   len == 0 -> end of entry
                        len <  0 -> |len| bytes stored verbatim
                        len >  0 -> len bytes of LZ77 data

Every chunk expands to exactly 16384 bytes, the last one excepted — which
makes a cheap and very effective integrity check (see `unwrap(strict=True)`).
The match window is **continuous across chunks** and starts pre-filled with
zeros, so matches early in an entry can legitimately reach back past its
first byte.

The LZ77 stream is a 16-bit little-endian flag word followed by 16 tokens,
consumed MSB first. A 0 bit means one literal byte. A 1 bit means a token
starting `(b0, b1)`, where ``hi = b0 >> 4`` and ``lo = b0 & 15``:

===== ====================================================== =====
``hi``  meaning                                              bytes
===== ====================================================== =====
0       run: ``b1`` repeated ``lo + 3`` times (3-18)          2
1       run: ``b2`` repeated ``((b1 << 4) | lo) + 19`` (19-4114) 3
2       match, length = ``b2 + 16`` (16-271)                  3
3-15    match, length = ``hi`` (3-15)                         2
===== ====================================================== =====

Match distance is always ``((b1 << 4) | lo) + 3``, i.e. 3-4098. Note that the
same 12-bit field is a distance for matches and a repeat count for ``hi == 1``.

This format is undocumented; everything here was worked out by hand. See
docs/FORMAT.md for how, and for the gotchas in the decoded data.
"""
import struct

MAGIC = b'\x01IDICOMP'
CHUNK = 16384
#: The window is pre-initialised to 4098 zero bytes — the maximum match
#: distance — because matches near the start of an entry reach back into it.
PROLOGUE = 4098


class LZError(Exception):
    pass


def _lz_into(out, s):
    p, n = 0, len(s)
    while p + 2 <= n:
        flag = struct.unpack_from('<H', s, p)[0]
        p += 2
        for _ in range(16):
            if p >= n:
                return
            if not (flag & 0x8000):
                out.append(s[p])
                p += 1
                flag = (flag << 1) & 0xFFFF
                continue
            flag = (flag << 1) & 0xFFFF
            if p + 2 > n:
                return
            b0, b1 = s[p], s[p + 1]
            p += 2
            hi, lo = b0 >> 4, b0 & 0x0F
            if hi == 0:                                  # short run
                out += bytes([b1]) * (lo + 3)
                continue
            if hi == 1:                                  # long run
                if p >= n:
                    return
                out += bytes([s[p]]) * (((b1 << 4) | lo) + 19)
                p += 1
                continue
            dist = ((b1 << 4) | lo) + 3
            ln = hi
            if hi == 2:                                  # extended length
                if p >= n:
                    return
                ln = s[p] + 16
                p += 1
            if dist > len(out):
                raise LZError(f'match distance {dist} exceeds {len(out)} '
                              'bytes of history')
            st = len(out) - dist
            for k in range(ln):
                out.append(out[st + k])


def unwrap(blob, strict=False):
    """Decompress one IDICOMP payload.

    Returns ``(data, bytes_consumed)``. With ``strict=True`` the 16 KB chunk
    invariant is enforced, which reliably catches a misparse.
    """
    if blob[:8] != MAGIC:
        raise LZError(f'bad IDICOMP magic {blob[:8]!r}')
    out = bytearray(PROLOGUE)
    p = 9
    while p + 2 <= len(blob):
        v = struct.unpack_from('<h', blob, p)[0]
        p += 2
        if v == 0:
            break
        body = blob[p:p + abs(v)]
        p += abs(v)
        before = len(out)
        if v < 0:
            out += body
        else:
            _lz_into(out, body)
        grew = len(out) - before
        if strict and grew > CHUNK:
            raise LZError(f'chunk expanded to {grew} bytes, over the '
                          f'{CHUNK}-byte maximum')
        if strict and grew < CHUNK and p + 2 <= len(blob) and \
                struct.unpack_from('<h', blob, p)[0] != 0:
            raise LZError(f'short chunk ({grew} bytes) before the end of '
                          'the entry')
    return bytes(out[PROLOGUE:]), p


def is_compressed(blob):
    return blob[:8] == MAGIC
