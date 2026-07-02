#!/usr/bin/env python3
import json
import re
import csv
from pathlib import Path


PATCH = Path("outputs/translations_quality_v2_resolved_reflow15_noreloc.json")
EDITABLE = Path("outputs/translation_quality_v2_editable_resolved_reflow15_noreloc.json")
SIMPLE = Path("outputs/translation_edit_simple_resolved_reflow15_noreloc.json")
META = Path("outputs/translation_edit_simple_resolved_reflow15_noreloc.meta.json")
README = Path("outputs/translation_edit_simple_README.md")
CANONICAL_TEXT = Path("outputs/dialog_structure_resolved/text_control_usage.csv")

JA_SOURCE = "\uc77c\ubcf8\uc5b4_\uc6d0\ubb38"
JA_DIALOG = "\uc77c\ubcf8\uc5b4_\ub300\uc0ac"
KO_TRANSLATION = "\ud55c\uad6d\uc5b4_\ubc88\uc5ed"
KO_INSERT = "\ud55c\uad6d\uc5b4_\uc0bd\uc785"

TOKEN_RE = re.compile(r"\{(?:PAUSE(?::[0-9A-Fa-f]{4})?|RAW:[0-9A-Fa-f]+|SEG:0000|CTRL:[0-9A-Fa-f]{4}|[0-9A-Fa-f]{4})\}")
FULL_SPACE = "\u3000"


def clean_ja_dialog(text: str) -> str:
    text = TOKEN_RE.sub(" ", text or "")
    text = text.replace("\\n", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", " ")
    text = text.replace(FULL_SPACE, " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def load_canonical_source() -> dict[tuple, str]:
    if not CANONICAL_TEXT.exists():
        return {}
    out = {}
    with CANONICAL_TEXT.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (
                row["script"],
                row["member"],
                int(row["dialog_id"]),
                int(row["block_index"]),
                int(row["element_index"]),
            )
            out[key] = row["text"]
    return out


def clean_ko_translation(text: str) -> str:
    text = TOKEN_RE.sub("", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", " ")
    text = text.replace(FULL_SPACE, " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def main() -> None:
    patch_rows = json.loads(PATCH.read_text(encoding="utf-8"))
    editable_rows = json.loads(EDITABLE.read_text(encoding="utf-8")) if EDITABLE.exists() else []
    canonical = load_canonical_source()
    simple = []
    meta = []
    for index, row in enumerate(patch_rows):
        row_key = (
            row["script"],
            row["pack_member"],
            int(row["dialog_id"]),
            int(row["block_index"]),
            int(row["element_index"]),
        )
        ja_source = canonical.get(row_key, row.get("text", "")).replace("\\n", "\n")
        ko_insert = row.get("ko", "")
        ko_edit = ""
        if index < len(editable_rows):
            ko_edit = editable_rows[index].get("ko_edit") or editable_rows[index].get("ko_game") or ""
        ko_translation = clean_ko_translation(ko_edit or ko_insert)
        simple.append(
            {
                JA_SOURCE: ja_source,
                JA_DIALOG: clean_ja_dialog(ja_source),
                KO_TRANSLATION: ko_translation,
                KO_INSERT: ko_insert,
            }
        )
        meta.append(
            {
                "script": row["script"],
                "pack_index": row["pack_index"],
                "pack_member": row["pack_member"],
                "dialog_id": row["dialog_id"],
                "block_index": row["block_index"],
                "element_index": row["element_index"],
                "text_offset": row["text_offset"],
                "raw_hex": row["raw_hex"],
                "terminator_hex": row["terminator_hex"],
                "key": row.get("key", ""),
                "source_table": row.get("source_table", ""),
            }
        )
    SIMPLE.write_text(json.dumps(simple, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    README.write_text(
        "\n".join(
            [
                "# Simple Translation Edit File",
                "",
                "Edit this file:",
                "",
                "- `outputs/translation_edit_simple_resolved_reflow15_noreloc.json`",
                "",
                "Fields:",
                "",
                f"- `{JA_SOURCE}`: Japanese source with control markers and line breaks. Reference only.",
                f"- `{JA_DIALOG}`: Japanese visible text without control markers and line breaks. Reference only.",
                f"- `{KO_TRANSLATION}`: edit this field. Spacing is preserved.",
                f"- `{KO_INSERT}`: generated game insertion text. Do not edit by hand unless debugging.",
                "",
                "Hidden build metadata is stored separately:",
                "",
                "- `outputs/translation_edit_simple_resolved_reflow15_noreloc.meta.json`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(SIMPLE)
    print(META)
    print(len(simple))


if __name__ == "__main__":
    main()
