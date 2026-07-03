@echo off
setlocal
cd /d "%~dp0"

set "SOURCE_ISO=Boku no Natsuyasumi Portable.iso"
set "PATCH_FILE=Boku_no_Natsuyasumi_Portable_KR_pause_guard_v0.1.2.iso.xdelta"
set "OUTPUT_ISO=Boku no Natsuyasumi Portable KR pause-guard v0.1.2.iso"

if not exist "%SOURCE_ISO%" (
  echo [ERROR] Put the original "%SOURCE_ISO%" in this folder.
  pause
  exit /b 1
)

if exist "%OUTPUT_ISO%" del /f /q "%OUTPUT_ISO%"

"xdelta.exe" -f -d -s "%SOURCE_ISO%" "%PATCH_FILE%" "%OUTPUT_ISO%"
if errorlevel 1 (
  echo [ERROR] Failed to patch ISO.
  pause
  exit /b 1
)

echo Patch complete: "%OUTPUT_ISO%"
pause
