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
OUT_DIR = Path("work/translation_survey")


def is_japanese_text(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if (
            0x3040 <= code <= 0x30FF
            or 0x3400 <= code <= 0x9FFF
            or 0xFF00 <= code <= 0xFFEF
            or ch in "「」『』、。…〜ー"
        ):
            return True
    return False


def visible_len(text: str) -> int:
    count = 0
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = text.find("}", i + 1)
            if end != -1:
                i = end + 1
                continue
        if text[i] not in "\n":
            count += 1
        i += 1
    return count


def decode_full_segment(segment: bytes, table: dict[int, str]) -> tuple[str, list[int]]:
    out = []
    words = []
    for pos in range(0, len(segment) // 2 * 2, 2):
        value = struct.unpack_from("<H", segment, pos)[0]
        words.append(value)
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
    return "".join(out), words


def page_count(text: str) -> int:
    return len(text.split("{PAUSE}")) if text else 0


def iter_dialog_segments(root: Path, table: dict[int, str]):
    for script_path in sorted((root / "map" / "gz").glob("*.bin")):
        script_data = script_path.read_bytes()
        try:
            top_members = boku_tools.parse_pack_entries(script_data, with_names=True)
        except Exception:
            continue

        for pack_index, member in enumerate(top_members):
            gz_data = script_data[member["offset"] : member["offset"] + member["size"]]
            try:
                payload = gzip.decompress(gz_data[4:] if member["name"].endswith(".gzx") else gz_data)
                parts = boku_tools.parse_pack_entries(payload, with_names=False)
            except Exception:
                continue
            if len(parts) <= 1 or parts[1]["offset"] == 0:
                continue

            dialogs = payload[parts[1]["offset"] : parts[1]["offset"] + parts[1]["size"]]
            if len(dialogs) < 4:
                continue
            block_count = struct.unpack_from("<I", dialogs, 0)[0]
            if block_count > 10000:
                continue

            for block_index in range(block_count):
                fat = 4 + block_index * 8
                if fat + 8 > len(dialogs):
                    break
                dialog_id, block_len, block_off = struct.unpack_from("<HHI", dialogs, fat)
                if block_off + block_len > len(dialogs) or block_len < 4:
                    continue
                block = dialogs[block_off : block_off + block_len]
                element_count = struct.unpack_from("<I", block, 0)[0]
                if element_count > 1000 or 4 + element_count * 4 > len(block):
                    continue
                offsets = [struct.unpack_from("<I", block, 4 + i * 4)[0] for i in range(element_count)]
                for element_index, offset in enumerate(offsets):
                    if offset == 0 or offset >= len(block):
                        continue
                    next_offsets = [o for o in offsets if o > offset]
                    end = min(next_offsets) if next_offsets else len(block)
                    segment = block[offset:end]
                    full_text, words = decode_full_segment(segment, table)
                    first_text, first_raw = boku_tools.decode_dialog_words(segment, table)
                    if not is_japanese_text(full_text):
                        continue
                    yield {
                        "script": script_path.name,
                        "pack_index": pack_index,
                        "pack_member": member["name"],
                        "dialog_id": dialog_id,
                        "block_index": block_index,
                        "element_index": element_index,
                        "segment_offset": offset,
                        "raw_bytes": len(segment),
                        "full_text": full_text,
                        "first_text": first_text,
                        "full_chars": visible_len(full_text),
                        "first_chars": visible_len(first_text),
                        "pages": page_count(full_text),
                        "missed_after_first": full_text != first_text and first_text in full_text,
                    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = boku_tools.load_table(TABLE)
    rows = list(iter_dialog_segments(ROOT, table))

    json_path = OUT_DIR / "dialog_segments_full.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = OUT_DIR / "dialog_segments_full.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "script",
                "pack_index",
                "pack_member",
                "dialog_id",
                "block_index",
                "element_index",
                "raw_bytes",
                "full_chars",
                "first_chars",
                "pages",
                "missed_after_first",
                "full_text",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})

    by_script = Counter(row["script"] for row in rows)
    chars_by_script = defaultdict(int)
    pages_by_script = defaultdict(int)
    hidden_by_script = Counter()
    for row in rows:
        chars_by_script[row["script"]] += row["full_chars"]
        pages_by_script[row["script"]] += row["pages"]
        if row["missed_after_first"]:
            hidden_by_script[row["script"]] += 1

    total_chars = sum(row["full_chars"] for row in rows)
    first_chars = sum(row["first_chars"] for row in rows)
    hidden_rows = [row for row in rows if row["missed_after_first"]]

    md = []
    md.append("# Translation Target Survey\n")
    md.append("## Summary\n")
    md.append(f"- Full dialog segments: {len(rows)}")
    md.append(f"- Scripts with dialog text: {len(by_script)}")
    md.append(f"- Full visible character units: {total_chars}")
    md.append(f"- First-line extractor visible units: {first_chars}")
    md.append(f"- Additional units found by full segment scan: {total_chars - first_chars}")
    md.append(f"- Segments with text after first extracted chunk: {len(hidden_rows)}")
    md.append("")
    md.append("## Top Scripts\n")
    md.append("| Script | Segments | Pages | Chars | Hidden Segments |")
    md.append("|---|---:|---:|---:|---:|")
    for script, count in by_script.most_common(30):
        md.append(
            f"| {script} | {count} | {pages_by_script[script]} | "
            f"{chars_by_script[script]} | {hidden_by_script[script]} |"
        )
    md.append("")
    md.append("## Hidden/Continuation Samples\n")
    md.append("These are examples where the old extractor stopped before later text in the same element.")
    md.append("")
    for row in hidden_rows[:25]:
        sample = row["full_text"].replace("\n", "\\n")
        md.append(
            f"- {row['script']} dialog {row['dialog_id']} element {row['element_index']} "
            f"pages={row['pages']} chars={row['full_chars']}: `{sample[:180]}`"
        )
    md.append("")
    md.append("## Files\n")
    md.append(f"- JSON: `{json_path}`")
    md.append(f"- CSV: `{csv_path}`")
    md_path = OUT_DIR / "translation_target_survey.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(md_path)
    print(json_path)
    print(csv_path)


if __name__ == "__main__":
    main()
