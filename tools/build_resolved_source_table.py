#!/usr/bin/env python3
import csv
import json
from pathlib import Path


BASE = Path("outputs/eboot_font_table/eboot_font_table_cp932.txt")
OVERFLOW = Path("outputs/dialog_structure_eboot/overflow_glyph_candidates.csv")
OUT_DIR = Path("outputs/resolved_font_table")
OUT_TABLE = OUT_DIR / "source_font_table_resolved.txt"
OUT_MAP = OUT_DIR / "overflow_added_map.json"


def parse_table(path: Path) -> dict[int, str]:
    table = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if len(line) >= 8 and line[:4].isdigit() and " = " in line:
            table[int(line[:4])] = line.split(" = ", 1)[1]
    return table


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = parse_table(BASE)
    additions = []
    with OVERFLOW.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            char = row.get("candidate_char", "")
            if not char:
                continue
            code = int(row["word_dec"])
            confidence = float(row.get("confidence") or 0)
            if confidence < 0.8:
                continue
            existing = table.get(code)
            if existing and existing != char:
                raise ValueError(f"conflicting code {code:04X}: {existing!r} vs {char!r}")
            table[code] = char
            additions.append(
                {
                    "code_hex": row["word_hex"],
                    "code_dec": code,
                    "char": char,
                    "count": int(row.get("count") or 0),
                    "basis": row.get("candidate_basis", ""),
                    "confidence": confidence,
                    "first_location": row.get("first_location", ""),
                }
            )

    max_code = max(table)
    lines = []
    for code in range(max_code + 1):
        if code in table:
            lines.append(f"{code:04d} = {table[code]}")
    OUT_TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_MAP.write_text(json.dumps(additions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme = [
        "# Resolved Source Font Table",
        "",
        "- Base: executable table extracted from `BOOT.BIN`.",
        "- Overflow additions: context-verified `0x05EF+` candidates.",
        f"- Base entries: {len(parse_table(BASE))}",
        f"- Overflow additions: {len(additions)}",
        f"- Max code: `0x{max_code:04X}`",
        "",
        "Use this table for readable Japanese source extraction only. The executable's contiguous table still ends at `0x05EE`; overflow entries should remain documented separately for insertion/runtime work.",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(OUT_TABLE)
    print(f"overflow_additions={len(additions)} max_code=0x{max_code:04X}")


if __name__ == "__main__":
    main()
