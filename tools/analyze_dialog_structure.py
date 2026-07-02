#!/usr/bin/env python3
import csv
import json
from pathlib import Path


IN_DIR = Path("outputs/dialog_structure_v1")
OUT_DIR = IN_DIR


def short_question(text: str) -> bool:
    visible = text.replace("\n", "").replace("{PAUSE}", "")
    return 0 < len(visible) <= 24 and ("？" in visible or "?" in visible or visible.endswith("…"))


def main() -> None:
    blocks = json.loads((IN_DIR / "dialog_blocks_structured.json").read_text(encoding="utf-8"))
    menu_blocks = []
    segment_break_rows = []
    risky_join_rows = []
    control_rows = []

    for block in blocks:
        text_elements = [
            e for e in block["elements"]
            if e.get("role_hint") == "text" and e.get("text")
        ]
        short_questions = [e for e in text_elements if short_question(e["text"])]
        multi_run = [e for e in text_elements if e.get("run_count", 0) > 1]
        if len(short_questions) >= 3 and len(text_elements) >= len(short_questions) + 1:
            menu_blocks.append(
                {
                    "script": block["script"],
                    "member": block["pack_member"],
                    "dialog_id": block["dialog_id"],
                    "block_index": block["block_index"],
                    "text_element_count": len(text_elements),
                    "short_question_count": len(short_questions),
                    "question_elements": ", ".join(str(e["element_index"]) for e in short_questions[:30]),
                    "first_questions": " / ".join(e["text"].replace("\n", " ") for e in short_questions[:8]),
                }
            )

        for e in multi_run:
            run_texts = [run["text"].replace("\n", "\\n") for run in e["runs"]]
            segment_break_rows.append(
                {
                    "script": block["script"],
                    "member": block["pack_member"],
                    "dialog_id": block["dialog_id"],
                    "block_index": block["block_index"],
                    "element_index": e["element_index"],
                    "key": e.get("key", ""),
                    "run_count": e["run_count"],
                    "end_reasons": " / ".join(run["end_reason"] for run in e["runs"]),
                    "runs": " || ".join(run_texts[:12]),
                    "full_text_without_controls": e["text"].replace("\n", "\\n"),
                }
            )
            # A likely bad join is a segment break where a later run starts a new speaker or the first run already closes a quote.
            for idx, run in enumerate(e["runs"][:-1]):
                next_run = e["runs"][idx + 1]
                text = run["text"].strip()
                next_text = next_run["text"].strip()
                if text.endswith("」") or "「" in next_text[:8]:
                    risky_join_rows.append(
                        {
                            "script": block["script"],
                            "member": block["pack_member"],
                            "dialog_id": block["dialog_id"],
                            "block_index": block["block_index"],
                            "element_index": e["element_index"],
                            "key": e.get("key", ""),
                            "run_index": idx,
                            "reason": "closed_quote_or_new_speaker_after_segment_break",
                            "before": text.replace("\n", "\\n"),
                            "after": next_text.replace("\n", "\\n"),
                            "full_text_without_controls": e["text"].replace("\n", "\\n"),
                        }
                    )

        for e in text_elements:
            counts = e.get("control_counts") or {}
            if counts:
                control_rows.append(
                    {
                        "script": block["script"],
                        "member": block["pack_member"],
                        "dialog_id": block["dialog_id"],
                        "block_index": block["block_index"],
                        "element_index": e["element_index"],
                        "key": e.get("key", ""),
                        "controls": json.dumps(counts, ensure_ascii=False, sort_keys=True),
                        "text": e["text"].replace("\n", "\\n"),
                    }
                )

    def write_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(OUT_DIR / "menu_blocks.csv", menu_blocks)
    write_csv(OUT_DIR / "segment_break_elements.csv", segment_break_rows)
    write_csv(OUT_DIR / "risky_segment_joins.csv", risky_join_rows)
    write_csv(OUT_DIR / "text_control_usage.csv", control_rows)

    notes = [
        "# Dialog Structure V1 Notes",
        "",
        "## Control Words",
        "",
        "- `8001`: explicit line break.",
        "- `8002`: page break / wait for next message page.",
        "- `8000`: normal text terminator.",
        "- `0000`: segment break inside an element. Do not treat this as a normal printable space. Some entries continue the same sentence after it, but menu/branch text can use it to separate logical runs.",
        "- Unknown non-table words are emitted as `CTRL:hhhh` in the structured token stream and should be preserved unless their role is understood.",
        "",
        "## Translation Rules",
        "",
        "- Translate by `script + pack_member + dialog_id + block_index + element_index + run_index`, not only by visible text.",
        "- For menu blocks, keep short question/choice elements separate from later response elements.",
        "- Do not merge text across `0000` blindly. Review `segment_break_elements.csv` and especially `risky_segment_joins.csv` before making a single Korean string.",
        "- Preserve `8001` and `8002` positions semantically: line wrap may change, but page breaks should remain aligned with the original message flow unless tested in game.",
        "- For yes/no or option prompts, keep the full option string inside the same original element and do not pull following response elements into it.",
        "",
        "## Generated Files",
        "",
        "- `dialog_blocks_structured.json`: full block/element/run structure.",
        "- `dialog_text_units.json`: run-level text units for translation.",
        "- `menu_blocks.csv`: likely choice/help/menu blocks.",
        "- `segment_break_elements.csv`: elements split by `0000` segment breaks.",
        "- `risky_segment_joins.csv`: segment breaks likely unsafe to auto-merge.",
        "- `text_control_usage.csv`: controls used by actual text slots.",
    ]
    (OUT_DIR / "STRUCTURE_NOTES.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    summary = {
        "menu_blocks": len(menu_blocks),
        "segment_break_elements": len(segment_break_rows),
        "risky_segment_joins": len(risky_join_rows),
        "text_control_usage_rows": len(control_rows),
    }
    (OUT_DIR / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
