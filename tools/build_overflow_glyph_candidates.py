#!/usr/bin/env python3
import csv
from pathlib import Path


INVENTORY = Path("outputs/dialog_structure_eboot/unknown_word_inventory.csv")
OUT = Path("outputs/dialog_structure_eboot/overflow_glyph_candidates.csv")

CANDIDATES = {
    "05FE": ("\u6cd5", "\u5fc5\u52dd\u6cd5 / \u65b9\u6cd5", 0.95),
    "0600": ("\u52e7", "\u304a\u52e7\u3081", 0.95),
    "05F3": ("\u6765", "\u6765\u3066\u3044\u308b", 0.95),
    "05F4": ("\u5354", "\u5354\u529b", 0.98),
    "05EF": ("\u5fa9", "\u5fa9\u7fd2", 0.98),
    "05F1": ("\u52e2", "\u904b\u52e2", 0.95),
    "05F9": ("\u6f54", "\u6f54\u7656", 0.95),
    "05FA": ("\u7656", "\u6f54\u7656", 0.95),
    "05FD": ("\u596e", "\u8208\u596e", 0.95),
    "0601": ("\u7bc7", "\u5192\u967a\u7bc7", 0.95),
    "0602": ("\u7948", "\u304a\u7948\u308a", 0.95),
    "05FB": ("\u52a3", "\u8ca0\u3051\u305a\u52a3\u3089\u305a", 0.95),
    "05FC": ("\u5831", "\u5831\u544a", 0.95),
    "05FF": ("\u96e3", "\u96e3\u3057\u3044", 0.95),
    "0603": ("\u559c", "\u559c\u3093\u3067", 0.95),
    "05F2": ("\u5fd9", "\u5fd9\u3057\u3044", 0.95),
    "05F8": ("\u663c", "\u304a\u663c", 0.95),
    "0604": ("\u8ab0", "\u8ab0\u306e\u5c45\u5019", 0.95),
    "0605": ("\u614b", "\u614b\u5ea6", 0.95),
    "0606": ("\u6fc0", "\u6fc0\u3057\u3044", 0.95),
    "060D": ("\u616e", "\u9060\u616e", 0.95),
    "05F6": ("\u77e5", "\u77e5\u3063\u3066\u308b", 0.8),
    "05F5": ("\u7523", "\u7523\u5375", 0.95),
    "0608": ("\u9060", "\u9060\u304f\u96e2", 0.8),
    "0609": ("\u8ddd", "\u8ddd\u96e2", 0.9),
    "060A": ("\u708e", "\u708e\u5929\u4e0b", 0.85),
    "05F7": ("\u8f9b", "\u8f9b\u3044\u601d\u3044\u51fa", 0.85),
}


def main() -> None:
    with INVENTORY.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out_rows = []
    for row in rows:
        char, basis, confidence = CANDIDATES.get(row["word_hex"], ("", "", ""))
        out_rows.append(
            {
                **row,
                "candidate_char": char,
                "candidate_basis": basis,
                "confidence": confidence,
            }
        )
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)
    print(OUT)


if __name__ == "__main__":
    main()
