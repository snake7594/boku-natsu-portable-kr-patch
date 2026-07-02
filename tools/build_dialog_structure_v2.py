#!/usr/bin/env python3
import csv
import json
import os
from collections import Counter
from pathlib import Path


IN_DIR = Path(os.environ.get("BOKU_STRUCTURE_IN", "outputs/dialog_structure_v1"))
OUT_DIR = Path(os.environ.get("BOKU_STRUCTURE_ANALYSIS_OUT", "outputs/dialog_structure_v2"))
LEGACY_TARGETS = Path(os.environ.get("BOKU_LEGACY_TARGETS", "work/translation_survey/dialog_targets_refined.json"))

MAX_KO_LINE_CHARS = 15
MAX_DIALOG_LINES = 3


def visible_text(text: str) -> str:
    return text.replace("\n", "").replace("{PAUSE}", "")


def display_visible_text(text: str) -> str:
    cleaned = text
    while "{PAUSE:" in cleaned:
        start = cleaned.find("{PAUSE:")
        end = cleaned.find("}", start)
        if end == -1:
            break
        cleaned = cleaned[:start] + "{PAUSE}" + cleaned[end + 1:]
    return visible_text(cleaned)


def normalize_runs(element: dict) -> tuple[list[dict], str, dict[str, int], list[str]]:
    normalized_runs = []
    control_counts = dict(element.get("control_counts") or {})
    page_args = []
    for run in element.get("runs", []):
        tokens = run.get("tokens", [])
        text_parts = []
        visible_parts = []
        normalized_tokens = []
        idx = 0
        while idx < len(tokens):
            token = tokens[idx]
            if token.get("kind") == "page":
                arg_token = tokens[idx + 1] if idx + 1 < len(tokens) else None
                arg_word = arg_token.get("word") if arg_token else "????"
                text_parts.append(f"{{PAUSE:{arg_word}}}")
                normalized_tokens.append({
                    "kind": "control",
                    "name": "page",
                    "word": token.get("word"),
                    "arg_word": arg_word,
                    "text": f"{{PAUSE:{arg_word}}}",
                })
                control_counts["page_arg"] = control_counts.get("page_arg", 0) + 1
                page_args.append(arg_word)
                idx += 2 if arg_token else 1
                continue
            if token.get("kind") == "newline":
                text_parts.append("\n")
                normalized_tokens.append(token)
            elif token.get("kind") in {"char", "glyph_token"}:
                text_parts.append(token.get("text", ""))
                visible_parts.append(token.get("text", ""))
                normalized_tokens.append(token)
            elif token.get("kind") == "control":
                normalized_tokens.append(token)
            idx += 1
        text = "".join(text_parts)
        normalized_runs.append({
            **{k: v for k, v in run.items() if k != "tokens"},
            "text": text,
            "visible_text": "".join(visible_parts),
            "visible_len": len("".join(visible_parts)),
            "line_count": len(text.splitlines()) if text else 0,
            "page_count": text.count("{PAUSE:") + text.count("{PAUSE}") + 1 if text else 0,
            "tokens": normalized_tokens,
        })
    return normalized_runs, "".join(run["text"] for run in normalized_runs), control_counts, page_args


def labels_for(text: str, run_count: int, elem_index: int, sibling_count: int) -> list[str]:
    visible = display_visible_text(text)
    labels = []
    if run_count > 1:
        labels.append("multi_run")
    if elem_index >= 4 and elem_index % 2 == 0:
        labels.append("dialog_text_slot")
    if sibling_count >= 4:
        labels.append("multi_text_block")
    if 0 < len(visible) <= 40 and ("\u3000" in visible or " " in visible):
        labels.append("choice_like_spacing")
    if any(token in visible for token in ["べき", "なぜ", "どこ", "どう", "どれ", "何", "いつ", "？", "?"]):
        labels.append("choice_question_like")
    if len(visible) <= 24 and sibling_count >= 3:
        labels.append("short_branch_text")
    return labels


def short_question(text: str) -> bool:
    visible = display_visible_text(text)
    return 0 < len(visible) <= 28 and any(token in visible for token in ["べき", "なぜ", "どこ", "どう", "どれ", "何", "いつ", "？", "?"])


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def location_key(row: dict) -> tuple:
    return (
        row.get("script", ""),
        row.get("pack_member", row.get("member", "")),
        int(row.get("dialog_id", -1)),
        int(row.get("block_index", -1)),
        int(row.get("element_index", -1)),
    )


def build_legacy_risks(elements_by_key: dict[tuple, dict]) -> list[dict]:
    if not LEGACY_TARGETS.exists():
        return []
    legacy = json.loads(LEGACY_TARGETS.read_text(encoding="utf-8"))
    rows = []
    for item in legacy:
        key = location_key(item)
        element = elements_by_key.get(key)
        if not element:
            rows.append({
                "risk": "legacy_location_missing_in_structured_extract",
                "script": key[0],
                "member": key[1],
                "dialog_id": key[2],
                "block_index": key[3],
                "element_index": key[4],
                "legacy_text": item.get("full_text", item.get("text", "")),
                "structured_text": "",
                "detail": "Old target row has no matching structured text element.",
            })
            continue
        legacy_text = item.get("full_text", item.get("text", ""))
        structured_text = element.get("normalized_text", element.get("text", ""))
        run_count = int(element.get("run_count", 0))
        raw_hex = item.get("raw_hex", "")
        terminator_hex = item.get("terminator_hex", "")
        reasons = []
        if run_count > 1:
            reasons.append("structured_element_has_multiple_runs")
        if terminator_hex.upper() == "0000":
            reasons.append("legacy_stopped_at_0000_segment_break")
        if legacy_text and legacy_text != structured_text:
            reasons.append("legacy_text_differs_from_full_structured_text")
        if raw_hex.upper().endswith("0000") and run_count > 1:
            reasons.append("legacy_raw_ends_before_following_run")
        if reasons:
            rows.append({
                "risk": "|".join(reasons),
                "script": key[0],
                "member": key[1],
                "dialog_id": key[2],
                "block_index": key[3],
                "element_index": key[4],
                "legacy_text": legacy_text.replace("\n", "\\n"),
                "structured_text": structured_text.replace("\n", "\\n"),
                "detail": f"legacy_raw_bytes={len(raw_hex) // 2}; structured_runs={run_count}",
            })
    return rows


def main() -> None:
    blocks = json.loads((IN_DIR / "dialog_blocks_structured.json").read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    units = []
    editable = []
    menu_blocks = []
    segment_break_rows = []
    risky_join_rows = []
    text_control_rows = []
    control_inventory = {}
    page_arg_inventory = Counter()
    elements_by_key = {}

    for block in blocks:
        text_elements = [e for e in block["elements"] if e.get("role_hint") == "text" and e.get("text")]
        for e in text_elements:
            runs, text, counts, page_args = normalize_runs(e)
            e["normalized_runs"] = runs
            e["normalized_text"] = text
            e["normalized_control_counts"] = counts
            e["page_args"] = page_args
        short_questions = [e for e in text_elements if short_question(e["normalized_text"])]
        if len(short_questions) >= 3 and len(text_elements) >= len(short_questions) + 1:
            menu_blocks.append({
                "script": block["script"],
                "member": block["pack_member"],
                "dialog_id": block["dialog_id"],
                "block_index": block["block_index"],
                "text_element_count": len(text_elements),
                "short_question_count": len(short_questions),
                "question_elements": ", ".join(str(e["element_index"]) for e in short_questions[:40]),
                "first_questions": " / ".join(e["normalized_text"].replace("\n", " ") for e in short_questions[:10]),
            })

        for element in text_elements:
            key = (
                block["script"],
                block["pack_member"],
                int(block["dialog_id"]),
                int(block["block_index"]),
                int(element["element_index"]),
            )
            elements_by_key[key] = element
            page_arg_inventory.update(element.get("page_args", []))
            element_text = element["normalized_text"]
            element_runs = element["normalized_runs"]
            labels = labels_for(element_text, element["run_count"], element["element_index"], len(text_elements))
            counts = element.get("normalized_control_counts") or {}
            if counts:
                text_control_rows.append({
                    "script": block["script"],
                    "member": block["pack_member"],
                    "dialog_id": block["dialog_id"],
                    "block_index": block["block_index"],
                    "element_index": element["element_index"],
                    "key": element.get("key", ""),
                    "controls": json.dumps(counts, ensure_ascii=False, sort_keys=True),
                    "text": element_text.replace("\n", "\\n"),
                })
                for name, count in counts.items():
                    item = control_inventory.setdefault(name, {"name": name, "count": 0, "examples": []})
                    item["count"] += int(count)
                    if len(item["examples"]) < 8:
                        item["examples"].append({
                            "script": block["script"],
                            "member": block["pack_member"],
                            "dialog_id": block["dialog_id"],
                            "block_index": block["block_index"],
                            "element_index": element["element_index"],
                            "text": element_text[:120],
                        })

            run_records = []
            for run in element_runs:
                unit = {
                    "unit_id": len(units),
                    "unit_key": f"{block['script']}|{block['pack_member']}|{block['dialog_id']}|{block['block_index']}|{element['element_index']}|{run['run_index']}",
                    "script": block["script"],
                    "pack_index": block["pack_index"],
                    "pack_member": block["pack_member"],
                    "dialog_id": block["dialog_id"],
                    "block_index": block["block_index"],
                    "element_index": element["element_index"],
                    "run_index": run["run_index"],
                    "key": element.get("key", ""),
                    "labels": labels,
                    "end_reason": run["end_reason"],
                    "end_word": run.get("end_word"),
                    "ja": run["text"],
                    "visible_text": run["visible_text"],
                    "visible_len": run["visible_len"],
                    "line_count": run["line_count"],
                    "page_count": run["page_count"],
                    "element_run_count": element["run_count"],
                    "raw_element_text": element_text,
                }
                units.append(unit)
                run_records.append({
                    "run_index": run["run_index"],
                    "end_reason": run["end_reason"],
                    "end_word": run.get("end_word"),
                    "ja": run["text"],
                    "ko_edit": "",
                    "note": "",
                })

            editable.append({
                "type": "dialog_element",
                "id": f"{block['script']}|{block['pack_member']}|{block['dialog_id']}|{block['block_index']}|{element['element_index']}",
                "script": block["script"],
                "pack_index": block["pack_index"],
                "member": block["pack_member"],
                "dialog_id": block["dialog_id"],
                "block_index": block["block_index"],
                "element_index": element["element_index"],
                "key": element.get("key", ""),
                "labels": labels,
                "limits": {
                    "ko_line_chars": MAX_KO_LINE_CHARS,
                    "dialog_lines": MAX_DIALOG_LINES,
                    "preserve_run_count": True,
                    "preserve_page_breaks": True,
                },
                "control_counts": counts,
                "ja": element_text,
                "ko_element_edit": "",
                "runs": run_records,
                "page_args": element.get("page_args", []),
                "raw_ja_with_unparsed_page_args": element["text"],
                "human_note": "",
            })

            if element.get("run_count", 0) > 1:
                segment_break_rows.append({
                    "script": block["script"],
                    "member": block["pack_member"],
                    "dialog_id": block["dialog_id"],
                    "block_index": block["block_index"],
                    "element_index": element["element_index"],
                    "key": element.get("key", ""),
                    "run_count": element["run_count"],
                    "end_reasons": " / ".join(run["end_reason"] for run in element_runs),
                    "runs": " || ".join(run["text"].replace("\n", "\\n") for run in element_runs[:12]),
                    "full_text_without_controls": element_text.replace("\n", "\\n"),
                })
                for idx, run in enumerate(element_runs[:-1]):
                    next_run = element_runs[idx + 1]
                    before = run["text"].strip()
                    after = next_run["text"].strip()
                    if before.endswith("」") or "「" in after[:8]:
                        risky_join_rows.append({
                            "script": block["script"],
                            "member": block["pack_member"],
                            "dialog_id": block["dialog_id"],
                            "block_index": block["block_index"],
                            "element_index": element["element_index"],
                            "key": element.get("key", ""),
                            "run_index": idx,
                            "reason": "closed_quote_or_new_speaker_after_segment_break",
                            "before": before.replace("\n", "\\n"),
                            "after": after.replace("\n", "\\n"),
                            "full_text_without_controls": element_text.replace("\n", "\\n"),
                        })

    legacy_risks = build_legacy_risks(elements_by_key)
    choice_candidates = [unit for unit in units if any(label in unit["labels"] for label in ["choice_like_spacing", "choice_question_like", "short_branch_text"])]
    multi_run_units = [unit for unit in units if unit["element_run_count"] > 1]

    (OUT_DIR / "dialog_text_units.json").write_text(json.dumps(units, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "translation_structured_v2_editable.json").write_text(json.dumps(editable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "choice_candidates.json").write_text(json.dumps(choice_candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "multi_run_units.json").write_text(json.dumps(multi_run_units, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "text_control_inventory.json").write_text(json.dumps(sorted(control_inventory.values(), key=lambda x: (-x["count"], x["name"])), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "page_arg_inventory.json").write_text(json.dumps([
        {"arg_word": word, "count": count}
        for word, count in page_arg_inventory.most_common()
    ], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_csv(OUT_DIR / "dialog_text_units.csv", [
        {k: (("|".join(v) if k == "labels" else v)) for k, v in unit.items() if k in ["unit_id", "unit_key", "script", "pack_member", "dialog_id", "block_index", "element_index", "run_index", "labels", "end_reason", "visible_len", "line_count", "page_count", "ja"]}
        for unit in units
    ])
    write_csv(OUT_DIR / "menu_blocks.csv", menu_blocks)
    write_csv(OUT_DIR / "segment_break_elements.csv", segment_break_rows)
    write_csv(OUT_DIR / "risky_segment_joins.csv", risky_join_rows)
    write_csv(OUT_DIR / "text_control_usage.csv", text_control_rows)
    write_csv(OUT_DIR / "legacy_mapping_risks.csv", legacy_risks)

    notes = [
        "# Dialog Structure V2 Notes",
        "",
        "## Confirmed Control Words",
        "",
        "- `8001`: explicit line break.",
        "- `8002`: page break / wait marker. In text slots it is followed by one argument word, represented as `{PAUSE:hhhh}`.",
        "- `8000`: normal element terminator.",
        "- `FFFF`: alternate terminator observed in raw parsing.",
        "- `0000`: segment break inside one element. It is not a normal terminator for extraction.",
        "",
        "## Translation/Inserting Rules",
        "",
        "- Use the element id plus run index as the stable translation key.",
        "- Preserve the number and order of runs for any element with `run_count > 1`.",
        "- Preserve `{PAUSE:hhhh}` tokens exactly. The `hhhh` part is control data, not visible text.",
        "- Do not merge across `0000` unless that exact element has been manually verified in-game.",
        "- Yes/no and menu-like prompts are separate text elements in a larger block; do not append the following response element to the prompt translation.",
        f"- Current Korean layout rule: max {MAX_KO_LINE_CHARS} chars per line, max {MAX_DIALOG_LINES} lines for a normal dialogue page.",
        "- `ko_element_edit` is available for simple single-run elements. For multi-run or menu/choice-like elements, fill `runs[].ko_edit` instead.",
        "",
        "## Files",
        "",
        "- `translation_structured_v2_editable.json`: structured editable base for future translation/insertion.",
        "- `dialog_text_units.csv`: run-level source text table.",
        "- `menu_blocks.csv`: likely menu/help/choice blocks.",
        "- `segment_break_elements.csv`: elements containing `0000` segment breaks.",
        "- `risky_segment_joins.csv`: segment breaks that should not be auto-joined.",
        "- `legacy_mapping_risks.csv`: old extraction rows that differ from the full structured source.",
        "- `text_control_inventory.json`: text-slot-only control usage inventory.",
        "- `page_arg_inventory.json`: inventory of the one-word argument following `8002`.",
    ]
    (OUT_DIR / "STRUCTURE_NOTES.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    summary = {
        "editable_elements": len(editable),
        "text_units": len(units),
        "choice_candidates": len(choice_candidates),
        "menu_blocks": len(menu_blocks),
        "segment_break_elements": len(segment_break_rows),
        "risky_segment_joins": len(risky_join_rows),
        "legacy_mapping_risks": len(legacy_risks),
        "text_control_usage_rows": len(text_control_rows),
        "page_arg_unique": len(page_arg_inventory),
        "page_arg_total": sum(page_arg_inventory.values()),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
