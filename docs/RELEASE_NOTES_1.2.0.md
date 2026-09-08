# Starfield Atlas / 星图寻迹 1.2.0

[English](#english) · [简体中文](#简体中文) · [日本語](#日本語)

## English

Version 1.2.0 expands faint-object coverage, introduces a compact photo-analysis
workbench, and exports annotations from the original full-resolution source.

### Catalogue expansion

- Full HYG v4.1: **119,625 stars**, including **104,027 fainter than V=7**.
  The default in-photo stellar magnitude limit is V=12. The inventory no longer
  stops after a small number of bright labels; HIP/HD/HYG objects remain
  searchable and selectable. All **2,253 Chinese star labels** are retained.
- Added all **1,791** updated Lynds dark-nebula records from CDS VII/7A, retaining
  cloud centres, area, opacity classes and related Barnard identifiers.
- Combined runtime inventory: **15,162** projectable catalogue entries, including
  **1,793 dark-nebula entries**. This includes 790 historical OpenNGC entries
  classified as stars or double stars, not 15,162 separate galaxies and nebulae.
- Cached, vectorized sky-cap filtering projects only relevant stars. Full
  inventory and default annotation density are independent.
- The **Deep-sky catalogue** selector now filters the returned DSO inventory:
  common targets admit known magnitude ≤10 or named/Messier display-recommended
  objects; extended admits magnitude ≤15 or named/Messier display-recommended
  objects; complete (default) retains all in-field entries, including unnamed
  LDN clouds and unknown magnitudes. The stellar V=12 limit is independent.
- Corrected the IC 434 display name to identify the emission region behind the
  Horsehead; NGC 2024 remains the Flame Nebula and Barnard 33 the Horsehead.
  The original source CSV and checksum remain intact; the correction is
  documented against NASA/ESA sources.

### Workbench and annotation

- Compact image-first layout with toolbar controls, searchable/paginated
  catalogue table, magnitude filtering, coordinate details and object selection.
- Fit-to-window and 100% scale of the displayed image (reduced RAW/TIFF previews are labelled; exports remain full resolution), pointer-centred zoom and panning, and
  original/annotation switching. Shortcuts: `Ctrl+O`, `Ctrl+S`, `0`, `1`, `H`,
  `+`/`−`, and `Esc` for cancellation during analysis.
- Initial annotation: **85% opacity**, normal-weight text at **18 px** and lines
  at **1.25 px per 1920 px image width**, using moderate green `#69BE7A`, yellow
  `#D4B953` and purple `#A391BF`. Sparse density allows up to **35 labels** before
  collision handling. **Constellation lines start off**, with strength 55 when
  enabled. The default has no thick outlines, glow or central filled dots.
- Hollow circles or corner brackets protect stellar centres. Colour, font
  weight/size, opacity, line width, contrast and label density remain adjustable.
- Faint targets can be selected from the catalogue without filling the initial
  photograph with thousands of marks. Newly added unnamed LDN clouds stay out of
  the default labels until requested through deeper settings or selection.

### RAW and full-resolution export

- Camera RAW decoded by rawpy/LibRaw, including supported ARW, CR2/CR3, NEF, DNG,
  RAF, ORF and RW2 cameras. Full-resolution development uses the active image
  area and applies camera orientation once.
- Annotated RAW exports as **16-bit TIFF**, with the original RAW retained
  unchanged. Rendered annotations cannot be saved back as an unchanged sensor
  mosaic in the original proprietary RAW container.
- JPG/JPEG, PNG and supported single-frame TIFF preserve the oriented source
  pixel dimensions, container and supported bit depth. Coloured annotations
  convert grayscale to RGB at the same sample depth.
- Style re-export reuses the established sky coordinates and composites over
  the retained source on the local backend. It does not repeat plate solving or
  export a reduced browser preview canvas.
- Native image operations are serialized and conversion/compositing use bounded
  strips. Full-resolution images can still require substantial memory.
- **Original pixel dimensions are preserved; file byte size cannot remain
  identical** after adding annotations or recompressing JPEG.

### Real-photo validation

| Input | Preserved pixels / format | Stars fainter than V=7 in catalogue field | Full pipeline |
|---|---|---:|---:|
| Original 28 mm photograph | 9504 × 6336 / JPEG | 7,281 | 9.186 s |
| Original 70 mm photograph | 9504 × 6336 / JPEG | 1,385 | 4.479 s |
| Public Orion photograph | 5218 × 3485 / JPEG | 1,035 | 2.246 s |
| Public Cygnus photograph | 4428 × 3452 / JPEG | 1,149 | 2.146 s |

The original-photo centres and field sizes exactly reproduce the stored
solutions; the public solutions agree with the rounded historical values within
0.0000005 degrees. These are local test timings, not universal guarantees.
Automated coverage includes catalogue identity/magnitude handling, star-core
protection, native image samples, export consistency, progress and cancellation.

A real Nikon D3S NEF was decoded to **4284 × 2844 uint16 RGB**, with focal length,
exposure and capture metadata. This validates the RAW decoder/export path; it
does **not** establish a successful plate solve of that aurora photograph.
See [the validation record](VALIDATION_1.2.0.md) and [RAW details](RAW_AND_EXPORT.md).

### Retained capabilities and limits

Local tetra3 blind solving, optional EXIF, drag/drop and paste, real progress,
cancel/retry, first-person celestial-sphere navigation, WCS photo footprints,
DSS2/Legacy/2MASS survey layers and the offline NASA guide remain available.

Catalogue projection is explicitly labelled `catalog_position` with
`pixelDetected: false`; it does not prove that a faint object appears in the
exposure. HYG's sparse faint tail reaches V=21 but is not complete to that limit.
Positions retain epoch/equinox J2000; high-proper-motion stars are not moved to
an assumed capture date. LDN area-equivalent circles are approximate size guides,
not measured cloud outlines. RAW support depends on LibRaw and the camera model.
Very narrow fields, true fisheye images, heavy cloud and severe star trails remain
limitations of the bundled solving model.

### Download

- `Starfield-Atlas-Windows-x64-v1.2.0.zip` — extract completely and run `星图寻迹.exe`.
- `SHA256SUMS.txt` — checksums for the release assets.

Requires Windows 10/11 x64 and Microsoft Edge WebView2 Runtime. Application code
is GPL-3.0-only; catalogue, image and library terms remain separate. See
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) and the bundled licence files.

---

## 简体中文

1.2.0 扩充暗弱天体目录，采用紧凑的照片分析工作台，并从原始全分辨率文件导出标注。

### 目录扩充

- 完整 HYG v4.1：**119,625 颗恒星**，其中 **104,027 颗暗于 V=7**，照片目录默认查询到 V=12。不再把清单限制为十几颗亮星，可搜索和选择 HIP/HD/HYG 目标；保留全部 **2,253 个中文星名**。
- 新增 CDS VII/7A 新版 Lynds 暗星云全部 **1,791 条**，保留云中心、面积、不透明度和相关 Barnard 编号。
- 运行时合计 **15,162 条**可投影目录记录，其中 **1,793 条暗星云记录**；总数包含 790 条历史 OpenNGC 恒星／双星记录，不是 15,162 个不同星系和星云。
- 缓存恒星方向向量，先筛选天区再投影。完整目录清单与初始标注密度独立。
- **深空目录**选择器实际筛选返回清单：常用天体保留已知星等 ≤10 或被建议显示的有俗名／梅西耶目标；扩展目录保留星等 ≤15 或上述具名推荐目标；默认完整目录保留全部视场内条目，包含无俗名 LDN 和未知星等。独立的恒星上限仍为 V=12。
- 修正 IC 434 显示名为“马头星云背景发射区”；NGC 2024 保持“火焰星云”，Barnard 33 保持“马头星云”。原始目录 CSV 和校验和不变，修正依据 NASA/ESA 官方资料记录。

### 工作台与标注

- 以照片为中心的紧凑工具栏、可搜索和分页的目录表格、星等筛选、坐标信息与目标选择。
- 支持适应窗口、显示图像的 100% 像素比例（RAW/TIFF 缩小预览明确标为“100% 预览”，导出仍为原始分辨率）、以指针为中心缩放、平移和原图／标注切换。快捷键包括 `Ctrl+O`、`Ctrl+S`、`0`、`1`、`H`、`+`/`−`；分析时按 `Esc` 取消。
- 初始样式采用 **85% 不透明度**、普通字重，每 1920 像素图宽对应 **18 px 文字、1.25 px 线宽**，以及适中的绿色 `#69BE7A`、黄色 `#D4B953`、紫色 `#A391BF`。稀疏密度在避让前最多 **35 个标签**，**星座连线默认关闭**、启用强度 55；默认没有厚描边、光晕或中心实心点。
- 可选空心圆或四角框，并保护星体中心净空；颜色、字重、字号、不透明度、线宽、对比度和密度均可调。
- 可从目录单独选中暗目标。新加入的无俗名 LDN 暗星云不会仅因面积较大就在初始照片上显示，需通过更深目录设置或选择显示。

### RAW 与原尺寸导出

- 使用 rawpy/LibRaw 解析受支持的 ARW、CR2/CR3、NEF、DNG、RAF、ORF、RW2 等相机 RAW，按有效成像区域全分辨率显影，只应用一次方向校正。
- RAW 标注结果导出为 **16 位 TIFF**，原始 RAW 保持不变。不能把文字叠加进原始传感器马赛克后，仍保存为未改动的相机 RAW。
- JPG/JPEG、PNG 和受支持的单帧 TIFF 保留校正方向后的原始像素尺寸、容器和支持的位深。彩色标注把灰度转换为同位深 RGB。
- 修改样式后在本地后端复用已解算坐标，从保留的原件重新合成；无需再次星图解算，也不从浏览器缩小预览画布导出。
- 原尺寸图像任务串行执行，转换和合成按条带处理；超大图仍需要一定内存。
- **保留原始像素尺寸，不保证文件字节大小相同**。添加标注和 JPEG 重新压缩会改变文件大小。

### 真实照片验证

| 输入 | 保留的像素／格式 | 视场内暗于 V=7 的目录星 | 完整流程 |
|---|---|---:|---:|
| 用户原始 28 mm 照片 | 9504 × 6336 / JPEG | 7,281 | 9.186 秒 |
| 用户原始 70 mm 照片 | 9504 × 6336 / JPEG | 1,385 | 4.479 秒 |
| 公开猎户座照片 | 5218 × 3485 / JPEG | 1,035 | 2.246 秒 |
| 公开天鹅座照片 | 4428 × 3452 / JPEG | 1,149 | 2.146 秒 |

两张原片的中心坐标和视场完全复现已有结果；公开照片与历史舍入值的差异小于 0.0000005 度。耗时是本机实测，不是跨设备保证。自动化覆盖目录编号与星等、星核保护、原位深样本、导出一致性、进度及取消。

真实 Nikon D3S NEF 已解码成 **4284 × 2844、uint16 RGB**，并读取焦距、曝光和时间。这验证 RAW 解码／导出路径，**不代表这张极光照片成功完成星图解算**。详见[验证记录](VALIDATION_1.2.0.md)和 [RAW 说明](RAW_AND_EXPORT.md)。

### 保留功能与边界

继续支持本地 tetra3 盲解、可选 EXIF、拖入／粘贴、真实进度、取消／重试、第一人称内视天球、真实 WCS 视场、DSS2／Legacy／2MASS 巡天图层及 NASA 离线资料。

投影证据标记为 `catalog_position`、`pixelDetected: false`，不证明照片实际拍到了暗目标。HYG 暗端到 V=21 不等于完整覆盖至该星等。坐标保留 J2000 历元／分点，不按假定日期传播高自行恒星。LDN 等面积圆是近似尺寸参考，不是实测轮廓。RAW 型号支持由 LibRaw 决定；极窄视场、真实鱼眼、厚云、严重星轨仍有解算限制。

### 下载

- `Starfield-Atlas-Windows-x64-v1.2.0.zip`：完整解压后运行 `星图寻迹.exe`。
- `SHA256SUMS.txt`：发布资产的校验和。

需要 Windows 10/11 x64 与 Microsoft Edge WebView2 Runtime。应用代码为 GPL-3.0-only，目录、图片和依赖保留各自条款，详见[第三方通知](../THIRD_PARTY_NOTICES.md)及随包许可文件。

---

## 日本語

1.2.0 は暗い天体のカタログを拡充し、コンパクトな写真解析ワークベンチと元解像度からの注釈書き出しを提供します。

### カタログの拡充

- HYG v4.1 全体から **119,625 星**を収録し、うち **104,027 星は V=7 より暗い**恒星です。写真の検索制限は既定で V=12。明るい星を十数個だけ返す制限をなくし、HIP/HD/HYG の検索・選択と **2,253 件の中国語星名**を維持しました。
- 更新版 Lynds 暗黒星雲、CDS VII/7A の全 **1,791 件**を追加。雲の中心、面積、不透明度、関連 Barnard 番号を保持します。
- 実行時の投影可能記録は計 **15,162 件**、うち **1,793 件は暗黒星雲**です。790 件は歴史的 OpenNGC 恒星／二重星記録であり、15,162 個の異なる銀河・星雲という意味ではありません。
- 恒星方向ベクトルをキャッシュし、天域を絞ってから投影。全一覧と初期注釈密度を分離しました。
- **深空カタログ**選択は返す一覧を実際に絞り込みます。常用は既知等級 ≤10 または表示推奨の通称／メシエ天体、拡張は等級 ≤15 または同じ具名の推奨対象、既定の完全カタログは通称のない LDN・等級不明を含む視野内の全記録です。恒星の V=12 制限は独立しています。
- IC 434 を馬頭星雲の背後にある発光領域として表示するよう訂正。NGC 2024 は燃える木星雲、Barnard 33 は馬頭星雲として区別します。元 CSV とチェックサムを保持し、NASA/ESA の出典を記録しています。

### ワークベンチと注釈

- 写真中心の簡潔なツールバー、検索・ページ切り替え付き一覧、等級フィルター、座標、天体選択。
- 画面に合わせる表示、表示画像の 100% ピクセル倍率（縮小 RAW/TIFF プレビューは明示し、書き出しは元解像度を維持）、ポインターを中心とするズーム、パン、元画像／注釈切り替え。`Ctrl+O`、`Ctrl+S`、`0`、`1`、`H`、`+`/`−`、解析中の `Esc` に対応します。
- 初期状態は **不透明度 85%**、通常の太さ、画像幅 1920 px あたり **文字 18 px・線幅 1.25 px**、適度な緑 `#69BE7A`・黄 `#D4B953`・紫 `#A391BF`。疎な密度は衝突処理前で最大 **35 ラベル**、**星座線はオフ**、オン時の強度は 55。既定では太い縁取り・発光・中心の塗りつぶし点を使いません。
- 中空円またはコーナー枠で星像中心を保護。色、文字の太さとサイズ、不透明度、線幅、コントラスト、密度を調整できます。
- 暗い対象を一覧から個別選択できます。追加した通称のない LDN 雲は、大きいという理由だけで初期写真に描かず、深いカタログ設定や選択で表示します。

### RAW と元解像度出力

- rawpy/LibRaw により対応カメラの ARW、CR2/CR3、NEF、DNG、RAF、ORF、RW2 などをデコード。有効画像領域を全解像度で現像し、向きを一度補正します。
- 注釈付き RAW は **16-bit TIFF** に書き出し、元の RAW は保持します。センサーモザイクに文字を加えて、未変更のカメラ RAW のまま保存することはできません。
- JPG/JPEG、PNG、対応する単一フレーム TIFF は、向き補正後の元画素寸法、コンテナ、対応ビット深度を維持。カラー注釈はグレースケールを同ビット深度の RGB に変換します。
- スタイル変更ではローカル側で保存済み原画像と解決済み座標を再利用。再ソルブや縮小プレビューキャンバスからの書き出しを行いません。
- 元寸法処理を直列化し、変換と合成を帯状領域ごとに実行します。大画像では引き続き相応のメモリが必要です。
- **元の画素寸法は維持しますが、ファイルのバイト数は同じになりません**。注釈や JPEG 再圧縮でサイズが変わります。

### 実写真での検証

| 入力 | 維持した画素／形式 | 視野内の V=7 より暗いカタログ星 | 全処理 |
|---|---|---:|---:|
| 元の 28 mm 写真 | 9504 × 6336 / JPEG | 7,281 | 9.186 秒 |
| 元の 70 mm 写真 | 9504 × 6336 / JPEG | 1,385 | 4.479 秒 |
| 公開 Orion 写真 | 5218 × 3485 / JPEG | 1,035 | 2.246 秒 |
| 公開 Cygnus 写真 | 4428 × 3452 / JPEG | 1,149 | 2.146 秒 |

原画像 2 枚の中心と視野は既存の解と完全に一致し、公開写真は丸め済みの過去の値と 0.0000005 度未満で一致しました。時間はローカル測定値です。自動テストは識別子・等級、星像中心保護、元ビット深度の画素、出力の一貫性、進捗・キャンセルを対象にします。

実際の Nikon D3S NEF を **4284 × 2844 uint16 RGB** にデコードし、焦点距離・露出・時刻を読み取りました。これは RAW デコード／出力の検証であり、**そのオーロラ写真のプレートソルブ成功を意味しません**。[検証記録](VALIDATION_1.2.0.md)と [RAW 詳細](RAW_AND_EXPORT.md)を参照してください。

### 継続機能と制限

ローカル tetra3 ソルブ、任意の EXIF、ドロップ／貼り付け、実進捗、キャンセル／再試行、一人称天球、WCS 写真視野、DSS2／Legacy／2MASS、NASA オフラインガイドを維持しています。

投影は `catalog_position` と `pixelDetected: false` を示し、暗い天体が写真に写っている証明ではありません。HYG の暗い端が V=21 に達しても、その等級まで完全ではありません。座標は J2000 の元期・分点を保持し、仮定した日時へ固有運動を補正しません。LDN の等面積円は概略の大きさであり、実測の輪郭ではありません。RAW は LibRaw の対応カメラに依存し、極狭視野・魚眼・厚雲・強い星の流れには制限があります。

### ダウンロード

- `Starfield-Atlas-Windows-x64-v1.2.0.zip`：完全に展開し、`星图寻迹.exe` を実行します。
- `SHA256SUMS.txt`：リリースアセットのチェックサム。

Windows 10/11 x64 と Microsoft Edge WebView2 Runtime が必要です。アプリコードは GPL-3.0-only。カタログ、画像、ライブラリにはそれぞれの条件が適用されます。[第三者通知](../THIRD_PARTY_NOTICES.md)と同梱ライセンスを参照してください。
