#!/usr/bin/env python3
import csv
import json
from pathlib import Path


BASE_TABLE = Path("work/Boku-no-Natsuyasumi/font/table.txt")
SEEDS = [
    Path("outputs/dialog_structure_v2/unknown_word_candidates_seed.csv"),
    Path("outputs/dialog_structure_v3/unknown_word_candidates_seed2.csv"),
    Path("outputs/dialog_structure_v3/unknown_word_candidates_seed3.csv"),
    Path("outputs/dialog_structure_v3/unknown_word_candidates_seed4.csv"),
    Path("outputs/dialog_structure_v3/unknown_word_candidates_seed5_fix_seed1.csv"),
]
OUT_TABLE = Path("outputs/dialog_structure_v3/table_original_ext_seed.txt")
OUT_JSON = Path("outputs/dialog_structure_v3/table_original_ext_seed_map.json")


def parse_table(path: Path) -> dict[int, str]:
    table = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if len(line) >= 8 and line[:4].isdigit() and " = " in line:
            table[int(line[:4])] = line.split(" = ", 1)[1][:1]
    return table


def main() -> None:
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    table = parse_table(BASE_TABLE)
    additions = []
    for seed in SEEDS:
        if not seed.exists():
            continue
        with seed.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                word = int(row["word_hex"], 16)
                char = row["candidate_char"]
                if not char:
                    continue
                existing = table.get(word)
                if existing in {"?", "�"}:
                    existing = None
                if existing and existing != char:
                    raise ValueError(f"conflicting mapping for {word}: {existing!r} vs {char!r}")
                table[word] = char
                additions.append(
                    {
                        "code_dec": word,
                        "code_hex": row["word_hex"],
                        "char": char,
                        "basis": row.get("basis", ""),
                        "confidence": row.get("confidence", ""),
                        "seed": str(seed),
                    }
                )

    max_code = max(table)
    lines = []
    for code in range(max_code + 1):
        if code in table:
            lines.append(f"{code:04d} = {table[code]}")
    OUT_TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(additions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_TABLE}")
    print(f"additions={len(additions)} max_code={max_code}")


if __name__ == "__main__":
    main()
