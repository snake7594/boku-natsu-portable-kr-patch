#!/usr/bin/env python3
import json
import re
from pathlib import Path


SIMPLE = Path("outputs/translation_edit_simple_resolved_reflow15_noreloc.json")
META = Path("outputs/translation_edit_simple_resolved_reflow15_noreloc.meta.json")
OUT = Path("outputs/translation_structured_v3_reflow15.json")
REPORT = Path("outputs/translation_structured_v3_reflow15_report.json")
README = Path("outputs/translation_structured_v3_README.md")

JA_SOURCE = "\uc77c\ubcf8\uc5b4_\uc6d0\ubb38"
JA_DIALOG = "\uc77c\ubcf8\uc5b4_\ub300\uc0ac"
KO_TRANSLATION = "\ud55c\uad6d\uc5b4_\ubc88\uc5ed"
KO_INSERT = "\ud55c\uad6d\uc5b4_\uc0bd\uc785"

FULL_SPACE = "\u3000"
MAX_LINE_UNITS = 15
MAX_PAGE_LINES = 3
CHOICE_TERMINATORS = {"FFFF", "0180"}
PAUSE_RE = re.compile(r"\{PAUSE(?::([0-9A-Fa-f]{4}))?\}")
TOKEN_RE = re.compile(r"\{(?:PAUSE(?::[0-9A-Fa-f]{4})?|RAW:[0-9A-Fa-f]+|SEG:0000|CTRL:[0-9A-Fa-f]{4}|[0-9A-Fa-f]{4})\}")


def normalize_newlines(text: str) -> str:
    return (text or "").replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")


def visible_text(text: str, keep_spaces: bool = True) -> str:
    text = TOKEN_RE.sub(" ", normalize_newlines(text))
    text = text.replace(FULL_SPACE, " ")
    if keep_spaces:
        text = text.replace("\n", " ")
        text = re.sub(r"[ \t]+", " ", text)
    else:
        text = re.sub(r"[ \t\n]+", "", text)
    return text.strip()


def split_with_pauses(text: str) -> tuple[list[str], list[dict]]:
    text = normalize_newlines(text)
    pages = []
    waits = []
    last = 0
    for match in PAUSE_RE.finditer(text):
        pages.append(text[last:match.start()])
        raw = match.group(1)
        value = int(raw, 16) if raw else None
        waits.append(
            {
                "\ud1a0\ud070": match.group(0),
                "\uac12_hex": raw,
                "\uac12_dec": value,
                "\ucd08_60fps": round(value / 60, 3) if value is not None else None,
                "\uc6a9\ub3c4": "\uc774\uc804 \ud398\uc774\uc9c0 \uc790\ub3d9 \ub118\uae40/\ub300\uae30 \uc2dc\uac04",
            }
        )
        last = match.end()
    pages.append(text[last:])
    return pages, waits


def line_units(line: str) -> int:
    count = 0
    i = 0
    while i < len(line):
        if line[i] == "{":
            end = line.find("}", i + 1)
            if end != -1:
                i = end + 1
                continue
        count += 1
        i += 1
    return count


def page_lines(page: str) -> list[str]:
    return normalize_newlines(page).splitlines() or [normalize_newlines(page)]


def nonempty_lines(text: str) -> list[str]:
    return [line for line in page_lines(text) if visible_text(line, keep_spaces=False)]


def analyze_page(page: str, enforce_max_lines: bool = True) -> dict:
    lines = page_lines(page)
    lengths = [line_units(line) for line in lines]
    issues = []
    if enforce_max_lines and len(lines) > MAX_PAGE_LINES:
        issues.append(f"line_count {len(lines)} > {MAX_PAGE_LINES}")
    for line_no, length in enumerate(lengths, 1):
        if length > MAX_LINE_UNITS:
            issues.append(f"line {line_no} length {length} > {MAX_LINE_UNITS}")
    return {
        "\ud14d\uc2a4\ud2b8": normalize_newlines(page),
        "\uc2dc\uc57c\ud14d\uc2a4\ud2b8": visible_text(page),
        "\uc904": lines,
        "\uc904\uc218": len(lines),
        "\uc904\uae38\uc774": lengths,
        "\ubb38\uc81c": issues,
    }


def classify(row: dict, meta: dict, ja_pages: list[str], ko_pages: list[str]) -> list[str]:
    ja = row[JA_SOURCE]
    visible = visible_text(ja, keep_spaces=False)
    labels = []
    if len(ja_pages) > 1:
        labels.append("paged_dialog")
    else:
        labels.append("single_page")
    if "「" in visible or "\u300e" in visible:
        labels.append("speaker_dialog")
    if len(visible) <= 32 and "「" not in visible and "\u300e" not in visible:
        labels.append("short_text_or_choice")
    if any(ch in visible for ch in "？?"):
        labels.append("question")
    if len(visible) <= 48 and ("\n" in ja or "/" in ja):
        labels.append("menu_or_choice_candidate")
    if meta.get("terminator_hex", "").upper() in CHOICE_TERMINATORS:
        labels.append("choice_terminator")
    if len(visible) >= 20 and sum(1 for ch in visible if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff") == 0:
        labels.append("symbol_table_or_non_dialog")
    if len(ko_pages) != len(ja_pages):
        labels.append("page_count_mismatch")
    return labels


def build_entry(index: int, row: dict, meta: dict) -> tuple[dict, list[dict]]:
    ja_pages, waits = split_with_pauses(row[JA_SOURCE])
    ko_pages, ko_waits = split_with_pauses(row.get(KO_INSERT, ""))
    issues = []
    if len(ko_pages) != len(ja_pages):
        issues.append(
            {
                "\uc885\ub958": "page_count_mismatch",
                "\uc124\uba85": f"ko pages {len(ko_pages)} != ja pages {len(ja_pages)}",
            }
        )
    if [w.get("\uac12_hex") for w in ko_waits] != [w.get("\uac12_hex") for w in waits]:
        issues.append(
            {
                "\uc885\ub958": "pause_wait_mismatch",
                "\uc124\uba85": "Korean insertion must preserve Japanese {PAUSE:hhhh} values and order.",
            }
        )

    ja_page_items = []
    ko_page_items = []
    for page_index, page in enumerate(ja_pages):
        item = analyze_page(page)
        item["\ubc88\ud638"] = page_index + 1
        if page_index < len(waits):
            item["\ub2e4\uc74c\ud398\uc774\uc9c0_\ub300\uae30"] = waits[page_index]
        ja_page_items.append(item)

    for page_index, page in enumerate(ko_pages):
        terminator_hex = meta.get("terminator_hex", "").upper()
        choice_like = terminator_hex in CHOICE_TERMINATORS and len(ja_pages) == 1
        item = analyze_page(page, enforce_max_lines=not choice_like)
        item["\ubc88\ud638"] = page_index + 1
        if page_index < len(ko_waits):
            item["\ub2e4\uc74c\ud398\uc774\uc9c0_\ub300\uae30"] = ko_waits[page_index]
        for problem in item["\ubb38\uc81c"]:
            issues.append(
                {
                    "\uc885\ub958": "layout",
                    "\ud398\uc774\uc9c0": page_index + 1,
                    "\uc124\uba85": problem,
                }
            )
        if page_index < len(ja_pages):
            ja_visible = visible_text(ja_pages[page_index], keep_spaces=False)
            ko_visible = visible_text(page, keep_spaces=False)
            if ja_visible and not ko_visible:
                issues.append(
                    {
                        "\uc885\ub958": "empty_translated_page",
                        "\ud398\uc774\uc9c0": page_index + 1,
                        "\uc124\uba85": "Japanese page has visible text but Korean insertion page is empty.",
                    }
                )
        ko_page_items.append(item)

    labels = classify(row, meta, ja_pages, ko_pages)
    is_choice_terminator = meta.get("terminator_hex", "").upper() in CHOICE_TERMINATORS and len(ja_pages) == 1
    ja_choice_lines = nonempty_lines(ja_pages[0]) if is_choice_terminator else []
    ko_choice_lines = nonempty_lines(ko_pages[0]) if is_choice_terminator and ko_pages else []
    if is_choice_terminator:
        ja_line_count = len(ja_choice_lines)
        ko_line_count = len(ko_choice_lines)
        if ja_line_count != ko_line_count:
            issues.append(
                {
                    "\uc885\ub958": "choice_line_count_mismatch",
                    "\uc124\uba85": f"ko choice lines {ko_line_count} != source {ja_line_count}",
                }
            )
    entry = {
        "\uc778\ub371\uc2a4": index,
        "id": f"{meta['script']}|{meta['pack_member']}|{meta['dialog_id']}|{meta['block_index']}|{meta['element_index']}",
        "\uc704\uce58": {
            "script": meta["script"],
            "pack_index": meta["pack_index"],
            "pack_member": meta["pack_member"],
            "dialog_id": meta["dialog_id"],
            "block_index": meta["block_index"],
            "element_index": meta["element_index"],
            "text_offset": meta["text_offset"],
            "key": meta.get("key", ""),
        },
        "\ubd84\ub958": labels,
        "\uc81c\uc57d": {
            "\ud55c\uc904_\ucd5c\ub300": MAX_LINE_UNITS,
            "\ud398\uc774\uc9c0_\ucd5c\ub300\uc904": MAX_PAGE_LINES,
            "\ud398\uc774\uc9c0\uc218_\ubcf4\uc874": True,
            "\ub300\uae30\uac12_\ubcf4\uc874": True,
            "\uc6d0\ubb38_\uc904\ubc14\uafc8_\ubcf4\uc874": is_choice_terminator,
            "\uc694\uc18c\uc885\ub8cc": meta.get("terminator_hex", ""),
        },
        "\uc77c\ubcf8\uc5b4": {
            "\uc6d0\ubb38": row[JA_SOURCE],
            "\ub300\uc0ac": row[JA_DIALOG],
            "\ud398\uc774\uc9c0": ja_page_items,
            "\uc120\ud0dd\uc9c0": ja_choice_lines,
        },
        "\ud55c\uad6d\uc5b4": {
            "\ubc88\uc5ed": row[KO_TRANSLATION],
            "\uc120\ud0dd\uc9c0": ko_choice_lines,
            "\uc0bd\uc785": row.get(KO_INSERT, ""),
            "\ud398\uc774\uc9c0": ko_page_items,
        },
        "\ubb38\uc81c": issues,
    }
    return entry, issues


def main() -> None:
    rows = json.loads(SIMPLE.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    if len(rows) != len(meta):
        raise ValueError(f"row count mismatch: {len(rows)} != {len(meta)}")

    entries = []
    issue_rows = []
    label_counts = {}
    for index, (row, info) in enumerate(zip(rows, meta)):
        entry, issues = build_entry(index, row, info)
        entries.append(entry)
        for label in entry["\ubd84\ub958"]:
            label_counts[label] = label_counts.get(label, 0) + 1
        if issues:
            issue_rows.append(
                {
                    "\uc778\ub371\uc2a4": index,
                    "id": entry["id"],
                    "\ubd84\ub958": entry["\ubd84\ub958"],
                    "\ubb38\uc81c": issues,
                }
            )

    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "rows": len(entries),
        "issue_rows": len(issue_rows),
        "label_counts": label_counts,
        "issues": issue_rows[:500],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    README.write_text(
        "\n".join(
            [
                "# Translation Structured V3",
                "",
                "Edit source:",
                "",
                "- `outputs/translation_structured_v3_reflow15.json`",
                "",
                "Important fields:",
                "",
                "- `일본어.원문`: original source with `{PAUSE:hhhh}` page waits.",
                "- `일본어.페이지[]`: source split by page. `다음페이지_대기` belongs to the previous page.",
                "- `한국어.번역`: pure Korean translation. Edit this text, not the inserted text.",
                "- `한국어.삽입`: generated game text with page breaks, waits, and line breaks.",
                "- `한국어.선택지`: for rows labeled `choice_terminator`, edit this list to preserve one option per source line.",
                "- `한국어.페이지[]`: insertion split by page, with line lengths and layout issues.",
                "- `문제`: structural problems to fix before building.",
                "",
                "Workflow:",
                "",
                "1. Edit only `한국어.번역` in `translation_structured_v3_reflow15.json`.",
                "2. Run `python work/sync_translation_structured_v3.py`.",
                "3. Check `translation_structured_v3_reflow15_report.json`.",
                "4. Build only when `issue_rows` is 0, or when the remaining rows are intentionally exempted.",
                "",
                "Rules:",
                "",
                "- Preserve page count.",
                "- Preserve `{PAUSE:hhhh}` values and order.",
                "- Korean insertion pages must be max 15 units per line and max 3 lines per page.",
                "- Rows ending with `FFFF` or `0180` are treated as choice/menu terminators; preserve the source line breaks.",
                "- `8000` element endings are not represented as editable text. Do not merge separate JSON entries.",
                "- Choice/menu-like rows are labeled; keep them short and do not append following response text.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(OUT)
    print(REPORT)
    print(json.dumps({k: report[k] for k in ["rows", "issue_rows", "label_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
