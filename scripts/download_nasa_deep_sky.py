from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "backend" / "data" / "nasa-deep-sky"
IMAGE_DIR = DATA_DIR / "images"
MANIFEST_PATH = ROOT / "backend" / "data" / "nasa_deep_sky.json"
NASA_API = "https://images-api.nasa.gov"
USAGE_URL = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
USER_AGENT = "StarTraceOfflineCatalog/1.0 (+local educational astronomy app)"
MAX_IMAGE_SIZE = (960, 720)


def library(
    catalog_id: str,
    aliases: list[str],
    title_zh: str,
    title_en: str,
    object_class_zh: str,
    distance: str,
    description_zh: str,
    nasa_id: str,
    *,
    credit: str | None = None,
) -> dict[str, Any]:
    return {
        "catalog_id": catalog_id,
        "aliases": aliases,
        "title_zh": title_zh,
        "title_en": title_en,
        "object_class_zh": object_class_zh,
        "distance": distance,
        "description_zh": description_zh,
        "nasa_id": nasa_id,
        "source_url": f"https://images.nasa.gov/details/{nasa_id}",
        "credit": credit,
    }


def direct(
    catalog_id: str,
    aliases: list[str],
    title_zh: str,
    title_en: str,
    object_class_zh: str,
    distance: str,
    description_zh: str,
    source_url: str,
    asset_url: str,
    credit: str,
) -> dict[str, Any]:
    return {
        "catalog_id": catalog_id,
        "aliases": aliases,
        "title_zh": title_zh,
        "title_en": title_en,
        "object_class_zh": object_class_zh,
        "distance": distance,
        "description_zh": description_zh,
        "source_url": source_url,
        "asset_url": asset_url,
        "credit": credit,
    }


# Chinese summaries are original, concise paraphrases of the linked NASA records.
# The list is deliberately curated: a NASA-hosted page alone is not enough when
# the page marks an image as third-party copyrighted.
ENTRIES: tuple[dict[str, Any], ...] = (
    library(
        "NGC0224", ["M31"], "仙女座星系", "Andromeda Galaxy", "螺旋星系", "约 250 万光年",
        "本星系群中距离银河系最近的大型星系。紫外图像显示年轻恒星沿近似环状的旋臂分布，M32 与 M110 是它的卫星星系。",
        "PIA04921",
    ),
    direct(
        "NGC0221", ["M32"], "M32", "Messier 32", "致密椭圆星系", "约 250 万光年",
        "仙女座星系的致密卫星星系，恒星在核心区域高度集中。Hubble 的分辨率使研究者能把部分恒星从背景中分离出来。",
        "https://science.nasa.gov/image-detail/m32_acs_field2_3b_flat_gapfill_final/",
        "https://science.nasa.gov/wp-content/uploads/2023/04/m32_acs_field2_3b_flat_gapfill_final-jpg.webp",
        "NASA, ESA, A. Crotts, W. Freedman, J. Westphal; processing: Gladys Kober",
    ),
    direct(
        "NGC0205", ["M110"], "M110", "Messier 110", "矮椭圆星系", "约 270 万光年",
        "仙女座星系的卫星星系。它整体平滑，但 Hubble 图像仍能看到尘埃云、球状星团以及少量较年轻的蓝色恒星。",
        "https://science.nasa.gov/image-detail/m110/",
        "https://science.nasa.gov/wp-content/uploads/2023/04/m110.png",
        "NASA, ESA, STScI and D. Geisler (Universidad de Concepción)",
    ),
    library(
        "NGC0598", ["M33"], "三角座星系", "Triangulum Galaxy", "螺旋星系", "约 273 万光年",
        "本星系群第三大的螺旋星系。红外观测把尘埃和活跃恒星形成区勾勒出来，显示其可见盘面之外仍有延伸结构。",
        "PIA11969",
    ),
    library(
        "NGC5194", ["M51"], "涡状星系", "Whirlpool Galaxy", "相互作用螺旋星系", "约 2300 万光年",
        "典型的正面朝向旋涡结构；它与伴星系 NGC 5195 的引力作用强化了旋臂，并触发大量年轻恒星形成。",
        "PIA04230",
    ),
    direct(
        "NGC5055", ["M63"], "向日葵星系", "Sunflower Galaxy", "螺旋星系", "约 2700 万光年",
        "旋臂不是两条连续的巨臂，而是由许多短小片段层叠成向日葵般的纹理；外盘还延伸出十分微弱的恒星结构。",
        "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-63/",
        "https://science.nasa.gov/wp-content/uploads/2023/04/potw1536a-jpg.webp?w=1098",
        "ESA/Hubble and NASA",
    ),
    direct(
        "NGC0628", ["M74"], "幻影星系", "Phantom Galaxy", "螺旋星系", "约 3200 万光年",
        "近乎正面朝向我们的螺旋星系，清晰旋臂间散布着粉红色电离氢区；较低的表面亮度使它在目视观测中显得幽淡。",
        "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-74/",
        "https://assets.science.nasa.gov/dynamicimage/assets/science/missions/hubble/galaxies/spiral/Hubble_M74_2022_potw2235a.jpg?w=1600",
        "ESA/Hubble and NASA, R. Chandar",
    ),
    library(
        "NGC3031", ["M81"], "波德星系", "Bode's Galaxy", "螺旋星系", "约 1180 万光年",
        "M81 星系群的主要成员，拥有清晰对称的旋臂。多波段合成图把老年恒星、尘埃和新生恒星区分开来。",
        "PIA09579",
    ),
    library(
        "NGC3034", ["M82"], "雪茄星系", "Cigar Galaxy", "星暴星系", "约 1200 万光年",
        "与 M81 的近距离引力作用使其中心爆发式形成恒星，高速气体和尘埃从盘面上下喷出，形成醒目的双极外流。",
        "PIA04218",
    ),
    library(
        "NGC4486", ["M87", "Virgo A"], "M87", "Messier 87", "巨椭圆星系", "约 5500 万光年",
        "室女座星系团中心附近的巨椭圆星系。核心超大质量黑洞驱动相对论性喷流，红外图像可见喷流与周围介质形成的激波。",
        "PIA23122",
    ),
    library(
        "NGC5457", ["M101"], "风车星系", "Pinwheel Galaxy", "螺旋星系", "约 2100 万光年",
        "近乎正面朝向我们的巨大螺旋星系。盘面略不对称，旋臂中散布着大量明亮的恒星形成区。",
        "PIA04630",
    ),
    library(
        "NGC4594", ["M104"], "草帽星系", "Sombrero Galaxy", "近侧视螺旋星系", "约 2800 万光年",
        "明亮核球被厚重尘埃带环绕，外观像宽檐帽。它拥有异常丰富的球状星团系统，中心还存在超大质量黑洞。",
        "0700064", credit="NASA / Hubble Space Telescope / Spitzer Space Telescope",
    ),
    library(
        "NGC4826", ["M64"], "黑眼星系", "Black Eye Galaxy", "螺旋星系", "约 1700 万光年",
        "明亮核心前方的深色尘埃带形成“黑眼”外观。外层气体与内层恒星反向旋转，可能记录了一次古老的星系并合。",
        "0400392", credit="NASA / Hubble Space Telescope",
    ),
    library(
        "NGC0253", ["Sculptor Galaxy"], "银币星系", "Sculptor Galaxy", "星暴螺旋星系", "约 1140 万光年",
        "南天最明亮的近邻星系之一。WISE 红外图像穿透尘埃，显出核心附近强烈的恒星形成活动。",
        "PIA13440",
    ),
    library(
        "NGC1952", ["M1"], "蟹状星云", "Crab Nebula", "超新星遗迹", "约 6500 光年",
        "公元 1054 年超新星爆发留下的膨胀遗迹。中心脉冲星持续向周围注入高能粒子，塑造出快速变化的丝状结构。",
        "PIA03606",
    ),
    library(
        "NGC1976", ["M42"], "猎户座大星云", "Orion Nebula", "恒星形成区", "约 1340 光年",
        "距离地球最近的大质量恒星形成区之一。年轻巨星的辐射和恒星风在分子云中雕刻出空腔，红外光能看进被尘埃遮挡的区域。",
        "PIA25434",
    ),
    library(
        "NGC6523", ["M8"], "礁湖星云", "Lagoon Nebula", "发射星云", "约 4100 光年",
        "一座巨大的恒星育婴室，发光气体、冷尘埃和年轻星团交织。WISE 的红外视野揭示了可见光下被遮住的新生恒星。",
        "PIA13453",
    ),
    library(
        "NGC6611", ["M16"], "鹰状星云", "Eagle Nebula", "发射星云与星团", "约 6500 光年",
        "包含著名的“创生之柱”和年轻疏散星团 NGC 6611。巨星辐射一面压缩冷气体形成新星，一面侵蚀周围云柱。",
        "PIA25433",
    ),
    library(
        "NGC6618", ["M17"], "欧米伽星云", "Omega Nebula", "发射星云", "约 5500 光年",
        "银河系中规模较大的恒星形成区之一。炽热年轻恒星电离氢气，并把气体表面塑造成层叠的浪潮状结构。",
        "0302063", credit="NASA / Hubble Space Telescope",
    ),
    library(
        "NGC6514", ["M20"], "三叶星云", "Trifid Nebula", "发射与反射星云", "约 5200 光年",
        "发射星云、蓝色反射星云和暗尘埃带同处一个视场；暗带把明亮核心切成三瓣，因此得名“三叶”。",
        "PIA04220", credit="2MASS / NASA / JPL-Caltech",
    ),
    library(
        "NGC6853", ["M27"], "哑铃星云", "Dumbbell Nebula", "行星状星云", "约 1360 光年",
        "一颗类太阳恒星在生命末期抛出的外层气体。Hubble 近景显示许多致密气体结，正被中央白矮星的辐射照亮。",
        "PIA04249",
    ),
    library(
        "NGC6720", ["M57"], "环状星云", "Ring Nebula", "行星状星云", "约 2500 光年",
        "看似平面的光环其实是三维气体壳。中央恒星抛出的物质在紫外辐射下发光，外围还有更冷、更淡的分子结构。",
        "PIA07343",
    ),
    direct(
        "NGC0650", ["M76"], "小哑铃星云", "Little Dumbbell Nebula", "行星状星云", "约 3400 光年",
        "一颗濒死恒星抛出的双叶气体壳，中央亮条与两侧淡弧共同形成“小哑铃”外观；它也是梅西耶目录中较暗的目标之一。",
        "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-76/",
        "https://science.nasa.gov/wp-content/uploads/2024/04/hubble-34th-littledumbell-sm-stsci-01htddrc7nr68q120setwhmsaq.png?w=1600",
        "NASA, ESA and STScI",
    ),
    library(
        "NGC0281", ["Pacman Nebula"], "吃豆人星云", "Pacman Nebula", "电离氢区", "约 9200 光年",
        "仙后座方向的大型恒星形成云，轮廓像张口的游戏角色。WISE 红外图像穿过尘埃，显示内部年轻星团和被吹出的空腔。",
        "PIA14873",
    ),
    library(
        "NGC7635", ["Bubble Nebula"], "气泡星云", "Bubble Nebula", "电离氢区", "约 7100 光年",
        "一颗大质量恒星的高速恒星风扫起周围冷气体，形成约 7 光年宽的泡壳；密度不均使恒星看起来偏离气泡中心。",
        "GSFC_20171208_Archive_e000382", credit="NASA, ESA and the Hubble Heritage Team (STScI/AURA)",
    ),
    library(
        "NGC1499", ["California Nebula"], "加州星云", "California Nebula", "发射星云", "约 1000 光年",
        "英仙座方向的大片电离气体云，外形类似加利福尼亚州。Spitzer 的最后一幅任务拼图之一呈现了可见光与红外下不同的尘埃结构。",
        "PIA23650",
    ),
    library(
        "NGC7000", ["North America Nebula"], "北美洲星云", "North America Nebula", "电离氢区", "约 2600 光年",
        "天鹅座方向的广阔恒星形成区，暗尘埃塑造出“海湾”和大陆轮廓。红外观测显示许多约百万年年龄的年轻星团。",
        "PIA13843",
    ),
    library(
        "B033", ["Horsehead Nebula"], "马头星云", "Horsehead Nebula", "暗星云", "约 1375 光年",
        "冷而致密的尘埃云在明亮的 IC 434 发射区前形成剪影。Hubble 红外图像能穿透部分尘埃，显出云脊边缘的细丝。",
        "PIA16008",
    ),
    library(
        "NGC3372", ["Carina Nebula"], "船底座星云", "Carina Nebula", "巨型恒星形成区", "约 7600 光年",
        "银河系最壮观的恒星形成复合区之一，孕育多颗极大质量恒星。Webb 红外图像中的“宇宙悬崖”是被年轻恒星侵蚀的气体尘埃边缘。",
        "carina_nebula", credit="NASA, ESA, CSA and STScI",
    ),
    library(
        "NGC6992", ["Eastern Veil Nebula"], "东面纱星云", "Eastern Veil Nebula", "超新星遗迹", "约 2100 光年",
        "约八千年前一次大质量恒星爆炸形成的面纱星云东侧弧段。激波穿过稀薄星际气体，留下细长、褶皱的发光丝。",
        "GSFC_20171208_Archive_e000607", credit="NASA, ESA and the Hubble Heritage Team (STScI/AURA)",
    ),
    library(
        "NGC2237", ["Rosette Nebula"], "玫瑰星云", "Rosette Nebula", "恒星形成区", "约 5000 光年",
        "麒麟座方向的巨大分子云与电离气体区。中央年轻星团的辐射和风吹出空腔，外围尘埃继续孕育恒星。",
        "PIA09268",
    ),
    library(
        "NGC6543", ["Cat's Eye Nebula"], "猫眼星云", "Cat's Eye Nebula", "行星状星云", "约 3300 光年",
        "结构极其复杂的行星状星云，包含同心气体壳、高速喷流和激波结，记录了中央恒星分阶段抛出外层物质的过程。",
        "PIA16009",
    ),
    library(
        "NGC7293", ["Helix Nebula"], "螺旋星云", "Helix Nebula", "行星状星云", "约 650 光年",
        "距离最近的行星状星云之一，展示类太阳恒星晚年抛出的气体壳。紫外观测突出中央热白矮星与被电离的外层物质。",
        "PIA07902",
    ),
    library(
        "Mel022", ["M45"], "昴星团", "Pleiades", "疏散星团", "约 445 光年",
        "年轻、松散的开放星团，肉眼可见的亮星只是上千名成员中的一小部分。红外图像显示星团正穿过一片反射星光的尘埃云。",
        "PIA09263",
    ),
    direct(
        "NGC0869", ["Caldwell 14", "h Persei"], "英仙座 h 星团", "h Persei", "疏散星团", "约 7500 光年",
        "与 NGC 884 并列组成著名的英仙座双星团。两群年轻高温恒星可能形成于同一片分子云，在双筒镜中可同时收入视场。",
        "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/caldwell-14/",
        "https://science.nasa.gov/wp-content/uploads/2023/04/ngc869_884_inset_final-01-jpg.webp?w=1600",
        "Background: Digitized Sky Survey; Hubble: NASA, ESA and S. Casertano; processing: Gladys Kober",
    ),
    direct(
        "NGC0884", ["Caldwell 14", "chi Persei"], "英仙座 χ 星团", "chi Persei", "疏散星团", "约 7500 光年",
        "与 NGC 869 相邻的年轻疏散星团，是双星团中偏东的一员。两个星团只相隔数百光年，年龄都约为一千多万年。",
        "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/caldwell-14/",
        "https://science.nasa.gov/wp-content/uploads/2023/04/ngc869_884_inset_final-01-jpg.webp?w=1600",
        "Background: Digitized Sky Survey; Hubble: NASA, ESA and S. Casertano; processing: Gladys Kober",
    ),
    direct(
        "NGC6205", ["M13"], "武仙座球状星团", "Hercules Globular Cluster", "球状星团", "约 2.5 万光年",
        "由十万颗以上古老恒星组成的致密球状星团。靠近核心时恒星密度远高于太阳邻域，Hubble 能分辨出大量独立成员。",
        "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-13/",
        "https://assets.science.nasa.gov/content/dam/science/missions/hubble/stars/glular-clusters/Hubble_M13_2010_potw1011a.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg".replace("glular", "globular"),
        "NASA, ESA and the Hubble Heritage Team (STScI/AURA)",
    ),
    library(
        "IC1805", ["Heart Nebula"], "心脏星云", "Heart Nebula", "恒星形成区", "约 6000 光年",
        "与灵魂星云共同组成英仙臂中的巨大恒星形成复合区。WISE 在红外波段显示年轻恒星吹出的气泡，以及冷尘埃中正在形成的恒星。",
        "PIA13112",
    ),
    library(
        "IC1848", ["Soul Nebula", "W5"], "灵魂星云", "Soul Nebula", "恒星形成区", "约 6000 光年",
        "紧邻心脏星云的活跃恒星形成云，又称 W5。两者合计延伸数百光年，红外图像能看见气泡边缘和隐藏的年轻恒星。",
        "PIA13112",
    ),
)


def request_bytes(url: str, *, attempts: int = 3) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - retry transient NASA/CDN errors
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def request_json(url: str) -> dict[str, Any]:
    return json.loads(request_bytes(url).decode("utf-8"))


def library_record(nasa_id: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"nasa_id": nasa_id, "media_type": "image"})
    payload = request_json(f"{NASA_API}/search?{query}")
    items = payload.get("collection", {}).get("items", [])
    if not items:
        raise RuntimeError(f"NASA media item not found: {nasa_id}")
    item = items[0]
    data = item.get("data", [{}])[0]
    assets = request_json(f"{NASA_API}/asset/{urllib.parse.quote(nasa_id)}")
    urls = [
        str(asset.get("href", "")).replace("http://", "https://", 1)
        for asset in assets.get("collection", {}).get("items", [])
        if re.search(r"\.(?:jpe?g|png|webp)(?:\?.*)?$", str(asset.get("href", "")), re.I)
    ]
    if not urls:
        raise RuntimeError(f"NASA media item has no raster image: {nasa_id}")

    def preference(url: str) -> tuple[int, str]:
        lowered = url.lower()
        for index, marker in enumerate(("~large.", "~medium.", "~orig.", "~small.", "~thumb.")):
            if marker in lowered:
                return index, lowered
        return 5, lowered

    asset_url = sorted(urls, key=preference)[0]
    return {
        "asset_url": asset_url,
        "title": data.get("title"),
        "credit": data.get("secondary_creator") or data.get("photographer"),
        "center": data.get("center"),
        "date_created": data.get("date_created"),
    }


def encode_webp(payload: bytes) -> tuple[bytes, int, int]:
    Image.MAX_IMAGE_PIXELS = 200_000_000
    with Image.open(io.BytesIO(payload)) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        elif image.mode == "RGBA":
            background = Image.new("RGB", image.size, "black")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        image.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=84, method=6)
        return output.getvalue(), image.width, image.height


def safe_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:56].rstrip("-")


def existing_media() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    cache: dict[str, dict[str, Any]] = {}
    for raw in payload.get("objects", {}).values():
        if not isinstance(raw, dict):
            continue
        filename = raw.get("thumbnailFile")
        expected_hash = raw.get("thumbnailSha256")
        asset_url = raw.get("assetUrl")
        media_key = str(raw.get("nasaId") or asset_url or "")
        path = IMAGE_DIR / str(filename)
        if (
            not media_key
            or not isinstance(filename, str)
            or len(filename) > 80
            or not path.is_file()
            or not isinstance(expected_hash, str)
        ):
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            continue
        cache[media_key] = {
            "image_file": filename,
            "sha256": expected_hash,
            "width": raw.get("thumbnailWidth"),
            "height": raw.get("thumbnailHeight"),
            "asset_url": asset_url,
            "media_title_en": raw.get("mediaTitleEn"),
            "media_center": raw.get("mediaCenter"),
            "date_created": raw.get("mediaDate"),
            "credit": raw.get("credit") or "NASA",
        }
    return cache


def build(*, only: set[str] | None = None) -> dict[str, Any]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    objects: dict[str, Any] = {}
    media_cache: dict[str, dict[str, Any]] = {}
    reusable = existing_media()
    selected = [entry for entry in ENTRIES if only is None or entry["catalog_id"] in only]
    for index, entry in enumerate(selected, start=1):
        nasa_id = entry.get("nasa_id")
        media_key = str(nasa_id or entry["asset_url"])
        print(f"[{index:02d}/{len(selected):02d}] {entry['catalog_id']} · {entry['title_zh']}")
        media = media_cache.get(media_key)
        if media is None:
            media = reusable.get(media_key)
        if media is None:
            remote = library_record(str(nasa_id)) if nasa_id else {
                "asset_url": entry["asset_url"],
                "title": entry["title_en"],
                "credit": entry.get("credit"),
                "center": "NASA Science",
                "date_created": None,
            }
            raw = request_bytes(remote["asset_url"])
            encoded, width, height = encode_webp(raw)
            digest = hashlib.sha256(encoded).hexdigest()
            filename = f"{safe_key(media_key)}-{digest[:10]}.webp"
            (IMAGE_DIR / filename).write_bytes(encoded)
            media = {
                "image_file": filename,
                "sha256": digest,
                "width": width,
                "height": height,
                "asset_url": remote["asset_url"],
                "media_title_en": remote.get("title"),
                "media_center": remote.get("center"),
                "date_created": remote.get("date_created"),
                "credit": entry.get("credit") or remote.get("credit") or "NASA",
            }
        media_cache[media_key] = media
        objects[entry["catalog_id"]] = {
            "catalogId": entry["catalog_id"],
            "aliases": entry["aliases"],
            "titleZh": entry["title_zh"],
            "titleEn": entry["title_en"],
            "objectClassZh": entry["object_class_zh"],
            "distance": entry["distance"],
            "descriptionZh": entry["description_zh"],
            "thumbnailFile": media["image_file"],
            "thumbnailSha256": media["sha256"],
            "thumbnailWidth": media["width"],
            "thumbnailHeight": media["height"],
            "sourceUrl": entry["source_url"],
            "assetUrl": media["asset_url"],
            "nasaId": nasa_id,
            "mediaTitleEn": media["media_title_en"],
            "mediaCenter": media["media_center"],
            "mediaDate": media["date_created"],
            "credit": media["credit"],
        }
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": "NASA",
        "usageGuidelinesUrl": USAGE_URL,
        "runtimeNetworkRequired": False,
        "objectCount": len(objects),
        "uniqueImageCount": len(media_cache),
        "objects": dict(sorted(objects.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the curated NASA deep-sky offline media pack")
    parser.add_argument("--only", action="append", help="Catalog ID to download; may be repeated")
    args = parser.parse_args()
    payload = build(only=set(args.only) if args.only else None)
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Saved {payload['objectCount']} objects / {payload['uniqueImageCount']} images to "
        f"{MANIFEST_PATH.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
