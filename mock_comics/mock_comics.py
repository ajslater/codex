#!/usr/bin/env python3
"""Create large numbers of mocks comics."""

import random
import string
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostringlist

from comicbox.identifiers import (
    ASIN_NID,
    COMICVINE_NID,
    COMIXOLOGY_NID,
    GCD_NID,
    IDENTIFIER_URL_MAP,
    ISBN_NID,
    LCG_NID,
    METRON_NID,
    UPC_NID,
)
from comicbox.schemas.comicinfo import ComicInfoSchema
from fnvhash import fnv1a_32
from PIL import Image
from pycountry import languages

GROUPS = ("publisher", "imprint", "series")
M2MS = ("characters", "genres", "locations", "tags", "teams")
HEX_FILL = 8
PATH_STEP = 2
CHANCE_OF_NULL = 0.1
CHANCE_OF_BAD_TYPE = 0.2
CHOICES_STR = string.ascii_uppercase + string.digits
CONTRIBUTOR_TAGS = (
    "Colorist",
    "CoverArtist",
    "Editor",
    "Inker",
    "Letterer",
    "Penciller",
    "Writer",
)
FIELDS = {
    "TEXT": ("Summary", "Notes", "ScanInformation"),
    "INTS": {
        "Number": 1024,
        "AlternateNumber": 1024,
        "Count": 1024,
        "AlternateCount": 1024,
        "Year": 2030,
        "Month": 12,
        "Day": 31,
        "Volume": 2030,
        "PageCount": 1024,
        "StoryArcNumber": 1024,
    },
    "VARCHARS": {
        "AlternateSeries": 64,
        "LanguageISO": 2,
        "Format": 16,
        "Publisher": 24,
        "Imprint": 24,
        "Series": 64,
        "AgeRating": 18,
        "Title": 24,
        "Summary": 1024,
        "Notes": 128,
        "ScanInformation": 32,
        "MainCharacterOrTeam": 24,
        "Web": 64,
    },
    "DECIMALS": {"CommunityRating": 100.0},
    "NAME_LISTS": (
        "Genre",
        "Characters",
        "Tags",
        "Teams",
        "Locations",
        "StoryArc",
        "SeriesGroup",
    ),
    "contributorS": ("Colorist", "CoverArtist", "Editor", "Letterer", "Inker"),
}
BOOL_VALUES = ("yes", "no")
MANGA_VALUES = (*BOOL_VALUES, "yesandrighttoleft", "yesrtl")
NUM_M2M_NAMES = 20
NUM_CONTRIBUTORS = 15
STATUS_DELAY = 5
LANG_LIST = []
for lang in languages:
    try:
        LANG_LIST.append(lang.alpha_2)  # type: ignore
    except AttributeError:
        LANG_LIST.append(lang.alpha_3)  # type: ignore
COVER_RATIO = 1.5372233400402415
COVER_WIDTH = 250
COVER_HEIGHT = int(COVER_RATIO * COVER_WIDTH)


def is_valid():
    """Determine if to make the tag null or the wrong type."""
    n = random.random()
    if n < CHANCE_OF_NULL:
        return None
    return n >= CHANCE_OF_BAD_TYPE


def rand_string(length, choices=CHOICES_STR):
    """Return a random string of arbitrary length."""
    return "".join(random.choices(choices, k=length))


def rand_digits(length):
    """Return a random string of digits of arbitrary length."""
    return rand_string(length, string.digits)


def create_int(md, key, limit):
    """Add an int to the metadata."""
    v = is_valid()
    if v is None:
        return
    if not v:
        value = rand_string(5)
    else:
        limit = round(limit * 1.2)
        value = random.randint(0, limit)
    md[key] = value


def create_float(md, key, limit):
    """Add a float to the metadata."""
    v = is_valid()
    if v is None:
        return
    value = rand_string(5) if not v else random.random() * limit * 1.1
    md[key] = value


def create_str(md, key, limit):
    """Add random string to the metadata."""
    if is_valid() is None:
        return
    prefix = key + "_"
    length = random.randint(0, round(limit * 1.2)) - len(prefix)
    md[key] = prefix + rand_string(length)


def create_web(md, key, _limit):
    """Create a valid parsable web key."""
    if is_valid() is None:
        return
    nid = random.choice(tuple(IDENTIFIER_URL_MAP.keys()))
    if nid == COMICVINE_NID:
        suffix = "4000-" + rand_digits(6)
    elif nid in (METRON_NID, GCD_NID, LCG_NID):
        suffix = rand_string(5) + "/" + rand_string(5)
    elif nid == ASIN_NID:
        suffix = rand_string(10)
    elif nid == COMIXOLOGY_NID:
        suffix = "x/x/" + rand_string(10)
    elif nid == ISBN_NID:
        suffix = rand_digits(10)
    elif nid == UPC_NID:
        suffix = rand_digits(12)
    else:
        return

    url = IDENTIFIER_URL_MAP[nid] + suffix

    md[key] = url


def create_lang(md, key, _limit):
    """Add an iso language code."""
    lang_code = random.choice(LANG_LIST)
    md[key] = lang_code


def create_name_list(md, key):
    """Add m2m field the metadata."""
    if is_valid() is None:
        return
    m2m = []
    prefix = key + "_"
    for _ in range(random.randint(0, NUM_M2M_NAMES)):
        name = prefix + rand_string(64 - len(prefix))
        m2m.append(name)
    md[key] = ",".join(m2m)


def create_bool(md, key):
    """Create a boolean tag."""
    v = is_valid()
    if v is None:
        return
    value = rand_string(5) if not v else BOOL_VALUES[random.randint(0, 1)]
    md[key] = value


def create_manga(md):
    """Create a manga tag."""
    v = is_valid()
    if v is None:
        return
    value = rand_string(5) if not v else MANGA_VALUES[random.randint(0, 3)]
    md["Manga"] = value


def create_contributors(md):
    """Add contributors to the metadata."""
    v = is_valid()
    if v is None:
        return
    for _ in range(random.randint(0, NUM_CONTRIBUTORS)):
        role = random.choices(CONTRIBUTOR_TAGS, k=1)[0]
        person = rand_string(round(64 * 1.1))
        md[role] = person


def create_metadata():
    """Create ranomized metadata."""
    md = {}

    for key, limit in FIELDS["INTS"].items():
        create_int(md, key, limit)

    for key in FIELDS["TEXT"]:
        create_str(md, key, 100)

    for key, limit in FIELDS["VARCHARS"].items():
        if key == "LanguageISO":
            create_lang(md, key, limit)
        elif key == "Web":
            create_web(md, key, limit)
        else:
            create_str(md, key, limit)

    for key, limit in FIELDS["DECIMALS"].items():
        create_float(md, key, limit)

    for key in FIELDS["NAME_LISTS"]:
        create_name_list(md, key)

    create_bool(md, "BlackAndWhite")
    create_manga(md)
    create_contributors(md)

    root = Element(ComicInfoSchema.ROOT_TAGS[0])
    root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
    root.attrib["xmlns:xsd"] = "http://www.w3.org/2001/XMLSchema"

    for key, val in md.items():
        SubElement(root, key).text = str(val)
    return b"\n".join(tostringlist(root, encoding="utf-8"))


def create_cover_page():
    """Create a small randomly colored square image."""
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), (r, g, b))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_test_file(path):
    """Create a test file and write metadata to it."""
    # Create an minimal file to write to
    path.parent.mkdir(parents=True, exist_ok=True)
    md_data = create_metadata()
    image_data = create_cover_page()
    with zipfile.ZipFile(path, mode="w") as zf:
        zf.writestr("ComicInfo.xml", md_data)
        zf.writestr("cover.jpg", image_data)


def _hex_path(num):
    """Translate an integer into an efficient filesystem path."""
    num_str = f"{num:07}"
    fnv = fnv1a_32(bytes(num_str, "utf-8"))
    hex_str = format(fnv, f"0{HEX_FILL}x")
    parts = []
    for i in range(0, len(hex_str), PATH_STEP):
        parts.append(hex_str[i : i + PATH_STEP])
    path = Path("/".join(parts))
    return path.with_suffix(".cbz")


def create_file(root, index):
    """Create a test file."""
    path = root / _hex_path(index)
    path.parent.mkdir(exist_ok=True, parents=True)
    create_test_file(path)


def main(args):
    """Process args and create mock comics."""
    try:
        root = Path(args[1])
        num_comics = int(args[2])
    except Exception:
        print(f"{args[0]} <path> <num_comics>")
        sys.exit(1)

    since = time.time()
    index = 0
    for index in range(num_comics):
        create_file(root, index)
        now = time.time()
        if now - since > STATUS_DELAY:
            print(f"{index+1}/{num_comics}")
            since = now
    print(f"{index+1}/{num_comics}")


if __name__ == "__main__":
    main(sys.argv)
