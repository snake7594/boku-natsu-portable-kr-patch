#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boku_tools


PATCH = Path("outputs/translations_quality_v2_resolved_reflow15_noreloc.json")
EDITABLE = Path("outputs/translation_quality_v2_editable_resolved_reflow15_noreloc.json")
REPORT = Path("outputs/resolved_reflow15_noreloc_layout_fixes.json")
FULL_SPACE = "\u3000"
WIDTH = 15
RAW_RE = re.compile(r"^(?:\{RAW:[0-9A-Fa-f]+\})+")


def units(text: str) -> int:
    return boku_tools.layout_units(text)[0]


def split_page_prefix(page: str) -> tuple[str, str]:
    match = RAW_RE.match(page)
    if not match:
        return "", page
    return match.group(0), page[match.end() :]


def wrap_visible(text: str, width: int, max_lines: int) -> list[str]:
    text = text.replace("\n", FULL_SPACE)
    text = re.sub(f"{FULL_SPACE}+", FULL_SPACE, text).strip(FULL_SPACE)
    if not text:
        return [""]

    lines: list[str] = []
    line = ""
    for piece in re.split(f"({FULL_SPACE})", text):
        if piece == "":
            continue
        candidate = line + piece
        if line and units(candidate) > width:
            lines.append(line.strip(FULL_SPACE))
            line = piece.strip(FULL_SPACE)
        else:
            line = candidate
    if line:
        lines.append(line.strip(FULL_SPACE))

    if len(lines) <= max_lines and all(units(line) <= width for line in lines):
        return lines

    compact = text.replace(FULL_SPACE, "")
    compact_lines = [compact[i : i + width] for i in range(0, len(compact), width)] or [""]
    if len(compact_lines) <= max_lines:
        return compact_lines

    # Preserve all content, but pack the remainder onto the final line. The
    # caller will keep auditing; this path documents genuinely overfull pages.
    return compact_lines[: max_lines - 1] + ["".join(compact_lines[max_lines - 1 :])]


def fix_text(row: dict) -> tuple[str, list[str]]:
    ko_pages = row.get("ko", "").split("{PAUSE}")
    source_pages = row.get("text", "").split("{PAUSE}")
    changed = []
    fixed_pages = []
    for idx, page in enumerate(ko_pages):
        source_units = boku_tools.layout_units(source_pages[idx]) if idx < len(source_pages) else [0]
        width = max(WIDTH, max(source_units or [0]))
        max_lines = max(3, len(source_units))
        if len(boku_tools.layout_units(page)) <= max_lines and all(u <= width for u in boku_tools.layout_units(page)):
            fixed_pages.append(page)
            continue
        prefix, body = split_page_prefix(page)
        lines = wrap_visible(body, width, max_lines)
        rebuilt = prefix + "\n".join(lines)
        fixed_pages.append(rebuilt)
        changed.append(f"page{idx + 1}:{width}x{max_lines}")
    return "{PAUSE}".join(fixed_pages), changed


def main() -> None:
    os.environ["BOKU_LAYOUT_MODE"] = "page3"
    os.environ["BOKU_MAX_LINE_UNITS"] = str(WIDTH)
    os.environ["BOKU_MAX_PAGE_LINES"] = "3"
    rows = json.loads(PATCH.read_text(encoding="utf-8"))
    fixes = []
    for idx, row in enumerate(rows):
        try:
            boku_tools.validate_layout(row)
            continue
        except Exception as before:
            new_ko, changed = fix_text(row)
            old_ko = row.get("ko", "")
            row["ko"] = new_ko
            row["status"] = "resolved_reflow15_noreloc_layout_autofix"
            try:
                boku_tools.validate_layout(row)
                after = ""
            except Exception as exc:
                after = str(exc)
            fixes.append(
                {
                    "index": idx,
                    "script": row["script"],
                    "pack_member": row["pack_member"],
                    "dialog_id": row["dialog_id"],
                    "element_index": row["element_index"],
                    "changed": changed,
                    "before_error": str(before),
                    "after_error": after,
                    "old_ko": old_ko,
                    "new_ko": new_ko,
                }
            )
    PATCH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if EDITABLE.exists():
        edits = json.loads(EDITABLE.read_text(encoding="utf-8"))
        by_key = {
            (row["script"], row["pack_member"], int(row["dialog_id"]), int(row["block_index"]), int(row["element_index"])): row
            for row in rows
        }
        for edit in edits:
            row = by_key.get(
                (
                    edit["script"],
                    edit["member"],
                    int(edit["dialog_id"]),
                    int(edit["block_index"]),
                    int(edit["element_index"]),
                )
            )
            if row:
                edit["ko_game"] = row["ko"]
                if row.get("status") == "resolved_reflow15_noreloc_layout_autofix":
                    edit["status"] = row["status"]
                    warnings = list(edit.get("warnings", []))
                    if "resolved_layout_autofix:line15" not in warnings:
                        warnings.append("resolved_layout_autofix:line15")
                    edit["warnings"] = warnings
        EDITABLE.write_text(json.dumps(edits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    remaining = [fix for fix in fixes if fix["after_error"]]
    REPORT.write_text(
        json.dumps({"fixes": fixes, "remaining": remaining}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"fixed": len(fixes), "remaining": len(remaining)}, ensure_ascii=False))
    if remaining:
        for item in remaining[:20]:
            print(item["index"], item["after_error"])


if __name__ == "__main__":
    main()
