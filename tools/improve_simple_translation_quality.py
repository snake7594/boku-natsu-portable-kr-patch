#!/usr/bin/env python3
import json
import re
from pathlib import Path


SIMPLE = Path("outputs/translation_edit_simple_resolved_reflow15_noreloc.json")
REPORT = Path("outputs/translation_quality_improve_simple_report.json")

JA_SOURCE = "\uc77c\ubcf8\uc5b4_\uc6d0\ubb38"
JA_DIALOG = "\uc77c\ubcf8\uc5b4_\ub300\uc0ac"
KO_TRANSLATION = "\ud55c\uad6d\uc5b4_\ubc88\uc5ed"
KO_INSERT = "\ud55c\uad6d\uc5b4_\uc0bd\uc785"


def has_japanese(text: str) -> bool:
    return any(
        0x3040 <= ord(ch) <= 0x30FF
        or 0x31F0 <= ord(ch) <= 0x31FF
        or (0x4E00 <= ord(ch) <= 0x9FFF and ch not in "一二三四五六七八九十")
        for ch in text
    )


def normalize_spacing(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,\.?!、。？！」])", r"\1", text)
    text = re.sub(r"([「])\s+", r"\1", text)
    text = re.sub(r"\s+\n", "\n", text)
    return text.strip()


def apply_common_fixes(text: str, ja: str) -> tuple[str, list[str]]:
    original = text
    fixes = []
    replacements = [
        ("더이상", "더 이상"),
        ("할일", "할 일"),
        ("그림일기", "그림 일기"),
        ("일찌감치 자 버리는", "일찌감치 잠드는"),
        ("뭐이렇게", "뭐 이렇게"),
        ("네가만약", "네가 만약"),
        ("밤늦게까지", "밤 늦게까지"),
        ("복습도 해라", "복습을 잊지 마라"),
        ("찌르는거야", "찌르는 거야"),
        ("지는거야", "지는 거야"),
        ("있는거야", "있는 거야"),
        ("하는거야", "하는 거야"),
        ("것같", "것 같"),
        ("필승법이란다", "필승법이란다"),
        ("대체이게", "대체 이게"),
        ("아무튼이겨서", "아무튼 이겨서"),
        ("곤충씨름", "곤충 씨름"),
        ("씨름판에서", "씨름판에서"),
        ("스태미나만땅", "스태미나가 가득"),
        ("하늘의가락", "하늘의 가락"),
        ("직접만든", "직접 만든"),
        ("안에가끔", "안에 가끔"),
        ("사람이이삼", "사람이 이삼"),
        ("틀림없이이", "틀림없이 이"),
        ("수박 도둑를", "수박 도둑을"),
        ("수박 도둑를", "수박 도둑을"),
        ("수박 도둑를", "수박 도둑을"),
        ("수박 도둑을 가르쳐", "수박 도둑 이야기를 알려"),
    ]
    for src, dst in replacements:
        if src in text:
            text = text.replace(src, dst)
            fixes.append(f"replace:{src}->{dst}")

    if "秘密基地" in ja and "비밀 묘지" in text:
        text = text.replace("비밀 묘지", "비밀 기지")
        fixes.append("context:秘密基地")
    if "虫相撲" in ja:
        text = text.replace("벌레 씨름", "곤충 씨름")
        fixes.append("context:虫相撲")
    if "お勧め" in ja:
        text = text.replace("권하고 싶구나", "권하고 싶어")
        fixes.append("context:お勧め")
    if "潔癖" in ja:
        text = text.replace("결벽증이랄까", "깔끔한 걸 따진다고 할까")
        fixes.append("context:潔癖")
    if "誰のこと" in ja and "누구 얘기야" in text:
        text = text.replace("누구 얘기야?", "누구 말이야?")
        fixes.append("context:誰のこと")
    if "スイカ泥棒" in ja:
        text = text.replace("수박 서리", "수박 도둑")
        fixes.append("context:スイカ泥棒")
    if "お地蔵" in ja:
        text = text.replace("지장보살님", "지장보살")
        fixes.append("context:お地蔵")
    if "カミダノミ" in ja:
        text = text.replace("신령님께 빌기", "신에게 빌기")
        fixes.append("context:カミダノミ")
    if "凧" in ja:
        text = text.replace("연날리기", "연 날리기")
        text = text.replace("연을높이", "연을 높이")
        fixes.append("context:凧")
    if "絵日記" in ja:
        text = text.replace("그림일기", "그림 일기")
        fixes.append("context:絵日記")
    if "捕虫網" in ja:
        text = text.replace("포충망", "잠자리채")
        fixes.append("context:捕虫網")
    if "昆虫" in ja:
        text = text.replace("벌레", "곤충") if "희귀한 벌레" in text else text
        fixes.append("context:昆虫")
    ja_compact = ja.replace("\n", "")
    if "\u3042\u2026\u3046\u305d" in ja_compact and "\u8a69\u3063\u3066\u66f8\u3044\u3066\u3057\u3089\u3079" in ja_compact:
        text = "시라베「아… 아니… 내 이름은 시라베야」"
        fixes.append("exact:shirabe_name")
    if "\u308f\u305f\u3057\u306f\u3057\u3089\u3079" in ja_compact and "\u8a69\u3063\u3066\u66f8\u3044\u3066\u3057\u3089\u3079" in ja_compact:
        text = "시라베「나는 시라베야. 이름은 시라베라고 해」"
        fixes.append("exact:shirabe_intro")

    final_replacements = [
        ("수박 도둑를", "수박 도둑을"),
        ("수박 도둑을 가르쳐 줘야 할까?", "수박 도둑 이야기를 알려 줘야 할까?"),
    ]
    for src, dst in final_replacements:
        if src in text:
            text = text.replace(src, dst)
            fixes.append(f"final_replace:{src}->{dst}")

    text = normalize_spacing(text)
    if text != original and not fixes:
        fixes.append("spacing")
    return text, fixes


def main() -> None:
    rows = json.loads(SIMPLE.read_text(encoding="utf-8"))
    changed = []
    japanese_left = []
    for index, row in enumerate(rows):
        old = row[KO_TRANSLATION]
        new, fixes = apply_common_fixes(old, row[JA_DIALOG])
        if new != old:
            row[KO_TRANSLATION] = new
            changed.append({"index": index, "fixes": fixes, "old": old, "new": new})
        if has_japanese(new):
            japanese_left.append({"index": index, "ja": row[JA_DIALOG], "ko": new})

    SIMPLE.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        json.dumps(
            {
                "rows": len(rows),
                "changed": len(changed),
                "japanese_left": len(japanese_left),
                "changed_examples": changed[:100],
                "japanese_left_examples": japanese_left[:100],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "changed": len(changed), "japanese_left": len(japanese_left)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
