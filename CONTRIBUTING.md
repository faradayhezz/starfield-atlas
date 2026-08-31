# Contributing

Thank you for helping improve Starfield Atlas / 星图寻迹.

## English

1. Create a focused branch and keep unrelated changes out of the same pull request.
2. Run `setup.cmd` once, then run `scripts\test.ps1` and the frontend build before submitting.
3. For recognition changes, add or update an automated test and state whether the change affects plate solving, WCS projection, catalogue semantics, or only presentation.
4. Do not commit private photographs, EXIF-bearing user screenshots, caches, build environments, generated `results/`, or media without a confirmed redistribution licence.
5. New catalogues, sky tiles, or reference images must include their exact source page, version/date, licence or usage terms, required credit, and an integrity hash where practical.
6. A catalogue position is not pixel-level proof of visibility. Preserve the distinction between `catalog_position` and `expectedVisible` in code, UI, and documentation.

Useful commands:

```powershell
.\scripts\setup.ps1
.\scripts\run.ps1
.\scripts\test.ps1
.\scripts\build_windows.ps1
```

## 简体中文

请保持提交范围清晰；提交前运行自动化测试与前端构建。识别算法改动应附测试，并说明影响的是星图解算、WCS 投影、目录语义还是界面显示。不要提交私人照片、带 EXIF 的用户截图、缓存、构建环境、生成结果或没有明确再分发许可的素材。新增目录、巡天瓦片和样片必须记录来源、版本、许可证、署名和可行的完整性校验值。请始终区分“目录坐标落入视场”和“像素中确实可见”。

## 日本語

変更範囲を小さく保ち、提出前に自動テストとフロントエンドのビルドを実行してください。認識処理の変更にはテストを追加し、プレートソルブ、WCS 投影、カタログの意味、または表示のみの変更かを明記してください。個人写真、EXIF を含むユーザー画像、キャッシュ、ビルド環境、生成結果、再配布許諾が確認できない素材はコミットしないでください。新しいカタログ、サーベイタイル、実写サンプルには出典、版、利用条件、クレジット、可能な場合はハッシュを記録してください。
