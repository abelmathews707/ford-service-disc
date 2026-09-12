"""Unpack the archives on a disc into a directory tree."""
import json
import os
import re

from .arc import ArcError
from .idicomp import LZError, is_compressed, unwrap

#: Written alongside the unpacked books so a later `build` still knows which
#: disc the files came from.
DISC_JSON = '.fsd-disc.json'


def safe_name(name):
    n = name.replace('\\', '/').split('/')[-1]
    n = n.strip().lstrip('.') or '_'
    return re.sub(r'[\x00-\x1f:*?"<>|]', '_', n)


class Result:
    def __init__(self):
        self.files = 0
        self.bytes = 0
        self.failed = []       # (archive, entry name, reason)
        self.skipped = 0
        self.books = []

    @property
    def ok(self):
        return not self.failed

    def summary(self):
        s = f'{self.files} files, {self.bytes / 1e6:.1f} MB'
        if self.skipped:
            s += f', {self.skipped} unchanged'
        if self.failed:
            s += f', {len(self.failed)} FAILED'
        return s


def extract(source, dest, only=None, archives=None, validate=True, force=False,
            log=print, on_file=None):
    """Unpack `source` into `dest/<archive output directory>/`.

    `only` limits extraction to archive codes. `archives` selects exact,
    source-relative archive identities. `validate` turns on the 16 KB chunk
    check in the decoder, which is cheap and catches a misparse immediately.
    """
    res = Result()
    os.makedirs(dest, exist_ok=True)
    # Remember which disc this came from: the label is the best name for the
    # site when the books themselves don't identify a single vehicle.
    with open(os.path.join(dest, DISC_JSON), 'w', encoding='utf-8') as fh:
        json.dump({'label': source.label, 'source': source.kind}, fh, indent=1)
    refs = source.archives()
    if only or archives:
        codes = {code.casefold() for code in only or ()}
        identities = {identity.casefold() for identity in archives or ()}
        refs = [
            ref for ref in refs
            if ref.code.casefold() in codes or ref.identity in identities
        ]
    if not refs:
        raise ArcError('no .ARC archives found on this disc')

    for ref in refs:
        with ref.open() as arc:
            from .disc import book_of
            book = book_of(arc)
            if book:
                res.books.append(book)
            label = book.describe() if book else ref.code
            log(f'  {label}: {len(arc)} entries')
            outdir = os.path.join(dest, ref.output_dir)
            os.makedirs(outdir, exist_ok=True)

            for e in arc:
                name = safe_name(e.name)
                if not name:
                    res.failed.append((ref.code, e.name, 'unusable name'))
                    continue
                path = os.path.join(outdir, name)
                if not force and os.path.exists(path) and \
                        os.path.getsize(path) > 0:
                    res.skipped += 1
                    continue
                try:
                    raw = arc.raw(e)
                    # a few entries are stored uncompressed
                    data = unwrap(raw, strict=validate)[0] \
                        if is_compressed(raw) else raw
                except (LZError, ArcError) as ex:
                    res.failed.append((ref.code, e.name, str(ex)))
                    continue
                with open(path, 'wb') as fh:
                    fh.write(data)
                res.files += 1
                res.bytes += len(data)
                if on_file:
                    on_file(ref.code, name, len(data))
    return res
