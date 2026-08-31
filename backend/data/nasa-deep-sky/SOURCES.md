# NASA 深空天体离线资料包

本目录中的 WebP 是应用详情卡使用的离线预览图。每个文件都由 `scripts/download_nasa_deep_sky.py` 从 NASA 官方 HTTPS 地址下载并等比例缩放，未使用生成式图像，也未把搜索引擎缩略图当作原始素材。

完整的逐对象记录位于相邻的 `nasa_deep_sky.json`，包括：

- OpenNGC 规范目录 ID 与别名；
- NASA Image and Video Library 媒体编号（适用时）；
- NASA 原始页面与实际下载 URL；
- 图像署名、媒体中心和发布日期；
- 本地 WebP 的像素尺寸与 SHA-256；
- 由“星图寻迹”重新整理的简短中文事实说明。

## 选材规则

1. 只下载 `nasa.gov` 或其子域上的资源。
2. 优先使用 NASA Image and Video Library 的确定性媒体编号；库中没有独立条目时，使用 NASA Science 正式资源页的下载文件。
3. NASA 页面若把图像明确标记为第三方版权作品，则不纳入离线包。
4. 保留原始 credit，不使用 NASA 徽标，也不暗示 NASA 对本应用的认可。
5. 没有可靠素材的对象继续显示用户照片裁切，不使用相邻目标的图片冒充。

NASA 官方资料：

- [NASA Images and Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
- [NASA Image and Video Library API](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf)
- [NASA Image and Video Library](https://images.nasa.gov/)

NASA 内容通常可用于事实性、教育或信息用途，但 NASA 站点也可能展示第三方内容；实际使用应始终查看清单中的原始页面和 credit。NASA 是素材来源，不对“星图寻迹”生成的识别结果或中文文字负责。
