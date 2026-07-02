#!/usr/bin/env python3
import csv
import json
from pathlib import Path


ROOT = Path("work")
OUT = ROOT / "translation_master"


def normalize(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dialogs = json.loads((ROOT / "translation_survey" / "dialog_targets_refined.json").read_text(encoding="utf-8"))
    current_items = json.loads((ROOT / "translations_batch002_screens_0010_0018_spaced.json").read_text(encoding="utf-8"))
    current = {idx: item for idx, item in enumerate(current_items)}
    system_report = json.loads((ROOT / "system_text_patch" / "system_text_patch_report.json").read_text(encoding="utf-8"))

    rows = []
    for row in dialogs:
        cur = current.get(row["index"], {})
        rows.append(
            {
                "type": "dialog",
                "id": f"dialog:{row['index']}",
                "source_file": row["script"],
                "member": row["pack_member"],
                "location": f"dialog_id={row['dialog_id']} block={row['block_index']} elem={row['element_index']}",
                "pages": row["pages"],
                "ja": normalize(row["full_text"]),
                "ko": normalize(cur.get("ko", "")),
                "status": "translated" if cur.get("ko") else "needs_translation",
            }
        )

    seen_system = set()
    for idx, row in enumerate(system_report):
        key = (row["member"], row["offset_hex"], row["ja"])
        if key in seen_system:
            continue
        seen_system.add(key)
        rows.append(
            {
                "type": "system_message",
                "id": f"system:{idx}",
                "source_file": "",
                "member": row["member"],
                "location": row["offset_hex"],
                "pages": "",
                "ja": normalize(row["ja"]),
                "ko": normalize(row["ko"]),
                "status": "translated",
            }
        )

    json_path = OUT / "translation_master.json"
    csv_path = OUT / "translation_master.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "id", "source_file", "member", "location", "pages", "status", "ja", "ko"])
        writer.writeheader()
        writer.writerows(rows)

    translated = sum(1 for row in rows if row["status"] == "translated")
    needs = sum(1 for row in rows if row["status"] == "needs_translation")
    md = [
        "# Translation Master",
        "",
        f"- Total text rows: {len(rows)}",
        f"- Translated rows: {translated}",
        f"- Needs translation: {needs}",
        f"- Dialog rows: {sum(1 for row in rows if row['type'] == 'dialog')}",
        f"- System message rows: {sum(1 for row in rows if row['type'] == 'system_message')}",
        "",
        "## Current State",
        "",
        "- The current build contains the previously verified dialogue batch and translated save/load system messages.",
        "- Full-game dialogue insertion requires filling `ko` for the remaining dialogue rows, then rebuilding with the existing insertion pipeline.",
        "",
        "## Files",
        "",
        f"- JSON: `{json_path}`",
        f"- CSV: `{csv_path}`",
    ]
    md_path = OUT / "translation_master.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(md_path)
    print(json_path)
    print(csv_path)
    print(f"translated={translated} needs={needs}")


if __name__ == "__main__":
    main()
