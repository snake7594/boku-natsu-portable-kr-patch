# Publishing To GitHub

This local repository is already committed and tagged:

- Branch: `main`
- Tag: `v0.1.1-fixedpack`
- Commit: `5ccdbcf`

GitHub upload was not completed because this machine has no active GitHub CLI authentication and no `GH_TOKEN`/`GITHUB_TOKEN` environment variable.

## Option A: Create A New GitHub Repository

```powershell
cd "C:\Users\Jae Ho Lee\Documents\Codex\2026-06-30\mcpads-create-retro-game-kr-patch\github_release_repo"
gh auth login
gh repo create boku-natsu-portable-kr-patch --public --source . --remote origin --push
git push origin v0.1.1-fixedpack
gh release create v0.1.1-fixedpack `
  release-assets\Boku_no_Natsuyasumi_Portable_KR_fixedpack_v0.1.1.iso.xdelta `
  release-assets\apply_iso_patch.bat `
  release-assets\checksums.md `
  release-assets\README_KO.txt `
  release-assets\xdelta.exe `
  --title "Boku no Natsuyasumi Portable KR fixedpack v0.1.1" `
  --notes-file RELEASE_NOTES_v0.1.1.md
```

## Option B: Push To An Existing Repository

```powershell
cd "C:\Users\Jae Ho Lee\Documents\Codex\2026-06-30\mcpads-create-retro-game-kr-patch\github_release_repo"
gh auth login
git remote add origin https://github.com/OWNER/REPO.git
git push -u origin main
git push origin v0.1.1-fixedpack
gh release create v0.1.1-fixedpack `
  release-assets\Boku_no_Natsuyasumi_Portable_KR_fixedpack_v0.1.1.iso.xdelta `
  release-assets\apply_iso_patch.bat `
  release-assets\checksums.md `
  release-assets\README_KO.txt `
  release-assets\xdelta.exe `
  --title "Boku no Natsuyasumi Portable KR fixedpack v0.1.1" `
  --notes-file RELEASE_NOTES_v0.1.1.md
```

## Prepared Archives

The parent project folder also contains:

- `github_source_v0.1.1-fixedpack.zip`
- `github_release_assets_v0.1.1-fixedpack.zip`

These can be uploaded manually through the GitHub web UI if preferred.
