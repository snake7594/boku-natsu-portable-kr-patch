# v0.1.1-fixedpack

## Summary

Stability-focused Korean patch release for `Boku no Natsuyasumi Portable`.

## Changes

- Rebuilt Korean dialog with `{PAUSE:hhhh}` trailing zero disabled to avoid unwanted first-cell blanks on page 2/3.
- Disabled internal dialog pack relocation by default.
- Rebuilt the patch so all changed `map/gz` members preserve original inner pack offsets and sizes.
- Kept Korean startup font patch.
- Excluded unsafe save/load system text patching.

## Validation

- Original ISO MD5: `B4D363D59CB87E25AB76AFC5384CCA31`
- Patched ISO MD5: `CD2596F6BCAC02E1141049B3B4265BF0`
- xdelta MD5: `FF780A355506B848C16FD4CBD30B6CAF`
- `cdimg.idx` MD5: `A54FBD28004016AE810BCD1213DF5B20`
- `cdimg0.img` MD5: `48128F5D2122883912AD910005544795`
- xdelta apply verification: passed
- Inner pack offset/size audit: 0 bad rows

## Assets

- `Boku_no_Natsuyasumi_Portable_KR_fixedpack_v0.1.1.iso.xdelta`
- `apply_iso_patch.bat`
- `checksums.md`
- `README_KO.txt`
- `xdelta.exe`

The patched ISO itself is not distributed.
