#!/usr/bin/env python
"""Generate prodution icons from svg sources."""

import shutil
import subprocess
from pathlib import Path
from types import MappingProxyType

from cairosvg import svg2png

TOP_PATH = Path(__file__).parent.parent
SRC_IMG_PATH = TOP_PATH / Path("codex/img")
STATIC_IMG_PATH = TOP_PATH / Path("codex/static_src/img")
INKSCAPE_PATH = Path("/Applications/Inkscape.app/Contents/MacOS/inkscape")
ICONS = MappingProxyType(
    {
        "logo": 32,
        "logo-maskable": 180,
        "missing-cover": 0,
        "missing-page": 0,
        "publisher": 0,
        "imprint": 0,
        "series": 0,
        "volume": 0,
        "folder": 0,
        "story-arc": 0,
    }
)


def create_maskable_icon(input_path):
    """Create logo-maskable.svg from logo.svg by editing the XML."""
    with input_path.open("r") as f:
        lines = f.readlines()

    modified_lines = []
    for line in lines:
        modified_lines.append(line)
        if 'inkscape:label="logo"' in line:
            modified_lines.append('    transform="matrix(0.80,0,0,0.80,51.5,51.5)"')

    output_path = SRC_IMG_PATH / "logo-maskable.svg"
    with output_path.open("w") as f:
        f.writelines(modified_lines)


def transform_icon(name, size):
    """Transform svgs into optimized svgs and pngs."""
    svg_name = name + ".svg"
    input_svg_path = SRC_IMG_PATH / svg_name
    output_svg_path = STATIC_IMG_PATH / svg_name
    input_svg_mtime = input_svg_path.stat().st_mtime
    do_gen_svg = (
        not output_svg_path.exists()
        or output_svg_path.stat().st_mtime < input_svg_mtime
    )
    if do_gen_svg:
        if name == "logo":
            create_maskable_icon(input_svg_path)
        shutil.copy(input_svg_path, output_svg_path)

    if not size:
        return

    output_png_name = f"{name}-{size}"
    output_png_path = STATIC_IMG_PATH / (output_png_name + ".png")
    output_webp_path = STATIC_IMG_PATH / (output_png_name + ".webp")
    do_gen_png = (
        not output_webp_path.exists()
        or output_webp_path.stat().st_mtime < input_svg_mtime
    )
    if do_gen_png:
        svg2png(url=input_svg_path, write_to=output_png_path, width=size, height=size)


def picopt():
    """Optimize output with picopt."""
    # TODO use picopt API
    args = ("picopt", "-rtx" "SVG", "-c", "WEBP", STATIC_IMG_PATH)
    subprocess.run(args, check=False)  # noqa: S603


def main():
    """Create all icons."""
    for name, size in ICONS.items():
        transform_icon(name, size)
    picopt()


if __name__ == "__main__":
    main()
