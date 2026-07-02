#!/usr/bin/env python3
import json
import re
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path

import boku_tools


ROOT = Path("work")
REFINED = ROOT / "translation_survey" / "dialog_targets_refined.json"
BASE = ROOT / "translations.json"
TABLE = ROOT / "Boku-no-Natsuyasumi" / "font" / "table.txt"
OUT = ROOT / "translations_rough_all.json"
CACHE = ROOT / "rough_translate_cache.json"

SEP = "<<<SEG>>>"
PAUSE_TOKEN = "<<<PAUSE>>>"


def visible_len(text: str) -> int:
    count = 0
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = text.find("}", i + 1)
            if end != -1:
                i = end + 1
                continue
        if text[i] != "\n":
            count += 1
        i += 1
    return count


def split_raw_pages(raw_hex: str, table: dict[int, str]):
    raw = bytes.fromhex(raw_hex)
    pages = []
    current = []
    prefixes = []
    pos = 0
    while pos + 1 < len(raw):
        value = struct.unpack_from("<H", raw, pos)[0]
        if value in (0x8000, 0xFFFF):
            break
        if value == 0x8002:
            pages.append("".join(current))
            current = []
            pos += 2
            prefix = bytearray()
            if pos + 3 < len(raw):
                next_value = struct.unpack_from("<H", raw, pos)[0]
                after = struct.unpack_from("<H", raw, pos + 2)[0]
                if next_value not in (0x8000, 0x8001, 0x8002, 0xFFFF) and after == 0:
                    prefix.extend(raw[pos : pos + 4])
                    pos += 4
            prefixes.append(bytes(prefix).hex().upper())
            continue
        if value == 0:
            pos += 2
            continue
        if value == 0x8001:
            current.append("\n")
        elif value in table:
            current.append(table[value])
        else:
            current.append(f"{{{value:04X}}}")
        pos += 2
    pages.append("".join(current))
    return pages, prefixes


def normalize_for_mt(text: str) -> str:
    text = text.replace("{PAUSE}", PAUSE_TOKEN)
    return text


def google_translate_batch(texts: list[str]) -> list[str]:
    if not texts:
        return []
    q = f"\n{SEP}\n".join(normalize_for_mt(t) for t in texts)
    url = (
        "https://translate.googleapis.com/translate_a/single?client=gtx&sl=ja&tl=ko&dt=t&q="
        + urllib.parse.quote(q)
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            translated = "".join(part[0] for part in data[0]).replace(PAUSE_TOKEN, "{PAUSE}")
            parts = translated.split(SEP)
            if len(parts) == len(texts):
                return [part.strip() for part in parts]
        except Exception:
            if attempt == 3:
                raise
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("translation batch did not preserve separators")



def _normalize_visible_chars(text: str) -> str:
    punctuation = {
        ',': '\u3001', '.': '\u3002', '?': '\uff1f', '!': '\uff01', ':': '\uff1a', ';': '\uff1b',
        '(': '\uff08', ')': '\uff09', '[': '\u3010', ']': '\u3011', '/': '\uff0f', '-': '\u2212',
        '~': '\u301c', '"': '\u300d', "'": '\u2019', '%': '\uff05', '+': '\uff0b', '_': '\uff3f',
        '|': '\uff5c', '`': '\u2019', '\u201c': '\u300c', '\u201d': '\u300d', '\u2018': '\u2018',
        '\u2019': '\u2019', '\u2014': '\u2212', '\u00b7': '\u30fb',
    }
    out = []
    for ch in text.translate(str.maketrans(punctuation)):
        if '0' <= ch <= '9':
            out.append(chr(ord('\uff10') + ord(ch) - ord('0')))
        elif 'A' <= ch <= 'Z':
            out.append(chr(ord('\uff21') + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z':
            out.append(chr(ord('\uff41') + ord(ch) - ord('a')))
        elif ch == '\u3387':
            out.append('\uff27\uff22')
        else:
            out.append(ch)
    return ''.join(out)


def clean_ko(text: str) -> str:
    text = text.replace('\r', ' ').replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    token_re = re.compile(r'(\{(?:RAW:[0-9A-Fa-f]+|PAUSE|[0-9A-Fa-f]{4})\})')
    parts = []
    for part in token_re.split(text):
        if not part:
            continue
        if token_re.fullmatch(part):
            parts.append(part)
        else:
            parts.append(_normalize_visible_chars(part))
    return ''.join(parts)


def iter_wrappable_units(text: str):
    i = 0
    while i < len(text):
        if text[i] == '{':
            end = text.find('}', i + 1)
            if end != -1:
                yield text[i:end + 1], 0
                i = end + 1
                continue
        yield text[i], 0 if text[i] == '\n' else 1
        i += 1


def take_visible_units(units, budget: int):
    taken = []
    visible = 0
    while units:
        token, width = units[0]
        if width and visible + width > budget:
            break
        taken.append(token)
        visible += width
        units.pop(0)
    return ''.join(taken)


def truncate_visible(text: str, budget: int) -> str:
    if visible_len(text) <= budget:
        return text
    if budget <= 0:
        return ''
    units = list(iter_wrappable_units(text))
    return take_visible_units(units, max(0, budget - 1)) + '\u2026'


def wrap_to_budgets(text: str, budgets: list[int]) -> str:
    text = clean_ko(text).replace(' ', '\u3000')
    total = sum(max(0, b) for b in budgets)
    if total <= 0:
        return ''
    text = truncate_visible(text, total)
    units = list(iter_wrappable_units(text))
    lines = []
    for idx, budget in enumerate(budgets):
        if idx == len(budgets) - 1:
            lines.append(''.join(token for token, _ in units))
            units.clear()
        else:
            lines.append(take_visible_units(units, budget))
    return '\n'.join(lines)

def main() -> None:
    table = boku_tools.load_table(TABLE)
    refined = json.loads(REFINED.read_text(encoding="utf-8"))
    base = json.loads(BASE.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    page_jobs = []
    page_meta = []
    for row in refined:
        pages, prefixes = split_raw_pages(row["full_raw_hex"], table)
        for page_index, page in enumerate(pages):
            key = f"{row['index']}:{page_index}"
            if key not in cache:
                page_jobs.append(page)
                page_meta.append(key)

    batch_size = 24
    for start in range(0, len(page_jobs), batch_size):
        batch = page_jobs[start : start + batch_size]
        keys = page_meta[start : start + batch_size]
        translated = google_translate_batch(batch)
        for key, text in zip(keys, translated):
            cache[key] = text
        if start % (batch_size * 10) == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"translated pages {start + len(batch)}/{len(page_jobs)}")
        time.sleep(0.15)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    for row in refined:
        idx = row["index"]
        pages, prefixes = split_raw_pages(row["full_raw_hex"], table)
        ko_pages = []
        for page_index, page in enumerate(pages):
            budgets = [visible_len(line) for line in page.splitlines()] or [visible_len(page)]
            ko_pages.append(wrap_to_budgets(cache[f"{idx}:{page_index}"], budgets))
        joined = ko_pages[0] if ko_pages else ""
        for page_index, page in enumerate(ko_pages[1:]):
            raw_prefix = prefixes[page_index] if page_index < len(prefixes) else ""
            joined += "{PAUSE}"
            if raw_prefix:
                joined += f"{{RAW:{raw_prefix}}}"
            joined += page
        item = dict(base[idx])
        item["text"] = row["full_text"]
        item["raw_hex"] = row["full_raw_hex"]
        item["terminator_hex"] = row["terminator_hex"]
        item["ko"] = joined
        item["status"] = "rough_mt"
        base[idx] = item

    OUT.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    print(f"dialogs={len(base)} ko={sum(1 for item in base if item.get('ko'))}")


if __name__ == "__main__":
    main()
