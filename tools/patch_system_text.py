#!/usr/bin/env python3
import gzip
import json
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boku_tools


ROOT = Path("work/cdimg0_extracted")
BASE_TABLE = Path("work/Boku-no-Natsuyasumi/font/table.txt")
PREVIOUS_TRANSLATIONS = Path("work/translations_batch002_screens_0010_0018_spaced.json")
OUT_DIR = Path("work/system_text_patch")

START_CODE = 1800
END_CODE = 2047

TRANSLATIONS = {
    "①②③④⑤⑥⑦が差さっていません": "메모리스틱이　없습니다",
    "①②③④⑤⑥⑦にアクセス出来ません": "메모리스틱　접근　불가",
    "①②③④⑤⑥⑦の空き容量が不足しています\nセ－ブするには①②③④⑤⑥⑦の空き容量が\n３５２ＫＢ以上必要です": "메모리스틱　용량이　부족합니다\n저장하려면　여유　공간이\n３５２ＫＢ　이상　필요합니다",
    "このゲ－ムのファイルがありません": "게임　파일이　없습니다",
    "このゲ－ムを終了したファイルがありません": "종료한　게임　파일이　없습니다",
    "「お気に入り」ファイルがありません": "「즐겨찾기」파일이　없습니다",
    "デ－タの読み込みに失敗しました": "데이터　읽기에　실패했습니다",
    "デ－タの書き込みに失敗しました": "데이터　쓰기에　실패했습니다",
    "①②③④⑤⑥⑦が抜かれました": "메모리스틱이　빠졌습니다",
    "デ－タが壊れています": "데이터　손상됨",
    "①②③④⑤⑥⑦がロックされています": "메모리스틱이　잠겨　있습니다",
    "デ－タがありません": "데이터가　없습니다",
    "内部エラ－が発生しました": "내부　오류　발생",
    "スリ－プモ－ドに切り替わったため\n処理が中止されました": "슬립　모드로　전환되어\n처리가　중지되었습니다",
    "セ－ブに失敗しました": "저장에　실패했습니다",
    "ロ－ドに失敗しました": "불러오기　실패",
    "消去に失敗しました": "삭제　실패",
    "チェックに失敗しました": "확인에　실패했습니다",
    "はい": "예",
    "いいえ": "아니오",
    "ゲ－ムデ－タを整理しますか？": "게임　데이터를　정리할까요？",
    "【①②③④⑤⑥⑦を抜かないでください】": "【메모리스틱을　빼지　마세요】",
    "今日までの出来事を\n①②③④⑤⑥⑦に記録しますか？\n３５２ＫＢ以上使用します": "오늘까지의　일을\n메모리스틱에　기록할까요？\n３５２ＫＢ　이상　사용합니다",
    "①②③④⑤⑥⑦を調べています\n\u3000": "메모리스틱을　확인　중입니다\n\u3000",
    "どのファイルにセ－ブしますか？": "어느　파일에　저장할까요？",
    "どのファイルにセ－ブしますか？\n３５２ＫＢ以上使用します": "어느　파일에　저장할까요？\n３５２ＫＢ　이상　사용합니다",
    "このファイルでよろしいですか？": "이　파일로　괜찮습니까？",
    "上書きしてもよろしいですか？": "덮어써도　괜찮습니까？",
    "デ－タを書き込んでいます\n\u3000": "데이터를　쓰는　중입니다\n\u3000",
    "セ－ブが終了しました": "저장이　끝났습니다",
    "このままゲ－ムを続けますか？": "이대로　게임을　계속할까요？",
    "どのファイルをロ－ドしますか？": "어느　파일을　불러올까요？",
    "デ－タを読んでいます\n\u3000": "데이터　읽는중\n\u3000",
    "ロ－ドが終了しました": "불러오기　완료",
    "新しいファイル": "새　파일",
    "ボクの思い出\u3000８月０日": "나의　추억\u3000８월０일",
    "ボクの思い出\u3000８月００日": "나의　추억\u3000８월００일",
    "ＰＬＡＹＴＩＭＥ\u3000００：００：００": "ＰＬＡＹＴＩＭＥ\u3000００：００：００",
    "\u3000\u3000｝": "\u3000\u3000｝",
    "\u3000？）破損ファイル": "\u3000？）손상　파일",
    "ファイルのロ－ドを続けますか？": "파일　불러오기를　계속할까요？",
    "タイトル画面で【夏休みの思い出】を選び\n今回あなたが気に入\u3000た虫相撲の虫を\n「お気に入り」ファイルに登録しておくと\n次回にその虫を連れて行くことができます": "타이틀에서【여름방학의　추억】을　고르고\n마음에　든　곤충　씨름　곤충을\n「즐겨찾기」파일에　등록해　두면\n다음에　그　곤충을　데려갈　수　있습니다",
    "内容を見たい「お気に入り」ファイルを\n選んでください": "내용을　볼　「즐겨찾기」파일을\n선택해　주세요",
    "「お気に入り」ファイルを読み込んでいます\n\u3000": "「즐겨찾기」파일을　읽는　중입니다\n\u3000",
    "「お気に入り」ファイルを読みました": "「즐겨찾기」파일을　읽었습니다",
    "消したい「お気に入り」ファイルを\n選んでください": "지울　「즐겨찾기」파일을\n선택해　주세요",
    "お気に入り／\u3000\u3000\u3000\u3000\u3000\u3000\u3000\nを消してもいいですか？": "즐겨찾기／\u3000\u3000\u3000\u3000\u3000\u3000\u3000\n을　지워도　될까요？",
    "お気に入り／\u3000\u3000\u3000\u3000\u3000\u3000\u3000\nを消しています\n\u3000": "즐겨찾기／\u3000\u3000\u3000\u3000\u3000\u3000\u3000\n삭제중입니다\n\u3000",
    "お気に入り／\u3000\u3000\u3000\u3000\u3000\u3000\u3000\nを消しました": "즐겨찾기／\u3000\u3000\u3000\u3000\u3000\u3000\u3000\n을　지웠습니다",
    "今回の夏休みに「お気に入り」を\n連れていきますか？": "이번　여름방학에　「즐겨찾기」를\n데려갈까요？",
    "連れて行く「お気に入り」ファイルを\n選んでください": "데려갈　「즐겨찾기」파일을\n선택해　주세요",
    "これを連れて行きますか？": "이것을　데려갈까요？",
    "送信する「お気に入り」ファイルを\n選んでください\n送信しても「お気に入り」ファイルは\nなくなりません": "보낼　「즐겨찾기」파일을\n선택해　주세요\n보내도　「즐겨찾기」파일은\n사라지지　않습니다",
    "受信した「お気に入り」ファイルを\n①②③④⑤⑥⑦に記録しますか？\n３５２ＫＢ以上使用します": "받은　「즐겨찾기」파일을\n메모리스틱에　기록할까요？\n３５２ＫＢ　이상　사용합니다",
    "「お気に入り」ファイルを記録しています\n\u3000": "「즐겨찾기」파일을　기록　중입니다\n\u3000",
    "「お気に入り」ファイルを記録しました": "「즐겨찾기」파일을　기록했습니다",
    "お気に入り／\u3000\u3000\u3000\u3000\u3000\u3000\u3000\u3000を作成中です\n\u3000": "즐겨찾기／\u3000\u3000\u3000\u3000\u3000\u3000\u3000\u3000작성　중입니다\n\u3000",
    "新しい「お気に入り」ファイルができました": "새　「즐겨찾기」파일이　생겼습니다",
    "０１）お気に入り／\u3000\u3000\u3000\u3000\u3000\u3000\u3000": "０１）즐겨찾기／\u3000\u3000\u3000\u3000\u3000\u3000\u3000",
    "？？？？？？": "？？？？？？",
    "破損ファイル": "손상　파일",
    "このままゲ－ムをスタ－トさせて\nいいですか？": "이대로　게임을　시작해도\n괜찮습니까？",
    "「お気に入り」ファイルの送信先を\n募集しています\nしばらくお待ちください\n抜けたいときは×ボタンを押してください": "「즐겨찾기」파일　받을　상대를\n찾고　있습니다\n잠시　기다려　주세요\n나가려면　×버튼을　눌러　주세요",
    "「お気に入り」ファイルを送信中です": "「즐겨찾기」전송중",
    "「お気に入り」ファイルを送信しました": "「즐겨찾기」파일을　보냈습니다",
    "「お気に入り」ファイルの送信者を\n募集中です\nしばらくお待ちください": "「즐겨찾기」파일　보낸　사람을\n찾고　있습니다\n잠시　기다려　주세요",
    "送信者の返答を待\u3000ています\nしばらくお待ちください\n抜けたいときは×ボタンを押してください": "보낸　사람의　응답을　기다립니다\n잠시　기다려　주세요\n나가려면　×버튼을　눌러　주세요",
    "「お気に入り」ファイルを受信中です": "「즐겨찾기」파일을　받는　중입니다",
    "「お気に入り」ファイルを受信しました": "「즐겨찾기」파일을　받았습니다",
    "「お気に入り」のセ－ブを続けますか？": "「즐겨찾기」저장을　계속할까요？",
    "「お気に入り」のロ－ドを続けますか？": "「즐겨찾기」불러오기를　계속할까요？",
    "「お気に入り」の消去を続けますか？": "「즐겨찾기」삭제를　계속할까요？",
    "\u3000０００匹の\n\u3000アリが死亡した\u3000": "\u3000０００마리\n\u3000개미사망\u3000",
}


def load_ui_font() -> str:
    favorite = ROOT / "map" / "models" / "system" / "saveload_favorite.bin.gzx"
    payload = gzip.decompress(favorite.read_bytes()[4:])
    entries = boku_tools.parse_pack_entries(payload, with_names=True)
    font_entry = next(entry for entry in entries if entry["name"] == "FONT_UTF16.TXT")
    raw = payload[font_entry["offset"] : font_entry["offset"] + font_entry["size"]]
    return raw.decode("utf-16le")


def decode_runs(data: bytes, ui_font: str) -> list[dict]:
    runs = []
    start = None
    raw = bytearray()
    out = []
    for pos in range(0, len(data) - 1, 2):
        value = struct.unpack_from("<H", data, pos)[0]
        if value == 0x8000:
            if start is not None:
                raw.extend(data[pos : pos + 2])
                runs.append({"offset": start, "length": len(raw), "text": "".join(out), "raw": bytes(raw)})
            start = None
            raw = bytearray()
            out = []
        elif value == 0x8001:
            if start is None:
                start = pos
            raw.extend(data[pos : pos + 2])
            out.append("\n")
        elif value < len(ui_font):
            if start is None:
                start = pos
            raw.extend(data[pos : pos + 2])
            out.append(ui_font[value])
        elif value != 0:
            if start is None:
                start = pos
            raw.extend(data[pos : pos + 2])
            out.append(f"{{{value:04X}}}")
    return runs


def normalize_text(text: str) -> str:
    return text.replace(" ", "\u3000")


def make_hangul_assets() -> tuple[Path, Path, dict[str, int]]:
    previous = json.loads(PREVIOUS_TRANSLATIONS.read_text(encoding="utf-8"))
    texts = [item["ko"] for item in previous if item.get("ko")]
    texts.extend(TRANSLATIONS.values())

    table = boku_tools.load_table(BASE_TABLE)
    needed = []
    seen = set(table.values())
    for text in texts:
        for ch in boku_tools.iter_text_chars(normalize_text(text)):
            if "\uac00" <= ch <= "\ud7a3" and ch not in seen:
                needed.append(ch)
                seen.add(ch)
    available = [code for code in range(START_CODE, END_CODE + 1) if code not in table]
    if len(needed) > len(available):
        raise ValueError(f"not enough Hangul glyph slots: need {len(needed)}, available {len(available)}")

    glyphs = [{"code": code, "char": ch} for code, ch in zip(available, needed)]
    glyph_map = {
        "font": "C:/Windows/Fonts/malgun.ttf",
        "font_size": 13,
        "glyph_max_width": 9,
        "glyph_shift_x": -3,
        "glyph_shift_y": 0,
        "glyphs": glyphs,
    }
    glyph_map_path = OUT_DIR / "glyphs_system.json"
    glyph_map_path.write_text(json.dumps(glyph_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = BASE_TABLE.read_text(encoding="utf-8").splitlines()
    for glyph in glyphs:
        lines.append(f"{glyph['code']:04d} = {glyph['char']}")
    table_path = OUT_DIR / "table_system.txt"
    table_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return table_path, glyph_map_path, {item["char"]: item["code"] for item in glyphs}


def encode_ui_text(text: str, ui_font: str, hangul_codes: dict[str, int]) -> bytes:
    inverse = {ch: code for code, ch in enumerate(ui_font)}
    out = bytearray()
    for ch in normalize_text(text):
        if ch == "\n":
            out.extend(struct.pack("<H", 0x8001))
        elif ch in hangul_codes:
            out.extend(struct.pack("<H", hangul_codes[ch]))
        elif ch in inverse:
            out.extend(struct.pack("<H", inverse[ch]))
        else:
            raise ValueError(f"cannot encode UI character {ch!r} in {text!r}")
    out.extend(struct.pack("<H", 0x8000))
    return bytes(out)


def patch_bms_member(payload: bytearray, member: dict, ui_font: str, hangul_codes: dict[str, int], report: list[dict]) -> None:
    data = bytearray(payload[member["offset"] : member["offset"] + member["size"]])
    runs = decode_runs(data, ui_font)
    for run in runs:
        ko = TRANSLATIONS.get(run["text"])
        if ko is None:
            continue
        encoded = encode_ui_text(ko, ui_font, hangul_codes)
        if len(encoded) > run["length"]:
            raise ValueError(
                f"translation too long in {member['name']} at 0x{run['offset']:X}: "
                f"{len(encoded)} > {run['length']} {run['text']!r} -> {ko!r}"
            )
        start = run["offset"]
        data[start : start + run["length"]] = encoded + b"\x00" * (run["length"] - len(encoded))
        report.append(
            {
                "member": member["name"],
                "offset_hex": f"0x{run['offset']:X}",
                "budget_bytes": run["length"],
                "encoded_bytes": len(encoded),
                "ja": run["text"],
                "ko": normalize_text(ko),
            }
        )
    payload[member["offset"] : member["offset"] + member["size"]] = data


def patch_gzx_pack(src: Path, dst: Path, ui_font: str, hangul_codes: dict[str, int], report: list[dict]) -> None:
    original = src.read_bytes()
    payload = bytearray(gzip.decompress(original[4:]))
    entries = boku_tools.parse_pack_entries(payload, with_names=True)
    for member in entries:
        if member["name"].lower().endswith(".bms"):
            patch_bms_member(payload, member, ui_font, hangul_codes, report)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(boku_tools.make_gzip(bytes(payload), original))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table_path, glyph_map_path, hangul_codes = make_hangul_assets()
    ui_font = load_ui_font()
    report = []

    replacements = Path("work/replacements_system_text_full")
    if replacements.exists():
        shutil.rmtree(replacements)
    replacements.mkdir(parents=True)

    # Rebuild the already verified dialogue batch with the new table/code assignments.
    boku_tools.rebuild_scripts_raw(ROOT, table_path, PREVIOUS_TRANSLATIONS, replacements)

    # Patch startup font with all Hangul needed by dialogue and system UI.
    boku_tools.patch_font_glyphs(
        ROOT / "01startup" / "startup.bin.gzx",
        table_path,
        glyph_map_path,
        replacements / "01startup" / "startup.bin.gzx",
        OUT_DIR / "table_system_patched.txt",
    )

    for rel in [
        Path("map/models/system/saveload_normal.bin.gzx"),
        Path("map/models/system/saveload_favorite.bin.gzx"),
        Path("01startup/startup.bin.gzx"),
    ]:
        # startup is already patched for font above; patch only its BMS member in-place after font patch.
        src = replacements / rel if (replacements / rel).exists() else ROOT / rel
        patch_gzx_pack(src, replacements / rel, ui_font, hangul_codes, report)

    report_path = OUT_DIR / "system_text_patch_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"glyphs={len(hangul_codes)} patched_runs={len(report)}")
    print(table_path)
    print(glyph_map_path)
    print(report_path)
    print(replacements)


if __name__ == "__main__":
    main()
