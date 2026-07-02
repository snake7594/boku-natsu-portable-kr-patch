#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


STRUCTURED = Path("outputs/translation_structured_v3_reflow15.json")
SIMPLE = Path("outputs/translation_edit_simple_resolved_reflow15_noreloc.json")
REPORT = Path("outputs/translation_structured_v3_sync_report.json")

KO_TRANSLATION = "\ud55c\uad6d\uc5b4_\ubc88\uc5ed"


def main() -> None:
    structured = json.loads(STRUCTURED.read_text(encoding="utf-8"))
    simple = json.loads(SIMPLE.read_text(encoding="utf-8"))
    if len(structured) != len(simple):
        raise ValueError(f"row count mismatch: {len(structured)} != {len(simple)}")

    changed = 0
    missing = []
    for index, (entry, row) in enumerate(zip(structured, simple)):
        try:
            ko_data = entry["\ud55c\uad6d\uc5b4"]
            labels = entry.get("\ubd84\ub958", [])
            if "choice_terminator" in labels and ko_data.get("\uc120\ud0dd\uc9c0"):
                ko_translation = "\n".join(str(line) for line in ko_data["\uc120\ud0dd\uc9c0"])
            else:
                ko_translation = ko_data["\ubc88\uc5ed"]
        except KeyError:
            missing.append(index)
            continue
        if row.get(KO_TRANSLATION, "") != ko_translation:
            row[KO_TRANSLATION] = ko_translation
            changed += 1

    SIMPLE.write_text(json.dumps(simple, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Regenerate insertion/build JSON from the canonical simple edit file, then
    # regenerate this structured view so page/layout diagnostics stay current.
    subprocess.run([sys.executable, "work/sync_simple_translation_edit.py"], check=True)
    subprocess.run([sys.executable, "work/make_translation_structured_v3.py"], check=True)

    report = {
        "rows": len(structured),
        "changed_translations": changed,
        "missing_translation_rows": missing,
        "updated": [
            "outputs/translation_edit_simple_resolved_reflow15_noreloc.json",
            "outputs/translations_quality_v2_resolved_reflow15_noreloc.json",
            "outputs/translation_structured_v3_reflow15.json",
        ],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
