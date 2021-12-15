#!/usr/bin/env python3
"""Create large numbers of mocks comics."""
import string
import time
import zipfile

from io import BytesIO
from pathlib import Path
from random import choices, randint, random

from comicbox.metadata.comicinfoxml import ComicInfoXml
from fnvhash import fnv1a_32
from PIL import Image


GROUPS = ("publisher", "imprint", "series")
M2MS = ("characters", "genres", "locations", "tags", "teams")
HEX_FILL = 8
PATH_STEP = 2
CHANCE_OF_NULL = 0.1
CHOICES_STR = string.ascii_uppercase + string.digits
CREDIT_TAGS = (
    "Colorist",
    "CoverArtist",
    "Editor",
    "Inker",
    "Letterer",
    "Penciller",
    "Writer",
)


def rand_string(length):
    """Return a random string of arbitrary length."""
    return "".join(choices(CHOICES_STR, k=length))


def create_str(md, key, num):
    """Add random string to the metadata."""
    if random() < CHANCE_OF_NULL:
        return
    md[key] = rand_string(num)


def create_m2m(md, key, count, length):
    """Add m2m field the metadata."""
    if random() < CHANCE_OF_NULL:
        return
    m2m = set()
    for _ in range(randint(0, count)):
        name = rand_string(length)
        m2m.add(name)
    md[key] = m2m


def create_credits(md, num):
    """Add credits to the metadata."""
    credits = []
    if random() > CHANCE_OF_NULL:
        for _ in range(0, randint(0, num)):
            role = choices(CREDIT_TAGS, k=1)[0]
            credit = {"person": rand_string(10), "role": role}
            credits.append(credit)
    md["credits"] = credits


def create_int(md, key, max):
    """Add an int to the metadata."""
    if random() < CHANCE_OF_NULL:
        return
    md[key] = randint(0, max)


def create_float(md, key, max):
    """Add a float to the metadata."""
    if random() < CHANCE_OF_NULL:
        return
    md[key] = random() * max


def create_metadata():
    """Create ranomized metadata."""
    md = {}

    for group in GROUPS:
        create_str(md, group, 10)

    create_int(md, "volume", 2055)
    create_int(md, "volume_count", 10)
    create_int(md, "issue", 1000)
    create_int(md, "issue_count", 1000)
    create_int(md, "year", 2021)
    create_int(md, "month", 12)
    create_int(md, "day", 28)
    md["web"] = rand_string(40)
    for key in M2MS:
        create_m2m(md, key, 5, 20)
    create_credits(md, 15)

    parser = ComicInfoXml(metadata=md)
    md_str = parser.to_string()
    return md_str


def create_cover_page():
    """Create a small randomly colored square image."""
    r = randint(0, 255)
    g = randint(0, 255)
    b = randint(0, 255)
    img = Image.new("RGB", (250, 250), (r, g, b))
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
    hex_str = "{0:0{1}x}".format(fnv, HEX_FILL)
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
    root = Path(args[1])
    num_comics = int(args[2])

    since = time.time()
    for index in range(num_comics):
        create_file(root, index)
        now = time.time()
        if now - since > 10:
            print(f"{index}/{num_comics}")
            since = now


if __name__ == "__main__":
    import sys

    main(sys.argv)
