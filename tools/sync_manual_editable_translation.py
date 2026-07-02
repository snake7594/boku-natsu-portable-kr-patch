#!/usr/bin/env python3
import json
import os
import re
import shutil
from pathlib import Path

import boku_tools
import make_quality_v1_translations as q1


ROOT = Path("work")
OUTPUTS = Path("outputs")
EDITABLE_IN = OUTPUTS / "translation_quality_v2_editable.json"
REFINED = ROOT / "translation_survey" / "dialog_targets_refined.json"
ROUGH = ROOT / "translations_rough_all.json"
EDITABLE_OUT = ROOT / "translation_quality_v2" / "translation_quality_v2_editable.json"
PATCH_OUT = ROOT / "translations_quality_v2.json"
REPORT_OUT = ROOT / "translation_quality_v2" / "manual_sync_report.md"


PAUSE_WITH_RAW_RE = re.compile(r"\{PAUSE\}(?:\{RAW:[0-9A-Fa-f]+\})?")
GAME_TOKEN_RE = re.compile(r"\{(?:RAW:[0-9A-Fa-f]+|[0-9A-Fa-f]{4})\}")
FULL_SPACE = "\u3000"
MAX_PAGE_LINES = int(os.environ.get("BOKU_MAX_PAGE_LINES", "3"))
MAX_LINE_UNITS = int(os.environ.get("BOKU_MAX_LINE_UNITS", "15"))
COMPACT_REPLACEMENTS = [
    ("한　사람　몫을　하기도　전에", "제몫을　하기　전에"),
    ("결혼해서　여기로　와　버렸으니까", "결혼해　여기　왔으니까"),
    ("여기로　지나가면", "여길　지나가면"),
    ("용신　연못이나　꼭대기　산　같은　데", "용신못이나　꼭대기산도"),
    ("눈　깜짝할　새에", "금방"),
    ("갈　수　있어", "갈수　있어"),
    ("앞으로　몇　번、　장대로　쿡쿡", "몇번만　장대로　쿡쿡"),
    ("찌르기만　하면　땅에　떨어뜨릴　수　있을　것　같은　느낌　이었다", "찌르면　땅에　떨어질　듯했다"),
    ("여름　시골　산의　시끌벅적함과는", "여름　산의　소란과는"),
    ("너무나도　어울리지　않게、", "전혀　어울리지　않게、"),
    ("쓸쓸하고　그리고　슬프게　울려　퍼졌다", "쓸쓸하고　슬프게　울렸다"),
    ("몇　번이나　두드리면", "여러　번　두드리면"),
    ("화내는　방식이　달라지고", "화내는　방식이　바뀌고"),
    ("기술을　더　잘　쓰게　되는　것　같아", "기술을　더　잘　쓰나　봐"),
    ("기술을　더　잘　쓰게　되는　것같아", "기술을　더　잘　쓰나봐"),
    ("바싹　마른　불가사리와", "마른　불가사리와"),
    ("그리고　덤으로", "덤으로"),
    ("고양이　사체까지", "고양이　시체까지"),
    ("정신을　차려　보니", "정신　차려　보니"),
    ("찾으러　산을　올라온", "찾으러　온"),
    ("사람에게　보호받고　있었다는　거지", "사람에게　보호받았단　거지"),
    ("상급　학교에　진학하지　않아도", "상급학교에　안　가도"),
    ("자연스럽게　교양을　몸에　익힐　수　있을　거야", "자연스레　교양을　익힐　거야"),
    ("교양을　몸에　익힐　수있을거야", "교양을　익힐거야"),
    ("모에　자신이　조금　더　정리　할　시간을", "모에가　좀더　정리할　시간을"),
    ("모에　자신이　조금　더　정리할　시간을", "모에가　좀더　정리할　시간을"),
    ("지금　모에가　생각하고　있는　걸、　모에　자신이　조금　더　정리　할　시간을　갖지　않으면", "지금　모에　생각을　좀더　정리할　시간을　갖지　않으면"),
    ("아저씨들　사춘기　시절이라는　건", "아저씨들　사춘기란"),
    ("아저씨들　사춘기　시절이라는　건、", "아저씨들　사춘기란、"),
    ("몹시　가난　했던　무렵의　이야기란다", "몹시　가난했던　때란다"),
    ("몹시가난　했던　무렵의이야기란다", "몹시　가난했던　때란다"),
    ("농어　뮈니에르、　방방지", "농어　뮈니에르와　방방지"),
    ("복주머니　조림에　냉두부、", "유부주머니　조림과　냉두부、"),
    ("아줌마가　좋아하는　것들이었어", "아줌마　좋아하는　거였어"),
    ("전〜부　아줌마　좋아하는　거였어", "전〜부　내　취향이었어"),
    ("여름엔　가마에　불을　지피면", "여름엔　가마에　불　때면"),
    ("여름엔가마에　불을　지피면", "여름엔　가마에　불　때면"),
    ("더워서、　사실은　하고　싶지　않은데　말이지", "더워서、　실은　하기　싫거든"),
    ("더워서、　사실은　하고　싶지　않은데　말이지", "더워서、　실은　싫거든"),
    ("불을　지피지　않으면　안　되겠지", "불을　때야겠지"),
]
A0_FIXED_SLOT_REPLACEMENTS = [
    ("교감선생「어라　너도　곤충　씨름을　하고　있는　거니", "교감선생「곤충씨름을　하니"),
    ("교감선생「어라　너도　곤충/씨름을　하고　있는　거니", "교감선생「곤충씨름을　하니"),
    ("이기려면　시합　시작　직전에、　씨름판　위에서　곤충의　등을　콕콕　찌르는　거야", "이기려면　시작　직전、\n곤충　등을　콕콕　찔러"),
    ("이기려면　시합　시작　직전에、/씨름판　위에서　곤충의　등을/콕콕　찌르는　거야", "이기려면　시작　직전、\n곤충　등을　콕콕　찔러"),
    ("아무튼　몇　번이고　끈질기게　찔러　보렴", "몇　번이고　끈질기게\n찔러　보렴"),
    ("그러면　곤충이　흥분해서　기술이　잘　나온단다", "그러면　흥분해서\n기술이　잘　나온단다"),
    ("교감선생님「해마다　여름방학　후반에는", "교감선생님「매년　방학　후반엔"),
    ("연수　때문에　멀리　있는　도시까지　가게　되어　있단다", "연수로　먼　도시에　간단다"),
    ("요　몇　년、　백중　지나서부터", "요　몇　년、　백중　뒤엔"),
    ("산속　깊은　곳에　대학생　연구자가　온다는　모양인데", "깊은　산에　대학생\n연구자가　온다더구나"),
    ("잠자리채는　집　안에서는　못　쓰지만", "잠자리채는　집　안에선　못　써"),
    ("그래도　집　밖으로　나가서　잠자리채를　장비하면　언제든　쓸　수　있을　거야", "밖에서　장비하면\n언제든　쓸수　있어"),
    ("한번　시험　삼아　해　보렴", "한번　해　보렴"),
    ("근처　나무를　베어　쓰러뜨려서　다리를　만드는　수밖에　없구나", "근처　나무를　베어\n다리를　만들어야겠구나"),
    ("예를　들어　창고는　살펴　봤니", "창고는　살펴봤니"),
    ("매일　밤　늦게까지　공부해라！", "밤늦게까지　공부해라！"),
    ("１학기　복습을　잊지　마라！", "１학기　복습도　해라！"),
    ("아직　초등학생이고　말이지…", "아직　초등학생이니까…"),
    ("벌집이　무서워서　앞으로　나아갈　수　없어…", "벌집이　무서워　못　가…"),
    ("벌집이　무서워서　앞으로　나아갈　수없어…", "벌집　무서워　못　가…"),
    ("삼촌에게　수박　서리를　가르쳐　줘야　할까？", "수박　서리는　어떻게？"),
    ("삼촌에게　수박　서리를가르쳐　줘야　할까？", "수박　서리는？"),
    ("삼촌에게　수박　서리를　가르쳐/줘야　할까？", "수박　서리는　어떻게？"),
    ("다리가　없어서　더　나아갈　수　없는　곳이…", "다리가　없는　곳이…"),
    ("다리가　없어서　더　나아갈　수없는　곳이…", "다리　없는　곳이…"),
    ("다리가　없어서　더　나아갈　수/없는　곳이…", "다리가　없는　곳이…"),
    ("모에의　방에　들어갈　수　없는　건　왜？", "모에　방엔　왜　못　가？"),
    ("모에의　방에　들어갈　수없는　건　왜？", "모에　방엔　왜？"),
    ("모에의　방에　들어갈　수　없는/건　왜？", "모에　방엔　왜　못　가？"),
    ("곤충　씨름이라니　정말　그립구나", "곤충씨름、　그립구나"),
    ("선생님도　무척　좋아했단다", "선생님도　좋아했단다"),
    ("배가　고파진단　말이야…", "배가　고프거든…"),
    ("바다에서　헤엄치려면　어떻게　하면　돼？", "바다　수영은　어떻게？"),
    ("북적북적이라고　하니까　말인데", "북적북적하니　말인데"),
    ("여기　근처는　밤이　되면　개구리　군이　아주　시끌벅적해", "여긴　밤이면　개구리들이　시끌해"),
    ("에헤、　봄이　시작될　무렵　얘기지만", "에헤、　초봄　얘기지만"),
    ("구경하게　해　줘、　바이바〜이！", "구경시켜　줘、　바이바〜이！"),
    ("내가　글쎄、　연적인　여자애한테", "내가　연적인　애한테"),
    ("대체　이게　무슨　소릴　하고　있는　거야", "대체　무슨　소릴　하는　거야"),
    ("그거、　주변을　신경　쓰면서　보고　있는　거야", "그거、　주변을　보며　보는　거야"),
    ("혹시　눈치　보느라　밥을　못　먹는　거야？", "혹시　눈치　보여　밥　못　먹어？"),
    ("골칫덩어리　초등학생？", "골칫덩어리　초딩？"),
    ("몇번만　장대로　쿡쿡　찌르기만　하면　땅에　떨어뜨릴　수있을　것같은　느낌이었다", "몇번만　장대로　쿡쿡　찌르면　땅에　떨어질　듯했다"),
    ("몇번만　장대로　쿡쿡　찌르기만　하면　땅에　떨어뜨릴　수있을　것같은　느낌　이었다", "몇번만　장대로　쿡쿡　찌르면　땅에　떨어질　듯했다"),
    ("내가　집으로　돌아가기　전날、", "내가　돌아가기　전날、"),
    ("고속도로　아래의　비밀　묘지에는　아무도　없었다", "고속도로　밑　비밀　묘지엔　아무도　없었다"),
    ("그것은　당연히、　나에게는　쓸쓸한　일이었지만", "당연히　내겐　쓸쓸했지만"),
    ("그래도、　아이는　아이　나름의　잔혹함을　알고　있는　법이라서", "그래도　아이는　나름의　잔혹함을　아는　법이라"),
    ("연못　위를　건너오는　서늘한　바람은이　시골　산에서의　짧은　여름의　시간이", "연못　위를　건너온　서늘한　바람은　이　산골의　짧은　여름이"),
    ("이제、　얼마　남지　않았다는　것을　내게　느끼게했다", "이제　얼마　남지　않았음을　느끼게했다"),
    ("이런　일도　있는　거지…　그렇게　생각하면서도", "그럴　수도　있지…　그렇게　생각해도"),
    ("폭죽을　손에　넣었다！", "폭죽을　얻었다！"),
    ("나는、　그　금속질의　차가운　빛을、　눈도　깜빡이지　않고　줄곧　바라보고　있었다", "나는　그　차가운　금속빛을　눈도　깜빡이지　않고　봤다"),
    ("언덕　위에서　바라보는　풍경은　어쩐지　심호흡이라기보다는", "언덕　위　풍경은　어쩐지　심호흡보다"),
    ("커다란　하품이　어울릴　것같은　실로　느긋한　것이었다", "큰　하품이　어울리는　느긋함이었다"),
    ("연을　날리겠습니까？　예　아니오", "연을　날릴까요？　예　아니오"),
    ("무엇을　읽을까요？　희귀　곤충도감　즐거운　연　백과", "무엇을　읽을까요？　곤충도감　연　백과"),
    ("무엇을　읽을까요？　희귀/곤충도감　즐거운　연　백과", "무엇을　읽을까요？　곤충도감　연　백과"),
    ("클라리넷　배우기　시작했어", "클라리넷을　배워"),
    ("가을　문화제　때　둘이서　연주할거야", "가을　문화제에서　둘이　연주해"),
    ("멀리에　산기슭의　사기노사토　마을이　보였다", "멀리　산기슭　사기노사토가　보였다"),
    ("멀리에　산기슭의　사기노사토/마을이　보였다", "멀리　산기슭　사기노사토가　보였다"),
    ("아저씨네　마당　저　안쪽가축　우리　옆쪽으로", "마당　안쪽　가축우리　옆에"),
    ("유키노　강　상류로　반딧불이　개울까지이어지는　길이　있잖니", "유키노강　상류　반딧불이　개울로　가는　길이　있잖니"),
    ("인생이란　참　여러가지야〜　라든가　확〜　하고　온다든가", "인생은　여러가지야〜　라든가　확〜　온다든가"),
    ("대실패의　권　같은　느낌이었어", "대실패　같은　느낌이었어"),
    ("머리　같은　거　어지럽지　않아？", "머리　어지럽지　않아？"),
    ("목표　온도야！", "목표　온도야！"),
    ("가마　아궁이에　불을　지피마", "가마에　불을　지필게"),
    ("귀뚜라미　울음소리에　흔들리는　내가마의　아직　여린　불에　내　아이　안기네", "귀뚜라미　소리에　흔들리는　내　가마의　여린　불에　내　아이　안기네"),
    ("이제이도끼도　슬슬　수명이　다　됐나", "이　도끼도　슬슬　수명이　됐나"),
    ("새　걸로　써야겠다", "새걸　써야겠다"),
    ("커다란　항아리에　마른　나뭇가지가　장식되어　있다", "큰　항아리에　마른　가지가　장식돼　있다"),
    ("그것은、　잔뜩　흐려　슬픈　저녁노을　하늘을　배경으로", "그건　흐리고　슬픈　저녁노을을　배경으로"),
    ("복엽기　두　대가　그려진　프라모델　상자였다", "복엽기　두　대가　그려진　프라모델　상자였다"),
    ("이제가을이　왔단다　어서　너희　집으로　돌아가렴", "이제　가을이야　어서　집으로　가렴"),
    ("잠자리들의　무리는　나에게、　그렇게　말하고　있는　것만　같았다", "잠자리　무리가　내게　그렇게　말하는　듯했다"),
    ("양철　지붕에　커다란　구멍　낡고　다　쓰러져가는　바닷가　집", "양철　지붕엔　큰　구멍　낡고　쓰러져가는　바닷가　집"),
    ("보쿠는　보쿠야！　도시　학교에　다니는　초등학생이고、　선생님은　나카지마　선생님！", "보쿠는　보쿠야！　도시　학교　초등학생이고、　담임은　나카지마　선생님！"),
    ("센다이　대학에서　대학생　하고　있어　전공은　자연과학…", "센다이대　학생이야　전공은　자연과학…"),
    ("너한테　그런　소리　듣고　싶지　않아", "너한테　그런　말　듣기　싫어"),
    ("꼬맹이의　등신대　개그는、　왠지　페이스가　흐트러진단　말이야", "꼬맹이　개그는　왠지　페이스가　흐트러져"),
    ("난데없이、　참으로　요상하고　괴상한　장치가　나타난　것이다", "난데없이　요상한　장치가　나타났다"),
    ("소리를　감지하면　녹음이　시작돼", "소리를　감지하면　녹음돼"),
    ("설탕물은　없어져　있었다", "설탕물은　없었다"),
    ("수령이　얼마나　되는　걸까", "몇　살이나　됐을까"),
    ("그　상수리나무　거목은　나와　파란　하늘　사이에　우뚝　솟아", "그　커다란　상수리나무는　나와　파란　하늘　사이에　솟아"),
    ("햇살　속에서　고요히、　그리고　기분　좋게　우듬지를　흔들고　있었다", "햇살　속에서　고요히　기분　좋게　우듬지를　흔들었다"),
    ("크고　커다란　쩍　갈라진　덜컹덜컹　나무", "크고　갈라진　덜컹덜컹　나무"),
    ("설탕물을　바른다　나무를　걷어찬다", "설탕물　바르기　나무　차기"),
    ("앞쪽　숲의　우듬지를　스친　저편에", "앞숲　우듬지　너머에"),
    ("먼저、　작은아버지의　집과　그　마당의　감나무가", "먼저　작은아버지　집과　마당의　감나무가"),
    ("여름　햇살을　받으며　어렴풋이　흔들거리는　모습이　있었고", "여름　햇살　속에　어렴풋이　흔들렸고"),
    ("다시　그　너머、　산의　능선이　다소　완만해진　언저리에는", "그　너머　산등성이가　완만해진　곳엔"),
    ("수박도둑은、　딱　보기에도　팔심이　세　보이는　동네　아이였다", "수박도둑은　딱　봐도　힘센　동네　아이였다"),
    ("나의　늘　그러던　버릇이　시작되었다", "내　늘　그렇던　버릇이　시작됐다"),
    ("대학생인　미인인데　해마다　여름　동안이　산에　틀어박혀서", "미인　대학생인데　해마다　여름엔　산에　틀어박혀"),
    ("그래서　우리　집에　목욕을　하러　오는　거란다", "그래서　우리　집에　목욕하러　온단다"),
    ("책을　보고만들어　주었으면　하는　연을　고르렴！", "책을　보고　만들고　싶은　연을　고르렴！"),
    ("낮에、　아저씨가　공방에　있을　때라도、　뭘　골랐는지　알려주러　오려무나", "낮에　아저씨가　공방에　있을　때　뭘　골랐는지　알리러　오렴"),
    ("올해는　용신　연못　근처까지　들어가는　모양이야", "올해는　용신못　근처까지　간대"),
    ("책을　잔뜩가지고　들어가서　텐트에서　생활하고　있어", "책을　잔뜩　들고　가　텐트에서　살아"),
    ("지장보살님을　왼쪽으로가서　숲을　빠져나가면　큰　연못이　있잖아", "지장보살님　왼쪽　숲을　지나면　큰　연못이　있잖아"),
    ("그럼、　잘　먹겠습니다〜", "잘　먹겠습니다〜"),
    ("그럼、　잘　먹겠습니다！", "잘　먹겠습니다！"),
    ("무슨　소린지　모르겠어", "무슨　소린지　몰라"),
    ("만사　순조로웠습니다　주지육림이었습니다　악몽　같았습니다", "순조로웠다　주지육림이었다　악몽　같았다"),
    ("인생은　여러가지야〜　라든가　확〜　온다든가", "인생　여러가지야〜　확〜　온다든가"),
    ("내가　없는　동안　무슨　사건이라도　있었니？", "내가　없는　동안　무슨　일　있었니？"),
    ("오늘은　지쳐　버렸네　보쿠　집　잘봐　줘서　수고했어", "오늘은　지쳤네　보쿠　집　봐줘서　수고했어"),
    ("그거　참　수고　많았구나", "참　수고　많았구나"),
    ("안　적혀　있어", "안　적혀있어"),
    ("살아　있어　주면　좋을　텐데", "살아　있으면　좋을　텐데"),
    ("잘　먹겠습니다！", "잘먹겠습니다！"),
    ("거짓말이야　거짓말", "농담이야"),
    ("무슨　소린지　몰라", "무슨　소린지　몰라"),
    ("…하아　…입맛이　없어", "…하아　입맛　없어"),
    ("무슨　일　있어？", "무슨　일이야？"),
    ("무슨　일이야？", "왜　그래？"),
    ("노라는　어느　날　갑자기　우리　집　대문　앞에　있었단다", "노라는　어느　날　갑자기　우리　집　앞에　있었단다"),
    ("결국　주인이　누군지　알　수가　없어서", "끝내　주인을　알　수　없어서"),
    ("그대로　우리　집　노라가　되어　버린　거란다", "그대로　우리　집　노라가　됐단다"),
    ("부모님이라는　건", "부모님은"),
    ("인간적인　결함이라든가、　큰　속임수같은　걸　찾아낼　수가　없었어", "인간적　결함이나　큰　속임수를　찾을　수　없었어"),
    ("완벽에가까운　존재　였단다", "완벽에　가까운　존재였단다"),
    ("평판이　좋은　모양이야", "평판이　좋은가　봐"),
    ("집에서　쓰려고만든　거라、　어디서도　팔지　않을　텐데　말이지", "집에서　쓰려고　만든　거라　어디서도　안　팔　텐데"),
    ("목욕을　오래　하는　걸　잘하니까", "목욕을　오래　하니까"),
    ("너무　남　듣기　안　좋은　말은　하지　말아　줬으면　좋겠구나", "남　듣기　안　좋은　말은　삼가　줬으면　좋겠구나"),
    ("오늘　밤은　후텁지근하구나", "오늘　밤은　후텁하구나"),
    ("내일、　가마에　불을　넣을거야", "내일　가마에　불　넣을거야"),
    ("오른쪽부터　순서대로　밀가루・설탕・소금", "오른쪽부터　밀가루・설탕・소금"),
    ("무엇을　마시겠습니까？　노라표　우유　보리차", "무엇을　마실까요？　노라표　우유　보리차"),
    ("설탕물을　손에　넣었다", "설탕물을　얻었다"),
    ("설탕을　발견했다", "설탕을　찾았다"),
    ("도시랑　똑같은　하늘이나　구름을　똑같은　시간에　여기서도　볼　수있다면", "도시와　같은　하늘과　구름을　같은　시간에　여기서도　본다면"),
    ("보쿠　군이　돌아간　뒤에도　전화로　말이야", "보쿠　군이　돌아간　뒤에도　전화로"),
    ("같은　하늘을　보며、　같은　마음으로　같은이야기를　할　수있을　텐데", "같은　하늘을　보며　같은　마음으로　얘기할　수있을　텐데"),
    ("그　오래된　편지를　읽었더니　말이야", "그　오래된　편지를　읽고　나니"),
    ("내　고민　같은　건、　어쩌면　하찮은　걸까？", "내　고민은　어쩌면　하찮은　걸까？"),
    ("머리가　뒤죽박죽　빙글빙글", "머리가　뒤죽박죽이야"),
    ("소리의　물결이　조용히　숲속으로　빨려　들어가서", "소리의　물결이　조용히　숲으로　스며서"),
    ("잠이　덜　깬　아기　너구리나　구애　중인　땅벌　군　같은　애들이", "잠　덜　깬　아기　너구리나　구애　중인　땅벌들이"),
    ("모두모두　행복해져가는　것같은　기분이　들어", "모두　행복해지는　기분이　들어"),
    ("희미한　별들이、　빼곡히　들어차　있는　것같지　않아？", "희미한　별들이　빼곡한　것같지　않아？"),
    ("가을　벌레들의　속삭임을　듣는　저녁、　인거야", "가을벌레　속삭임을　듣는　저녁이야"),
    ("가마　아저씨　얼굴이　새빨개져서　화내고　있다", "가마　아저씨가　새빨개져　화내고　있다"),
    ("조금만　더　있으면　목표　온도야！", "조금만　더면　목표　온도야！"),
    ("이제　조금만　더　하면　돼", "이제　조금만　하면　돼"),
    ("조금만　있으면　오랜만의　현금　수입이야！", "조금만　있으면　오랜만의　수입이야！"),
    ("목표의　구십　퍼센트이상은　됐으려나", "목표의　구십퍼센트는　됐으려나"),
    ("순식간에　그쳤지만　엄청나게　쏟아졌지", "금방　그쳤지만　엄청　쏟아졌지"),
    ("한　번　더가르쳐　줄래？", "다시　알려줘"),
    ("말귀　잘　알아듣는　착한　아이구나、　기특하다！", "말귀　잘　알아듣는　착한　아이구나！"),
    ("위험한　곳에는가면", "위험한　곳엔　가면"),
    ("기가　센　성격　같지만", "기가　세　보이지만"),
    ("이기면이길수록　더　강해　지는거야", "이길수록　더　강해져"),
    ("튼튼해서　체력이　잘　안　줄어드는　거　라든가、　여러　특징이　있어", "튼튼해서　체력이　안　줄거나　여러　특징이　있어"),
    ("용신　연못가에　있는　방공호에　들어가　본　적　있어？", "용신못가　방공호에　들어가　봤어？"),
    ("냉장고에　보리차나　우유가　있으니까、　마음대로　꺼내서　마셔도　돼", "냉장고에　보리차랑　우유가　있으니　마셔도　돼"),
    ("엄마가만삭이라　맡아　두고　있어", "엄마가　만삭이라　맡아뒀어"),
    ("목욕탕에서　깜짝　놀란　덕분에", "목욕탕에서　놀란　덕분에"),
    ("오르듯이만들어져　있어서", "오르듯　만들어져서"),
    ("천도이상까지　올릴　수가　있단다", "천도　넘게　올릴수　있단다"),
    ("비탈　위쪽으로　올라가기　때문에", "비탈　위로　올라가기　때문에"),
    ("연을만들어　주길　바라는　것같은데、　미안하구나", "연을　만들어　달라는　것같은데　미안하구나"),
    ("지금부터만들어도　보쿠가　여기　있는　동안엔　완성이　안　되겠구나", "지금부터　만들어도　네가　있는　동안엔　완성　못하겠구나"),
    ("얼굴　그림　연을　손에　넣었다", "얼굴　그림　연을　얻었다"),
    ("높이높이", "높이"),
    ("몇　수　위인　것같구나", "몇　수　위구나"),
    ("든든하게　느껴지기　시작했단다", "든든하게　느껴진단다"),
]


def pause_raw_tokens(*texts: str) -> list[str]:
    for text in texts:
        tokens = PAUSE_WITH_RAW_RE.findall(text or "")
        if any("{RAW:" in token for token in tokens):
            return [token if "{RAW:" in token else "{PAUSE}" for token in tokens]
    return []


def preserve_raw_after_pause(text: str, reference_tokens: list[str]) -> str:
    if not reference_tokens:
        return text
    pos = 0

    def repl(_: re.Match) -> str:
        nonlocal pos
        if pos >= len(reference_tokens):
            return "{PAUSE}"
        token = reference_tokens[pos]
        pos += 1
        return token

    return PAUSE_WITH_RAW_RE.sub(repl, text)


def normalize_manual_text(text: str) -> str:
    return text.replace("～", "〜").replace("麻疹", "홍역")


def page_line_budget(source_page: str) -> int:
    return max(MAX_LINE_UNITS, max(boku_tools.layout_units(source_page) or [0]))


def unit_width(text: str) -> int:
    return boku_tools.layout_units(text)[0]


def pieces(text: str):
    pos = 0
    for match in GAME_TOKEN_RE.finditer(text):
        if match.start() > pos:
            for ch in text[pos : match.start()]:
                yield ch
        yield match.group(0)
        pos = match.end()
    if pos < len(text):
        for ch in text[pos:]:
            yield ch


def piece_width(piece: str) -> int:
    return 0 if GAME_TOKEN_RE.fullmatch(piece) else 1


def split_long_segment(segment: str, width: int) -> list[str]:
    out: list[str] = []
    line = ""
    line_width = 0
    for piece in pieces(segment):
        next_width = line_width + piece_width(piece)
        if line and next_width > width:
            out.append(line.rstrip(FULL_SPACE))
            line = piece.lstrip(FULL_SPACE)
            line_width = unit_width(line)
        else:
            line += piece
            line_width = next_width
    if line:
        out.append(line.rstrip(FULL_SPACE))
    return out


def wrap_page(text: str, width: int) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\n \t\u3000]+", FULL_SPACE, text).strip(FULL_SPACE)
    if not text:
        return [""]

    lines: list[str] = []
    line = ""
    for segment in re.split(f"({FULL_SPACE}+)", text):
        if not segment:
            continue
        if segment.startswith(FULL_SPACE):
            if line:
                line += FULL_SPACE
            continue
        candidate = (line + segment).rstrip(FULL_SPACE)
        if unit_width(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line.rstrip(FULL_SPACE))
            line = ""
        for chunk in split_long_segment(segment, width):
            if not line:
                line = chunk
            elif unit_width(line + FULL_SPACE + chunk) <= width:
                line = line + FULL_SPACE + chunk
            else:
                lines.append(line.rstrip(FULL_SPACE))
                line = chunk
    if line:
        lines.append(line.rstrip(FULL_SPACE))
    return lines or [""]


def compact_text(text: str) -> str:
    compacted = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", FULL_SPACE)
    for _ in range(2):
        for src, dst in COMPACT_REPLACEMENTS:
            compacted = compacted.replace(src, dst)
        compacted = re.sub(rf"([가-힣]){FULL_SPACE}(은|는|이|가|을|를|에|로|와|과|도|만|부터|까지|처럼|보다)", r"\1\2", compacted)
        compacted = re.sub(rf"(것|수){FULL_SPACE}(같|있|없)", r"\1\2", compacted)
        compacted = re.sub(rf"{FULL_SPACE}(했다|였다|란다|거야|같아|봐)", r"\1", compacted)
    return compacted


def compact_fixed_slot_text(text: str) -> str:
    compacted = text
    for _ in range(3):
        compacted = compact_text(compacted)
        for src, dst in A0_FIXED_SLOT_REPLACEMENTS:
            compacted = compacted.replace(src, dst)
    return compacted


def split_by_capacity(text: str, source_pages: list[str]) -> list[str]:
    flat = PAUSE_WITH_RAW_RE.sub(FULL_SPACE, text)
    flat = re.sub(r"[\n \t\u3000]+", FULL_SPACE, flat).strip(FULL_SPACE)
    if not flat:
        return ["" for _ in source_pages]

    pages: list[str] = []
    current = ""
    source_index = 0
    max_units = page_line_budget(source_pages[source_index]) * MAX_PAGE_LINES
    for segment in re.split(f"({FULL_SPACE}+)", flat):
        if not segment:
            continue
        if segment.startswith(FULL_SPACE):
            if current:
                current += FULL_SPACE
            continue
        candidate = (current + segment).rstrip(FULL_SPACE)
        remaining_pages = len(source_pages) - len(pages) - 1
        if current and unit_width(candidate) > max_units and remaining_pages > 0:
            pages.append(current.rstrip(FULL_SPACE))
            source_index += 1
            current = segment
            max_units = page_line_budget(source_pages[source_index]) * MAX_PAGE_LINES
        else:
            current = candidate
    pages.append(current.rstrip(FULL_SPACE))
    while len(pages) < len(source_pages):
        pages.append("")
    if len(pages) > len(source_pages):
        pages = pages[: len(source_pages) - 1] + [FULL_SPACE.join(pages[len(source_pages) - 1 :])]
    return pages


def reflow_to_page3(ja: str, edit_text: str, reference_tokens: list[str]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    game = q1.normalize_visible(edit_text, game_spacing=True)
    source_pages = ja.split("{PAUSE}")
    page_texts = PAUSE_WITH_RAW_RE.split(game)

    if len(page_texts) != len(source_pages):
        warnings.append(f"reflow_page_redistributed:{len(page_texts)}->{len(source_pages)}")
        page_texts = split_by_capacity(game, source_pages)

    out_pages: list[str] = []
    for page_index, page in enumerate(page_texts[: len(source_pages)]):
        width = page_line_budget(source_pages[page_index])
        lines = wrap_page(page, width)
        if len(lines) > MAX_PAGE_LINES or any(unit_width(line) > width for line in lines):
            compacted_page = compact_text(page)
            compacted_lines = wrap_page(compacted_page, width)
            if len(compacted_lines) <= len(lines):
                page = compacted_page
                lines = compacted_lines
        if len(lines) > MAX_PAGE_LINES:
            merged = lines[: MAX_PAGE_LINES - 1] + [FULL_SPACE.join(lines[MAX_PAGE_LINES - 1 :])]
            merged_compacted = compact_text("\n".join(merged))
            merged_lines = wrap_page(merged_compacted, width)
            if len(merged_lines) <= MAX_PAGE_LINES and all(unit_width(line) <= width for line in merged_lines):
                lines = merged_lines
            else:
                warnings.append(f"reflow_over_capacity:page{page_index + 1}:{len(lines)}>{MAX_PAGE_LINES}")
                lines = merged
        for line_index, line in enumerate(lines):
            line_width = unit_width(line)
            if line_width > width:
                warnings.append(f"reflow_line_over_width:page{page_index + 1}:line{line_index + 1}:{line_width}>{width}")
        out_pages.append("\n".join(lines))

    while len(out_pages) < len(source_pages):
        out_pages.append("")

    tokens = reference_tokens or ["{PAUSE}"] * (len(source_pages) - 1)
    joined = out_pages[0]
    for index, page in enumerate(out_pages[1:]):
        token = tokens[index] if index < len(tokens) else "{PAUSE}"
        joined += token + page
    return joined, warnings


def warning_key(warning: str) -> str:
    return warning.split(":", 1)[0]


def is_symbol_table_like(text: str) -> bool:
    glyph_tokens = re.findall(r"\{[0-9A-Fa-f]{4}\}", text)
    if len(glyph_tokens) >= 8:
        return True
    if "「" not in text and text.count("\u3000") >= 8 and len(text) <= 120:
        return True
    return False


def shrink_known_fixed_slot(row: dict, ko_game: str) -> tuple[str, list[str]]:
    warnings = []
    if True:
        compacted = compact_fixed_slot_text(ko_game)
        if compacted != ko_game:
            ko_game, _ = reflow_to_page3(row["full_text"], compacted, pause_raw_tokens(compacted))
            ko_game = preserve_raw_after_pause(ko_game, pause_raw_tokens(compacted))
            warnings.append("manual_sync:auto_shrink_a0_fixed_slot")
    if row["script"] == "G1a.bin" and row["pack_member"] == "M_G02113.bin.gz" and row["dialog_id"] == 8050:
        ellipsis = chr(0x2026)
        if ellipsis in ko_game:
            ko_game = ko_game.replace(ellipsis, "", 1)
            warnings.append("manual_sync:auto_shrink_fixed_slot")
    return ko_game, warnings


def main() -> None:
    editable = json.loads(EDITABLE_IN.read_text(encoding="utf-8"))
    refined = json.loads(REFINED.read_text(encoding="utf-8"))
    rough = json.loads(ROUGH.read_text(encoding="utf-8"))
    refined_by_index = {int(row["index"]): row for row in refined}

    patch_rows = []
    synced_editable = []
    counts: dict[str, int] = {}

    for edit in editable:
        idx = int(edit["index"])
        row = refined_by_index[idx]
        base = dict(rough[idx])
        ja = row["full_text"]
        if is_symbol_table_like(ja):
            ko_edit = ja
            symbol_table_preserved = True
        else:
            ko_edit = normalize_manual_text(edit.get("ko_edit") or edit.get("ko_game") or "")
            symbol_table_preserved = False
        reference_tokens = pause_raw_tokens(edit.get("ko_game", ""), base.get("ko", ""))
        ko_edit = preserve_raw_after_pause(ko_edit, reference_tokens)
        ko_game, layout_warnings = reflow_to_page3(ja, ko_edit, reference_tokens)
        ko_game = preserve_raw_after_pause(ko_game, reference_tokens)
        ko_game, fixed_slot_warnings = shrink_known_fixed_slot(row, ko_game)

        warnings = []
        for old_warning in edit.get("warnings", []):
            if any(token in str(old_warning) for token in ("reflow_over_capacity", "reflow_line_over_width", "truncated_line", "dropped_extra_lines")):
                continue
            warnings.append(old_warning)
        warnings.extend(f"manual_sync:{w}" for w in layout_warnings if not w.startswith("reflow_"))
        warnings.extend(fixed_slot_warnings)
        if ko_edit != edit.get("ko_edit"):
            warnings.append("manual_sync:raw_marker_restored")
        if ko_game != edit.get("ko_game"):
            warnings.append("manual_sync:ko_game_regenerated")
        if symbol_table_preserved:
            warnings.append("manual_sync:symbol_table_preserved")
        seen = set()
        deduped_warnings = []
        for warning in warnings:
            if warning not in seen:
                seen.add(warning)
                deduped_warnings.append(warning)
                counts[warning_key(warning)] = counts.get(warning_key(warning), 0) + 1

        item = dict(base)
        item["text"] = ja
        item["raw_hex"] = row["full_raw_hex"]
        item["terminator_hex"] = row["terminator_hex"]
        item["ko"] = ko_game
        item["status"] = "manual_edit_sync"
        patch_rows.append(item)

        synced = dict(edit)
        synced["ja"] = ja
        synced["ko_edit"] = ko_edit
        synced["ko_game"] = ko_game
        synced["status"] = "manual_edit_sync"
        synced["warnings"] = deduped_warnings
        synced_editable.append(synced)

    EDITABLE_OUT.parent.mkdir(parents=True, exist_ok=True)
    EDITABLE_OUT.write_text(json.dumps(synced_editable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PATCH_OUT.write_text(json.dumps(patch_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Keep a timestamp-free working backup of the exact user-edited source.
    shutil.copy2(EDITABLE_IN, ROOT / "translation_quality_v2" / "translation_quality_v2_editable_user_input.json")

    lines = [
        "# Manual Editable Sync Report",
        "",
        f"- Source editable: `{EDITABLE_IN}`",
        f"- Synced editable: `{EDITABLE_OUT}`",
        f"- Patch JSON: `{PATCH_OUT}`",
        f"- Entries: `{len(synced_editable)}`",
        "",
        "## Warning Counts",
        "",
    ]
    for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{key}`: {value}")
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(PATCH_OUT)
    print(EDITABLE_OUT)
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
