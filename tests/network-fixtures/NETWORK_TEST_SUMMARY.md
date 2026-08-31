# 网络真实星空照片识别测试汇总

测试日期：2026-08-30（Asia/Shanghai）

所有输入均从可追溯的公开网页下载，为真实相机照片或真实照片堆栈；没有使用 AI 生成星图、天文软件截图或程序合成星场。解算前没有向应用提供 RA/Dec。

| 样本 | 来源/类型 | 结果 | 视场 | 匹配星 / RMSE | OpenNGC / 预计可见 |
| --- | --- | --- | --- | --- | --- |
| Orion wide field | Wikimedia，Sony a6100，50 mm（等效约 75 mm） | 成功，1.59 s | 23.19° × 15.61° | 22 / 32.3″ | 63 / 8 |
| Wide Field in Cygnus | Wikimedia，Canon EOS 4000D，50 mm | 成功，1.51 s | 20.99° × 16.43° | 16 / 68.7″ | 43 / 7 |
| Cassiopeia 20210115 | Wikimedia，Canon EOS 6D，50 mm | 成功，16.72 s | 38.61° × 26.29° | 16 / 21.2″ | 92 / 16 |
| NASA ISS006-E-28028 | NASA 宇航员南十字座/船底座照片 | 成功，13.93 s | 23.01° × 15.85° | 14 / 45.0″ | 59 / 8 |
| The Milky Way in Israel | Wikimedia，Nikon D5500，35 mm，高 ISO、银河核心、薄云和地景 | **可靠性门限失败** | EXIF 估计约 40° 级 | 未输出伪解 | 无目录投影 |

## 成功样本的独立内容核对

- 猎户座：M42/M43、M78、IC 434、NGC 2024、NGC 1977 与马头星云区域落点正确。
- 天鹅座：M29、M39、北美洲星云、鹈鹕星云和新月星云落点正确。
- 仙后座：M52、M103、NGC 281、NGC 457、双星团、心脏/灵魂星云落点正确。
- NASA：NASA 原页面预先指明的 Southern Cross 与 Keyhole/Carina Nebula 和本地盲解结果一致，并同时落出煤袋、珠宝盒星团和 IC 2602。

## 保留失败样本的意义

银河压力样本在约 30 秒内尝试了中央分块和四套星点提取参数，仍未得到满足匹配数、残差和假阳性概率门限的解。应用返回明确失败，没有为了给出结果而接受伪解。该图将用于后续改进高密银河、强亮度渐变和带地景照片的分块策略。

## 详细来源与产物

- Wikimedia 三张成功样本与银河失败样本：[SOURCES_AND_RESULTS.md](SOURCES_AND_RESULTS.md)
- NASA 来源、权利说明和结果：[SOURCES.md](SOURCES.md)
- 猎户座标注预览：[../../docs/images/orion-annotated-public.jpg](../../docs/images/orion-annotated-public.jpg)
- 天鹅座标注预览：[../../docs/images/cygnus-annotated-public.jpg](../../docs/images/cygnus-annotated-public.jpg)
- NASA 标注预览：[../../docs/images/nasa-southern-cross-annotated-public.jpg](../../docs/images/nasa-southern-cross-annotated-public.jpg)
