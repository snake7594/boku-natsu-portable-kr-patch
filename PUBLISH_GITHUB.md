# GitHub 게시 기록

이 저장소는 GitHub에 게시되어 있습니다.

- 저장소: `snake7594/boku-natsu-portable-kr-patch`
- 브랜치: `main`
- 태그: `v0.1.1-fixedpack`
- 릴리즈: `v0.1.1-fixedpack`

## 릴리즈 갱신 명령

릴리즈 노트나 자산을 다시 올릴 때는 다음 명령을 사용합니다.

```powershell
cd "C:\Users\Jae Ho Lee\Documents\Codex\2026-06-30\mcpads-create-retro-game-kr-patch\github_release_repo"

git add .
git commit -m "문서와 릴리즈 설명 갱신"
git push origin main

gh release edit v0.1.1-fixedpack `
  --repo snake7594/boku-natsu-portable-kr-patch `
  --title "나의 여름방학 포터블 한글패치 fixedpack v0.1.1" `
  --notes-file RELEASE_NOTES_v0.1.1.md

gh release upload v0.1.1-fixedpack `
  release-assets\README_KO.txt `
  release-assets\checksums.md `
  --repo snake7594/boku-natsu-portable-kr-patch `
  --clobber
```

## 수동 업로드용 압축 파일

상위 프로젝트 폴더에는 다음 파일도 준비되어 있습니다.

- `github_source_v0.1.1-fixedpack.zip`
- `github_release_assets_v0.1.1-fixedpack.zip`
