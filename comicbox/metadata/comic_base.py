"""Metadata class for a comic archive."""
from decimal import Decimal

import pycountry
import regex


IMAGE_EXT_RE = regex.compile(r"\.(jpe?g|png|gif|webp)$", regex.IGNORECASE)


class ComicBaseMetadata(object):
    """Comicbox Metadata Class."""

    @property
    def FILENAME(self):  # noqa: N802
        raise NotImplementedError("Subclasses should implement this!")

    class ReadingDirection(object):
        """Reading direction enum."""

        LTR = "ltr"
        RTL = "rtl"

        @classmethod
        def parse(cls, val):
            """Match a reading direction to an acceptable value."""
            val = val.strip().lower()
            if val == cls.RTL:
                return cls.RTL
            elif val == cls.LTR:
                return cls.LTR

    STR_SET_TAGS = set(("characters", "locations", "tags", "teams", "genre"))
    DICT_LIST_TAGS = set(("credits", "pages"))
    PYCOUNTRY_TAGS = set(("country", "language"))
    DECIMAL_TAGS = set(
        ("alternate_issue", "alternate_issue_count", "issue", "issue_count", "price")
    )
    INT_TAGS = set(
        ("day", "last_mark", "month", "page_count", "volume", "volume_count", "year",)
    )
    IGNORE_COMPARE_TAGS = ("ext", "remainder")

    def __init__(self, string=None, path=None, metadata=None):
        """Initialize the metadata dict or parse it from a source."""
        self.metadata = {}
        self._page_filenames = []
        if metadata is not None:
            self.metadata = metadata
            return
        elif string is not None:
            self.from_string(string)
            return
        elif path is not None:
            self.from_file(path)
            return

    @staticmethod
    def _pycountry(tag, name, long_to_alpha2=True):
        if tag == "country":
            module = pycountry.countries
        elif tag == "language":
            module = pycountry.languages
        else:
            raise NotImplementedError(f"no pycountry module for {tag}")
        name = name.strip()
        # Language lookup fails for 'en' unless alpha_2 is specified.
        if len(name) == 2:
            obj = module.get(alpha_2=name)
        else:
            obj = module.lookup(name)

        if long_to_alpha2:
            return obj.alpha_2
        else:
            return obj.name

    @staticmethod
    def parse_decimal(num):
        """Fix half comic issue which are everywhere."""
        if isinstance(num, str):
            num = num.strip()
            num = num.replace("½", ".5")
            num = num.replace("1/2", ".5")
            num = num.replace(" ", "")
        elif not isinstance(num, (int, float)):
            raise ValueError(f"Can't convert {num} to a number.")
        return Decimal(num)

    @staticmethod
    def decimal_to_type(dec):
        """Return an integer if we can."""
        if dec % 1 == 0:
            return int(dec)
        else:
            return float(dec)

    def get_num_pages(self):
        """Get the number of pages."""
        return len(self._page_filenames)

    def set_page_names(self, archive_filenames):
        """Parse the filenames that are comic pages."""
        self._page_filenames = []
        for filename in archive_filenames:
            if IMAGE_EXT_RE.search(filename) is not None:
                self._page_filenames.append(filename)

    def get_pagename(self, index):
        """Get the filename of the page by index."""
        return self._page_filenames[index]

    def _add_credit(self, person, role):
        """Add a credit to the metadata."""
        credit = {"person": person.strip(), "role": role.strip()}

        if not credit["person"]:
            return

        if self.metadata.get("credits") is None:
            self.metadata["credits"] = []

        # if we've already added it, return
        for old_credit in self.metadata["credits"]:
            if (
                old_credit["person"].lower() == credit["person"].lower()
                and old_credit["role"].lower() == credit["role"].lower()
            ):
                return

        self.metadata["credits"].append(credit)

    def _get_cover_page_filenames_tagged(self):
        return set()

    def get_cover_page_filename(self):
        """Get filename of most likely coverpage."""
        cover_image = None
        coverlist = self._get_cover_page_filenames_tagged()
        if coverlist:
            cover_image = sorted(coverlist)[0]
        if not cover_image:
            cover_image = self.metadata.get("cover_image")
        if not cover_image and self._page_filenames:
            cover_image = self._page_filenames[0]
        return cover_image

    def get_pagenames_from(self, index_from):
        """Return a list of page filenames from the given index onward."""
        return self._page_filenames[index_from:]

    @classmethod
    def _compare_dict_list(cls, dl_a, dl_b):
        # There's probably a slicker generic way to do this
        for d_a in dl_a:
            match = False
            for d_b in dl_b:
                if d_a == d_b:
                    match = True
                    break
            if not match:
                print("Could not find:", d_a)
                return False
        return True

    @classmethod
    def _compare_metadatas(cls, md_a, md_b):
        for key, val in md_a.items():
            if key in cls.IGNORE_COMPARE_TAGS:
                continue
            if key in cls.DICT_LIST_TAGS:
                res = cls._compare_dict_list(val, md_b[key])
                if not res:
                    return False
                res = cls._compare_dict_list(md_b[key], val)
                if not res:
                    return False
            elif isinstance(val, set):
                for a, b in zip(sorted(val), sorted(md_b[key])):
                    if a != b:
                        print(f"{a} != {b}")
                        return False
            else:
                if md_b[key] != val:
                    print(f"{key}: {md_b[key]} != {val}")
                    return False
        return True

    def __eq__(self, obj):
        """== operator."""
        md = obj.metadata
        return self._compare_metadatas(md, self.metadata) and self._compare_metadatas(
            self.metadata, md
        )

    def synthesize_metadata(self, md_list):
        """Overlay the metadatas in precedence order."""
        for md in md_list:
            self.metadata.update(md)

        # synthesize credits
        # NOT "pages", only comes from cix anyway
        synth_dict_list = {}
        for md in md_list:
            dict_list = md.get("credits")
            if not isinstance(dict_list, list):
                continue
            if dict_list:
                synth_dict_list.update(dict_list)
        md["credits"] = synth_dict_list

        # synthesize sets of attributes
        for tag in self.STR_SET_TAGS:
            synth_str_set = set()
            for md in md_list:
                str_set = md.get(tag)
                if str_set:
                    synth_str_set.update(str_set)
            md[tag] = synth_str_set

    def compute_page_count(self):
        """Compute the page count from the number of images."""
        self.metadata["page_count"] = len(self._page_filenames)

    def compute_page_metadata(self, archive_filenames):
        """Rectify lots of metadatas."""
        self.set_page_names(archive_filenames)

        # Page Count
        if self.metadata.get("page_count") is None:
            self.compute_page_count()

        # Cover Image
        self.metadata["cover_image"] = self.get_cover_page_filename()

    def from_string(self, string):
        """Stub method."""
        raise NotImplementedError()

    def from_file(self, string):
        """Stub method."""
        raise NotImplementedError()

    # SCHEMA = {
    #    # CIX, CBI AND COMET
    #    "genre": str,
    #    "issue": int,
    #    "credits": [{"name": str, "role": str}],
    #    "language": str,  # two letter iso code
    #    "publisher": str,
    #    "series": str,
    #    "title": str,
    #    "volume": int,
    #    "year": int,
    #    "month": int,
    #    "day": int,
    #    # CIX AND CBI ONLY
    #    "comments": str,
    #    "issue_count": int,
    #    # CIX AND COMET ONLY
    #    "characters": set,
    #    "reading_direction": ReadingDirection,
    #    "maturity_rating": str,
    #    "format": str,
    #    # CBI AND COMET ONLY
    #    "critical_rating": str,
    #    # CIX ONLY
    #    "alternate_issue": int,
    #    "alternate_issue_count": int,
    #    "alternate_series": str,
    #    "black_and_white": bool,
    #    "imprint": str,
    #    "locations": set,
    #    "manga": bool,
    #    "notes": str,
    #    "pages": [{"page": int, "type": "PageType"}],
    #    "scan_info": str,
    #    "series_group": str,
    #    "story_arc": str,
    #    "teams": set,
    #    "web": str,
    #    # CBI_ONLY
    #    "country": str,
    #    "user_rating": str,
    #    "volume_count": int,
    #    "tags": set,
    #    # COMET_ONLY
    #    "cover_image": str,
    #    "description": str,
    #    "identifier": str,
    #    "last_mark": int,
    #    "price": float,
    #    "rights": str,
    #    "page_count": int,
    #    "is_version_of": str,
    #    # COMICBOX_ONLY
    #    "ext": str,
    #    "remainder": sr
    # }
    # SPECIAL_TAGS = (
    #    "credits",
    #    "language",
    #    "country",
    #    "date",
    #    "pages",
    #    "reading_direction",
    #    "manga",
    # )
    # BOOL_TAGS = ("black_and_white", "manga")
