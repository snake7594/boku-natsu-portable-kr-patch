#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boku_tools


SIMPLE = Path("outputs/translation_edit_simple_resolved_reflow15_noreloc.json")
META = Path("outputs/translation_edit_simple_resolved_reflow15_noreloc.meta.json")
OUT_PATCH = Path("outputs/translations_quality_v2_resolved_reflow15_noreloc.json")
OUT_REPORT = Path("outputs/translation_edit_simple_sync_report.json")

JA_SOURCE = "\uc77c\ubcf8\uc5b4_\uc6d0\ubb38"
JA_DIALOG = "\uc77c\ubcf8\uc5b4_\ub300\uc0ac"
KO_TRANSLATION = "\ud55c\uad6d\uc5b4_\ubc88\uc5ed"
KO_INSERT = "\ud55c\uad6d\uc5b4_\uc0bd\uc785"

FULL_SPACE = "\u3000"
MAX_WIDTH = 15
MAX_LINES = 3
CHOICE_TERMINATORS = {"FFFF", "0180"}
TOKEN_RE = re.compile(r"\{(?:PAUSE(?::[0-9A-Fa-f]{4})?|RAW:[0-9A-Fa-f]+|SEG:0000|CTRL:[0-9A-Fa-f]{4}|[0-9A-Fa-f]{4})\}")
PAUSE_WITH_RAW_RE = re.compile(r"\{PAUSE(?::[0-9A-Fa-f]{4})?\}(?:\{RAW:[0-9A-Fa-f]+\})?")
PAUSE_SOURCE_RE = re.compile(r"\{PAUSE(?::[0-9A-Fa-f]{4})?\}")
ASCII_TO_FULLWIDTH = str.maketrans(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
)


def visible_compact(text: str) -> str:
    text = TOKEN_RE.sub("", text or "")
    text = text.replace("\n", "")
    text = text.replace(FULL_SPACE, "")
    text = re.sub(r"\s+", "", text)
    return text.strip()


def normalize_edit(text: str) -> str:
    text = TOKEN_RE.sub("", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = (
        text.replace(",", "\u3001")
        .replace(".", "\uff0e")
        .replace("?", "\uff1f")
        .replace("!", "\uff01")
        .replace(":", "\uff1a")
        .replace(";", "\uff1b")
        .replace("~", "")
        .replace("\u301c", "")
        .replace("\uff5e", "")
        .replace("(", "\uff08")
        .replace(")", "\uff09")
        .replace("/", "\uff0f")
        .replace("\u00b7", "\u30fb")
        .replace("-", "\u30fc")
    )
    text = text.translate(ASCII_TO_FULLWIDTH)
    text = text.replace("\n", " ")
    text = text.replace(FULL_SPACE, " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()
    return text.replace(" ", FULL_SPACE)


def normalize_choice_line(text: str) -> str:
    return normalize_edit(text).replace("\n", FULL_SPACE).strip(FULL_SPACE)


def normalize_insert_punctuation(text: str) -> str:
    return (
        (text or "")
        .replace(",", "\u3001")
        .replace(".", "\uff0e")
        .replace("?", "\uff1f")
        .replace("!", "\uff01")
        .replace(":", "\uff1a")
        .replace(";", "\uff1b")
        .replace("~", "")
        .replace("\u301c", "")
        .replace("\uff5e", "")
        .replace("(", "\uff08")
        .replace(")", "\uff09")
        .replace("/", "\uff0f")
        .replace("\u00b7", "\u30fb")
        .replace("-", "\u30fc")
    ).translate(ASCII_TO_FULLWIDTH)


def source_pages(ja_source: str) -> list[str]:
    return PAUSE_SOURCE_RE.split(ja_source)


def build_text_for_validation(ja_source: str) -> str:
    return PAUSE_SOURCE_RE.sub("{PAUSE}", ja_source)


def pause_tokens(existing_insert: str, page_count: int) -> list[str]:
    needed = max(0, page_count - 1)
    return PAUSE_SOURCE_RE.findall(existing_insert or "")[:needed]


def source_pause_tokens(ja_source: str) -> list[str]:
    return PAUSE_SOURCE_RE.findall(ja_source or "")


def source_visible_lines(ja_source: str) -> list[str]:
    cleaned = TOKEN_RE.sub("", ja_source or "")
    lines = [line.replace(FULL_SPACE, " ").strip() for line in cleaned.splitlines()]
    return [line for line in lines if line]


def unit_len(text: str) -> int:
    return boku_tools.layout_units(text)[0]


def split_words(text: str) -> list[str]:
    text = text.replace("\n", FULL_SPACE)
    parts = [part for part in re.split(f"({FULL_SPACE}+)", text) if part]
    return parts or [""]


def page_budget(ja_page: str) -> tuple[int, int]:
    source_units = boku_tools.layout_units(TOKEN_RE.sub("", ja_page))
    width = MAX_WIDTH
    lines = max(MAX_LINES, len(source_units))
    return width, lines


def text_units(text: str) -> int:
    return unit_len(text.replace("\n", ""))


def slice_by_units(text: str, units: int) -> tuple[str, str]:
    if units <= 0:
        return "", text
    if text_units(text) <= units:
        return text, ""
    return text[:units], text[units:]


def split_page_chunk(text: str, units: int, min_units: int = 0) -> tuple[str, str]:
    text = text.strip(FULL_SPACE)
    if text_units(text) <= units:
        return text, ""
    hard, rest = slice_by_units(text, units)
    search_start = max(min_units, units // 2)
    split_at = -1
    for idx, ch in enumerate(hard):
        if idx + 1 >= search_start and ch == FULL_SPACE:
            split_at = idx
    if split_at > 0:
        left = hard[:split_at].strip(FULL_SPACE)
        right = (hard[split_at + 1 :] + rest).strip(FULL_SPACE)
        if left:
            return left, right
    return hard.strip(FULL_SPACE), rest.strip(FULL_SPACE)


def page_capacity(ja_page: str) -> int:
    width, lines = page_budget(ja_page)
    return width * min(lines, MAX_LINES)


def distribute(text: str, pages: list[str]) -> list[str]:
    if len(pages) <= 1:
        return [text]

    source_weights = []
    for page in pages:
        visible = TOKEN_RE.sub("", page).replace("\n", "").replace(FULL_SPACE, "")
        source_weights.append(max(1, len(visible)))
    source_total = sum(source_weights) or len(pages)
    total_units = text_units(text)

    out = []
    remaining_text = text.strip(FULL_SPACE)
    consumed_units = 0
    consumed_weight = 0
    capacities = [page_capacity(page) for page in pages]
    for page_index in range(len(pages) - 1):
        consumed_weight += source_weights[page_index]
        capacity = capacities[page_index]
        remaining_capacity = sum(capacities[page_index + 1 :])
        remaining_units = text_units(remaining_text)
        minimum_take = max(0, remaining_units - remaining_capacity)
        target_cumulative = round(total_units * consumed_weight / source_total)
        desired = target_cumulative - consumed_units
        desired = max(minimum_take, min(capacity, desired))
        if desired <= 0 and TOKEN_RE.sub("", pages[page_index]).strip() and remaining_units:
            desired = min(capacity, remaining_units)
        chunk, remaining_text = split_page_chunk(remaining_text, desired, minimum_take)
        out.append(chunk)
        consumed_units += text_units(chunk)
    out.append(remaining_text.strip(FULL_SPACE))

    # If a later source page contains visible text, avoid generating an empty
    # Korean page. Move one trailing word from the previous page when possible.
    for i in range(1, len(out)):
        source_visible = TOKEN_RE.sub("", pages[i]).replace("\n", "").strip()
        if not source_visible or out[i].strip(FULL_SPACE):
            continue
        for prev in range(i - 1, -1, -1):
            prev_parts = split_words(out[prev])
            real_parts = [p for p in prev_parts if p.strip(FULL_SPACE)]
            if len(real_parts) <= 1:
                continue
            moved = real_parts[-1]
            out[prev] = FULL_SPACE.join(real_parts[:-1])
            out[i] = moved
            break
    return out


def wrap_page(text: str, width: int, max_lines: int) -> str:
    parts = split_words(text)
    lines = []
    line = ""
    for part in parts:
        candidate = line + part
        if line and unit_len(candidate) > width:
            lines.append(line.strip(FULL_SPACE))
            line = part.strip(FULL_SPACE)
        else:
            line = candidate
    if line:
        lines.append(line.strip(FULL_SPACE))
    if len(lines) <= max_lines and all(unit_len(line) <= width for line in lines):
        return "\n".join(lines)
    compact = text.replace(FULL_SPACE, "").replace("\n", "")
    lines = [compact[i : i + width] for i in range(0, len(compact), width)] or [""]
    return "\n".join(lines)


def distribute_choice_lines(ja_source: str, ko_translation: str) -> list[str]:
    source_lines = source_visible_lines(ja_source)
    line_count = max(1, len(source_lines))
    raw_lines = [
        normalize_choice_line(line)
        for line in (ko_translation or "").replace("\r\n", "\n").replace("\r", "\n").splitlines()
        if line.strip()
    ]
    if len(raw_lines) == line_count:
        return raw_lines

    normalized = normalize_edit(ko_translation)
    parts = split_words(normalized)
    weights = [max(1, len(line.replace(" ", ""))) for line in source_lines] or [1]
    total_weight = sum(weights)
    total_units = text_units(normalized)
    out = []
    current = ""
    part_index = 0
    consumed_weight = 0
    for line_index in range(line_count - 1):
        consumed_weight += weights[line_index]
        target_units = max(1, round(total_units * consumed_weight / total_weight))
        remaining_lines = line_count - line_index - 1
        while part_index < len(parts):
            remaining_parts = len(parts) - part_index
            if remaining_parts <= remaining_lines:
                break
            candidate = current + parts[part_index]
            if current and text_units(candidate) >= target_units:
                break
            current = candidate
            part_index += 1
        if not current and part_index < len(parts):
            current = parts[part_index]
            part_index += 1
        out.append(current.strip(FULL_SPACE))
        current = ""
    while part_index < len(parts):
        current += parts[part_index]
        part_index += 1
    out.append(current.strip(FULL_SPACE))
    while len(out) < line_count:
        out.append("")
    return out[:line_count]


def make_choice_insert(ja_source: str, ko_translation: str, terminator_hex: str) -> str:
    lines = distribute_choice_lines(ja_source, ko_translation)
    text = "\n".join(lines)
    if terminator_hex.upper() == "FFFF" and ja_source.endswith("\n"):
        text += "\n"
    return text


def make_insert(ja_source: str, ko_translation: str, existing_insert: str, info: dict | None = None) -> str:
    terminator_hex = (info or {}).get("terminator_hex", "").upper()
    if terminator_hex in CHOICE_TERMINATORS and not PAUSE_SOURCE_RE.search(ja_source):
        return make_choice_insert(ja_source, ko_translation, terminator_hex)
    pages = source_pages(ja_source)
    tokens = source_pause_tokens(ja_source)
    if len(tokens) < len(pages) - 1:
        tokens = pause_tokens(existing_insert, len(pages))
    if len(tokens) < len(pages) - 1:
        tokens = tokens + ["{PAUSE}"] * (len(pages) - 1 - len(tokens))
    normalized = normalize_edit(ko_translation)
    distributed = distribute(normalized, pages)
    wrapped = []
    for page, ko_page in zip(pages, distributed):
        width, lines = page_budget(page)
        wrapped.append(wrap_page(ko_page, width, lines))
    out = []
    for index, page in enumerate(wrapped):
        out.append(page)
        if index < len(tokens):
            out.append(tokens[index])
    return "".join(out)


def fits_layout(ja_source: str, ko_insert: str, info: dict) -> bool:
    try:
        if info.get("terminator_hex", "").upper() in CHOICE_TERMINATORS and not PAUSE_SOURCE_RE.search(ja_source):
            validate_choice_insert(ja_source, ko_insert, info.get("terminator_hex", ""))
        else:
            validate_strict_insert(ja_source, ko_insert)
        return True
    except Exception:
        return False


def validate_strict_insert(ja_source: str, ko_insert: str) -> None:
    source = source_pages(ja_source)
    target = source_pages(ko_insert)
    if len(target) > len(source):
        raise ValueError(f"page count {len(target)} > {len(source)}")
    for page_index, page in enumerate(target):
        units = boku_tools.layout_units(page)
        if len(units) > MAX_LINES:
            raise ValueError(f"page {page_index + 1}: line count {len(units)} > {MAX_LINES}")
        for line_index, count in enumerate(units):
            if count > MAX_WIDTH:
                raise ValueError(
                    f"page {page_index + 1} line {line_index + 1}: {count} glyphs > {MAX_WIDTH}"
                )


def validate_choice_insert(ja_source: str, ko_insert: str, terminator_hex: str) -> None:
    expected = len(source_visible_lines(ja_source))
    actual = len([line for line in ko_insert.splitlines() if line.strip()])
    if expected != actual:
        raise ValueError(f"choice line count {actual} != source {expected}")
    for line_index, line in enumerate([line for line in ko_insert.splitlines() if line.strip()], 1):
        count = unit_len(line)
        if count > MAX_WIDTH:
            raise ValueError(f"choice line {line_index}: {count} glyphs > {MAX_WIDTH}")


def main() -> None:
    os.environ["BOKU_LAYOUT_MODE"] = "page3"
    os.environ["BOKU_MAX_LINE_UNITS"] = str(MAX_WIDTH)
    os.environ["BOKU_MAX_PAGE_LINES"] = str(MAX_LINES)

    simple = json.loads(SIMPLE.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    if len(simple) != len(meta):
        raise ValueError(f"simple/meta row count mismatch: {len(simple)} != {len(meta)}")

    patch_rows = []
    changed = 0
    regenerated = 0
    layout_issues = []
    for index, (row, info) in enumerate(zip(simple, meta)):
        ja_source = row[JA_SOURCE]
        ko_translation = row[KO_TRANSLATION]
        old_insert = normalize_insert_punctuation(row.get(KO_INSERT, ""))
        if visible_compact(ko_translation) == visible_compact(old_insert) and fits_layout(ja_source, old_insert, info):
            ko_insert = old_insert
            row[KO_INSERT] = ko_insert
        else:
            changed += 1
            ko_insert = make_insert(ja_source, ko_translation, old_insert, info)
            regenerated += 1
            row[KO_INSERT] = ko_insert

        item = dict(info)
        item["text"] = build_text_for_validation(ja_source)
        item["ko"] = ko_insert
        item["status"] = "simple_translation_sync"
        patch_rows.append(item)
        try:
            if info.get("terminator_hex", "").upper() in CHOICE_TERMINATORS and not PAUSE_SOURCE_RE.search(ja_source):
                validate_choice_insert(ja_source, ko_insert, info.get("terminator_hex", ""))
            else:
                validate_strict_insert(ja_source, ko_insert)
        except Exception as exc:
            layout_issues.append({"index": index, "error": str(exc)})

    SIMPLE.write_text(json.dumps(simple, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_PATCH.write_text(json.dumps(patch_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "rows": len(simple),
        "changed_translations": changed,
        "regenerated_inserts": regenerated,
        "layout_issues": layout_issues,
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "layout_issues"}, ensure_ascii=False))
    print(f"layout_issues={len(layout_issues)}")


if __name__ == "__main__":
    main()
