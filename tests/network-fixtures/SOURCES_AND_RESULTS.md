# 网络真实星空照片测试记录

测试日期：2026-08-30（Asia/Shanghai）

这些照片来自 Wikimedia Commons，均为真实相机拍摄/堆栈的宽场星空照片，不是 AI 生成图。测试使用项目当前的本地 `backend.pipeline.analyze_image` 完整流程：读取图片、盲解星图、查询离线目录、生成预览与全尺寸标注、输出 JSON。没有向解算器提供人工 RA/Dec。

## 1. 猎户座 50 mm 宽场

- 本地文件：`wikimedia_orion_wide_field_50mm.jpg`
- Wikimedia 文件页：<https://commons.wikimedia.org/wiki/File:Orion_wide_field.jpg>
- 原始文件直链：<https://upload.wikimedia.org/wikipedia/commons/a/a9/Orion_wide_field.jpg>
- 作者：Martinbernardi
- 拍摄日期：2024-12-24（文件页）；图像内嵌处理元数据另记载观测开始于 2024-12-25 09:39:26 UTC
- 授权：Creative Commons Attribution 4.0 International（CC BY 4.0）
- 授权页：<https://creativecommons.org/licenses/by/4.0/>
- 原始尺寸：5218 × 3485，11,970,605 bytes
- SHA-256：`80E7D9EA56C9271198DB38B49934F37EF6E7FE05868E0452596B8FD78EA89029`
- 器材/曝光（文件页）：Sony a6100；Sony E 50 mm f/1.8 OSS（约 75 mm 等效）；Sky-Watcher Star Adventurer；约 278 × 30 s；ISO 800；f/2.4；Siril 堆栈、Darktable 后期。

### 当前应用实测

- 结果：成功，`tetra3-full-frame`
- 完整流程耗时：1.593 s；其中盲解 619 ms
- 解算中心：RA 84.416267°，Dec −1.132724°
- 视场：23.189937° × 15.605858°
- 匹配星：22
- RMSE：32.335 arcsec
- 假阳性概率：9.5944 × 10⁻²⁷
- 目录统计：OpenNGC 63 条；预计画面可见 8 条；亮星 12；星座 2
- 预计可见目标：M42、M43、M78、IC 434、NGC 1909、NGC 2024、NGC 1977、B 33
- 本地结果目录（不纳入 Git）：`results/orion/`

文件页 JPEG 的“Image title”仍保留早期 FITS/WCS 处理记录，其中给出原始堆栈中心 RA 84.6034°、Dec −1.34114°，且给出 49.722 mm 焦距。当前下载文件已由原 6024 × 4024 裁成 5218 × 3485；独立盲解所得天区、视场和猎户座目标位置与该记录一致。

## 2. 天鹅座 50 mm 宽场

- 本地文件：`wikimedia_cygnus_wide_field_50mm.jpg`
- Wikimedia 文件页：<https://commons.wikimedia.org/wiki/File:Wide_Field_in_Cygnus_(Giuseppe_Donatiello).jpg>
- 原始文件直链：<https://upload.wikimedia.org/wikipedia/commons/d/dd/Wide_Field_in_Cygnus_%28Giuseppe_Donatiello%29.jpg>
- 原始发布页：<https://www.flickr.com/photos/133259498@N05/55459910617/>
- 作者：Giuseppe Donatiello；文件说明同时署名 Giuseppe Donatiello 与 Giovanni Vincenzo Donatiello
- 拍摄日期：2026-08-12 22:38:12
- 授权：Creative Commons CC0 1.0 Universal Public Domain Dedication
- 授权页：<https://creativecommons.org/publicdomain/zero/1.0/>
- 原始尺寸：4428 × 3452，21,369,478 bytes
- SHA-256：`3E810C2C10F34073F4202304FBF23DBD4F7F983D4E629E03E67834E327FF0240`
- 器材/曝光（文件页）：Canon EOS 4000D；Canon EF 50 mm f/1.8，收至 f/4；总曝光 1200 s；ISO 3200。
- 相机地点（文件页）：39.941709° N，16.145535° E。

### 当前应用实测

- 结果：成功，`tetra3-full-frame`
- 完整流程耗时：1.510 s；其中盲解 605 ms
- 解算中心：RA 310.163882°，Dec +44.989014°
- 视场：20.989249° × 16.434753°
- 匹配星：16
- RMSE：68.721 arcsec
- 假阳性概率：5.2235 × 10⁻¹⁴
- 目录统计：OpenNGC 43 条；预计画面可见 7 条；亮星 11；星座 1
- 预计可见目标：M39、M29、NGC 7000、IC 5070、NGC 6888、IC 5068、NGC 6991
- 本地结果目录（不纳入 Git）：`results/cygnus/`

输出图经过人工目视检查：北美洲星云、鹈鹕星云、新月星云、M29 与天鹅座线框均落在对应的真实图像结构/星点位置上，没有发现整体镜像、90° 旋转或明显平移错误。

## 3. 仙后座 50 mm 宽场

- 本地文件：`wikimedia_cassiopeia_20210115_cc-by-sa4.jpg`
- Wikimedia 文件页：<https://commons.wikimedia.org/wiki/File:Cassiopeia_20210115.jpg>
- 原始文件直链：<https://upload.wikimedia.org/wikipedia/commons/1/1c/Cassiopeia_20210115.jpg>
- 作者：BreakdownDiode
- 拍摄日期：2021-01-15 23:02:24
- 授权：Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）
- 原始尺寸：5472 × 3648，2,064,543 bytes
- SHA-256：`AFE2581224B0D3663AC25368D17DC88BA8E6D0DB2AE31E1C5F9F67176E94EA1B`
- EXIF：Canon EOS 6D；50 mm；890 s；f/2.8；ISO 1000。

### 当前应用实测

- 结果：成功，`tetra3-central-crop`
- 完整流程耗时：16.724 s；其中盲解 15.917 s
- 解算中心：RA 14.745061°，Dec +60.401122°
- 视场：38.605807° × 26.286295°
- 匹配星：16
- RMSE：21.222 arcsec
- 假阳性概率：5.2235 × 10⁻¹⁴
- 目录统计：OpenNGC 92 条；预计画面可见 16 条；亮星 12；星座 5
- 预计可见目标包括：M31、M76、M110、M52、M103、IC 1805、IC 1848、NGC 869/884、NGC 457、NGC 7635、NGC 281 和 NGC 7822
- 本地结果目录（不纳入 Git）：`results/cassiopeia/`

标注预览经过人工检查：仙后座 W 形、M52、M103、NGC 281、NGC 457、心脏/灵魂星云与双星团均落在正确天区，未见整体偏移或镜像。

## 4. 带地景的银河高 ISO 压力测试（预期保留失败）

- 本地文件：`wikimedia_milky_way_israel_cc0.jpeg`
- Wikimedia 文件页：<https://commons.wikimedia.org/wiki/File:The_Milky_Way_In_Israel_(217459071).jpeg>
- 原始文件直链：<https://upload.wikimedia.org/wikipedia/commons/a/af/The_Milky_Way_In_Israel_%28217459071%29.jpeg>
- 作者：Tom Nipravsky
- 拍摄日期：2017-06-24 03:49:19
- 授权：CC0 1.0 Universal Public Domain Dedication
- 原始尺寸：1778 × 2048，1,267,513 bytes
- SHA-256：`92248F2BDC554B5C362DC99DF29EED6BE88A04D64557B20428E2F6FE0CEA9500`
- EXIF：Nikon D5500；35 mm（35 mm 等效 52 mm）；10 s；f/1.8；ISO 6400。

### 当前应用实测

- 结果：未得到满足可靠性门限的解，应用正确返回失败，没有输出伪造坐标或目录标注。
- 已尝试中央 1209 px 分块和 4 套星点提取参数，约 30 s 后停止。
- 画面包含银河核心极高密星场、显著色彩/亮度渐变、薄云与底部地景；中央分块恰落在银河最密区域，当前星点提取没有形成可靠四星模式。
- 这个样本保留为回归压力测试，说明“照片中肉眼能看到大量星点”并不保证当前解算器一定成功。

## 复现

机器可读完整结果在本地生成并保存在忽略的目录：

- `results/orion/results.json`
- `results/cygnus/results.json`
- `results/cassiopeia/results.json`

相应的 `original-preview.jpg`、`annotated-preview.jpg` 和 `annotated-full.jpg` 在同目录生成，但不纳入 Git。首页使用的压缩公开预览位于 [`docs/images`](../../docs/images/)，以控制仓库体积并避免提交重复产物。
