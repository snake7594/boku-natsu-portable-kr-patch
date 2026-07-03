# v0.1.3-image-kr

## 요약

타이틀, 시작 메뉴, 저장 데이터 이미지, 주요 게임 메뉴처럼 이미지에 직접 박혀 있던 일본어 UI를 한글화한 릴리즈입니다. v0.1.2의 pause-guard 대사 안정화는 그대로 유지했습니다.

## 변경 사항

- 타이틀 로고와 시작 메뉴 항목을 한글 이미지로 교체했습니다.
- 저장 데이터용 `ICON0/PIC1` 이미지를 한글화했습니다.
- 게임 내 주요 말풍선 메뉴 이미지를 한글화했습니다.
- 곤충 채집, 곤충 씨름, 연날리기, 일기/휴식 계열 메뉴 이미지를 한글화했습니다.
- 이미지 패치 스크립트 `tools/patch_title_system_images.py`를 추가했습니다.
- 이미지 패치 보고서와 상태 문서를 `reports/`에 추가했습니다.

## 패치 대상 내부 파일

- `map/models/title/title.bin`
- `map/models/system/saveload_normal.bin.gzx`
- `map/models/system/saveload_favorite.bin.gzx`
- `map/models/sub/0sub.bin.gzx`
- `map/models/sub/item.bin.gzx`
- `map/models/sub/specimen2.bin`
- `map/models/sub/sumo.dat`
- `map/models/sub/kite_book.bin`
- `map/models/sub/kite_select.bin.gzx`
- `diary/icon.bin`

## 검증

- 원본 ISO MD5: `B4D363D59CB87E25AB76AFC5384CCA31`
- 패치 ISO MD5: `0AF6DEC9F2097369A7ECFC584C0A5985`
- xdelta MD5: `AFCB48C0051713A8FF0CEECDB4A110DE`
- `cdimg.idx` MD5: `A54FBD28004016AE810BCD1213DF5B20`
- `cdimg0.img` MD5: `7D157EF18CCF6A1A503753F0DB9B317A`
- xdelta 적용 검증: 통과
- `cdimg.idx`는 v0.1.2와 동일하여 내부 파일 배치표 변경 없음

## 릴리즈 파일

- `Boku_no_Natsuyasumi_Portable_KR_image_kr_v0.1.3.iso.xdelta`
- `apply_iso_patch.bat`
- `checksums.md`
- `README_KO.txt`
- `xdelta.exe`

패치된 ISO 자체는 배포하지 않습니다.
