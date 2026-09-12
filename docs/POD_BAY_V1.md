# `POD BAY` version 1 research

Status: reader implemented; synthetic tests and full CLI validation pending.

This document records container metadata only. It contains no Ford manual
content or extracted files.

## Evidence set

Six unique version 1 archives were examined: `E1O`, `E2O`, `EYO`, `S1O`,
`S2O`, and `SYO`. They contain 26,162 records. The same six archive payloads
occur byte-for-byte in two preserved source copies, so only one copy was
needed for structural analysis.

## Container layout

`POD BAY` is an earlier layout in the same archive family as `BAY POD`. The
reversed words are a format/version marker, not an instruction to reverse
bytes elsewhere.

| Offset | Size | Meaning |
| ---: | ---: | --- |
| `0` | 7 | ASCII `POD BAY` |
| `7` | 2 | Version marker `01 00` |
| `9` | 4 | Little-endian record count |
| `13` | `count * 15` | Record table |
| after table | variable | IDICOMP entry payloads |

Each record is 15 bytes:

| Record offset | Size | Meaning |
| ---: | ---: | --- |
| `0` | 6 | Packed eight-character filename stem |
| `6` | 2 | Packed three-character extension |
| `8` | 4 | Little-endian absolute payload offset |
| `12` | 3 | Little-endian payload length |

The first payload begins immediately after the record table in every examined
archive. Each stored length reaches the next record offset, or EOF for the
last record. Implementations should use the stored length and validate bounds;
deriving it from the next offset discards an integrity field.

The observed `01 00` may be a little-endian version or a one-byte version plus
a reserved zero. The available media cannot distinguish those interpretations,
so the reader should validate the complete marker rather than assume either.

## Filename encoding

The stem contains eight most-significant-first 6-bit symbols in 48 bits. The
observed alphabet is:

- `0`: trailing padding
- `1` through `10`: `0` through `9`
- `11` through `36`: `A` through `Z`
- `37`: `_`

The extension uses three symbols from the same alphabet as a big-endian
base-38 value:

```text
value = first * 38^2 + second * 38 + third
```

All 26,162 records decode to these extensions:

| Encoded bytes | Extension | Records |
| --- | --- | ---: |
| `58 8e` | `EPL` | 6 |
| `62 c6` | `GIF` | 20,469 |
| `6a 13` | `HTM` | 4,742 |
| `83 dc` | `MDB` | 3 |
| `94 cc` | `PDF` | 936 |
| `bc 22` | `WCF` | 6 |

No invalid symbols, malformed padding, or duplicate full filenames were found
within an archive. Three stored `HTM` files contain stylesheet-like content;
their encoded filenames should still be preserved.

## Payload compatibility

Every record offset points to an `\x01IDICOMP\x01` entry. The existing strict
IDICOMP decoder successfully consumed sampled entries of every observed type
without trailing bytes. An independent full pass decoded all 26,162 entries
the same way. All six decoded `EPL` manifests parse with the existing manifest
parser.

Production validation remains a separate checkpoint: the completed reader
must perform its own full-source deep probe before support is considered done.

## Confidence and open questions

Confidence is high for the documented layout across these six archives: every
record satisfies the same field interpretation, and the decoded extensions
match their payload types. The following remain deliberately unresolved:

- whether the two-byte version marker is one field or version plus reserved;
- whether another version 1 producer permits gaps or out-of-order payloads;
- what symbols `38` through `63` mean, if they are valid at all; and
- why Ford reversed the magic words between the two layouts.

The implementation should reject unobserved encodings rather than guess, and
future owned media can broaden compatibility with new evidence.

## Difference from `BAY POD` version 2

| Property | `POD BAY` v1 | `BAY POD` v2 |
| --- | --- | --- |
| Header | 13 bytes | 17 bytes |
| Record | 15 bytes | 16 bytes |
| Filename | Packed 8.3 name in record | Plain name in a separate table |
| Offset | 32-bit absolute | 32-bit absolute |
| Length | 24-bit in record | 32-bit in record |
| Payload | IDICOMP | IDICOMP |

The implementation reuses `Entry`, raw/read operations, the IDICOMP decoder,
manifest parser, disc discovery, extraction, and viewer pipeline. Container
dispatch and record/name decoding use a distinct version 1 path.

Until another valid archive demonstrates otherwise, the reader requires the
observed record-order continuity: the first payload begins at the table end,
each stored length reaches the next offset, and the final payload reaches EOF.
This rejects gaps, descending offsets, overlaps, and unaccounted trailing data
instead of guessing how to handle an unseen variation.

## Experimental branch findings

The unmerged `agent/pod-bay-v1` branch at `e0efc8f` is useful reference code,
but it is not correct support:

- it decodes only the stem and discards the encoded extension;
- it labels the stored length as unknown metadata and infers a length from the
  next offset;
- its fixture hardcodes the `GIF` extension value for every record and writes
  zero for the stored length;
- extensionless names prevent manifest discovery and break downstream type,
  extraction, and link handling;
- unknown packed symbols become `?` instead of a format error; and
- unsupported magic/version pairs can reach the wrong parser.

The public [`darrenadixonpi/pod-bay`](https://github.com/darrenadixonpi/pod-bay)
implementation supplied the correct stem algorithm but makes the same
extension and length assumptions. The public
[`John-MustangGT/ford-workshop-manual-tools`](https://github.com/John-MustangGT/ford-workshop-manual-tools)
fallback confirms that the payloads use IDICOMP, but it scans for markers and
invents filenames rather than fully decoding the table. Neither implementation
should be copied wholesale.

## Recorded revisions

| Source | Revision |
| --- | --- |
| `shad0wca7/ford-service-disc` branch point | `aa0e2ad632dfce5498cd9699c0b4e11908a45c34` |
| Experimental `agent/pod-bay-v1` | `e0efc8fd724d276f2c8b47b1ac4c5d1dacb38f6b` |
| `darrenadixonpi/pod-bay` reference | `92fdae477d91b61ef86d1aea5a50f458d93fca77` |
| `John-MustangGT/ford-workshop-manual-tools` reference | `98516fb65ec79aaadb837e7c46876921dddaa081` |
