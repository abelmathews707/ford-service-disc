# Service Manual Extractor — current handoff

Updated: 2026-09-15
Current checkpoint: GM USB copied/inspected; design and test plan prepared.
Production GM extraction/import support has not been implemented.

## Start here

1. Read [GM inspection findings](GM_HTML_INSPECTION.md), especially integrity.
2. Select one step from [GM HTML implementation plan](GM_HTML_PLAN.md).
3. Read that step's [test gate](GM_HTML_TEST_PLAN.md).
4. Verify branches, working-tree changes and input identities before acting.

The user wants the same Repair Buddy experience across makes, with the manuals
providing the content. Work is intentionally split into small sequential tasks
to manage Codex usage. Do not implement all steps on a generic “continue.”

## Repository state and compatibility

| Item | State at this checkpoint |
| --- | --- |
| GitHub fork | `https://github.com/abelmathews707/service-manual-extractor` |
| Previous fork name | `abelmathews707/ford-service-disc` |
| Existing local checkout | `/Users/asokmathews/Documents/ford-service-disc` |
| Feature branch | `codex/gm-html-manuals` |
| Branch baseline | `f1bdc8d`, main and `v0.1.0` foundation |
| Upstream | `https://github.com/shad0wca7/ford-service-disc.git` |
| Compatible existing command | `python -m fsd` |
| Repair Buddy | `/Users/asokmathews/Documents/repair-buddy`, main `d59c8c8` |
| Workshop toolkit | `/Users/asokmathews/Documents/workshop-manual-toolkit-main`, main `d150e7d` |

GitHub was renamed with the user's chosen name. The local `origin` URL was
updated and fork/upstream identity verified. The local folder and `fsd` package
retain their names so Repair Buddy's existing dependency configuration works.
Other historical docs/records may still use the old repo name; do not rewrite
old provenance or mass-rename paths. No original release tag was changed.

Repair Buddy has three pre-existing documentation edits on main (`README.md`,
`docs/current-handoff.md`, `docs/project-design.md`) recording a deferred
commercial-release milestone. This task did not modify those files. Create a
separate branch for the later Repair Buddy integration and preserve that work.
The workshop toolkit is independently versioned and unchanged.

## Local manual data

All files and detailed reports are outside Git at:

`/Users/asokmathews/Documents/service-manual-data/gm-usb-2026-09-15`

The inspection report lists the exact original, extracted, second-copy, recovery
and verification paths. No data was added to Repair Buddy's live database.
ZIP inputs are now excluded by this repo's `.gitignore`; future tests should
synthesize archives and future CI should extend its existing content guard.

## Important findings

- Three ZIPs labelled 6.0L, 6.6L and 8.1L; ordinary HTML exports with local
  images, SVG wiring, navigation trees and diagnostic tables.
- Readable indexes identify 2006 vehicles, not validated 2001–2006 coverage.
- Some source pages/captions qualify different engines/vehicles. Retain that
  context; selecting a book is not enough to establish applicability.
- 6.6L: 60,009 valid files extracted; 760 image files fail.
- 8.1L: 54,998 valid files extracted; 5,483 HTML files fail.
- Both of those copies match their USB SHA-256. The source archives are damaged.
- 6.0L: repeated USB-read hashes differ. Two local copies are preserved, both
  have invalid directory data; a separate recovery attempt is also invalid.
  No complete 6.0L extraction is available.

## Verification performed

- Copied all five files in the selected manual folder; performed source/copy
  hash checks and a separate 6.0L recopy/recheck.
- Read/CRC/length-checked every listed file in the 6.6L and 8.1L archives,
  extracted successful members and saved exact failures and file manifests.
- Inspected entry pages, script/style, navigation, procedures, tables, diagrams
  and source warnings. This was not a full browser/diagnostic acceptance test.
- Existing extractor suite: 59 tests pass; CLI help/version pass.
- Documentation whitespace and local document-link checks pass. New production
  adapter and integration tests remain planned.

## Next task

**Step 1: resolve source integrity**, preferably with a fresh seller/download
copy and reproducible validation. The user confirmed they have no separate
download and will contact the eBay seller for replacement files. Do not repeat
unbounded repair attempts against the current unstable USB.

If a reliable source is unavailable, explicitly carry the source blocker into
the handoff and work from synthetic fixtures when the user selects Step 2.
Do not mark real-manual acceptance complete on partially recovered content.

Model recommendations are in the step table: Terra Medium for routine adapter
work, Sol Medium/High for structure/integration, Luna Low for mechanical
checks/docs, and Astra High only for difficult unresolved design/review.
