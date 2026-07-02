#!/usr/bin/env python3
import csv
import gzip
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boku_tools


ROOT = Path("work/cdimg0_extracted")
TABLE = Path("work/Boku-no-Natsuyasumi/font/table.txt")
TRANSLATIONS = Path("work/translations.json")
OUT_DIR = Path("work/translation_survey")


def visible_len(text: str) -> int:
    count = 0
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = text.find("}", i + 1)
            if end != -1:
                i = end + 1
                continue
        if text[i] != "\n":
            count += 1
        i += 1
    return count


def decode_full_segment(segment: bytes, table: dict[int, str]) -> tuple[str, bytes]:
    out = []
    consumed = bytearray()
    for pos in range(0, len(segment) // 2 * 2, 2):
        value = struct.unpack_from("<H", segment, pos)[0]
        consumed.extend(segment[pos : pos + 2])
        if value in (0x8000, 0xFFFF):
            break
        if value == 0x8001:
            out.append("\n")
        elif value == 0x8002:
            out.append("{PAUSE}")
        elif value in table:
            out.append(table[value])
        elif value == 0:
            out.append("　")
        else:
            out.append(f"{{{value:04X}}}")
    return "".join(out), bytes(consumed)


def load_dialogs_for_member(script: str, pack_index: int):
    script_data = (ROOT / "map" / "gz" / script).read_bytes()
    members = boku_tools.parse_pack_entries(script_data, with_names=True)
    member = members[pack_index]
    gz_data = script_data[member["offset"] : member["offset"] + member["size"]]
    payload = gzip.decompress(gz_data[4:] if member["name"].endswith(".gzx") else gz_data)
    parts = boku_tools.parse_pack_entries(payload, with_names=False)
    return payload[parts[1]["offset"] : parts[1]["offset"] + parts[1]["size"]]


def full_segment_for(item: dict, dialogs: bytes, table: dict[int, str]) -> tuple[str, bytes]:
    block_count = struct.unpack_from("<I", dialogs, 0)[0]
    block_index = item["block_index"]
    if block_index >= block_count:
        raise ValueError("block index out of range")
    dialog_id, block_len, block_off = struct.unpack_from("<HHI", dialogs, 4 + block_index * 8)
    block = dialogs[block_off : block_off + block_len]
    element_count = struct.unpack_from("<I", block, 0)[0]
    offsets = [struct.unpack_from("<I", block, 4 + i * 4)[0] for i in range(element_count)]
    elem = item["element_index"]
    start = offsets[elem]
    end = min([o for o in offsets if o > start] or [len(block)])
    segment = block[start:end]
    return decode_full_segment(segment, table)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = boku_tools.load_table(TABLE)
    items = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    dialogs_cache = {}
    rows = []

    for idx, item in enumerate(items):
        key = (item["script"], item["pack_index"])
        if key not in dialogs_cache:
            dialogs_cache[key] = load_dialogs_for_member(*key)
        full_text, full_raw = full_segment_for(item, dialogs_cache[key], table)
        old_text = item["text"]
        rows.append(
            {
                "index": idx,
                "script": item["script"],
                "pack_index": item["pack_index"],
                "pack_member": item["pack_member"],
                "dialog_id": item["dialog_id"],
                "block_index": item["block_index"],
                "element_index": item["element_index"],
                "pages": len(full_text.split("{PAUSE}")) if full_text else 0,
                "old_chars": visible_len(old_text),
                "full_chars": visible_len(full_text),
                "extra_chars": visible_len(full_text) - visible_len(old_text),
                "has_continuation": full_text != old_text and old_text in full_text,
                "old_text": old_text,
                "full_text": full_text,
                "full_raw_hex": full_raw.hex().upper(),
                "terminator_hex": full_raw[-2:].hex().upper() if full_raw else "",
            }
        )

    json_path = OUT_DIR / "dialog_targets_refined.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = OUT_DIR / "dialog_targets_refined.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "index",
                "script",
                "pack_member",
                "dialog_id",
                "block_index",
                "element_index",
                "pages",
                "old_chars",
                "full_chars",
                "extra_chars",
                "has_continuation",
                "full_text",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})

    by_script = Counter(row["script"] for row in rows)
    pages_by_script = defaultdict(int)
    old_chars_by_script = defaultdict(int)
    full_chars_by_script = defaultdict(int)
    continuation_by_script = Counter()
    for row in rows:
        pages_by_script[row["script"]] += row["pages"]
        old_chars_by_script[row["script"]] += row["old_chars"]
        full_chars_by_script[row["script"]] += row["full_chars"]
        if row["has_continuation"]:
            continuation_by_script[row["script"]] += 1

    continuations = [row for row in rows if row["has_continuation"]]
    md = []
    md.append("# Refined Translation Target Survey\n")
    md.append("This survey starts from the existing text extractor's 8,526 real dialogue entries, then expands each entry to the full element segment so pages after `0x0000` spaces and `{PAUSE}` markers are counted.")
    md.append("")
    md.append("## Summary")
    md.append("")
    md.append(f"- Dialogue entries: {len(rows)}")
    md.append(f"- Scripts: {len(by_script)}")
    md.append(f"- Pages: {sum(row['pages'] for row in rows)}")
    md.append(f"- Existing extractor visible units: {sum(row['old_chars'] for row in rows)}")
    md.append(f"- Full segment visible units: {sum(row['full_chars'] for row in rows)}")
    md.append(f"- Additional visible units found: {sum(row['extra_chars'] for row in rows)}")
    md.append(f"- Entries with continuation text: {len(continuations)}")
    md.append("")
    md.append("## Top Scripts")
    md.append("")
    md.append("| Script | Entries | Pages | Old Chars | Full Chars | Continuations |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for script, count in by_script.most_common(30):
        md.append(
            f"| {script} | {count} | {pages_by_script[script]} | "
            f"{old_chars_by_script[script]} | {full_chars_by_script[script]} | "
            f"{continuation_by_script[script]} |"
        )
    md.append("")
    md.append("## Continuation Samples")
    md.append("")
    for row in continuations[:30]:
        sample = row["full_text"].replace("\n", "\\n")
        md.append(
            f"- #{row['index']} {row['script']} dialog {row['dialog_id']} "
            f"element {row['element_index']} pages={row['pages']} "
            f"old={row['old_chars']} full={row['full_chars']}: `{sample[:220]}`"
        )
    md.append("")
    md.append("## Files")
    md.append("")
    md.append(f"- JSON: `{json_path}`")
    md.append(f"- CSV: `{csv_path}`")
    md_path = OUT_DIR / "translation_target_survey_refined.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(md_path)
    print(json_path)
    print(csv_path)


if __name__ == "__main__":
    main()
