# Pause Guard Fixed-Pack Build Status

Date: 2026-07-03

## Purpose

Fix the page 2/3 first-character loss introduced by the previous no-pause-zero build.

## Cause

The previous build removed the `0000` word after `{PAUSE:hhhh}`. In-game, that word appears to be consumed as a page-start guard. Without it, the engine can consume the first visible Korean character of the next page.

## Fix

- Restored `{PAUSE:hhhh}` encoding to `8002 hhhh 0000`.
- Kept literal Korean text free of intentional leading spaces after `{PAUSE}`.
- Rebuilt with internal dialog relocation disabled.
- Fit all overflowing members by spacing compaction only. No content trimming was required.

## Validation

- Changed script files: 59.
- Changed member/top rows audited: 392.
- Inner pack offset/size changes after fix: 0.
- Pause sample verifies `8002 hhhh 0000`.
- Space compaction actions: 80 total.
- Tail/content trim actions: 0.

## Build

- Build directory: `work/build_pause_guard_fixedpack`
- `cdimg.idx` MD5: `A54FBD28004016AE810BCD1213DF5B20`
- `cdimg0.img` MD5: `784B13BBC5A045756A540B21F7C23614`

## Applied Game Directory

- `C:\Users\Jae Ho Lee\Pictures\psp\roms\Boku no Natsuyasumi Portable\PSP_GAME\USRDIR\cdimg.idx`
- `C:\Users\Jae Ho Lee\Pictures\psp\roms\Boku no Natsuyasumi Portable\PSP_GAME\USRDIR\cdimg0.img`

Backup before applying:

- `cdimg.pre_20260703_pause_guard_fixedpack.idx`
- `cdimg0.pre_20260703_pause_guard_fixedpack.img`
