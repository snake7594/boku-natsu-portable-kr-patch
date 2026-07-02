#!/usr/bin/env python3
import json
import os
import shutil
from pathlib import Path

import boku_tools
import patch_system_text


ROOT = Path("work/cdimg0_extracted")
BASE_IDX = Path("work/build/cdimg.idx")
BASE_IMG = Path("work/build/cdimg0.img")
TRANSLATIONS = Path(os.environ.get("BOKU_TRANSLATIONS", "work/translations_rough_all.json"))
OUT_DIR = Path(os.environ.get("BOKU_PATCH_OUT_DIR", "work/full_rough_patch"))
REPLACEMENTS = Path(os.environ.get("BOKU_REPLACEMENTS", "work/replacements_full_rough"))
BUILD = Path(os.environ.get("BOKU_BUILD", "work/build_full_rough"))
BASE_TABLE = Path("work/Boku-no-Natsuyasumi/font/table.txt")

START_CODE = 1024
END_CODE = 2047


def is_korean_glyph(ch: str) -> bool:
    return "\uac00" <= ch <= "\ud7a3" or "\u3130" <= ch <= "\u318f"


def collect_glyph_chars() -> list[str]:
    items = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    chars = []
    seen = set()
    for item in items:
        for ch in boku_tools.iter_text_chars(item.get("ko", "")):
            if is_korean_glyph(ch) and ch not in seen:
                chars.append(ch)
                seen.add(ch)
    for text in patch_system_text.TRANSLATIONS.values():
        for ch in boku_tools.iter_text_chars(text):
            if is_korean_glyph(ch) and ch not in seen:
                chars.append(ch)
                seen.add(ch)
    return chars


def write_font_assets(chars: list[str]) -> tuple[Path, Path, dict[str, int]]:
    table = boku_tools.load_table(BASE_TABLE)
    codes = list(range(START_CODE, END_CODE + 1))
    if len(chars) > len(codes):
        raise ValueError(f"not enough glyph slots: need {len(chars)}, have {len(codes)}")
    glyphs = [{"code": code, "char": ch} for code, ch in zip(codes, chars)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    glyph_map = {
        "font": os.environ.get("BOKU_FONT", "C:/Windows/Fonts/malgun.ttf"),
        "font_size": int(os.environ.get("BOKU_FONT_SIZE", "13")),
        "glyph_max_width": int(os.environ.get("BOKU_GLYPH_MAX_WIDTH", "9")),
        "glyph_shift_x": int(os.environ.get("BOKU_GLYPH_SHIFT_X", "-3")),
        "glyph_shift_y": int(os.environ.get("BOKU_GLYPH_SHIFT_Y", "0")),
        "glyph_fill_hangul": os.environ.get("BOKU_GLYPH_FILL_HANGUL", "0") == "1",
        "glyph_fill_size": int(os.environ.get("BOKU_GLYPH_FILL_SIZE", "16")),
        "glyphs": glyphs,
    }
    glyph_path = OUT_DIR / "glyphs_full_rough.json"
    glyph_path.write_text(json.dumps(glyph_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = BASE_TABLE.read_text(encoding="utf-8").splitlines()
    for glyph in glyphs:
        lines.append(f"{glyph['code']:04d} = {glyph['char']}")
    table_path = OUT_DIR / "table_full_rough.txt"
    table_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return table_path, glyph_path, {g["char"]: g["code"] for g in glyphs}


def main() -> None:
    chars = collect_glyph_chars()
    table_path, glyph_path, hangul_codes = write_font_assets(chars)

    if REPLACEMENTS.exists():
        shutil.rmtree(REPLACEMENTS)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    REPLACEMENTS.mkdir(parents=True)
    BUILD.mkdir(parents=True)

    boku_tools.rebuild_scripts_raw(ROOT, table_path, TRANSLATIONS, REPLACEMENTS)
    boku_tools.patch_font_glyphs(
        ROOT / "01startup" / "startup.bin.gzx",
        table_path,
        glyph_path,
        REPLACEMENTS / "01startup" / "startup.bin.gzx",
        OUT_DIR / "table_full_rough_patched.txt",
    )

    ui_font = patch_system_text.load_ui_font()
    report = []
    for rel in [
        Path("map/models/system/saveload_normal.bin.gzx"),
        Path("map/models/system/saveload_favorite.bin.gzx"),
        Path("01startup/startup.bin.gzx"),
    ]:
        src = REPLACEMENTS / rel if (REPLACEMENTS / rel).exists() else ROOT / rel
        patch_system_text.patch_gzx_pack(src, REPLACEMENTS / rel, ui_font, hangul_codes, report)
    (OUT_DIR / "system_text_patch_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    boku_tools.rebuild_cdimg(
        BASE_IDX,
        BASE_IMG,
        ROOT,
        REPLACEMENTS,
        BUILD / "cdimg.idx",
        BUILD / "cdimg0.img",
    )
    print(f"glyphs={len(chars)} system_runs={len(report)}")
    print(BUILD / "cdimg.idx")
    print(BUILD / "cdimg0.img")


if __name__ == "__main__":
    main()
