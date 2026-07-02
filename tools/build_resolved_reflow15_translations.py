#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(".")
OLD_PATCH = ROOT / "outputs/translations_quality_v2_manual_reflow15_noreloc.json"
OLD_EDITABLE = ROOT / "outputs/translation_quality_v2_editable_synced_reflow15_noreloc.json"
STRUCTURED = ROOT / "outputs/dialog_structure_resolved/raw/dialog_blocks_structured.json"
OUT_PATCH = ROOT / "outputs/translations_quality_v2_resolved_reflow15_noreloc.json"
OUT_EDITABLE = ROOT / "outputs/translation_quality_v2_editable_resolved_reflow15_noreloc.json"
OUT_REPORT = ROOT / "outputs/resolved_reflow15_noreloc_status.md"


def key(row: dict) -> tuple:
    return (
        row["script"],
        row.get("pack_member") or row.get("member"),
        int(row["dialog_id"]),
        int(row["block_index"]),
        int(row["element_index"]),
    )


def build_resolved_text_map() -> dict[tuple, str]:
    blocks = json.loads(STRUCTURED.read_text(encoding="utf-8"))
    out: dict[tuple, str] = {}
    duplicates: set[tuple] = set()
    for block in blocks:
        for element in block.get("elements", []):
            if element.get("role_hint") != "text":
                continue
            text = element.get("text", "")
            if not text:
                continue
            item_key = (
                block["script"],
                block["pack_member"],
                int(block["dialog_id"]),
                int(block["block_index"]),
                int(element["element_index"]),
            )
            if item_key in out and out[item_key] != text:
                duplicates.add(item_key)
                continue
            out[item_key] = text
    if duplicates:
        raise ValueError(f"conflicting resolved text keys: {len(duplicates)}")
    return out


def count_tokenish(text: str) -> int:
    count = 0
    i = 0
    while i < len(text):
        if i + 5 < len(text) and text[i] == "{" and text[i + 5] == "}":
            token = text[i + 1 : i + 5]
            if all(ch in "0123456789ABCDEFabcdef" for ch in token):
                count += 1
                i += 6
                continue
        i += 1
    return count


def main() -> None:
    resolved = build_resolved_text_map()
    old_patch = json.loads(OLD_PATCH.read_text(encoding="utf-8"))
    old_editable = json.loads(OLD_EDITABLE.read_text(encoding="utf-8"))

    updated_patch = []
    patch_matched = 0
    patch_unmatched = 0
    tokenish_before = 0
    tokenish_after = 0
    changed_examples = []

    for row in old_patch:
        item = dict(row)
        old_text = item.get("text", "")
        new_text = resolved.get(key(item))
        tokenish_before += count_tokenish(old_text)
        if new_text is not None:
            patch_matched += 1
            item["text"] = new_text
            tokenish_after += count_tokenish(new_text)
            if old_text != new_text and len(changed_examples) < 12:
                changed_examples.append(
                    {
                        "script": item["script"],
                        "pack_member": item["pack_member"],
                        "dialog_id": item["dialog_id"],
                        "element_index": item["element_index"],
                        "old": old_text,
                        "new": new_text,
                    }
                )
        else:
            patch_unmatched += 1
            tokenish_after += count_tokenish(old_text)
        item["source_table"] = "resolved_boot_table_plus_overflow"
        updated_patch.append(item)

    old_patch_by_key = {key(row): row for row in updated_patch}
    updated_editable = []
    editable_matched = 0
    editable_unmatched = 0
    for row in old_editable:
        item = dict(row)
        patch_row = old_patch_by_key.get(key(item))
        if patch_row:
            item["ja"] = patch_row["text"]
            item["status"] = "resolved_reflow15_noreloc"
            warnings = list(item.get("warnings", []))
            note = "resolved_source_text_synced"
            if note not in warnings:
                warnings.append(note)
            item["warnings"] = warnings
            editable_matched += 1
        else:
            editable_unmatched += 1
        updated_editable.append(item)

    OUT_PATCH.write_text(json.dumps(updated_patch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_EDITABLE.write_text(json.dumps(updated_editable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Resolved Reflow15 No-Relocation Translation Upgrade",
        "",
        "- Base Korean translation: `outputs/translations_quality_v2_manual_reflow15_noreloc.json`",
        "- Source text authority: `outputs/dialog_structure_resolved/raw/dialog_blocks_structured.json`",
        f"- Patch rows: {len(updated_patch)}",
        f"- Patch rows matched to resolved source text: {patch_matched}",
        f"- Patch rows preserved without resolved match: {patch_unmatched}",
        f"- Editable rows matched: {editable_matched}",
        f"- Editable rows preserved without patch match: {editable_unmatched}",
        f"- Four-hex source placeholders before: {tokenish_before}",
        f"- Four-hex source placeholders after: {tokenish_after}",
        "",
        "## Changed Source Examples",
        "",
    ]
    for example in changed_examples:
        lines.extend(
            [
                f"- `{example['script']}/{example['pack_member']}` dialog `{example['dialog_id']}` element `{example['element_index']}`",
                f"  - old: `{example['old'][:160].replace(chr(10), ' / ')}`",
                f"  - new: `{example['new'][:160].replace(chr(10), ' / ')}`",
            ]
        )
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_PATCH)
    print(OUT_EDITABLE)
    print(
        json.dumps(
            {
                "patch_rows": len(updated_patch),
                "patch_matched": patch_matched,
                "patch_unmatched": patch_unmatched,
                "editable_matched": editable_matched,
                "editable_unmatched": editable_unmatched,
                "tokenish_before": tokenish_before,
                "tokenish_after": tokenish_after,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
