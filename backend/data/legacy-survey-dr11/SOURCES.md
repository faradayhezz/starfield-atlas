# DESI Legacy Imaging Surveys DR11 内置星图

本目录保存“星图寻迹”使用的 DESI Legacy Imaging Surveys Data Release 11（DR11）低层级 JPEG 瓦片。它们来自项目官方 Sky Viewer 的公开瓦片接口，不是模拟图或 AI 生成图。

## 官方来源

- Berkeley Lab 发布说明：<https://newscenter.lbl.gov/2026/08/10/scientists-release-biggest-2d-map-of-the-universe/>
- DR11 数据说明：<https://www.legacysurvey.org/dr11/description/>
- DR11 数据文件：<https://www.legacysurvey.org/dr11/files/>
- 官方交互查看器：<https://www.legacysurvey.org/viewer?layer=ls-dr11>
- 图像使用和署名说明：<https://www.legacysurvey.org/acknowledgment/>

## 内置范围

完整 DR11 是由约 5.6 万亿像素组成的瓦片化数据产品，而不是一张单体“原图”。应用下载并内置 Web Mercator 层级 0–5，足以在全景和普通相机广角视场下离线定位。更高层级可以在用户主动开启“官方高清”后从同一官方瓦片服务读取，并只缓存在本机。

瓦片坐标沿用官方查看器：地图经度为 `180° - RA`，纬度为 `Dec`。每次更新由 `scripts/download_legacy_survey_tiles.py` 生成 `manifest.json`，记录每个文件的 SHA-256、字节数和数据来源。

## 授权与署名

Legacy Surveys 图层按 CC BY 4.0 发布。应用内始终显示官方要求的原文署名：

> Legacy Surveys / D. Lang (Perimeter Institute)

数据空白区表示 DR11 没有覆盖，不应解释为该天区没有天体。
