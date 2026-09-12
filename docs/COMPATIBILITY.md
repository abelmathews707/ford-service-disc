# Disc compatibility

Ford sold service information on disc under the generic "Technical Service
Publications" name for many years and across most of the range. This tool was
developed against **one** of those discs. Nothing in it is specific to that
title, but only tested discs can be listed as tested.

**Please report yours** — whether it worked or not, using the
[disc report template](../../issues/new?template=disc-report.yml). A success
is as useful as a failure: it is the only way this table grows.

Do not attach disc content, images or extracted files to a report. The output
of `fsd probe` is all that is needed.

## Confirmed

| Disc | Volume | Books | Result |
|---|---|---|---|
| 2020 Mustang Service Information | `20SLB` | SLB (SERVICE), ELB (EVTM), VL2 (PCED) | Full — 10,230/10,230 entries decode; site builds with 0 broken references |

## Archive-format validation

This is narrower than the end-to-end result above: it proves that archives can
be parsed and decompressed, not that their extracted books have completed the
viewer build and link-audit pipeline.

| Layout | Owned archive set | Entries | Result |
|---|---|---:|---|
| `POD BAY` version 1 | E1O, E2O, EYO, S1O, S2O, SYO | 26,162 | All names, bounds, stored lengths, and payload continuity validate; every entry strictly decompresses and passes a format-appropriate structural check; all six manifests parse |

The same six version 1 archives occur byte-for-byte in two preserved source
copies and are counted once. Sample probes of additional owned `BAY POD`
version 2 sources were clean. A separate deep probe found the known baseline
decoder warning below.

## Why other discs are likely to work

The tool does not hardcode anything from the disc above:

- **Archives are found by scanning** for `*.ARC`, not by expecting
  `CONTENT/USENI4/`. Other locales and layouts are fine.
- **Books identify themselves.** Each archive carries a `<CODE>.epl` manifest
  giving its type, code and the vehicles it covers, and that is what the tool
  reads. A disc using different codes needs no changes.
- **Filename patterns are derived** from each book's own code, with a fallback
  that detects the shared prefix from the files if the manifest and filenames
  disagree.
- **Missing books are tolerated.** A disc with only a workshop manual, or only
  wiring, builds fine.
- **The book type can be guessed** from the files if a `.epl` is missing.
- **Sector layouts are detected**, so plain ISOs, MODE1/2352 raw dumps,
  MODE2/FORM1 and 2448-byte dumps with subchannel data all read.

The strongest circumstantial evidence is the PCED volume on the tested disc:
it is a shared book that Ford ships for 23 different vehicles, which means the
same container is in use right across the range.

## Known limits

- **Only SERVICE, EVTM and PCED books get a layout.** Any other book type
  extracts to files normally, but the viewer skips it and says so. If you hit
  one, please report the type — that is exactly the information needed to add
  support.
- **Only the exact observed markers are supported:** `POD BAY 01 00` and
  `BAY POD 02 00`. Other marker or version combinations are rejected rather
  than guessed; please report one if you find it.
- **One older French-Canadian `BAY POD` version 2 archive has a known strict
  decoder warning.** Entry `S2169A03.htm` in archive `S21` expands one chunk to
  16,388 bytes instead of 16,384. The exact same archived payload fails on the
  unchanged base revision, so this is not caused by version 1 support.
- **Non-English end-to-end site builds are untested.** Nothing should depend on
  language, but the encoding fallback assumes Windows-1252 where UTF-8 fails,
  which may be wrong for other locales.
- **Rock Ridge and Joliet are not read** from images. These discs use plain
  8.3 uppercase names, so this has not mattered; a disc relying on long
  filenames would need it.

## If your disc does not work

Run the deep check, which decodes every entry rather than a sample:

```bash
python3 -m fsd probe /path/to/disc --deep
```

Then open an issue with that output. Useful extras:

- `ls /Volumes/YOURDISC` (or `dir D:\`) if no archives were found at all
- the exact error and traceback if extraction or the build failed

If `probe` is clean but the **build** produces an empty or odd-looking site,
that usually means the book uses a structure the layout code does not expect.
Extraction still gives you every file, so nothing is lost in the meantime:

```bash
python3 -m fsd extract /path/to/disc -o extracted
```
