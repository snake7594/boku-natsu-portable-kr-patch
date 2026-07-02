#!/usr/bin/env python3
import json
import re
from pathlib import Path


MASTER = Path("work/translation_master/translation_master.json")
BASE_TRANSLATIONS = Path("work/translations.json")
OUT_TRANSLATIONS = Path("work/translations_from_master.json")


def dialog_index(row_id: str) -> int | None:
    match = re.fullmatch(r"dialog:(\d+)", row_id)
    return int(match.group(1)) if match else None


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    translations = json.loads(BASE_TRANSLATIONS.read_text(encoding="utf-8"))
    applied = 0
    for row in master:
        if row.get("type") != "dialog":
            continue
        ko = row.get("ko", "")
        if not ko:
            continue
        idx = dialog_index(row.get("id", ""))
        if idx is None or idx >= len(translations):
            raise ValueError(f"invalid dialog id: {row.get('id')}")
        translations[idx]["ko"] = ko
        applied += 1
    OUT_TRANSLATIONS.write_text(json.dumps(translations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"applied dialog translations: {applied}")
    print(OUT_TRANSLATIONS)


if __name__ == "__main__":
    main()
