"""Command line interface: `python3 -m fsd ...`"""
import argparse
import os
import shutil
import sys
import tempfile

from . import __version__
from .arc import ArcError
from .disc import DiscError, open_source
from .extract import extract as do_extract
from .iso import IsoError


def _err(msg):
    print(f'error: {msg}', file=sys.stderr)
    return 2


def _human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024


# ----------------------------------------------------------------- commands
def cmd_probe(a):
    from .probe import as_json, probe, report
    with open_source(a.disc) as src:
        info = probe(src, sample=a.sample, deep=a.deep)
    print(as_json(info) if a.json else '', end='')
    if not a.json:
        report(info)
    return 0 if info['ok'] else 1


def cmd_extract(a):
    with open_source(a.disc) as src:
        print(f'Reading {src.label} ({src.kind})')
        res = do_extract(src, a.out, only=a.book, archives=a.archive,
                         validate=not a.no_validate, force=a.force)
    print(f'\n{res.summary()}  ->  {a.out}')
    for arc, name, why in res.failed[:10]:
        print(f'  FAILED {arc}/{name}: {why}', file=sys.stderr)
    if res.failed:
        print(f'\n{len(res.failed)} entries failed. Please open an issue with '
              'the output of `fsd probe --deep`.', file=sys.stderr)
        return 1
    return 0


def cmd_build(a):
    from .build import build
    build(a.extracted, a.out, title=a.title)
    print(f'\nSite written to {a.out}')
    print(f'Serve it with:  python3 -m fsd serve {a.out}')
    return 0


def cmd_iso(a):
    from .iso import SectorSource
    with open(a.image, 'rb') as f:
        src = SectorSource(f)
        if not src.raw:
            print(f'{a.image} already has {src.stride}-byte sectors; '
                  'nothing to convert.')
            return 0
        print(f'Converting {src.stride}-byte raw sectors -> 2048-byte ISO')

        def prog(done, total):
            pct = 100 * done / total if total else 100
            print(f'\r  {pct:5.1f}%  {done}/{total} sectors', end='', flush=True)
        with open(a.out, 'wb') as o:
            src.to_iso(o, progress=prog)
    print(f'\nWrote {a.out} ({_human(os.path.getsize(a.out))})')
    return 0


def cmd_serve(a):
    import functools
    import http.server
    root = os.path.abspath(a.site)
    if not os.path.isdir(root):
        return _err(f'{root}: not a directory')
    if not os.path.exists(os.path.join(root, 'index.html')):
        return _err(f'{root} has no index.html — is this a built site?')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=root)

    # Threaded: a single procedure page can pull hundreds of images, and a
    # one-request-at-a-time server makes that crawl.
    class Server(http.server.ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    with Server((a.host, a.port), handler) as httpd:
        where = a.host if a.host not in ('', '0.0.0.0') else 'localhost'
        print(f'Serving {root}\n  http://{where}:{a.port}/\nCtrl-C to stop.')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nStopped.')
    return 0


def cmd_all(a):
    """Disc to browsable site in one step."""
    from .build import build
    keep = a.keep_extracted
    tmp = a.extracted or (None if keep else tempfile.mkdtemp(prefix='fsd-'))
    dest = a.extracted or tmp
    try:
        with open_source(a.disc) as src:
            print(f'Reading {src.label} ({src.kind})')
            res = do_extract(src, dest, only=a.book, archives=a.archive,
                             validate=not a.no_validate)
        print(f'  {res.summary()}\n')
        if res.failed:
            for arc, name, why in res.failed[:10]:
                print(f'  FAILED {arc}/{name}: {why}', file=sys.stderr)
            return 1
        build(dest, a.out, title=a.title)
    finally:
        if tmp and not keep and not a.extracted:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f'\nSite written to {a.out}')
    if a.serve:
        a.site = a.out
        return cmd_serve(a)
    print(f'Serve it with:  python3 -m fsd serve {a.out}')
    return 0


# ------------------------------------------------------------------- parser
def make_parser():
    p = argparse.ArgumentParser(
        prog='fsd',
        description='Read Ford Technical Service Publications discs — '
                    'workshop manual, wiring diagrams and PCED — without the '
                    'original Windows software.',
        epilog='DISC may be a mounted disc (/Volumes/20SLB, D:\\), a folder '
               'holding a copy of one, or a disc image (.iso/.img/.bin). '
               'Images are read in place: no mounting and no root needed.')
    p.add_argument('--version', action='version', version=f'fsd {__version__}')
    sub = p.add_subparsers(dest='cmd', required=True, metavar='COMMAND')

    q = sub.add_parser('probe', help='identify a disc and check it can be read')
    q.add_argument('disc')
    q.add_argument('--sample', type=int, default=25,
                   help='entries to test-decode per archive (default 25)')
    q.add_argument('--deep', action='store_true',
                   help='decode every entry — slow, but definitive')
    q.add_argument('--json', action='store_true', help='machine-readable output')
    q.set_defaults(fn=cmd_probe)

    q = sub.add_parser('extract', help='unpack the archives to a folder')
    q.add_argument('disc')
    q.add_argument('-o', '--out', default='extracted', help='(default: extracted)')
    q.add_argument('-b', '--book', action='append',
                   help='only this archive code, e.g. -b SLB (repeatable)')
    q.add_argument('--archive', action='append',
                   help='only this exact source-relative archive path')
    q.add_argument('--force', action='store_true', help='re-extract existing files')
    q.add_argument('--no-validate', action='store_true',
                   help='skip the 16 KB chunk check')
    q.set_defaults(fn=cmd_extract)

    q = sub.add_parser('build', help='build the web viewer from an extracted disc')
    q.add_argument('extracted')
    q.add_argument('-o', '--out', default='site', help='(default: site)')
    q.add_argument('--title', help='override the site title')
    q.set_defaults(fn=cmd_build)

    q = sub.add_parser('all', help='extract and build in one step')
    q.add_argument('disc')
    q.add_argument('-o', '--out', default='site', help='(default: site)')
    q.add_argument('--extracted', help='keep the unpacked files here '
                                       '(default: a temporary folder)')
    q.add_argument('--keep-extracted', action='store_true')
    q.add_argument('-b', '--book', action='append')
    q.add_argument('--archive', action='append')
    q.add_argument('--title')
    q.add_argument('--no-validate', action='store_true')
    q.add_argument('--serve', action='store_true', help='serve the site when done')
    q.add_argument('--port', type=int, default=8848)
    q.add_argument('--host', default='127.0.0.1')
    q.set_defaults(fn=cmd_all)

    q = sub.add_parser('serve', help='serve a built site over HTTP')
    q.add_argument('site', nargs='?', default='site')
    q.add_argument('-p', '--port', type=int, default=8848)
    q.add_argument('--host', default='127.0.0.1',
                   help='use 0.0.0.0 to reach it from other machines')
    q.set_defaults(fn=cmd_serve)

    q = sub.add_parser('iso', help='convert a raw (2352-byte sector) dump to ISO')
    q.add_argument('image')
    q.add_argument('out')
    q.set_defaults(fn=cmd_iso)
    return p


def main(argv=None):
    args = make_parser().parse_args(argv)
    try:
        return args.fn(args)
    except (DiscError, IsoError, ArcError) as ex:
        return _err(str(ex))
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        print('\nInterrupted.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
