from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def create_icon(destination: Path) -> None:
    scale = 4
    size = 256
    canvas = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    def box(values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(value * scale for value in values)  # type: ignore[return-value]

    draw.rounded_rectangle(box((0, 0, 256, 256)), radius=48 * scale, fill="#191E24")
    for points in (((92, 52), (52, 52), (52, 92)), ((164, 52), (204, 52), (204, 92)),
                   ((204, 164), (204, 204), (164, 204)), ((92, 204), (52, 204), (52, 164))):
        draw.line([(x * scale, y * scale) for x, y in points], fill="#83AFA6", width=12 * scale)
    draw.line([(76 * scale, 156 * scale), (124 * scale, 116 * scale), (172 * scale, 140 * scale)], fill="#647E87", width=6 * scale)
    star = [(124, 76), (133.6, 106.4), (164, 116), (133.6, 125.6), (124, 156), (114.4, 125.6), (84, 116), (114.4, 106.4)]
    draw.polygon([(x * scale, y * scale) for x, y in star], fill="#E0E8E9")
    draw.ellipse(box((162, 130, 182, 150)), fill="#83AFA6")
    draw.ellipse(box((70, 150, 82, 162)), fill="#B6C5CB")

    icon = canvas.resize((size, size), Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    icon.save(
        destination,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    icon.save(destination.with_suffix(".png"))
    canvas.close()
    icon.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    create_icon(args.destination)


if __name__ == "__main__":
    main()
