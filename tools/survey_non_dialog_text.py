#!/usr/bin/env python3
import csv
import gzip
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boku_tools


ROOT = Path("work/cdimg0_extracted")
EBOOT = Path(r"C:\Users\Jae Ho Lee\Pictures\psp\roms\Boku no Natsuyasumi Portable\PSP_GAME\SYSDIR\EBOOT.BIN")
OUT_DIR = Path("work/non_dialog_survey")

TEXT_EXTS = {".bin", ".bms", ".bmh", ".dat", ".gzx", ".prx", ".txt"}
SKIP_EXTS = {".pmf", ".sgd", ".pm2", ".png", ".at3"}
INCLUDE_DIR_PREFIXES = {
    ("00modules_new",),
    ("01startup",),
    ("demo",),
    ("diary",),
    ("map", "models", "system"),
}
MIN_JP_CHARS = 2
TABLE = Path("work/Boku-no-Natsuyasumi/font/table.txt")
KEYWORDS = [
    "\u30e1\u30e2\u30ea\u30fc",
    "\u30bb\u30fc\u30d6",
    "\u30ed\u30fc\u30c9",
    "\u306f\u3044",
    "\u3044\u3044\u3048",
    "\u65e5\u8a18",
    "\u8a2d\u5b9a",
    "\u7d42\u4e86",
    "\u30a8\u30e9\u30fc",
    "\u30ab\u30fc\u30c9",
    "\u30b9\u30bf\u30fc\u30c8",
    "\u30b2\u30fc\u30e0",
    "\u30c7\u30fc\u30bf",
    "\u4fdd\u5b58",
    "\u8aad\u8fbc",
    "\u524a\u9664",
    "\u4e0a\u66f8",
    "\u7d9a\u304d",
    "\u521d\u3081",
    "\u590f\u4f11\u307f",
    "\u30dc\u30af",
]


def is_japanese(ch: str) -> bool:
    return (
        "\u3040" <= ch <= "\u30ff"
        or "\u3400" <= ch <= "\u9fff"
        or "\uf900" <= ch <= "\ufaff"
    )


def japanese_count(text: str) -> int:
    return sum(1 for ch in text if is_japanese(ch))


def printable_score(text: str) -> float:
    if not text:
        return 0.0
    ok = 0
    for ch in text:
        code = ord(ch)
        if ch in "\r\n\t" or 0x20 <= code <= 0x7E or is_japanese(ch) or ch in "、。，．！？「」『』（）ー…・〜":
            ok += 1
    return ok / len(text)


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def add_candidate(rows: list[dict], source: str, layer: str, encoding: str, offset: int, raw: bytes, text: str) -> None:
    text = clean_text(text)
    if japanese_count(text) < MIN_JP_CHARS:
        return
    if printable_score(text) < 0.65:
        return
    if len(text) > 500:
        text = text[:500] + "..."
    rows.append(
        {
            "source": source,
            "layer": layer,
            "encoding": encoding,
            "offset_hex": f"0x{offset:X}",
            "raw_len": len(raw),
            "jp_chars": japanese_count(text),
            "text": text,
        }
    )


def add_text_file_candidate(rows: list[dict], source: str, layer: str, data: bytes) -> None:
    for encoding in ("utf-16le", "cp932"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if japanese_count(text) >= 20 and printable_score(text) >= 0.8:
            add_candidate(rows, source, layer, encoding, 0, data, text)
            return


def scan_keyword_encodings(data: bytes, source: str, layer: str, rows: list[dict]) -> None:
    for keyword in KEYWORDS:
        for encoding in ("cp932", "utf-16le"):
            needle = keyword.encode(encoding)
            offset = data.find(needle)
            while offset >= 0:
                start = max(0, offset - 80)
                end = min(len(data), offset + len(needle) + 160)
                chunk = data[start:end]
                try:
                    text = chunk.decode(encoding, errors="ignore")
                except UnicodeDecodeError:
                    text = keyword
                add_candidate(rows, source, layer, f"{encoding}:keyword", offset, needle, text)
                offset = data.find(needle, offset + len(needle))


def scan_game16(data: bytes, source: str, layer: str, table: dict[int, str], rows: list[dict]) -> None:
    start = None
    out = []
    raw = bytearray()

    def flush() -> None:
        nonlocal start, out, raw
        if start is not None:
            text = "".join(out)
            visible = sum(1 for ch in text if ch != "\n")
            if visible >= 2 and japanese_count(text) >= 1:
                add_candidate(rows, source, layer, "game16", start, bytes(raw), text)
        start = None
        out = []
        raw = bytearray()

    for pos in range(0, len(data) - 1, 2):
        value = struct.unpack_from("<H", data, pos)[0]
        if value in table or value in (0x8000, 0x8001, 0x8002):
            if start is None:
                start = pos
            raw.extend(data[pos : pos + 2])
            if value == 0x8000:
                flush()
            elif value == 0x8001:
                out.append("\n")
            elif value == 0x8002:
                out.append("{PAUSE}")
            else:
                out.append(table[value])
        else:
            flush()
    flush()


def scan_cp932(data: bytes, source: str, layer: str, rows: list[dict]) -> None:
    start = None
    buf = bytearray()

    def flush(end: int) -> None:
        nonlocal start, buf
        if start is not None and len(buf) >= 4:
            try:
                text = bytes(buf).decode("cp932")
            except UnicodeDecodeError:
                text = bytes(buf).decode("cp932", errors="ignore")
            add_candidate(rows, source, layer, "cp932", start, bytes(buf), text)
        start = None
        buf = bytearray()

    i = 0
    while i < len(data):
        b = data[i]
        valid = False
        take = 0
        if b in (0x09, 0x0A, 0x0D) or 0x20 <= b <= 0x7E or 0xA1 <= b <= 0xDF:
            valid = True
            take = 1
        elif i + 1 < len(data) and (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC):
            b2 = data[i + 1]
            if 0x40 <= b2 <= 0xFC and b2 != 0x7F:
                valid = True
                take = 2
        if valid:
            if start is None:
                start = i
            buf.extend(data[i : i + take])
            i += take
        else:
            flush(i)
            i += 1
    flush(len(data))


def scan_utf16le(data: bytes, source: str, layer: str, rows: list[dict]) -> None:
    start = None
    buf = bytearray()

    def unit_ok(value: int) -> bool:
        ch = chr(value)
        return ch in "\r\n\t" or 0x20 <= value <= 0x7E or is_japanese(ch) or ch in "、。，．！？「」『』（）ー…・〜"

    def flush(end: int) -> None:
        nonlocal start, buf
        if start is not None and len(buf) >= 8:
            try:
                text = bytes(buf).decode("utf-16le")
            except UnicodeDecodeError:
                text = bytes(buf).decode("utf-16le", errors="ignore")
            add_candidate(rows, source, layer, "utf-16le", start, bytes(buf), text)
        start = None
        buf = bytearray()

    i = 0
    while i + 1 < len(data):
        value = struct.unpack_from("<H", data, i)[0]
        if value and unit_ok(value):
            if start is None:
                start = i
            buf.extend(data[i : i + 2])
            i += 2
        else:
            flush(i)
            i += 2
    flush(len(data))


def maybe_gzip_payload(data: bytes) -> bytes | None:
    for start in (0, 4):
        if len(data) > start + 2 and data[start : start + 2] == b"\x1f\x8b":
            try:
                return gzip.decompress(data[start:])
            except (OSError, EOFError):
                return None
    return None


def maybe_pack_members(data: bytes) -> list[tuple[str, bytes]]:
    if len(data) < 12:
        return []
    count = struct.unpack_from("<I", data, 0)[0]
    if count <= 0 or count > 512:
        return []

    def plausible_header(with_names: bool) -> bool:
        entry_size = 0x0C if with_names else 0x08
        header_end = 4 + count * entry_size
        if header_end > len(data):
            return False
        offsets = []
        for i in range(count):
            base = 4 + i * entry_size
            off, size = struct.unpack_from("<II", data, base)
            if off == 0 and size == 0:
                continue
            if off < header_end or size <= 0 or off + size > len(data):
                return False
            offsets.append(off)
            if with_names:
                name_off = struct.unpack_from("<I", data, base + 8)[0]
                if name_off < header_end or name_off >= len(data) or b"\0" not in data[name_off : min(len(data), name_off + 256)]:
                    return False
        return bool(offsets)

    for with_names in (True, False):
        if not plausible_header(with_names):
            continue
        try:
            entries = boku_tools.parse_pack_entries(data, with_names=with_names)
        except Exception:
            continue
        if not entries:
            continue
        valid = []
        for entry in entries:
            off = entry["offset"]
            size = entry["size"]
            if off == 0 or size == 0:
                continue
            if off < 4 or size < 0 or off + size > len(data):
                valid = []
                break
            valid.append((entry["name"], data[off : off + size]))
        if valid:
            return valid
    return []


def scan_blob(source: str, layer: str, data: bytes, rows: list[dict], table: dict[int, str], depth: int = 0) -> None:
    label = f"{source} {layer}".lower()
    scan_keyword_encodings(data, source, layer, rows)
    if ".bms" in label or ".bmh" in label:
        scan_game16(data, source, layer, table, rows)
    if ".txt" in label:
        add_text_file_candidate(rows, source, layer, data)
    if depth >= 2:
        return
    payload = maybe_gzip_payload(data)
    if payload:
        scan_blob(source, f"{layer}:gzip", payload, rows, table, depth + 1)
    for name, member in maybe_pack_members(data):
        scan_blob(source, f"{layer}:pack:{name}", member, rows, table, depth + 1)


def candidate_files() -> list[Path]:
    files = [EBOOT]
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if len(rel_parts) >= 2 and rel_parts[0] == "map" and rel_parts[1] == "gz":
            continue
        if not any(rel_parts[: len(prefix)] == prefix for prefix in INCLUDE_DIR_PREFIXES):
            continue
        suffix = path.suffix.lower()
        if suffix in SKIP_EXTS:
            continue
        if suffix in TEXT_EXTS:
            files.append(path)
    return files


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = boku_tools.load_table(TABLE)
    rows: list[dict] = []
    files = candidate_files()
    for path in files:
        source = str(path)
        if path.is_relative_to(Path.cwd()):
            source = str(path.relative_to(Path.cwd()))
        try:
            data = path.read_bytes()
        except OSError as exc:
            rows.append(
                {
                    "source": source,
                    "layer": "file",
                    "encoding": "error",
                    "offset_hex": "",
                    "raw_len": 0,
                    "jp_chars": 0,
                    "text": str(exc),
                }
            )
            continue
        scan_blob(source, "file", data, rows, table)

    unique = []
    seen = set()
    for row in rows:
        key = (row["source"], row["layer"], row["encoding"], row["offset_hex"], row["text"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    rows = sorted(unique, key=lambda row: (row["source"], row["layer"], row["encoding"], row["offset_hex"]))

    json_path = OUT_DIR / "non_dialog_text_candidates.json"
    csv_path = OUT_DIR / "non_dialog_text_candidates.csv"
    md_path = OUT_DIR / "non_dialog_text_survey.md"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "layer", "encoding", "offset_hex", "raw_len", "jp_chars", "text"])
        writer.writeheader()
        writer.writerows(rows)

    by_source = Counter(row["source"] for row in rows)
    by_encoding = Counter(row["encoding"] for row in rows)
    layers = defaultdict(int)
    for row in rows:
        top = row["layer"].split(":")[0]
        layers[top] += 1

    md = []
    md.append("# Non-dialog Text Survey")
    md.append("")
    md.append("This survey scans EBOOT.BIN and non-script resource files for Japanese text candidates outside the dialogue table.")
    md.append("Candidates are collected from game 16-bit text streams, explicit UTF-16 text files, and direct CP932/UTF-16 keyword hits, including gzip payloads and simple pack members where detected.")
    md.append("")
    md.append("## Summary")
    md.append("")
    md.append(f"- Files scanned: {len(files)}")
    md.append(f"- Candidate strings: {len(rows)}")
    md.append(f"- Encodings: {dict(by_encoding)}")
    md.append(f"- Top-level layers: {dict(layers)}")
    md.append("")
    md.append("## Top Sources")
    md.append("")
    md.append("| Source | Candidates |")
    md.append("|---|---:|")
    for source, count in by_source.most_common(30):
        md.append(f"| `{source}` | {count} |")
    md.append("")
    md.append("## EBOOT.BIN Candidates")
    md.append("")
    eboot_rows = [row for row in rows if row["source"].endswith("EBOOT.BIN")]
    if eboot_rows:
        for row in eboot_rows[:80]:
            md.append(f"- `{row['offset_hex']}` {row['encoding']}: `{row['text']}`")
        if len(eboot_rows) > 80:
            md.append(f"- ... {len(eboot_rows) - 80} more in CSV/JSON")
    else:
        md.append("- No Japanese candidates found in EBOOT.BIN by this scanner.")
    md.append("")
    md.append("## System/Menu Resource Samples")
    md.append("")
    sample_rows = [row for row in rows if "system" in row["source"].lower() or "startup" in row["source"].lower() or row["source"].endswith(".prx")]
    for row in sample_rows[:100]:
        md.append(f"- `{row['source']}` `{row['layer']}` `{row['offset_hex']}` {row['encoding']}: `{row['text']}`")
    if len(sample_rows) > 100:
        md.append(f"- ... {len(sample_rows) - 100} more in CSV/JSON")
    md.append("")
    md.append("## Files")
    md.append("")
    md.append(f"- JSON: `{json_path}`")
    md.append(f"- CSV: `{csv_path}`")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(md_path)
    print(json_path)
    print(csv_path)
    print(f"files={len(files)} rows={len(rows)} eboot={len([r for r in rows if r['source'].endswith('EBOOT.BIN')])}")


if __name__ == "__main__":
    main()
