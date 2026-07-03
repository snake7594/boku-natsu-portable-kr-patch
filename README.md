# 나의 여름방학 포터블 한글패치

PSP 게임 `Boku no Natsuyasumi Portable`의 한글패치 제작 프로젝트입니다.

이 저장소에는 패치 제작 도구, 한국어 번역 데이터, 한글 폰트/테이블 데이터, 안정성 검증 보고서, xdelta 배포 파일이 들어 있습니다. 원본 게임 ISO, 패치된 ISO, 추출된 게임 바이너리는 포함하지 않습니다.

## 현재 릴리즈

- 버전: `v0.1.1-fixedpack`
- 원본 ISO MD5: `B4D363D59CB87E25AB76AFC5384CCA31`
- xdelta 적용 후 패치 ISO MD5: `CD2596F6BCAC02E1141049B3B4265BF0`
- 내장 `cdimg.idx` MD5: `A54FBD28004016AE810BCD1213DF5B20`
- 내장 `cdimg0.img` MD5: `48128F5D2122883912AD910005544795`

## 패치 적용 방법

`release-assets/` 폴더의 파일을 사용합니다.

1. 원본 ISO를 `apply_iso_patch.bat`와 같은 폴더에 둡니다.
2. 원본 ISO 파일 이름을 `Boku no Natsuyasumi Portable.iso`로 맞춥니다.
3. `apply_iso_patch.bat`를 실행합니다.
4. `Boku no Natsuyasumi Portable KR fixedpack v0.1.1.iso`가 생성됩니다.

## v0.1.1 수정 내용

이전 빌드에서는 한국어 대사가 원본 dialog 고정 영역을 넘는 경우 12개 `map/gz` 멤버가 내부적으로 다시 포장될 수 있었습니다. 그 결과 내부 pack offset/size가 바뀌어 PPSSPP 방치/자동 재생 크래쉬나 배경 깨짐이 발생할 수 있었습니다.

이번 릴리즈는 dialog 재배치를 금지한 상태로 다시 빌드했습니다. 최종 검증 결과는 다음과 같습니다.

- 변경된 script 파일: 59개
- 감사한 변경 멤버/상위 항목: 392개
- 수정 후 내부 pack offset/size 변경: 0개
- 공간 초과 멤버 중 띄어쓰기 압축만으로 해결한 행: 46개
- 내용 절단이 필요했던 행: 0개

## 알려진 제한

save/load 시스템 텍스트 패치는 현재 경로에 mojibake 문제가 있어 공개 빌드에 넣기에는 안전하지 않다고 판단했습니다. 그래서 이번 릴리즈에서는 제외했습니다.

## 폴더 구성

- `tools/`: 추출, 분석, 재빌드, 폰트, 검증 스크립트
- `translations/`: 편집용 및 빌드용 한국어 번역 JSON
- `font/`: 현재 빌드에 사용한 폰트 테이블과 글리프 매핑
- `reports/`: 안정성 및 fixed-pack 검증 보고서
- `release-assets/`: xdelta 패치, 체크섬, 적용 보조 스크립트

## 참고

이 프로젝트는 팬 번역 연구 프로젝트입니다. 패치를 적용하려면 사용자가 직접 보유한 정품 원본 ISO가 필요합니다.
