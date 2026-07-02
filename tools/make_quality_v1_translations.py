#!/usr/bin/env python3
import json
import re
from pathlib import Path

import boku_tools


ROOT = Path("work")
REFINED = ROOT / "translation_survey" / "dialog_targets_refined.json"
ROUGH = ROOT / "translations_rough_all.json"
OUT_DIR = ROOT / "translation_quality"
EDITABLE = OUT_DIR / "translation_quality_v1_editable.json"
PATCH_TRANSLATIONS = ROOT / "translations_quality_v1.json"
REPORT = OUT_DIR / "translation_quality_v1_report.md"


SPEAKER_MAP = {
    "ボク": "보쿠",
    "おじ": "아저씨",
    "おば": "아주머니",
    "教頭せんせ": "교감 선생님",
    "ヨシコ": "요시코",
    "ヤスコ": "야스코",
    "モエ": "모에",
    "萌": "모에",
    "太陽": "타이요",
    "小説家": "소설가",
    "郵便屋": "우체부",
    "坊さん": "스님",
    "和尚": "스님",
    "父": "아빠",
    "母": "엄마",
}


TERM_REPLACEMENTS = [
    ("나 「", "보쿠「"),
    ("나「", "보쿠「"),
    ("내 「", "보쿠「"),
    ("저 「", "보쿠「"),
    ("삼촌", "아저씨"),
    ("숙모", "아주머니"),
    ("이모", "아주머니"),
    ("메모리 스틱", "메모리스틱"),
    ("여름 방학", "여름방학"),
    ("곤충 스모", "곤충 씨름"),
    ("곤충씨름", "곤충 씨름"),
    ("즐겨 찾기", "즐겨찾기"),
    ("로드", "불러오기"),
    ("세이브", "저장"),
    ("데이타", "데이터"),
    ("타이틀 화면", "타이틀 화면"),
    ("괜찮습니까", "괜찮을까요"),
    ("계속합니까", "계속할까요"),
    ("차갑다……", "차가워…"),
    ("차갑다…", "차가워…"),
    ("어디 …", "어디야"),
    ("뭐야 …", "뭐지"),
    ("일 재검토\n해버렸어", "널\n다시 봤어"),
    ("일 재검토해버렸어", "널 다시 봤어"),
]


PUNCT_MAP = str.maketrans(
    {
        ",": "、",
        ".": "。",
        "?": "？",
        "!": "！",
        ":": "：",
        ";": "；",
        "(": "（",
        ")": "）",
        "[": "【",
        "]": "】",
        "/": "／",
        "-": "−",
        "~": "〜",
        '"': "”",
        "%": "％",
        "+": "＋",
        "_": "＿",
        "|": "｜",
        "`": "’",
        "“": "「",
        "”": "」",
        "·": "・",
        "—": "−",
    }
)


TOKEN_RE = re.compile(r"(\{(?:RAW:[0-9A-Fa-f]+|PAUSE|[0-9A-Fa-f０-９Ａ-Ｆａ-ｆ]{4})\})")


def visible_len(text: str) -> int:
    return boku_tools.layout_units(text)[0] if "\n" not in text else sum(boku_tools.layout_units(text))


def iter_units(text: str):
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = text.find("}", i + 1)
            if end != -1:
                yield text[i : end + 1], 0
                i = end + 1
                continue
        yield text[i], 0 if text[i] == "\n" else 1
        i += 1


def truncate_to_budget(text: str, budget: int) -> tuple[str, bool]:
    if visible_len(text) <= budget:
        return text, False
    if budget <= 0:
        return "", True
    out = []
    count = 0
    for token, width in iter_units(text):
        if width and count + width > max(0, budget - 1):
            break
        out.append(token)
        count += width
    return "".join(out) + "…", True


def normalize_tokens(text: str) -> str:
    table = str.maketrans("０１２３４５６７８９ＡＢＣＤＥＦａｂｃｄｅｆ", "0123456789ABCDEFabcdef")

    def repl(match: re.Match) -> str:
        token = match.group(0)
        if token.startswith("{RAW:") or token == "{PAUSE}":
            return token
        return "{" + token[1:5].translate(table).upper() + "}"

    return TOKEN_RE.sub(repl, text)


def normalize_visible(text: str, *, game_spacing: bool) -> str:
    parts = []
    for part in TOKEN_RE.split(text):
        if not part:
            continue
        if TOKEN_RE.fullmatch(part):
            parts.append(normalize_tokens(part))
            continue
        part = part.replace("\u3000", " ")
        part = re.sub(r"[ \t]+", " ", part)
        part = part.translate(PUNCT_MAP)
        if game_spacing:
            chars = []
            for ch in part:
                if "0" <= ch <= "9":
                    chars.append(chr(ord("０") + ord(ch) - ord("0")))
                elif "A" <= ch <= "Z":
                    chars.append(chr(ord("Ａ") + ord(ch) - ord("A")))
                elif "a" <= ch <= "z":
                    chars.append(chr(ord("ａ") + ord(ch) - ord("a")))
                else:
                    chars.append(ch)
            part = "".join(chars)
        if game_spacing:
            part = part.replace(" ", "\u3000")
        parts.append(part)
    return "".join(parts).strip()


def source_speaker(ja: str) -> tuple[str | None, str | None]:
    m = re.match(r"^([^「\n{}]{1,12})「", ja)
    if not m:
        return None, None
    raw = m.group(1)
    return raw, SPEAKER_MAP.get(raw, raw)


def fix_terms(text: str) -> str:
    for src, dst in TERM_REPLACEMENTS:
        text = text.replace(src, dst)
    text = re.sub(r"\s+「", "「", text)
    text = re.sub(r"「\s+", "「", text)
    text = re.sub(r"\s+」", "」", text)
    return text


def strip_existing_speaker(ko: str) -> str:
    if "「" in ko:
        return ko.split("「", 1)[1]
    return ko


def improve_dialog(ja: str, rough_ko: str) -> tuple[str, list[str]]:
    warnings = []
    text = normalize_tokens(rough_ko)
    text = normalize_visible(text, game_spacing=False)
    text = fix_terms(text)

    raw_speaker, ko_speaker = source_speaker(ja)
    if ko_speaker:
        body = strip_existing_speaker(text).strip()
        text = f"{ko_speaker}「{body}"
        warnings.append(f"speaker_fixed:{raw_speaker}->{ko_speaker}")
    elif ja.startswith("「") and not text.startswith("「"):
        text = "「" + text
        warnings.append("opening_quote_restored")

    if ja.rstrip().endswith("」") and not text.rstrip().endswith("」"):
        text = text.rstrip() + "」"
        warnings.append("closing_quote_restored")

    text = text.replace("… …", "…").replace("…… …", "……")
    text = re.sub(r" {2,}", " ", text)
    return text, warnings


def to_game_layout(ja: str, edit_text: str) -> tuple[str, list[str]]:
    warnings = []
    game = normalize_visible(edit_text, game_spacing=True)
    source_units = boku_tools.layout_units(ja)
    lines = game.splitlines() or [game]
    out_lines = []
    for idx, line in enumerate(lines[: len(source_units)]):
        fixed, truncated = truncate_to_budget(line, source_units[idx])
        if truncated:
            warnings.append(f"truncated_line:{idx + 1}")
        out_lines.append(fixed)
    if len(lines) > len(source_units):
        warnings.append("dropped_extra_lines")
    while len(out_lines) > 1 and out_lines[-1] == "":
        out_lines.pop()
    return "\n".join(out_lines), warnings


def main() -> None:
    refined = json.loads(REFINED.read_text(encoding="utf-8"))
    rough = json.loads(ROUGH.read_text(encoding="utf-8"))
    editable = []
    patch_rows = []
    warning_counts: dict[str, int] = {}

    for row, base in zip(refined, rough):
        ja = row["full_text"]
        rough_ko = base.get("ko", "")
        edit_text, warnings = improve_dialog(ja, rough_ko)
        game_text, layout_warnings = to_game_layout(ja, edit_text)
        warnings.extend(layout_warnings)
        if re.search(r"\{[0-9A-F]{4}\}", game_text):
            warnings.append("contains_unresolved_game_glyph_token")
        if "…" in game_text and any(w.startswith("truncated") for w in warnings):
            warnings.append("meaning_may_be_shortened")

        for warning in warnings:
            key = warning.split(":", 1)[0]
            warning_counts[key] = warning_counts.get(key, 0) + 1

        item = dict(base)
        item["text"] = ja
        item["raw_hex"] = row["full_raw_hex"]
        item["terminator_hex"] = row["terminator_hex"]
        item["ko"] = game_text
        item["status"] = "quality_v1"
        patch_rows.append(item)

        editable.append(
            {
                "type": "dialog",
                "index": row["index"],
                "script": row["script"],
                "member": row["pack_member"],
                "dialog_id": row["dialog_id"],
                "block_index": row["block_index"],
                "element_index": row["element_index"],
                "pages": row["pages"],
                "ja": ja,
                "ko_rough": normalize_visible(rough_ko, game_spacing=False),
                "ko_edit": edit_text,
                "ko_game": game_text,
                "status": "quality_v1_auto_postedit",
                "warnings": warnings,
                "human_note": "",
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EDITABLE.write_text(json.dumps(editable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PATCH_TRANSLATIONS.write_text(json.dumps(patch_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Translation Quality V1 Report",
        "",
        f"- Dialog entries: {len(patch_rows)}",
        f"- Editable JSON: `{EDITABLE}`",
        f"- Patch JSON: `{PATCH_TRANSLATIONS}`",
        "",
        "## Warning Counts",
        "",
    ]
    for key, count in sorted(warning_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{key}`: {count}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(PATCH_TRANSLATIONS)
    print(EDITABLE)
    print(json.dumps(warning_counts, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
