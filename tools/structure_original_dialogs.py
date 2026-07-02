#!/usr/bin/env python3
import csv
import gzip
import json
import os
import re
import struct
from pathlib import Path

import boku_tools


ROOT = Path(os.environ.get("BOKU_EXTRACTED_ROOT", "work/cdimg0_extracted"))
TABLE = Path(os.environ.get("BOKU_TABLE", "work/Boku-no-Natsuyasumi/font/table.txt"))
OUT_DIR = Path(os.environ.get("BOKU_STRUCTURE_OUT", "outputs/dialog_structure_v1"))

CONTROL_NAMES = {
    0x0000: "segment_break",
    0x8000: "terminator",
    0xFFFF: "terminator_ff",
    0x8001: "newline",
    0x8002: "page",
}


def read_c_string(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b"\0", offset)
    if end == -1:
        end = len(data)
    return data[offset:end].decode("ascii", errors="replace")


def word_hex(value: int) -> str:
    return f"{value:04X}"


def decode_segment(segment: bytes, table: dict[int, str]) -> dict:
    words = [
        struct.unpack_from("<H", segment, pos)[0]
        for pos in range(0, len(segment) - 1, 2)
    ]
    tokens = []
    runs = []
    current = []
    control_counts: dict[str, int] = {}
    terminator_seen = False

    def flush_run(end_reason: str, end_word: int | None = None):
        nonlocal current
        if not current and end_reason not in {"segment_break", "terminator", "terminator_ff"}:
            return
        text = "".join(token["text"] for token in current if token["kind"] in {"char", "newline", "page", "glyph_token"})
        visible = "".join(token["text"] for token in current if token["kind"] in {"char", "glyph_token"})
        controls = [token for token in current if token["kind"] == "control"]
        runs.append(
            {
                "run_index": len(runs),
                "end_reason": end_reason,
                "end_word": word_hex(end_word) if end_word is not None else None,
                "text": text,
                "visible_text": visible,
                "visible_len": len(visible),
                "line_count": len(text.splitlines()) if text else 0,
                "page_count": text.count("{PAUSE}") + 1 if text else 0,
                "controls": controls,
                "tokens": current,
            }
        )
        current = []

    for index, value in enumerate(words):
        token = {
            "word_index": index,
            "word": word_hex(value),
            "value": value,
            "kind": "",
            "text": "",
        }
        if value == 0x8001:
            token["kind"] = "newline"
            token["text"] = "\n"
            current.append(token)
        elif value == 0x8002:
            token["kind"] = "page"
            token["text"] = "{PAUSE}"
            current.append(token)
        elif value in (0x0000, 0x8000, 0xFFFF):
            token["kind"] = "control"
            token["name"] = CONTROL_NAMES[value]
            control_counts[token["name"]] = control_counts.get(token["name"], 0) + 1
            tokens.append(token)
            flush_run(token["name"], value)
            if value in (0x8000, 0xFFFF):
                terminator_seen = True
                # Keep trailing padding out of the logical token stream.
                break
            continue
        elif value in table:
            token["kind"] = "char"
            token["text"] = table[value]
            current.append(token)
        else:
            token["kind"] = "control"
            token["name"] = "unknown_word"
            token["text"] = f"{{CTRL:{value:04X}}}"
            control_counts[token["name"]] = control_counts.get(token["name"], 0) + 1
            current.append(token)
        tokens.append(token)

    if current:
        flush_run("segment_end", None)

    full_text = "".join(run["text"] for run in runs)
    return {
        "words_hex": "".join(struct.pack("<H", word).hex().upper() for word in words),
        "tokens": tokens,
        "runs": runs,
        "full_text": full_text,
        "run_count": len(runs),
        "control_counts": control_counts,
        "terminator_seen": terminator_seen,
    }


def classify_unit(text: str, run_count: int, elem_index: int, sibling_count: int) -> list[str]:
    labels = []
    visible = text.replace("\n", "").replace("{PAUSE}", "")
    if run_count > 1:
        labels.append("multi_run")
    if elem_index >= 4 and elem_index % 2 == 0:
        labels.append("dialog_text_slot")
    if elem_index >= 3 and elem_index % 2 == 1:
        labels.append("speaker_or_key_slot")
    if sibling_count >= 4:
        labels.append("multi_text_block")
    if 0 < len(visible) <= 40 and ("\u3000" in visible or "　" in visible):
        labels.append("choice_like_spacing")
    if re.search(r"(する|します|です|か|？).{0,8}(はい|いいえ)", visible):
        labels.append("choice_question_like")
    if len(visible) <= 24 and sibling_count >= 3:
        labels.append("short_branch_text")
    return labels


def main() -> None:
    table = boku_tools.load_table(TABLE)
    scripts_dir = ROOT / "map" / "gz"
    blocks = []
    units = []
    control_inventory: dict[str, dict] = {}

    for script_path in sorted(scripts_dir.glob("*.bin")):
        script_data = script_path.read_bytes()
        top_entries = boku_tools.parse_pack_entries(script_data, with_names=True)
        for pack_entry in top_entries:
            if pack_entry["offset"] == 0 or pack_entry["size"] == 0:
                continue
            packed = script_data[pack_entry["offset"] : pack_entry["offset"] + pack_entry["size"]]
            try:
                payload = boku_tools.gzip_payload(packed)
            except Exception:
                continue
            inner_entries = boku_tools.parse_pack_entries(payload, with_names=False)
            if len(inner_entries) <= 1 or inner_entries[1]["offset"] == 0:
                continue
            dialog_entry = inner_entries[1]
            dialogs = payload[dialog_entry["offset"] : dialog_entry["offset"] + dialog_entry["size"]]
            if len(dialogs) < 4:
                continue
            block_count = struct.unpack_from("<I", dialogs, 0)[0]
            for block_index in range(block_count):
                fat = 4 + block_index * 8
                if fat + 8 > len(dialogs):
                    continue
                dialog_id, block_len, block_offset = struct.unpack_from("<HHI", dialogs, fat)
                if block_offset + block_len > len(dialogs):
                    continue
                block = dialogs[block_offset : block_offset + block_len]
                if len(block) < 4:
                    continue
                element_count = struct.unpack_from("<I", block, 0)[0]
                if element_count > 256:
                    continue
                offsets = [
                    struct.unpack_from("<I", block, 4 + idx * 4)[0]
                    for idx in range(element_count)
                    if 4 + idx * 4 + 4 <= len(block)
                ]
                boundaries = sorted({off for off in offsets if 0 < off < len(block)} | {len(block)})
                next_boundary = {off: boundaries[pos + 1] for pos, off in enumerate(boundaries[:-1])}
                text_elements = []
                element_records = []
                for elem_index, off in enumerate(offsets):
                    record = {
                        "element_index": elem_index,
                        "offset": off,
                        "role_hint": "text" if elem_index >= 4 and elem_index % 2 == 0 else ("key" if elem_index >= 3 and elem_index % 2 == 1 else "header"),
                    }
                    if off == 0 or off >= len(block):
                        record["empty"] = True
                        element_records.append(record)
                        continue
                    end = next_boundary.get(off, len(block))
                    segment = block[off:end]
                    decoded = decode_segment(segment, table)
                    key = read_c_string(block, offsets[elem_index - 1]) if elem_index >= 1 and offsets[elem_index - 1] else ""
                    record.update(
                        {
                            "end": end,
                            "size": len(segment),
                            "key": key,
                            "run_count": decoded["run_count"],
                            "text": decoded["full_text"],
                            "control_counts": decoded["control_counts"],
                            "terminator_seen": decoded["terminator_seen"],
                            "runs": decoded["runs"],
                        }
                    )
                    if decoded["full_text"] and record["role_hint"] == "text":
                        text_elements.append(record)
                    for token in decoded["tokens"]:
                        if token["kind"] == "control":
                            inv_key = token.get("name", "control") + ":" + token["word"]
                            item = control_inventory.setdefault(
                                inv_key,
                                {
                                    "name": token.get("name", "control"),
                                    "word": token["word"],
                                    "count": 0,
                                    "examples": [],
                                },
                            )
                            item["count"] += 1
                            if len(item["examples"]) < 8:
                                item["examples"].append(
                                    {
                                        "script": script_path.name,
                                        "member": pack_entry["name"],
                                        "dialog_id": dialog_id,
                                        "block_index": block_index,
                                        "element_index": elem_index,
                                        "text": decoded["full_text"][:120],
                                    }
                                )
                    element_records.append(record)

                block_record = {
                    "script": script_path.name,
                    "pack_index": pack_entry["index"],
                    "pack_member": pack_entry["name"],
                    "dialog_id": dialog_id,
                    "block_index": block_index,
                    "block_offset": block_offset,
                    "block_length": block_len,
                    "element_count": element_count,
                    "offsets": offsets,
                    "text_element_count": len(text_elements),
                    "elements": element_records,
                }
                blocks.append(block_record)
                for element in text_elements:
                    labels = classify_unit(element["text"], element["run_count"], element["element_index"], len(text_elements))
                    for run in element["runs"]:
                        units.append(
                            {
                                "unit_id": len(units),
                                "script": script_path.name,
                                "pack_index": pack_entry["index"],
                                "pack_member": pack_entry["name"],
                                "dialog_id": dialog_id,
                                "block_index": block_index,
                                "element_index": element["element_index"],
                                "run_index": run["run_index"],
                                "key": element.get("key", ""),
                                "labels": labels,
                                "end_reason": run["end_reason"],
                                "text": run["text"],
                                "visible_text": run["visible_text"],
                                "visible_len": run["visible_len"],
                                "line_count": run["line_count"],
                                "page_count": run["page_count"],
                                "raw_element_text": element["text"],
                                "element_run_count": element["run_count"],
                            }
                        )

    choice_candidates = [
        unit for unit in units
        if any(label in unit["labels"] for label in ["choice_like_spacing", "choice_question_like", "short_branch_text"])
    ]
    multi_run_units = [unit for unit in units if unit["element_run_count"] > 1]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "dialog_blocks_structured.json").write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "dialog_text_units.json").write_text(json.dumps(units, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "control_code_inventory.json").write_text(json.dumps(sorted(control_inventory.values(), key=lambda x: (-x["count"], x["word"])), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "choice_candidates.json").write_text(json.dumps(choice_candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "multi_run_units.json").write_text(json.dumps(multi_run_units, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with (OUT_DIR / "dialog_text_units.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["unit_id", "script", "pack_member", "dialog_id", "block_index", "element_index", "run_index", "labels", "end_reason", "visible_len", "line_count", "page_count", "text"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for unit in units:
            writer.writerow({**{k: unit.get(k, "") for k in fieldnames}, "labels": "|".join(unit["labels"])})

    summary = {
        "blocks": len(blocks),
        "units": len(units),
        "choice_candidates": len(choice_candidates),
        "multi_run_units": len(multi_run_units),
        "control_codes": len(control_inventory),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
