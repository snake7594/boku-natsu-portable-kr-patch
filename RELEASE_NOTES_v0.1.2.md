# v0.1.2-pause-guard

## 요약

2페이지/3페이지로 넘어가는 대사의 첫 글자가 사라질 수 있던 문제를 수정한 릴리즈입니다.

## 원인

v0.1.1에서는 페이지 시작 공백을 없애기 위해 `{PAUSE:hhhh}` 뒤의 `0000` 워드를 제거했습니다. 하지만 실제 엔진은 이 워드를 페이지 시작 처리용 더미로 소비하는 것으로 보입니다. 이 더미가 없으면 다음 페이지의 첫 실제 글자가 소비되어 화면에서 사라질 수 있었습니다.

## 변경 사항

- `{PAUSE:hhhh}` 인코딩을 `8002 hhhh 0000` 형태로 복원했습니다.
- 한국어 번역문 자체에는 `{PAUSE}` 뒤 불필요한 선행 공백을 넣지 않았습니다.
- 내부 dialog pack 재배치 금지는 유지했습니다.
- 고정 영역 초과는 띄어쓰기 압축만으로 해결했습니다.
- 내용 절단은 발생하지 않았습니다.
- startup 한글 폰트 패치는 유지했습니다.
- 안전하지 않은 save/load 시스템 텍스트 패치는 계속 제외했습니다.

## 검증

- 원본 ISO MD5: `B4D363D59CB87E25AB76AFC5384CCA31`
- 패치 ISO MD5: `D84261DC135C746EA7679FD7FCDFB7F3`
- xdelta MD5: `78F9E4F714E3180EA47E228075DD847A`
- `cdimg.idx` MD5: `A54FBD28004016AE810BCD1213DF5B20`
- `cdimg0.img` MD5: `784B13BBC5A045756A540B21F7C23614`
- xdelta 적용 검증: 통과
- 내부 pack offset/size 감사: 문제 항목 0개
- `{PAUSE:hhhh}` 뒤 `0000` 더미 워드 복원 확인

## 릴리즈 파일

- `Boku_no_Natsuyasumi_Portable_KR_pause_guard_v0.1.2.iso.xdelta`
- `apply_iso_patch.bat`
- `checksums.md`
- `README_KO.txt`
- `xdelta.exe`

패치된 ISO 자체는 배포하지 않습니다.
