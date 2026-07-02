# Boku no Natsuyasumi Portable KR Patch

PSP game `Boku no Natsuyasumi Portable` Korean patch project.

This repository contains the patch-building tools, Korean translation data, font/table data, stability audit reports, and xdelta release assets. It does not include the original game ISO, patched ISO, or extracted proprietary game binaries.

## Current Release

- Version: `v0.1.1-fixedpack`
- Original ISO MD5: `B4D363D59CB87E25AB76AFC5384CCA31`
- Patched ISO MD5 after applying xdelta: `CD2596F6BCAC02E1141049B3B4265BF0`
- Embedded `cdimg.idx` MD5: `A54FBD28004016AE810BCD1213DF5B20`
- Embedded `cdimg0.img` MD5: `48128F5D2122883912AD910005544795`

## Applying The Patch

Use the files in `release-assets/`.

1. Put your original ISO next to `apply_iso_patch.bat`.
2. Rename it to `Boku no Natsuyasumi Portable.iso`.
3. Run `apply_iso_patch.bat`.
4. The output ISO will be `Boku no Natsuyasumi Portable KR fixedpack v0.1.1.iso`.

## What v0.1.1 Fixes

The previous build could repack 12 `map/gz` members when translated dialog exceeded the original fixed dialog slot. That changed inner pack offsets/sizes and could cause PPSSPP idle/autoplay crashes or corrupted backgrounds.

This release rebuilds dialog data with relocation disabled. The final audit reports:

- Changed script files: 59
- Changed member/top rows audited: 392
- Inner pack offset/size changes after fix: 0
- Overflowing members fixed by spacing compaction only: 46 rows
- Content trimming required: 0 rows

## Important Limitation

Save/load system text patching is intentionally excluded in this release because the current system text patch path contains mojibake and is not safe enough for a public build.

## Directory Layout

- `tools/`: extraction, analysis, rebuild, font, and audit scripts.
- `translations/`: editable and build-ready Korean translation JSON.
- `font/`: font table and glyph mapping used by the current build.
- `reports/`: stability and fixed-pack audit reports.
- `release-assets/`: xdelta patch, checksum file, and patch helper script.

## Notes

This is a fan-translation research project. You need your own legally obtained original ISO to apply the patch.
