# Fixed-Pack Minimal No-Pause-Zero Build Status

Date: 2026-07-02

## Purpose

Stabilize the Korean dialogue build after PPSSPP idle/autoplay crashes and house background corruption.

## Main Finding

The previous no-pause-zero build silently repacked 12 `map/gz` members because their rebuilt dialog payloads exceeded the original fixed dialog slot. That changed inner pack offsets/sizes and could corrupt resources or script reads.

## Fix

- Rebuilt with `BOKU_PAUSE_TRAILING_ZERO=0`.
- Rebuilt with relocation disabled.
- Set `work/boku_tools.py` default relocation policy to disabled.
- Preserved stable `cdimg.idx` layout.
- Kept startup Korean font patch.
- Skipped unsafe save/load system text patching.
- For the 12 overflowing members, compacted only spaces in 46 rows; no content trimming was required.

## Validation

- No-relocation failure list before fix: `outputs/no_relocation_failures_no_pause_zero.json`.
- Minimal fit report: `outputs/fixedpack_minimal_fit_report.json`.
- Static member audit after fix: `outputs/fixedpack_minimal_static_member_audit.json`.
- Changed script files: 59.
- Changed member/top rows audited: 392.
- Inner pack offset/size changes after fix: 0.

## Build

- Build directory: `work/build_fixedpack_minimal_no_pause_zero`
- `cdimg.idx` MD5: `A54FBD28004016AE810BCD1213DF5B20`
- `cdimg0.img` MD5: `48128F5D2122883912AD910005544795`

## Applied Game Directory

- `C:\Users\Jae Ho Lee\Pictures\psp\roms\Boku no Natsuyasumi Portable\PSP_GAME\USRDIR\cdimg.idx`
- `C:\Users\Jae Ho Lee\Pictures\psp\roms\Boku no Natsuyasumi Portable\PSP_GAME\USRDIR\cdimg0.img`

Backup before applying:

- `cdimg.pre_20260702_fixedpack_minimal_no_pause_zero.idx`
- `cdimg0.pre_20260702_fixedpack_minimal_no_pause_zero.img`
