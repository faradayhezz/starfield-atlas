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

    draw.rounded_rectangle(box((0, 0, 256, 256)), radius=64 * scale, fill="#101618")
    draw.ellipse(box((40, 40, 216, 216)), outline="#2bd875", width=12 * scale)
    draw.line(box((128, 52, 128, 88)), fill="#718078", width=8 * scale)
    draw.line(box((128, 168, 128, 204)), fill="#718078", width=8 * scale)
    draw.line(box((52, 128, 88, 128)), fill="#718078", width=8 * scale)
    draw.line(box((168, 128, 204, 128)), fill="#718078", width=8 * scale)
    star = [(128, 84), (139, 117), (172, 128), (139, 139), (128, 172), (117, 139), (84, 128), (117, 117)]
    draw.polygon([(x * scale, y * scale) for x, y in star], fill="#f3f7f4")
    draw.ellipse(box((182, 58, 202, 78)), fill="#f4ce3a")
    draw.arc(box((139, 69, 201, 135)), start=184, end=260, fill="#2bd875", width=8 * scale)

    icon = canvas.resize((size, size), Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    icon.save(
        destination,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    create_icon(args.destination)


if __name__ == "__main__":
    main()
