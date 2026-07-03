# v0.1.1-fixedpack

## 요약

`Boku no Natsuyasumi Portable` 한글패치의 안정화 릴리즈입니다.

## 변경 사항

- 2페이지/3페이지 대사 첫 칸에 불필요한 공백이 들어가지 않도록 `{PAUSE:hhhh}` 뒤의 trailing zero 처리를 조정했습니다.
- 내부 dialog pack 재배치를 기본적으로 금지했습니다.
- 변경된 모든 `map/gz` 멤버가 원본 내부 pack offset/size를 유지하도록 다시 빌드했습니다.
- startup 한글 폰트 패치는 유지했습니다.
- 안전하지 않은 save/load 시스템 텍스트 패치는 제외했습니다.

## 검증

- 원본 ISO MD5: `B4D363D59CB87E25AB76AFC5384CCA31`
- 패치 ISO MD5: `CD2596F6BCAC02E1141049B3B4265BF0`
- xdelta MD5: `FF780A355506B848C16FD4CBD30B6CAF`
- `cdimg.idx` MD5: `A54FBD28004016AE810BCD1213DF5B20`
- `cdimg0.img` MD5: `48128F5D2122883912AD910005544795`
- xdelta 적용 검증: 통과
- 내부 pack offset/size 감사: 문제 항목 0개

## 릴리즈 파일

- `Boku_no_Natsuyasumi_Portable_KR_fixedpack_v0.1.1.iso.xdelta`
- `apply_iso_patch.bat`
- `checksums.md`
- `README_KO.txt`
- `xdelta.exe`

패치된 ISO 자체는 배포하지 않습니다.
