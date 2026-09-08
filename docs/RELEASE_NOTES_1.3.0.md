# Starfield Atlas / 星图寻迹 1.3.0

[English](#english) · [简体中文](#简体中文) · [日本語](#日本語)

![NASA imagery in the real Orion workbench](images/workbench-1.3.0-nasa.jpg)

![Expanded stellar catalogue in the public Orion photograph](images/workbench-1.3.0-stars.jpg)

## English

Version 1.3.0 expands the catalogue to **2,552,824 real stars**, makes faint
markers thinner without covering neighbouring objects, and brings NASA images
into the visible catalogue workflow.

### Stars and annotations

- Retains **119,625 HYG v4.1 stars**, adds **2,433,199 AT-HYG v3.2 / Tycho-2
  stars**, and preserves all **2,253 Chinese names**. Additional stars have
  TYC identifiers; only the Sun and explicit source HYG duplicates are excluded.
  Nearby physical components are not merged by coordinate proximity.
- **432 offline spatial cells, 49.8 MB total**, with a bounded cache. The
  default magnitude limit is **12**, retaining each record's **V or VT band**.
  Tycho-2 is approximately 90% complete at V≈11.5; neither its faintest entry
  nor HYG's sparse V=21 tail is an image-detection or completeness limit.
- Independent stellar label budgets: **20 / 60 / 180, default 60**. Deep-sky
  budgets: **35 / 90 / 180, default 35**. Collision handling may show fewer
  labels; the full searchable inventory is retained. Old few-bright-star flags
  no longer limit stellar label selection.
- Removes dark underlays from hollow circles and corner brackets, including
  high-contrast mode. No filled centre point or marker glow is added.
- Compact faint deep-sky objects and stars of magnitude 7 or fainter default
  to **0.6× base line width**, adjustable independently. Labels avoid complete
  marker disks; crowded labels may use thin leaders from the outline.
- Keeps moderate green/yellow/purple, 85% opacity, normal-weight 18 px text and
  1.25 px base lines per 1920 px image width. High contrast strengthens text
  only. Preview and original-resolution export share these rules.

### Wide phone photographs without EXIF

The no-EXIF search now tries a 32% central probe and interleaves scales before
using slower extraction fallbacks. The actual 4032 × 3024 phone photograph
blind-solved 22 stars, then validated 106 full-field anchors, including 26 held
out of calibration and 16 held-out stars outside the crop. Global RMS was
2.60 original pixels; the false-positive score remained 9.59 × 10⁻²⁷.
Its camera metadata was genuinely absent and no reference coordinates were
used as solver hints. Native JPEG dimensions were preserved. The star-derived
TAN field is 69.9711° × 55.6036°; a reference screenshot is only a coarse check,
not a calibration target. Existing hinted DSLR and ESA-fixture paths remain
unchanged. See [full phone verification](PHONE_WIDE_FIELD_1.3.0.md).

### NASA images beside the catalogue

- A visible thumbnail column and selected-object detail **above the table**
  show images, descriptions, credits and source links while browsing.
- Keeps **39 mapped objects / 37 unique official NASA observation images**;
  adds **68 offline NASA SkyView DSS2 Red cutouts** centred on exact catalogue
  coordinates. Dedicated object imagery and surrounding survey cutouts are
  explicitly distinguished.
- Survey credits: **STScI / Palomar Observatory / AAO**, delivered by **NASA
  GSFC SkyView**, with provider and original-source links retained.
- Missing cutouts for other eligible targets load on demand, with at most
  **three concurrent requests**, local caching and a photo-crop fallback.
  This is not a promise of dedicated NASA portraits or offline imagery for
  every NGC/IC entry.
- Photos stay local. SkyView requests contain the target's **public catalogue
  coordinates and field size**, not image bytes or camera metadata. Missing
  sky-view tiles retain their existing on-demand network behaviour. NASA has
  not endorsed this application.

### Real-photo verification and download

| Real input | In-field stars | Full source pipeline | Native JPEG export |
| --- | ---: | ---: | --- |
| Private 28 mm wide field | 160,076 | 12.587 s | 9504 × 6336 |
| Private galaxy-group field | 8,331 | 5.868 s | 9504 × 6336 |
| Public Orion photograph | 18,059 | 2.509 s | 5218 × 3485 |
| Private wide phone photograph, no EXIF | 266,351 | 9.096 s | 4032 × 3024 |

Fresh-process measurements include solving, catalogue projection, preview,
native export and complete JSON writing, excluding browser/network time.
Large JSON responses support gzip transfer, and the table uses pagination;
complete wide-field inventories still need memory. See
[source provenance, memory measurements and checks](STELLAR_CATALOG_1.3.0.md).

RAW decoding and 16-bit TIFF output, native JPG/PNG/TIFF dimensions and supported
bit depths, progress, cancellation/retry, first-person sky and photo footprints
remain available. The [1.2.1 drag/MPO fixes](RELEASE_NOTES_1.2.1.md) are retained.
Results remain `catalog_position` with `pixelDetected: false`: extra catalogue
entries are not a claim of more independently verified pixel detections.

Download **`Starfield-Atlas-Windows-x64-v1.3.0.zip`**, extract completely, close
the older app, then run `星图寻迹.exe`. Windows 10/11 x64 and WebView2 are
required. The release includes `SHA256SUMS.txt`. Application code is
GPL-3.0-only; catalogues and imagery keep their separate source terms.

Sources: [official NASA media](../backend/data/nasa-deep-sky/SOURCES.md),
[SkyView/DSS2 cutouts](../backend/data/nasa-survey-cutouts/SOURCES.md),
[AT-HYG attribution](../backend/data/LICENSES/ATHYG-CC-BY-SA-4.0.md).

---

## 简体中文

1.3.0 将目录扩充到 **2,552,824 颗真实恒星**，让暗弱标记更细、圆圈交叠时背景仍然
可见，并把 NASA 图片直接放进目录浏览流程。

### 恒星与标注

- 保留 **119,625 颗 HYG v4.1 恒星**，新增 **2,433,199 颗 AT-HYG v3.2／Tycho-2
  恒星**，保留全部 **2,253 个中文星名**。新增星带有 TYC 编号，只剔除太阳及来源
  明确给出的 HYG 重复编号，不按位置接近合并不同恒星分量。
- **432 个离线空间分片合计 49.8 MB**，按相关天区读取并限制缓存。默认上限
  **12 等**，逐条保留 **V／VT 波段**。Tycho-2 在 V≈11.5 处约有 90% 完备性；
  最暗记录和 HYG 的稀疏 V=21 暗端都不代表完整覆盖深度或照片检测极限。
- 恒星标注独立为 **20／60／180 个、默认 60**；深空为 **35／90／180 个、默认
  35**。实际显示还要经过避让，不截断完整可搜索清单。旧版少量亮星的推荐标志
  不再限制恒星标签选取。
- 移除空心圆／四角框周围的深色底线，高对比模式也不再覆盖背景或相邻圆弧。
  不添加中心实心点和标记光晕。
- 紧凑暗弱深空天体及 7 等或更暗恒星默认采用 **0.6 倍基础线宽**，比例可独立调节。
  文字避开完整标记圆盘，拥挤处可从轮廓到标签绘制细引线。
- 保留适中的绿／黄／紫、85% 不透明度、普通字重，每 1920 像素图宽对应 18 px
  文字和 1.25 px 基础线宽。高对比只增强文字；预览与原尺寸导出使用同一套规则。

### 无 EXIF 的手机宽场照片

无 EXIF 搜索新增 32% 中央区域，并先轮流尝试不同尺度，再进入较慢的提取回退。
真实 4032 × 3024 手机照片盲匹配 22 个星点，随后验证 106 个全画面锚点，其中
26 个不参与拟合、16 个位于原裁切区外。全画面 RMS 为原图 2.60 px，假阳性评分
仍为 9.59 × 10⁻²⁷。原文件确实没有相机元数据，没有把参考坐标用于解算提示；
JPEG 原像素尺寸保留。星点几何求得 TAN 视场 69.9711° × 55.6036°，参考截图
仅做粗略核对，不作为强制校准目标。已有 DSLR 焦距提示路径及 ESA 样片回归保持
不变。详见[手机完整验证](PHONE_WIDE_FIELD_1.3.0.md)。

### 在目录旁查看 NASA 图片

- 增加可见缩略图列，选中目标的图文详情放在**表格上方**，浏览时直接看到图片、
  简介、署名及来源链接。
- 保留 **39 个天体映射／37 张唯一 NASA 官方观测图**；另内置 **68 张 NASA
  SkyView DSS2 Red 巡天配图**，均按目录精确坐标截取。目标专门观测素材与周围
  天区的巡天图明确区分。
- 原巡天署名归 **STScI／Palomar Observatory／AAO**，由 **NASA GSFC SkyView**
  提供裁切服务；保留服务商与原始出处链接。
- 其他符合条件的目标按需读取缺失配图，同时最多 **3 个请求**，保存本地缓存，
  不可用时回退到照片裁切。不保证每个 NGC／IC 条目都有 NASA 专门摄影，也不代表
  所有目标已离线收齐。
- 照片留在本地。SkyView 请求只包含目标的**公开目录坐标和视场大小**，不发送
  用户照片字节或相机元数据。天球仍按需请求未缓存瓦片，NASA 未背书本应用。

### 真实照片验证与下载

| 真实输入 | 视场内恒星 | 源码完整流程 | 原尺寸 JPEG 导出 |
| --- | ---: | ---: | --- |
| 私人 28 mm 宽场照片 | 160,076 | 12.587 秒 | 9504 × 6336 |
| 私人星系群照片 | 8,331 | 5.868 秒 | 9504 × 6336 |
| 公开猎户座照片 | 18,059 | 2.509 秒 | 5218 × 3485 |
| 无 EXIF 的私人手机宽场照片 | 266,351 | 9.096 秒 | 4032 × 3024 |

每次为新进程，包含解算、目录投影、预览、原尺寸导出和完整 JSON 写入，不含浏览器／
网络耗时。大 JSON 支持 gzip 传输，目录按页显示；完整宽场清单仍需相应内存。
详见[来源、内存实测与校验](STELLAR_CATALOG_1.3.0.md)。

继续支持 RAW 解析与 16 位 TIFF 标注输出、JPG／PNG／TIFF 原尺寸及支持的位深、
真实进度、取消／重试、内视天球与照片视场，并保留 [1.2.1 拖放／MPO 修复](RELEASE_NOTES_1.2.1.md)。
结果仍为 `catalog_position`、`pixelDetected: false`；增加目录条目不等于已经从
像素验证检测到了这些暗星。

下载 **`Starfield-Atlas-Windows-x64-v1.3.0.zip`**，完整解压，关闭旧版后运行
`星图寻迹.exe`。需要 Windows 10／11 x64 与 WebView2，发布附带 `SHA256SUMS.txt`。
应用代码为 GPL-3.0-only，目录和图片继续适用各自来源条款。

来源：[NASA 官方素材](../backend/data/nasa-deep-sky/SOURCES.md)、
[SkyView／DSS2 巡天图](../backend/data/nasa-survey-cutouts/SOURCES.md)、
[AT-HYG 署名与许可](../backend/data/LICENSES/ATHYG-CC-BY-SA-4.0.md)。

---

## 日本語

1.3.0 はカタログを **2,552,824 個の実在する恒星**へ拡張し、暗い対象のマーカーを
細くして隣の円や星像を隠さないようにしました。NASA 画像も一覧から直接確認できます。

### 恒星と注釈

- **HYG v4.1 の 119,625 星**を保持し、**AT-HYG v3.2／Tycho-2 の 2,433,199 星**
  を追加。**2,253 件の中国語星名**を保持し、追加恒星には TYC ID を表示します。
  太陽と出典が明示する HYG 重複だけを除外し、近い別々の恒星成分は統合しません。
- **432 個のオフライン空間セル、合計 49.8 MB**。必要な天域だけを読み込み、
  キャッシュを制限します。等級上限の既定は **12**、各記録の **V／VT バンド**を
  明示します。Tycho-2 は V≈11.5 で約 90% 完全ですが、最暗記録や HYG の疎な
  V=21 の端は、完全な収録深度や写真の検出限界を示しません。
- 恒星ラベルは **20／60／180 個、既定 60**、深宇宙天体は **35／90／180 個、
  既定 35**。衝突回避で表示数が減ることはありますが、全一覧を切り詰めません。
  旧版の少数の明るい星の推奨フラグも、恒星選択を制限しません。
- 中空円／コーナー枠の暗い下地を除去し、高コントラスト時も隣の円弧や背景を
  隠しません。中心の塗りつぶし点やマーカーの光彩はありません。
- コンパクトで暗い深宇宙天体と 7 等以上の暗い恒星は、既定で線幅を **0.6 倍**に
  します。比率は独立調整可能。文字は円盤全体を避け、混雑時は輪郭から文字へ
  細い引出線を使えます。
- 適度な緑／黄／紫、不透明度 85%、画像幅 1920 px あたり通常ウェイトの文字
  18 px・基本線幅 1.25 px を維持。高コントラストは文字だけに作用し、
  プレビューと元解像度出力で同じ規則を使います。

### EXIF のない広角スマートフォン写真

EXIF なしの検索へ 32% の中央領域を追加し、抽出条件の追加試行より先に各尺度を
試します。実際の 4032 × 3024 写真は 22 星でブラインド解を得た後、106 星を
画面全域で検証しました。26 星は較正に使わず、うち 16 星は元の中央領域の外側
です。全体残差は原画素で RMS 2.60 px、偽陽性スコアは 9.59 × 10⁻²⁷。
元ファイルに撮影情報はなく、参考座標を解決ヒントには使いません。JPEG の元寸法を
保持し、星の幾何から求めた TAN 視野は 69.9711° × 55.6036° です。参考画面は
粗い照合だけに使い、較正値を強制しません。既存の DSLR 焦点情報付き処理と ESA
実画像の結果は維持します。[スマートフォン検証](PHONE_WIDE_FIELD_1.3.0.md)を参照。

### 一覧から見られる NASA 画像

- サムネイル列を追加し、選択天体の詳細を**表の上**へ配置しました。画像、解説、
  クレジット、出典リンクを確認しながら対象を選べます。
- **39 天体対応／37 枚の NASA 公式観測画像**を保持し、正確なカタログ座標を
  中心とする **NASA SkyView DSS2 Red サーベイ画像 68 枚**を同梱します。
  専用観測素材と周囲の天域を示すサーベイ配図は明示的に区別します。
- 原サーベイは **STScI／Palomar Observatory／AAO**、配信は **NASA GSFC
  SkyView**で、提供元と原典リンクを保持します。
- 他の対応対象は必要時に取得してキャッシュし、同時リクエストは最大 **3 件**。
  利用不可ならユーザー写真のクロップを表示します。すべての NGC／IC 記録に
  専用 NASA 写真やオフライン画像があるとは保証しません。
- 写真はローカルに保持。SkyView へは対象の**公開カタログ座標と視野サイズ**だけを
  送り、ユーザー写真や撮影メタデータは送信しません。未取得の天球タイルは従来どおり
  必要時に取得します。NASA による推奨を意味しません。

### 実測とダウンロード

| 実際の入力 | 視野内恒星 | ソース版の全処理 | 元寸法の JPEG 出力 |
| --- | ---: | ---: | --- |
| 非公開 28 mm 広角写真 | 160,076 | 12.587 秒 | 9504 × 6336 |
| 非公開の銀河群写真 | 8,331 | 5.868 秒 | 9504 × 6336 |
| 公開 Orion 写真 | 18,059 | 2.509 秒 | 5218 × 3485 |
| EXIF のない非公開スマートフォン写真 | 266,351 | 9.096 秒 | 4032 × 3024 |

各実測は新規プロセスでの解析、全カタログ投影、プレビュー、元寸法出力、JSON 保存を
含み、ブラウザー／ネットワーク時間を除きます。大きな JSON は gzip 転送、一覧は
ページ表示に対応しますが、広角の全一覧には相応のメモリが必要です。
[出典・メモリ実測・検証](STELLAR_CATALOG_1.3.0.md)を参照してください。

RAW 解析と 16-bit TIFF 出力、JPG／PNG／TIFF の元寸法と対応ビット深度、実進捗、
キャンセル／再試行、一人称天球と写真視野を継続し、[1.2.1 のドラッグ／MPO 修正](RELEASE_NOTES_1.2.1.md)
も保持します。根拠は `catalog_position`、`pixelDetected: false` のままで、
カタログ追加は実画像からの検出を保証しません。

**`Starfield-Atlas-Windows-x64-v1.3.0.zip`** を完全に展開し、旧版を閉じてから
`星图寻迹.exe` を実行します。Windows 10／11 x64 と WebView2 が必要です。
`SHA256SUMS.txt` を同梱します。アプリコードは GPL-3.0-only、カタログと画像には
各出典の独立した条件が適用されます。

出典：[NASA 公式素材](../backend/data/nasa-deep-sky/SOURCES.md)、
[SkyView／DSS2](../backend/data/nasa-survey-cutouts/SOURCES.md)、
[AT-HYG 帰属表示](../backend/data/LICENSES/ATHYG-CC-BY-SA-4.0.md)。
