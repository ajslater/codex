#!/usr/bin/env python
"""Generate production icons from svg sources."""

import shutil
import subprocess
from pathlib import Path
from types import MappingProxyType

from cairosvg import svg2png

TOP_PATH = Path(__file__).parent.parent
SRC_IMG_PATH = TOP_PATH / Path("img")
STATIC_IMG_PATH = TOP_PATH / Path("codex/static_src/img")
INKSCAPE_PATH = Path("/Applications/Inkscape.app/Contents/MacOS/inkscape")
_COVER_RATIO = 1.5372233400402415
ICONS = MappingProxyType(
    {
        "logo": (32, 32),
        "logo-maskable": (180, 180),
        "missing-cover": (165, round(165 * _COVER_RATIO)),
        "publisher": (),
        "imprint": (),
        "series": (),
        "volume": (),
        "folder": (),
        "story-arc": (),
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


def inkscape(input_path, export_path, width, height):
    """Transform svgs with xlinks into pngs."""
    # Needed because cairosvg doesn't support xlinks
    # https://github.com/Kozea/CairoSVG/issues/163
    args = (
        INKSCAPE_PATH,
        f"--export-width={width}",
        f"--export-height={height}",
        f"--export-filename={export_path}",
        input_path,
    )
    subprocess.run(args, check=False)  # noqa: S603


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
            (SRC_IMG_PATH / "missing-cover.svg").touch()
        shutil.copy(input_svg_path, output_svg_path)

    if not size:
        return
    width, height = size

    output_png_name = f"{name}-{width}"
    output_png_path = STATIC_IMG_PATH / (output_png_name + ".png")
    output_webp_path = STATIC_IMG_PATH / (output_png_name + ".webp")
    do_gen_png = (
        not output_webp_path.exists()
        or output_webp_path.stat().st_mtime < input_svg_mtime
    )
    if do_gen_png:
        if name == "missing-cover":
            inkscape(input_svg_path, output_png_path, width, height)
        else:
            svg2png(
                url=str(input_svg_path),
                write_to=str(output_png_path),
                output_width=width,
                output_height=height,
            )


def picopt():
    """Optimize output with picopt."""
    args = ("picopt", "-rtx", "SVG", "-c", "WEBP", STATIC_IMG_PATH)
    subprocess.run(args, check=False)  # noqa: S603


def main():
    """Create all icons."""
    for name, size in ICONS.items():
        transform_icon(name, size)
    picopt()


if __name__ == "__main__":
    main()
