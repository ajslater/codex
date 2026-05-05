#!/usr/bin/env python
"""
Re-inline logo.svg into comic.svg as gray.

Run when logo.svg changes to refresh the copy embedded inside comic.svg.
The black-circle background is dropped, and every fill/stroke is forced
to gray so the inlined logo matches the rest of comic.svg's outlines.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

TOP_PATH = Path(__file__).parent.parent
SRC_IMG_PATH = TOP_PATH / "img"
LOGO_PATH = SRC_IMG_PATH / "logo.svg"
COMIC_PATH = SRC_IMG_PATH / "comic.svg"
GRAY = "#808080"

_NS = {
    "": "http://www.w3.org/2000/svg",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "xlink": "http://www.w3.org/1999/xlink",
}
_SVG_NS = _NS[""]
_INKSCAPE_LABEL = f"{{{_NS['inkscape']}}}label"


def _gray_style(style):
    """Replace every fill/stroke color in a CSS style string with gray."""
    out = []
    for raw in style.split(";"):
        if ":" not in raw:
            if raw.strip():
                out.append(raw)
            continue
        key, _, val = raw.partition(":")
        key = key.strip()
        val = val.strip()
        if key in ("fill", "stroke") and val != "none":
            val = GRAY
        elif key in ("fill-opacity", "stroke-opacity") and val == "0":
            val = "1"
        out.append(f"{key}:{val}")
    return ";".join(out)


def _recolor(elem):
    """Force fill/stroke to gray on this element and all descendants."""
    style = elem.get("style")
    if style:
        elem.set("style", _gray_style(style))
    for attr in ("fill", "stroke"):
        val = elem.get(attr)
        if val and val != "none":
            elem.set(attr, GRAY)
    for child in elem:
        _recolor(child)


def _find_one(root, tag, **attrs):
    """Find the single descendant matching tag and attribute filters."""
    for elem in root.iter(f"{{{_SVG_NS}}}{tag}"):
        if all(elem.get(k) == v for k, v in attrs.items()):
            return elem
    pretty = ", ".join(f"{k}={v!r}" for k, v in attrs.items())
    msg = f"No <{tag}> with {pretty} found"
    raise RuntimeError(msg)


def main():
    """Re-inline logo.svg into comic.svg, recoloring to gray."""
    for prefix, uri in _NS.items():
        ET.register_namespace(prefix, uri)

    logo_root = ET.parse(LOGO_PATH).getroot()  # noqa: S314
    logo_group = _find_one(logo_root, "g", **{_INKSCAPE_LABEL: "logo"})

    comic_tree = ET.parse(COMIC_PATH)  # noqa: S314
    target = _find_one(comic_tree.getroot(), "svg", id="logo")

    for old in list(target):
        target.remove(old)
    for child in logo_group:
        if child.get(_INKSCAPE_LABEL) == "black-circle":
            continue
        _recolor(child)
        target.append(child)

    comic_tree.write(COMIC_PATH, xml_declaration=True, encoding="UTF-8")


if __name__ == "__main__":
    main()
