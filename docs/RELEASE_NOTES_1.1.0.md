# Starfield Atlas 1.1.0

## English

Starfield Atlas 1.1.0 turns a star-field photograph into an interactive, catalog-backed sky result while keeping the solving workflow local and transparent.

### Highlights

- Import images directly with the file picker, drag them from File Explorer or apps such as WeChat, or paste with `Ctrl+V`.
- Follow real stage-by-stage progress, cancel an active job, retry a failed job, and receive clear upload and analysis timeout errors instead of an indefinitely stalled screen.
- Process photographs up to about 60 MP with reduced peak memory use through staged decoding and rendering.
- Solve fields locally with tetra3 blind plate solving, then derive a real WCS solution including image coordinates, J2000 sky coordinates, rotation, plate scale, field size, and distortion handling.
- Match bright stars and deep-sky catalogs with explicit semantics: a catalog-position marker means the object lies within the solved field; visibility in the pixels still depends on exposure, aperture, sky quality, processing, and object surface brightness.
- Customize annotation color, contrast, label weight, and layer visibility for readable exports over bright or dark backgrounds.
- Explore the sky from a first-person viewpoint at the center of the celestial sphere, with continuous navigation, DSS2, Legacy Survey, and 2MASS HiPS imagery, standard object labels, and the photograph's WCS-derived field-of-view footprint.
- Browse an offline NASA information pack with selected object imagery, introductions, and source credits.
- Run from a portable Windows x64 package; no installer is required.

### Verification

- Backend automated test suite: **60/60 passed**.
- Release workflows include large-image handling, progress/cancellation/retry behavior, catalog matching, sky-view projection, and annotation output.

### Release assets

- `Starfield-Atlas-Windows-x64-v1.1.0.zip` — portable Windows x64 application.
- `SHA256SUMS.txt` — SHA-256 checksums for release verification.
- `aladin-lite-v3.8.1-source.zip` — corresponding Aladin Lite 3.8.1 source archive supplied for GPL compliance.

### Requirements and known limitations

- Windows 10/11 x64 and the Microsoft Edge WebView2 Runtime are required. Current Windows installations normally include WebView2; install the runtime from Microsoft if the application cannot open its interface.
- Plate solving requires enough sharp, unsaturated stars and a recognizable star pattern. Heavy clouds, severe trails, extreme defocus, very narrow fields, or aggressive image processing can prevent a solution.
- EXIF focal length, capture time, and camera metadata are optional hints, not substitutes for the astrometric solution; absent or incorrect EXIF may reduce convenience but does not invalidate a successful blind solve.
- Catalog inclusion does not guarantee that an object is visibly detectable in the photograph. Solar-system bodies and transient or moving events are not comprehensively identified in this release.
- Online HiPS layers require network access and remain subject to the availability, coverage, resolution, and rate limits of their providers. Offline solving and bundled catalog features remain available without them.
- Very large files can still require substantial memory and processing time depending on image format, bit depth, and host hardware.

### Licensing and data

The original project code is released under **GPL-3.0-only**. Bundled libraries, catalogs, survey imagery, NASA materials, translations, and test photographs retain their respective licenses, attribution requirements, and source terms. See the repository's `LICENSE`, `THIRD_PARTY_NOTICES.md`, data-license files, and test-source records before redistributing the application or its assets.

---

## 简体中文

星图寻迹 1.1.0 可将星空照片转换为可交互、由真实目录支撑的识别结果，同时保持本地解算流程透明可核验。

### 主要更新

- 支持文件选择器直接上传，也可从资源管理器、微信等软件拖入图片，或使用 `Ctrl+V` 粘贴。
- 展示真实的分阶段进度；支持取消正在运行的任务、失败后重试，并对上传和分析超时给出明确错误，不再长期停在假进度界面。
- 通过分阶段解码与渲染降低峰值内存占用，可处理约 6000 万像素照片。
- 使用 tetra3 在本地执行盲解，生成真实 WCS 解算结果，包括图像坐标、J2000 天球坐标、旋转角、像素比例尺、视场尺寸与畸变处理。
- 匹配亮星与深空天体目录，并明确标注语义：目录位置落入已解算视场，不代表该天体一定能在照片像素中直接看见；实际可见性仍取决于曝光、光圈、天空质量、后期处理和天体面亮度。
- 可选择标注颜色、对比度、字体粗细和图层显隐，让亮背景或暗背景上的导出结果都保持清晰。
- 提供“人在球心向外看”的第一人称内视天球，可连续浏览全天；支持 DSS2、Legacy Survey、2MASS HiPS 底图、常规天体标注，并以真实 WCS 投影显示当前照片视场轮廓。
- 内置精选 NASA 天体资料、图片、简介和来源署名，可离线浏览。
- 提供 Windows x64 便携版，解压即可运行，无需安装程序。

### 验证情况

- 后端自动化测试：**60/60 通过**。
- 发布验证覆盖大图处理、真实进度、取消与重试、目录匹配、天球投影和标注输出。

### Release 资产

- `Starfield-Atlas-Windows-x64-v1.1.0.zip` — Windows x64 便携版应用。
- `SHA256SUMS.txt` — 用于核验发布文件的 SHA-256 校验值。
- `aladin-lite-v3.8.1-source.zip` — 为履行 GPL 要求提供的 Aladin Lite 3.8.1 对应源码包。

### 运行要求与已知限制

- 需要 Windows 10/11 x64 和 Microsoft Edge WebView2 Runtime。当前 Windows 通常已内置 WebView2；若应用无法打开界面，请从微软安装该运行时。
- 星图解算需要足够数量、清晰且不过曝的恒星以及可辨认的星点结构。厚云、严重拖线、明显失焦、极窄视场或过度后期处理可能导致解算失败。
- EXIF 中的焦距、拍摄时间和相机信息仅作为辅助提示，不能替代天文测量解算；EXIF 缺失或错误可能降低便利性，但不会否定一次成功的盲解。
- 天体被目录覆盖并不保证能在原图中直接检测到。本版本尚不能完整识别太阳系天体、瞬变事件或移动目标。
- 在线 HiPS 图层需要网络连接，并受服务提供方的可用性、覆盖范围、分辨率和访问限制影响；本地解算及随包目录功能不依赖这些在线图层。
- 超大文件仍可能因格式、位深和电脑硬件不同而占用较多内存与处理时间。

### 许可证与数据条款

项目原创代码以 **GPL-3.0-only** 发布。随包库、天体目录、巡天图像、NASA 资料、翻译和测试照片分别保留各自的许可证、署名要求与来源条款。重新分发应用或相关资产前，请查看仓库中的 `LICENSE`、`THIRD_PARTY_NOTICES.md`、数据许可证文件和测试素材来源记录。

---

## 日本語

Starfield Atlas 1.1.0 は、星野写真を実在カタログに基づくインタラクティブな解析結果へ変換し、ローカルで行うプレートソルブの内容も確認できるようにします。

### 主な特長

- ファイル選択による直接アップロードに加え、エクスプローラーや WeChat などのアプリからのドラッグ＆ドロップ、`Ctrl+V` による貼り付けに対応しました。
- 各処理段階の実際の進捗を表示し、実行中のキャンセル、失敗後の再試行、アップロードおよび解析のタイムアウト通知に対応しました。進捗画面で無期限に停止することを防ぎます。
- 段階的なデコードとレンダリングによりピークメモリ使用量を抑え、約 6000 万画素の写真を処理できます。
- tetra3 によるローカルのブラインドプレートソルブを行い、画像座標、J2000 天球座標、回転角、ピクセルスケール、視野サイズ、歪み処理を含む実際の WCS 解を生成します。
- 明るい恒星と深宇宙天体のカタログを照合し、表示の意味を明確化しました。カタログ位置が解決済み視野内にあることは、その天体が写真の画素上で必ず見えることを意味しません。実際の可視性は露出、絞り、空の状態、画像処理、天体の表面輝度に依存します。
- 注釈の色、コントラスト、文字の太さ、レイヤー表示を調整でき、明るい背景と暗い背景のどちらでも読みやすい画像を書き出せます。
- 天球の中心から外側を見る一人称視点で全天を連続して移動できます。DSS2、Legacy Survey、2MASS の HiPS 画像、基本天体ラベル、実際の WCS から計算した写真視野の輪郭を表示します。
- 選定した NASA の天体画像、解説、出典クレジットを収録したオフライン資料を閲覧できます。
- インストーラー不要の Windows x64 ポータブル版を提供します。

### 検証

- バックエンド自動テスト：**60/60 合格**。
- 大画像処理、実進捗、キャンセルと再試行、カタログ照合、天球投影、注釈出力をリリース検証に含めています。

### Release アセット

- `Starfield-Atlas-Windows-x64-v1.1.0.zip` — Windows x64 ポータブルアプリ。
- `SHA256SUMS.txt` — リリースファイル確認用の SHA-256 チェックサム。
- `aladin-lite-v3.8.1-source.zip` — GPL 対応のために提供する Aladin Lite 3.8.1 の対応ソースアーカイブ。

### 動作要件と既知の制限

- Windows 10/11 x64 と Microsoft Edge WebView2 Runtime が必要です。通常は現在の Windows に含まれていますが、画面を開けない場合は Microsoft からランタイムをインストールしてください。
- プレートソルブには、十分な数の鮮明で飽和していない恒星と識別可能な星像パターンが必要です。厚い雲、強い星の流れ、著しいピンぼけ、極端に狭い視野、過度な画像処理では解が得られない場合があります。
- EXIF の焦点距離、撮影時刻、カメラ情報は補助情報であり、位置天文解の代わりではありません。EXIF がない、または誤っていても、ブラインドソルブが成功した場合の解を無効にはしません。
- カタログ内の天体が視野に含まれていても、写真上で検出可能とは限りません。本リリースでは、太陽系天体、突発天体、移動天体を網羅的には識別しません。
- オンライン HiPS レイヤーにはネットワーク接続が必要で、提供元の可用性、カバー範囲、解像度、アクセス制限の影響を受けます。ローカルソルブと同梱カタログ機能はオンラインレイヤーなしでも利用できます。
- 非常に大きなファイルでは、形式、ビット深度、PC の性能に応じて多くのメモリと処理時間が必要になる場合があります。

### ライセンスとデータ

本プロジェクトのオリジナルコードは **GPL-3.0-only** で公開されます。同梱ライブラリ、天体カタログ、サーベイ画像、NASA 資料、翻訳、テスト写真には、それぞれのライセンス、表示義務、配布元の条件が適用されます。アプリや素材を再配布する前に、リポジトリの `LICENSE`、`THIRD_PARTY_NOTICES.md`、データライセンス文書、テスト素材の出典記録を確認してください。
