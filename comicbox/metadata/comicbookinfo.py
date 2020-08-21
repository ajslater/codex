"""A class to encapsulate the ComicBookInfo data."""
from datetime import datetime

from ..version import VERSION
from .comic_json import ComicJSON


class ComicBookInfo(ComicJSON):
    """Comic Book Info metadata."""

    ROOT_TAG = "ComicBookInfo/1.0"
    JSON_KEYS = {
        "series": "series",
        "title": "title",
        "issue": "issue",
        "genre": "genre",
        "publisher": "publisher",
        "publicationMonth": "month",
        "publicationYear": "year",
        "numberOfIssues": "issue_count",
        "comments": "comments",
        "genre": "genre",
        "volume": "volume",
        "numberOfVolumes": "volume_count",
        "language": "language",
        "country": "country",
        "rating": "critical_rating",
        "tags": "tags",
        "credits": "credits",
        "pages": "page_count",
    }
    FILENAME = "ComicBookInfo.json"

    def _from_json_tags(self, root):
        for from_key, to_key in self.JSON_KEYS.items():
            val = root.get(from_key)
            if val is None:
                continue

            if to_key in self.INT_TAGS:
                val = int(val)
            if to_key in self.DECIMAL_TAGS:
                val = self.parse_decimal(val)
            elif to_key in self.PYCOUNTRY_TAGS:
                val = self._pycountry(to_key, val)
                if not val:
                    continue
            elif isinstance(val, str):
                val = val.strip()
                if not val:
                    continue
            elif isinstance(val, list):
                # credits and tags
                if len(val) == 0:
                    continue
            self.metadata[to_key] = val

    def _from_json_credits(self, root):
        credits = root.get("credits")
        for credit in credits:
            self._add_credit(credit.get("person"), credit.get("role"))

    def _from_json(self, json_obj):
        """Parse metadata from string."""
        root = json_obj[self.ROOT_TAG]
        self._from_json_tags(root)
        self._from_json_credits(root)

    def _to_json(self):
        """Create the dictionary that we will convert to JSON text."""
        cbi = {}
        json_obj = {
            "appID": f"Comicbox/{VERSION}",
            "lastModified": str(datetime.now()),
            self.ROOT_TAG: cbi,
        }

        for json_key, md_key in self.JSON_KEYS.items():
            val = self.metadata.get(md_key)
            if not val:
                continue
            elif md_key in self.DECIMAL_TAGS:
                if val % 1 == 0:
                    val = int(val)
                else:
                    val = float(val)
            elif md_key in self.PYCOUNTRY_TAGS:
                val = self._pycountry(md_key, val, False)
                if not val:
                    continue
            cbi[json_key] = val

        return json_obj
