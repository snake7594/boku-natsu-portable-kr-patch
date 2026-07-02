#!/usr/bin/env python3
import json
import re
from pathlib import Path

import boku_tools
import make_quality_v1_translations as q1


ROOT = Path("work")
REFINED = ROOT / "translation_survey" / "dialog_targets_refined.json"
ROUGH = ROOT / "translations_rough_all.json"
OUT_DIR = ROOT / "translation_quality_v2"
EDITABLE = OUT_DIR / "translation_quality_v2_editable.json"
PATCH_TRANSLATIONS = ROOT / "translations_quality_v2.json"
REPORT = OUT_DIR / "translation_quality_v2_report.md"


SPEAKER_MAP = {
    "ボク": "나",
    "おじ": "아저씨",
    "おば": "아줌마",
    "教頭せんせ": "교감",
    "ヨシコ": "요시코",
    "ヤスコ": "야스코",
    "モエ": "모에",
    "萌": "모에",
    "詩": "시",
    "太陽": "타이요",
    "ガッツ": "갓츠",
    "ファット": "팻",
    "アニキくん": "형아",
    "小説家": "소설가",
    "郵便屋": "우체부",
    "坊さん": "스님",
    "和尚": "스님",
    "父": "아빠",
    "母": "엄마",
}


EXACT_SOURCE = {
    "ボク「……　」": "나「……」",
    "ボク「あららら……」": "나「어라라라……」",
    "ボク「ぎゃあ！」": "나「으악！」",
    "ボク「やったぁ！」": "나「됐다！」",
    "ボク「ヒック！」": "나「딸꾹！」",
    "ボク「うん」": "나「응」",
    "ボク「うん！」": "나「응！」",
    "ボク「なんで？」": "나「왜？」",
    "ボク「え？」": "나「어？」",
    "ボク「あれ…？」": "나「어라…？」",
    "ボク「こんにちは」": "나「안녕하세요」",
    "ボク「そうなんだ」": "나「그렇구나」",
    "ボク「へぇ、そうなんだ」": "나「헤에、 그렇구나」",
    "ボク「ふ〜ん、そうなんだ」": "나「흐〜응、 그렇구나」",
    "ボク「よいしょっ！」": "나「영차！」",
    "ボク「はぁ？」": "나「뭐？」",
    "ボク「なに？」": "나「뭐？」",
    "ボク「なにを？」": "나「뭘？」",
    "ボク「どうしたの？」": "나「왜 그래？」",
    "ボク「うわ！」": "나「우와！」",
    "ボク「冷たぃ…」": "나「차가워…」",
    "ボク「あれ、なんだろう？」": "나「어라、 뭐지？」",
    "ボク「うわ！　なんだこりゃ？」": "나「우와！ 뭐야 이거？」",
    "ボク「ボクはボク」": "나「나는 나」",
    "ボク「え？　どこどこ」": "나「어？ 어디？」",
    "ボク「おじちゃんありがとう」": "나「아저씨 고마워」",
    "ボク「うん、おじちゃん\n　任しといて！{PAUSE}Ｈ　ボク、がんばるよ」": "나「응、 아저씨\n　나한테 맡겨！{PAUSE}나、 열심히 할게」",
    "ボク「なんかいるかなぁ」": "나「뭐가 있으려나」",
    "ボク「なんにもいないや」": "나「아무것도 없네」",
    "ボク「がっくし…」": "나「실망이다…」",
    "ボク「できるの？」": "나「할 수 있어？」",
    "ボク「おねえちゃん\n　どうしたの？」": "나「누나\n　왜 그래？」",
    "おじ「ごちそうさまでした」": "아저씨「잘 먹었습니다」",
    "おじ「じゃあ、いただきまーす」": "아저씨「자、 잘 먹겠습니다」",
    "おじ「じゃあ、いただきます！」": "아저씨「자、 잘 먹겠습니다！」",
    "おじ「名前は？」": "아저씨「이름은？」",
    "おじ「そうか…」": "아저씨「그렇구나…」",
    "おじ「ボクくん、凧、完成したよ」": "아저씨「얘야、 연 다 됐다」",
    "おじ「凧はまだ出来ていませ〜ん{PAUSE}Ｋ　もう、ちょっとだけ侍ってて\n　下さいね」": "아저씨「연은 아직이야〜{PAUSE}조금만 더\n　기다려 줘」",
    "おじ「凧を作って欲しい\n　ようだけど、ごめんね{PAUSE}ｒ　今から作ってもボクくんが\n　ここにいる間には完成\n　しないなぁ」": "아저씨「연을 만들고\n　싶은가 보구나、 미안{PAUSE}지금 시작해도 네가\n　여기 있는 동안엔\n　완성 못 하겠어」",
    "「ごちそうさまでした」": "「잘 먹었습니다」",
    "「いただきまーす」": "「잘 먹겠습니다」",
    "「いただきます！」": "「잘 먹겠습니다！」",
    "「砂糖を見つけた」": "「설탕을 찾았다」",
    "「砂糖水を手に入れた」": "「설탕물을 얻었다」",
    "「鍵がかかっている」": "「잠겨 있다」",
    "「ハハハ」": "「하하하」",
    "『朝顔は枯れていた…』": "『나팔꽃은 말라 있었다…』",
    "叔父にスイカ泥棒を教えるべき？": "수박 도둑을 알릴까？",
    "萌の部屋に入れないのはなぜ？": "모에 방엔 왜 못 들어가？",
    "近所の子供たちがいる場所は？": "동네 아이들은 어디에？",
    "蜂の巣が{04EE}くて先へ進めない…": "벌집이 무서워 못 가…",
    "橋がなくて先に進めない場所が…": "다리가 없어 못 가는 곳이…",
    "虫相{0404}に勝つためには？": "곤충 씨름에서 이기려면？",
    "夏休み中の過ごし方は？": "여름방학은 어떻게 보내？",
    "捕虫{05C7}はどうやって使うの？": "잠자리채는 어떻게 써？",
    "{0458}しい昆虫が見つかる場所は？": "희귀 곤충은 어디에 있어？",
    "上手な絵日記の書き方は？": "그림일기를 잘 쓰려면？",
    "一番眺めの良い場所はどこ？": "전망 좋은 곳은 어디？",
    "{046B}で{0436}ぐにはどうすればいいの？": "바다에서 수영하려면？",
    "運{05F1}を良くするには？": "운을 좋게 하려면？",
    "夜、おしっこに行くのが{04EE}い…": "밤에 화장실 가기 무서워…",
    "何を飲みますか？\nノラ印牛乳\n麦　茶\n": "무엇을 마실까？\n노라 우유\n보리차\n",
    "砂糖水を塗る\n木をけっとばす\n": "설탕물을 바른다\n나무를 걷어찬다\n",
    "はい\nいいえ\n": "예\n아니오\n",
    "凧を上げますか？\nはい\nいいえ\n": "연을 날릴까？\n예\n아니오\n",
    "うん、いいよ！\nそんなのやだよ！\n": "응、 좋아！\n그건 싫어！\n",
}


SOURCE_CONTAINS = [
    ("教頭せんせ「子供がたちが\n　集まる場所といえば\n　秘密墓地のことかい？」", "교감「아이들이\n　모이는 곳이라면\n　비밀 묘지 말이냐？」"),
    ("教頭せんせ「それは\n　先生も同じだ」", "교감「그건\n　선생님도 마찬가지야」"),
    ("教頭せんせ「さて、キミからは\n　なにか質{0438}があるかい？」", "교감「자、 너는\n　뭐 물어볼 게 있니？」"),
    ("教頭せんせ「いいかい{PAUSE}＞　虫{05C7}は必ず、家の外で\n　{0492}{0509}するんだからね」", "교감「알겠니{PAUSE}잠자리채는 반드시\n　집 밖에서 쓰는 거야」"),
    ("教頭せんせ「夜になって\n　もうやることがなかったら{PAUSE}Ｗ　絵日記を書いて\n　早めに寝てしまうことを\n　お{0600}めするよ」", "교감「밤이 되어\n　할 일이 없으면{PAUSE}그림일기를 쓰고\n　일찍 자는 걸\n　추천하마」"),
    ("教頭せんせ「虫相{0404}か\n　{05FF}かしいなー{PAUSE}ｘ　先生も大好きだったよ」", "교감「곤충 씨름인가\n　그립구나ー{PAUSE}선생님도 아주 좋아했지」"),
]


POST_REPLACEMENTS = [
    ("교두 선생님", "교감"),
    ("교두", "교감"),
    ("센세", "선생님"),
    ("보쿠", "나"),
    ("충상", "곤충 씨름"),
    ("포충", "잠자리채"),
    ("그림 일기", "그림일기"),
    ("여름 방학", "여름방학"),
    ("수박 도둑", "수박도둑"),
    ("오줌", "화장실"),
    ("품질", "질문"),
    ("질문이 있습", "물어볼 게 있"),
    ("좋게하", "좋게 하"),
    ("넣지 않는", "들어가지 못하는"),
    ("나나나츠야스미", "나의 여름방학"),
    ("재검토", "다시 봤"),
    ("일찍 자러 가는\n　것을", "일찍 자는 걸"),
    ("뒷면", "뒤쪽"),
    ("사람들이 있습니다", "많이 있구나"),
    ("어떤 너도", "너도"),
]


EXTRA_EXACT_SOURCE = {
    "\u866b\u76f8{0404}\u306b\u52dd\u3064\u305f\u3081\u306b\u306f\uff1f": "\uace4\ucda9\uc528\ub984 \uc2b9\ub9ac\ubc95\uff1f",
    "{0458}\u3057\u3044\u6606\u866b\u304c\u898b\u3064\u304b\u308b\u5834\u6240\u306f\uff1f": "\ud76c\uadc0\uace4\ucda9\uc740 \uc5b4\ub514\uff1f",
    "\u904b{05F1}\u3092\u826f\u304f\u3059\u308b\u306b\u306f\uff1f": "\uc6b4 \uc88b\uc544\uc9c0\ub294 \ubc95\uff1f",
    "\u591c\u3001\u304a\u3057\u3063\u3053\u306b\u884c\u304f\u306e\u304c{04EE}\u3044\u2026": "\ubc24 \ud654\uc7a5\uc2e4\uc774 \ubb34\uc11c\uc6cc\u2026",
    "\u304a\u3058\u300c\u51e7\u3092\u4f5c\u3063\u3066\u6b32\u3057\u3044\n\u3000\u3088\u3046\u3060\u3051\u3069\u3001\u3054\u3081\u3093\u306d{PAUSE}\uff52\u3000\u4eca\u304b\u3089\u4f5c\u3063\u3066\u3082\u30dc\u30af\u304f\u3093\u304c\n\u3000\u3053\u3053\u306b\u3044\u308b\u9593\u306b\u306f\u5b8c\u6210\n\u3000\u3057\u306a\u3044\u306a\u3041\u300d": "\uc544\uc800\uc528\u300c\uc5f0 \ub9d0\uc774\uc9c0\n\u3000\ubbf8\uc548\ud558\uc9c0\ub9cc{PAUSE}\uc9c0\uae08 \ub9cc\ub4e4\uc5b4\ub3c4 \ub124\uac00\n\u3000\uc5ec\uae30 \uc788\ub294 \ub3d9\uc548\uc5d4\n\u3000\uc644\uc131 \ubabb \ud574\u300d",
    "\u304a\u3058\u300c\u304a\u3081\u3067\u3068\u3046\u30dc\u30af\u304f\u3093\uff01{PAUSE}\uff12\u3000\u9ad8\u304f\u9ad8\u304f\u4e0a\u304c\u3063\u305f\u51e7\u304c\n\u3000\u3053\u306e\u5ead\u304b\u3089\u3082\u898b\u3048\u3066\u3044\u305f\u3088{PAUSE}\u3053\u3000\u3055\u3042\u3001\u3054\u8912\u7f8e\u306b\u6b21\u306e\u51e7\u3092\n\u3000\u4f5c\u3063\u3066\u3042\u3052\u308b\u304b\u3089\u9078\u3093\u3067\n\u3000\u304a\u3044\u3067\u300d": "\uc544\uc800\uc528\u300c\ucd95\ud558\ud55c\ub2e4\uff01{PAUSE}\ub192\uc774 \uc624\ub978 \uc5f0\uc774\n\u3000\ub9c8\ub2f9\uc5d0\uc11c\ub3c4 \ubcf4\uc600\uc5b4{PAUSE}\uc790\u3001 \uc0c1\uc73c\ub85c \ub2e4\uc74c \uc5f0\uc744\n\u3000\ub9cc\ub4e4\uc5b4 \uc904 \ud14c\ub2c8\n\u3000\uace8\ub77c \ubcf4\ub834\u300d",
}


EXTRA_CONTAINS_SOURCE = [
    (
        "\u6559\u982d\u305b\u3093\u305b\u300c\u30ad\u30df\u304c\u3082\u3057\n\u3000\u3046\u3061\u306e\u4e2d\u5b66\u306e\u751f\u5f92\u3060\u3063\u305f\u3089",
        "\uad50\uac10\u300c\ub124\uac00 \ub9cc\uc57d\n\u3000\uc6b0\ub9ac \uc911\ud559\uc0dd\uc774\ub77c\uba74{PAUSE}\ubc24\ub2a6\uac8c\uae4c\uc9c0 \uacf5\ubd80\ud574\uff01\n\u3000\uff11\ud559\uae30 \ubcf5\uc2b5\ub3c4 \uc78a\uc9c0 \ub9c8\uff01{PAUSE}\ub77c\uace0 \ub9d0\ud558\uace0\n\u3000\uc2f6\uc9c0\ub9cc{PAUSE}\uc544\uc9c1 \ucd08\ub4f1\ud559\uc0dd\uc774\uc9c0\u2026\u300d",
    ),
    (
        "\u6559\u982d\u305b\u3093\u305b\u300c\u866b{05C7}\u306f\u5bb6\u306e\u4e2d\u3067\u306f",
        "\uad50\uac10\u300c\uc7a0\uc790\ub9ac\ucc44\ub294 \uc9d1\uc548\uc5d0\uc120\n\u3000\ubabb \uc4f0\uc9c0\ub9cc{PAUSE}\uc9d1 \ubc16\uc5d0\uc11c\n\u3000\uc7a5\ube44\ud558\uba74\n\u3000\uc4f8 \uc218 \uc788\ub2e4{PAUSE}\ud55c\ubc88 \ud574 \ubcf4\ub834\u300d",
    ),
    (
        "\u6559\u982d\u305b\u3093\u305b\u300c\u3053\u306e\u8fba\u308a\u3067\n\u3000\u773a\u3081\u306e\u826f\u3044\u3068\u3053\u308d\u3063\u3066\u3044\u3046\u3068",
        "\uad50\uac10\u300c\uc774 \uadfc\ucc98\uc5d0\uc11c\n\u3000\uc804\ub9dd \uc88b\uc740 \uacf3\uc774\ub77c\uba74{PAUSE}\uaf2d\ub300\uae30\uc0b0 \uc815\uc0c1\uc774\uc9c0{PAUSE}\ud558\uc9c0\ub9cc \uadf8 \ub4f1\uc0b0\ub85c\ub294\n\u3000\uc77c\ucc0d \ub2eb\ud788\ub2c8\uae4c{PAUSE}\uadf8\ub0e5 \uac78\uc5b4\uc11c\n\u3000\uc2dc\uac04 \ub9de\ucdb0 \uac00\uae30\ub294{PAUSE}\uc870\uae08 \uc5b4\ub824\uc6b8 \uac8c\ub2e4\u300d",
    ),
    (
        "\u6559\u982d\u305b\u3093\u305b\u300c\u8fd1\u6240\u306e\u5b50\u4f9b\u305f\u3061\u3068",
        "\uad50\uac10\u300c\ub3d9\ub124 \uc560\ub4e4\uacfc\n\u3000\uce5c\ud574\uc9c0\uba74{PAUSE}\ube44\ubc00 \uc0db\uae38\uc744\n\u3000\ub4e4\uc744 \uc218 \uc788\ub2e4\u300d",
    ),
    (
        "\u6559\u982d\u305b\u3093\u305b\u300c\u3055\u3066\u3001\u30ad\u30df\u304b\u3089\u306f\n\u3000\u306a\u306b\u304b\u8cea{0438}\u304c\u3042\u308b\u304b\u3044\uff1f",
        "\uad50\uac10\u300c\uc790\u3001 \ub108\ub294\n\u3000\uc9c8\ubb38 \uc788\ub2c8\uff1f\u300d",
    ),
]


PRIORITY_CONTAINS_SOURCE = [
    (
        "\u304a\u3058\u300c\u51e7\u3092\u4f5c\u3063\u3066\u6b32\u3057\u3044",
        "\uc544\uc800\uc528\u300c\uc5f0\uc740\n\u3000\ubbf8\uc548\ud558\uc9c0\ub9cc{PAUSE}\uc9c0\uae08 \ud574\ub3c4\n\u3000\ub124\uac00 \uc788\ub294 \ub3d9\uc548\uc5d4\n\u3000\ubabb \ub05d\ub0b4\u300d",
    ),
    (
        "\u304a\u3058\u300c\u51e7\u306f\u307e\u3060\u51fa\u6765\u3066\u3044\u307e\u305b",
        "\uc544\uc800\uc528\u300c\uc5f0\uc740 \uc544\uc9c1\uc774\uc57c\u301c{PAUSE}\uc870\uae08\ub9cc\n\u3000\uae30\ub2e4\ub824 \uc918\u300d",
    ),
    (
        "\u304a\u3058\u300c\u304a\u3081\u3067\u3068\u3046\u30dc\u30af\u304f\u3093\uff01",
        "\uc544\uc800\uc528\u300c\ucd95\ud558\ud55c\ub2e4\uff01{PAUSE}\ub192\uc774 \uc624\ub978 \uc5f0\uc774\n\u3000\ub9c8\ub2f9\uc5d0\uc11c\ub3c4 \ubcf4\uc600\uc5b4{PAUSE}\uc790\u3001 \ub2e4\uc74c \uc5f0\uc744\n\u3000\ub9cc\ub4e4\uc5b4 \uc904 \ud14c\ub2c8\n\u3000\uace8\ub77c \ubcf4\ub834\u300d",
    ),
    (
        "\u300c\u30d4\u30ab\u30d4\u30ab\u306b\u307f\u304c\u304b\u308c\u305f",
        "\u300c\ubc18\uc9dd\ubc18\uc9dd \ub2e6\uc778\n\u3000\ud558\uc580 \uac00\uc2a4\ub808\uc778\uc9c0\u300d",
    ),
    (
        "\u300c\u3055\u308f\u308b\u3068\u3072\u3093\u3084\u308a\u51b7\u305f\u3044",
        "\u300c\ub9cc\uc9c0\uba74 \uc11c\ub298\ud55c\n\u3000\ud55c\uc5ec\ub984 \ub09c\ub85c\u300d",
    ),
    (
        "\u300c\u30ab\u30ec\u30f3\u30c0\u30fc\u3084\u5b66\u6821\u306e\u304a\u77e5\u3089\u305b",
        "\u300c\ub2ec\ub825\uacfc \ud559\uad50 \uc54c\ub9bc\n\u3000\uae09\uc2dd\ud45c \ub4f1\uc774 \ubd99\uc5b4 \uc788\ub2e4\u300d",
    ),
    (
        "\u304a\u3058\u300c\u3058\u3083\u3042\u3001\u3044\u305f\u3060\u304d\u307e\u3059\uff01",
        "\uc544\uc800\uc528\u300c\uc790\u3001 \uba39\uc790\uff01\u300d",
    ),
    (
        "\u300c\u3044\u305f\u3060\u304d\u307e\u3059\uff01\u300d",
        "\u300c\uc798 \uba39\uc790\uff01\u300d",
    ),
    (
        "\u7802\u7cd6\u6c34\u3092\u5857\u308b\n\u6728\u3092\u3051\u3063\u3068\u3070\u3059",
        "\uc124\ud0d5\ubb3c \ubc14\ub974\uae30\n\ub098\ubb34 \ucc28\uae30\n",
    ),
    (
        "\u304a\u3070\u300c\u304a\u3070\u3061\u3083\u3093\n\u3000\u5b50\u4f9b\u306e\u9803\u306e\u82b1\u706b\u5927\u4f1a\u3063\u3066",
        "\uc544\uc90c\ub9c8\u300c\uc5b4\ub9b4 \uc801\n\u3000\ubd88\uaf43\ub180\uc774\ub294{PAUSE}\ud0a4\uac00 \uc791\uc544\uc11c\n\u3000\uc55e\uc0ac\ub78c \uc720\uce74\ud0c0\ubc16\uc5d0\n\u3000\uae30\uc5b5\uc774 \uc5c6\uc5b4\u300d",
    ),
    (
        "\u590f\u4f11\u307f\u4e2d\u306e\u904e\u3054\u3057\u65b9\u306f\uff1f",
        "\ubc29\ud559\uc5d4 \ubb50\ud558\uc9c0\uff1f",
    ),
    (
        "\u6559\u982d\u305b\u3093\u305b\u300c\u305d\u308c\u306f\n\u3000\u5148\u751f\u3082\u540c\u3058\u3060",
        "\uad50\uac10\u300c\ub098\ub3c4\n\u3000\ub9c8\ucc2c\uac00\uc9c0\uc57c\u300d",
    ),
    (
        "\u6559\u982d\u305b\u3093\u305b\u300c\u866b\u76f8{0404}\u304b",
        "\uad50\uac10\u300c\uace4\ucda9\uc528\ub984\uff1f\n\u3000\uadf8\ub9bd\uad6c\ub098\u301c{PAUSE}\ub098\ub3c4 \uc88b\uc544\ud588\uc9c0\u300d",
    ),
    (
        "\u6559\u982d\u305b\u3093\u305b\u300c\u3044\u3044\u304b\u3044{PAUSE}",
        "\uad50\uac10\u300c\uc54c\uaca0\ub2c8{PAUSE}\uc7a0\uc790\ub9ac\ucc44\ub294 \uaf2d\n\u3000\uc9d1 \ubc16\uc5d0\uc11c \uc368\uc57c \ud574\u300d",
    ),
]


def normalized_source(text: str) -> str:
    return text.replace("\u3000", " ")


def raw_pause_tokens(rough_ko: str) -> list[str]:
    return re.findall(r"\{PAUSE\}(?:\{RAW:[0-9A-Fa-f]+\})?", rough_ko)


def inject_pause_tokens(text: str, rough_ko: str) -> str:
    tokens = raw_pause_tokens(rough_ko)
    if not tokens:
        return text
    pos = 0

    def repl(_: re.Match) -> str:
        nonlocal pos
        if pos >= len(tokens):
            return "{PAUSE}"
        token = tokens[pos]
        pos += 1
        return token

    return re.sub(r"\{PAUSE\}[^\S\n]*[Ａ-Ｚａ-ｚA-Za-z￥＞]*", repl, text)


def source_direct_translation(ja: str, rough_ko: str) -> tuple[str | None, list[str]]:
    normalized = normalized_source(ja)
    glyph_tokens = re.findall(r"\{[0-9A-Fa-f]{4}\}", ja)
    if "「" not in ja and len(glyph_tokens) >= 8:
        return inject_pause_tokens(ja, rough_ko), ["preserve_symbol_table_v2"]
    if "「" not in ja and ja.count("\u3000") >= 8 and len(ja) <= 120:
        return inject_pause_tokens(ja, rough_ko), ["preserve_symbol_table_v2"]
    for src, dst in PRIORITY_CONTAINS_SOURCE:
        if normalized_source(src) in normalized:
            return inject_pause_tokens(dst, rough_ko), ["manual_priority_v2"]
    extra_exact_table = {normalized_source(k): v for k, v in EXTRA_EXACT_SOURCE.items()}
    if normalized in extra_exact_table:
        return inject_pause_tokens(extra_exact_table[normalized], rough_ko), ["manual_exact_v2_extra"]
    for src, dst in EXTRA_CONTAINS_SOURCE:
        if normalized_source(src) in normalized:
            return inject_pause_tokens(dst, rough_ko), ["manual_pattern_v2_extra"]
    exact_table = {normalized_source(k): v for k, v in EXACT_SOURCE.items()}
    if normalized in exact_table:
        return inject_pause_tokens(exact_table[normalized], rough_ko), ["manual_exact_v2"]
    for src, dst in SOURCE_CONTAINS:
        if normalized_source(src) in normalized:
            return inject_pause_tokens(dst, rough_ko), ["manual_pattern_v2"]
    return None, []


def improve_dialog_v2(ja: str, rough_ko: str) -> tuple[str, list[str]]:
    direct, warnings = source_direct_translation(ja, rough_ko)
    if direct is not None:
        return direct, warnings

    old_map = dict(q1.SPEAKER_MAP)
    q1.SPEAKER_MAP.clear()
    q1.SPEAKER_MAP.update(SPEAKER_MAP)
    try:
        text, warnings = q1.improve_dialog(ja, rough_ko)
    finally:
        q1.SPEAKER_MAP.clear()
        q1.SPEAKER_MAP.update(old_map)

    for src, dst in POST_REPLACEMENTS:
        if src in text:
            text = text.replace(src, dst)
            warnings.append(f"post_replace_v2:{src}->{dst}")

    deduped = re.sub(r"^(교감|아저씨|아줌마|나|요시코|야스코|모에)「(?:\1|교감\s*선생님|교감\s*선원)[」\s　]*", r"\1「", text)
    if deduped != text:
        text = deduped
        warnings.append("dedup_speaker_v2")

    if ja.startswith("「") and text.startswith("나「"):
        text = text[1:]
        warnings.append("removed_false_speaker_v2")
    return text, warnings


def unresolved_count(text: str) -> int:
    return len(re.findall(r"\{[0-9A-Fa-f]{4}\}", text))


def main() -> None:
    refined = json.loads(REFINED.read_text(encoding="utf-8"))
    rough = json.loads(ROUGH.read_text(encoding="utf-8"))
    editable = []
    patch_rows = []
    warning_counts: dict[str, int] = {}

    for row, base in zip(refined, rough):
        ja = row["full_text"]
        rough_ko = base.get("ko", "")
        edit_text, warnings = improve_dialog_v2(ja, rough_ko)
        game_text, layout_warnings = q1.to_game_layout(ja, edit_text)
        warnings.extend(layout_warnings)
        unresolved = unresolved_count(game_text)
        if unresolved:
            warnings.append(f"contains_unresolved_game_glyph_token:{unresolved}")
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
        item["status"] = "quality_v2"
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
                "ko_rough": q1.normalize_visible(rough_ko, game_spacing=False),
                "ko_edit": edit_text,
                "ko_game": game_text,
                "status": "quality_v2_auto_postedit",
                "warnings": warnings,
                "human_note": "",
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EDITABLE.write_text(json.dumps(editable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PATCH_TRANSLATIONS.write_text(json.dumps(patch_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Translation Quality V2 Report",
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
