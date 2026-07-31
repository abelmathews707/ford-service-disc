# Ford "BAY POD" and IDICOMP — format specification

Ford's Technical Service Publications discs store their content in two
undocumented formats: an archive container whose magic bytes are `BAY POD`,
and an LZ77 compression variant identified by the string `IDICOMP`.

Neither appears to have been documented publicly before. Everything below was
worked out by inspecting a disc I own (2020 Mustang, volume `20SLB`) and is
implemented in `fsd/arc.py` and `fsd/idicomp.py`. It decodes all 10,230 files
on that disc with every integrity check passing.

> **This document is dedicated to the public domain under
> [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).**
> Copy it, quote it, reimplement it, put it in a wiki. No attribution needed.
> The specification is the useful artefact; it should not be locked to one
> implementation.

---

## 1. Disc layout

```
/CONTENT/<locale>/<CODE>.ARC     the content archives, e.g. USENI4/SLB.ARC
/DATA/                           FoxPro DBFs — registration metadata only
/VOLUME.ENC                      484-byte licence token (see §5)
/SETUP.EXE, DATA1.CAB, ...       the InstallShield viewer application
```

`<locale>` on the disc examined is `USENI4` (US English). `<CODE>` is a
three-character book code such as `SLB`, `ELB` or `VL2`.

Disc images are often raw dumps rather than plain ISOs. A CloneCD `.img` is
MODE1/2352: to get a mountable ISO, keep bytes 16..2063 of every 2352-byte
sector, dropping sync, header and ECC. Sectors of 2448 bytes (with subchannel
data) and MODE2/FORM1 (user data at offset 24) also occur. Detect the layout
by looking for `\x01CD001` at sector 16 for each candidate stride.

## 2. Archive container: `BAY POD`

```
offset  size    field
0       7       "BAY POD"
7       1       version (2 on every disc seen)
8       1       reserved, 0
9       4       u32   entry count
13      4       u32   name-table size in bytes
17      n*16    entry table
...     m       name table
...             entry payloads
```

Each 16-byte entry, all little-endian:

```
0   u32   name offset, relative to the start of the name table
4   u32   name length in bytes
8   u32   data offset, absolute within the file
12  u32   data length in bytes
```

Names are NUL-terminated 8.3 uppercase strings — flat, with no directories.
Payloads follow the name table and are IDICOMP-compressed.

### The `.epl` manifest

Every archive contains one small XML file, `<CODE>.epl`, describing the book:

```xml
<workunit>
  <type>PCED</type>
  <code>VL2</code>
  <title>Gasoline Engines</title>
  <vehicles>
    <vehicle><year>2020</year><name>Mustang</name><engine>All Gasoline Engines</engine></vehicle>
    ...
  </vehicles>
  <sections>
    <section><title>Table of Contents/Index</title><dest>VL2main.htm</dest></section>
  </sections>
</workunit>
```

Book types observed: `SERVICE` (workshop manual), `EVTM` (Electrical & Vacuum
Troubleshooting Manual, i.e. wiring) and `PCED` (Powertrain Control /
Emissions Diagnosis). This is the right place to identify a disc's contents —
the codes vary between titles but the manifest does not.

Two parsing notes: `<dest>` sometimes contains a URL with unescaped `&`, which
makes the file invalid XML, and `<sections>` contains its own `<title>`
elements which must not be mistaken for the book title.

## 3. Entry payload: IDICOMP

```
offset  size   field
0       8      "\x01IDICOMP"
8       1      version (1)
9       ...    chunk stream
```

The chunk stream is a sequence of:

```
i16 length     length == 0  ->  end of entry
               length <  0  ->  |length| bytes stored verbatim
               length >  0  ->  length bytes of LZ77 data
```

**Every chunk expands to exactly 16384 bytes**, except the last in an entry.
This is a strong integrity check — a misparse of the LZ layer almost always
produces a chunk of the wrong size, which is how the format was ultimately
pinned down.

The match window is **continuous across chunks**: it is not reset at a chunk
boundary. It also starts pre-filled with **4098 zero bytes**, so matches near
the start of an entry can legitimately reach back before its first byte.

## 4. The LZ77 stream

A chunk is a repeating structure of one 16-bit little-endian **flag word**
followed by up to 16 tokens. Flag bits are consumed **most-significant first**
(test `flag & 0x8000`, then shift left).

- **Bit 0** — one literal byte, copied to the output.
- **Bit 1** — a token beginning with two bytes `(b0, b1)`. Let
  `hi = b0 >> 4` and `lo = b0 & 0x0F`:

| `hi` | Meaning | Size |
|------|---------|------|
| `0` | Run: `b1` repeated `lo + 3` times (3–18) | 2 bytes |
| `1` | Run: a third byte `b2` repeated `((b1 << 4) \| lo) + 19` times (19–4114) | 3 bytes |
| `2` | Match, length = `b2 + 16` (16–271), where `b2` is a third byte | 3 bytes |
| `3`–`15` | Match, length = `hi` (3–15) | 2 bytes |

For matches, the distance back into the window is always:

```
distance = ((b1 << 4) | lo) + 3        range 3..4098
```

Note the symmetry: the same 12-bit field is a distance for matches and a
repeat count for `hi == 1`.

Matches may overlap the output being written — copy byte by byte, not with a
block move, so a length longer than the distance repeats the pattern.

The maximum distance (4098) is exactly the size of the zero prologue, which is
why a well-formed stream can never reference before the start of the window.

## 5. `VOLUME.ENC` is not content protection

`VOLUME.ENC` is 484 bytes: the ASCII string `IDIC00000004601` followed by
roughly 470 opaque bytes. It is a licence/volume token consumed by the
original Windows viewer, and it is very probably what produces the
*"This volume has expired and can no longer be used"* error that owners hit
when their system clock is past some date.

It plays no part in reading the content. All 10,230 files on the disc
decompress without it, and the decoder never opens it. The content is
compressed, not encrypted; there is no key anywhere in the pipeline.

## 6. Quirks in the decoded data

Things that will bite an implementer, all present in the source data:

- **SVG files omit `xmlns="http://www.w3.org/2000/svg"`.** Nothing renders
  until it is added back.
- **SVG `<desc>` blocks contain custom tags** such as `<Qualifier />`. Parse
  these files as XML; an HTML parser swallows the drawing.
- **Encoding is inconsistent.** Pages declare UTF-8 but a good number
  (~150 on this disc) are actually Windows-1252. Try UTF-8 strictly first,
  then fall back.
- **Some procedures are stored without the book-code prefix**, e.g.
  `G1234567.HTM` where the table of contents links to `SLBG1234567.HTM`.
  Those links were dead on the original disc.
- **PCED pages link "back to index"** via
  `/renderers/pced_2colframeset.asp?...`, a server-side URL that was never
  shipped on the disc and has always been dead.
- **A few `loc_view` references point at sheets that do not exist** on the
  disc at all.
- **Wiring metadata uses `<number>`, not `<num>`**, in `<CODE>CELTTL.XML`,
  while the per-cell files use `<num>`.
- **Inline connectors store both halves in one record.** Each `<Face>` carries
  its own gender, drawing, pin list and terminal part numbers; older entries
  instead put a single `<Pins>` list on the `<Connector>`.

## 7. How this was derived

Notes for anyone attacking a similar format, since the blind alleys took
longer than the solution.

Parametric guessing at the token layout failed completely. What worked was
**deriving ground truth from known plaintext**: the decoded files had to begin
with an SVG `<!DOCTYPE`, a JPEG `SOI` marker and quantisation tables, and so
on. Those known prefixes made it possible to read the flag word's bit order
straight out of the data rather than infer it.

The `hi == 1` case resisted longest. It was settled by exploiting the 16 KB
chunk invariant: build an oracle over 760 chunks, then solve for the repeat
count per `lo` value such that every chunk lands on exactly 16384 bytes. That
turned a guessing problem into an arithmetic one.

Two other assumptions cost real time and are worth naming — that the window
resets at each chunk boundary (it does not), and that matches can never point
before the start of the output (they can, into the zero prologue).

## 8. Validation

The implementation here was checked against the whole disc:

- 10,230 of 10,230 entries decode
- every chunk expands to exactly 16384 bytes except the last in each entry
- every entry's chunk stream is consumed exactly, with no trailing bytes
- content-level checks: JPEG/GIF/PDF magic and end markers, SVG and XML
  well-formedness, HTML end tags, no stray NUL bytes
- a random sample of decoded images re-encoded cleanly with an external tool
