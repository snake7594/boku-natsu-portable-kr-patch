#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path("work")))
import boku_tools  # noqa: E402


TRANSLATIONS = Path("work/translations_quality_v2.json")
EDITABLE = Path("work/translation_quality_v2/translation_quality_v2_editable.json")
TABLE = Path(os.environ.get("BOKU_AUDIT_TABLE", "work/quality_v2_patch/table_full_rough.txt"))
OUT_DIR = Path("work/translation_quality_v2")
REPORT_JSON = OUT_DIR / "quality_v2_rule_audit.json"
REPORT_MD = OUT_DIR / "quality_v2_rule_audit.md"

TOKEN_RE = re.compile(r"\{(?:PAUSE|RAW:[0-9A-Fa-f]+|[0-9A-Fa-f]{4})\}")
LAYOUT_MODE = os.environ.get("BOKU_LAYOUT_MODE", "")
MAX_PAGE_LINES = int(os.environ.get("BOKU_MAX_PAGE_LINES", "3"))
MAX_LINE_UNITS = int(os.environ.get("BOKU_MAX_LINE_UNITS", "15"))


def token_counts(text: str) -> dict[str, int]:
    return {
        "pause": text.count("{PAUSE}"),
        "raw": len(re.findall(r"\{RAW:[0-9A-Fa-f]+\}", text)),
        "glyph": len(re.findall(r"\{[0-9A-Fa-f]{4}\}", text)),
    }


def malformed_tokens(text: str) -> list[str]:
    bad = []
    for match in re.finditer(r"\{[^}]*\}|[{}]", text):
        token = match.group(0)
        if TOKEN_RE.fullmatch(token):
            continue
        bad.append(token)
    return bad


def visible_chars(text: str):
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = text.find("}", i + 1)
            if end != -1:
                i = end + 1
                continue
        ch = text[i]
        if ch != "\n":
            yield ch
        i += 1


def main() -> None:
    rows = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    editable = json.loads(EDITABLE.read_text(encoding="utf-8"))
    table = boku_tools.load_table(TABLE)
    chars = set(table.values())
    issues = []
    counts = {}

    for row, edit in zip(rows, editable):
        idx = edit["index"]
        ja = row["text"]
        ko = row.get("ko", "")
        def add(kind: str, detail: str):
            counts[kind] = counts.get(kind, 0) + 1
            issues.append(
                {
                    "index": idx,
                    "kind": kind,
                    "detail": detail,
                    "ja": ja,
                    "ko": ko,
                    "warnings": edit.get("warnings", []),
                }
            )

        if LAYOUT_MODE == "page3":
            source_pages = ja.split("{PAUSE}")
            ko_pages = ko.split("{PAUSE}")
            if len(ko_pages) > len(source_pages):
                add("page_count_overflow", f"{len(ko_pages)} > {len(source_pages)}")
            for page_index, ko_page in enumerate(ko_pages):
                source_units = boku_tools.layout_units(source_pages[page_index]) if page_index < len(source_pages) else [0]
                ko_units = boku_tools.layout_units(ko_page)
                allowed_lines = max(MAX_PAGE_LINES, len(source_units))
                allowed_width = max(MAX_LINE_UNITS, max(source_units or [0]))
                if len(ko_units) > allowed_lines:
                    add("line_count_overflow", f"page {page_index + 1}: {len(ko_units)} > {allowed_lines}")
                for line_index, ko_count in enumerate(ko_units):
                    if ko_count > allowed_width:
                        add("line_width_overflow", f"page {page_index + 1} line {line_index + 1}: {ko_count} > {allowed_width}")
        else:
            source_units = boku_tools.layout_units(ja)
            ko_units = boku_tools.layout_units(ko)
            if len(ko_units) > len(source_units):
                add("line_count_overflow", f"{len(ko_units)} > {len(source_units)}")
            for line_index, ko_count in enumerate(ko_units):
                source_count = source_units[line_index] if line_index < len(source_units) else 0
                if ko_count > source_count:
                    add("line_width_overflow", f"line {line_index + 1}: {ko_count} > {source_count}")

        bad_tokens = malformed_tokens(ko)
        if bad_tokens:
            add("malformed_token", ", ".join(bad_tokens[:5]))

        ja_tokens = token_counts(ja)
        ko_tokens = token_counts(ko)
        if ko_tokens["pause"] != ja_tokens["pause"]:
            add("pause_count_mismatch", f"{ko_tokens['pause']} != {ja_tokens['pause']}")
        if ko_tokens["raw"] != ja_tokens["pause"]:
            add("raw_marker_count_mismatch", f"{ko_tokens['raw']} != pauses {ja_tokens['pause']}")

        unsupported = sorted({ch for ch in visible_chars(ko) if ch not in chars})
        if unsupported:
            add("unsupported_char", "".join(unsupported[:20]))

        if any("truncated_line" in str(w) for w in edit.get("warnings", [])):
            add("truncated_line_warning", "translation was clipped to fit")
        if any("dropped_extra_lines" in str(w) for w in edit.get("warnings", [])):
            add("dropped_extra_lines_warning", "translation lost extra lines")
        if any("reflow_over_capacity" in str(w) for w in edit.get("warnings", [])):
            add("reflow_over_capacity_warning", "translation exceeded the 3-line page budget")
        if any("reflow_line_over_width" in str(w) for w in edit.get("warnings", [])):
            add("reflow_line_over_width_warning", "translation exceeded the per-line width budget")

        try:
            boku_tools.encode_dialog_text(ko, table, row["terminator_hex"])
        except Exception as exc:
            add("encode_failure", str(exc))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps({"counts": counts, "issues": issues}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# Quality V2 Rule Audit", "", "## Counts", ""]
    for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## First Issues", ""])
    for issue in issues[:80]:
        lines.append(f"- `{issue['kind']}` index={issue['index']} detail={issue['detail']}")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    print(REPORT_JSON)


if __name__ == "__main__":
    main()
