"""A class to encapsulate CoMet data."""
from decimal import Decimal
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ElementTree
from xml.etree.ElementTree import SubElement

from .comic_xml import ComicXml


class CoMet(ComicXml):
    """CoMet Metadata."""

    FILENAME = "comet.xml"
    ROOT_TAG = "comet"

    # http://www.denvog.com/comet/comet-specification/
    XML_TAGS = {
        "title": "title",
        "description": "description",
        "series": "series",
        "issue": "issue",
        "volume": "volume",
        "publisher": "publisher",
        # date is special
        "genre": "genre",
        # character transforms into a list
        "isVersionOf": "is_version_of",
        "price": "price",
        "format": "format",
        "language": "language",  # alpha2
        "rating": "maturity_rating",
        "rights": "rights",
        "identifier": "identifier",
        "pages": "page_count",
        "coverImage": "cover_image",
        "lastMark": "last_mark",
        "readingDirection": "reading_direction",
    }
    CREDIT_TAGS = {
        "creator": set(["creator"]),
        "writer": ComicXml.CREDIT_TAGS["Writer"],
        "penciller": ComicXml.CREDIT_TAGS["Penciller"],
        "editor": ComicXml.CREDIT_TAGS["Editor"],
        "coverDesigner": ComicXml.CREDIT_TAGS["Cover"],
        "letterer": ComicXml.CREDIT_TAGS["Letterer"],
        "inker": ComicXml.CREDIT_TAGS["Inker"],
        "colorist": ComicXml.CREDIT_TAGS["Colorist"],
    }
    TWOPLACES = Decimal("0.01")

    def _from_xml_tags(self, root):
        for from_tag, to_tag in self.XML_TAGS.items():
            element = root.find(from_tag)
            if element is None or element.text is None:
                continue
            val = element.text.strip()
            if not val:
                continue
            if to_tag == "reading_direction":
                val = self.ReadingDirection.parse(val)
                if not val:
                    continue
            if to_tag in self.INT_TAGS:
                val = int(val)
            elif to_tag == "price":
                val = Decimal(val).quantize(self.TWOPLACES)
            elif to_tag in self.DECIMAL_TAGS:
                val = self.parse_decimal(val)
            elif to_tag in self.PYCOUNTRY_TAGS:
                val = self._pycountry(to_tag, val)
                if not val:
                    continue
            self.metadata[to_tag] = val

    def _from_xml_credits(self, root):
        for role in self.CREDIT_TAGS.keys():
            for element in root.findall(role):
                self._add_credit(element.text, role)

    def _from_xml_date(self, root):
        node = root.find("date")
        if node is None:
            return
        parts = node.text.strip().split("-")
        if len(parts) > 0:
            self.metadata["year"] = int(parts[0])
        if len(parts) > 1:
            self.metadata["month"] = int(parts[1])
        if len(parts) > 2:
            self.metadata["day"] = int(parts[2])

    def _from_xml_characters(self, root):
        chars = set()
        for element in root.findall("character"):
            chars.add(element.text.strip())
        if chars:
            self.metadata["characters"] = chars

    def _from_xml(self, tree):
        root = self._get_xml_root(tree)
        self._from_xml_tags(root)
        self._from_xml_credits(root)
        self._from_xml_characters(root)
        self._from_xml_date(root)

    def _to_xml_root(self):
        root = Element(self.ROOT_TAG)
        root.attrib["xmlns:comet"] = "http://www.denvog.com/comet/"
        root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XmlSchema-instance"
        root.attrib[
            "xsi:schemaLocation"
        ] = "http://www.denvog.com http://www.denvog.com/comet/comet.xsd"
        return root

    def _to_xml_tags(self, root):
        for tag, comicbox_tag in self.XML_TAGS.items():
            if tag == "pages":
                continue
            val = self.metadata.get(comicbox_tag)
            if val is None:
                val = ""
            if comicbox_tag == "price":
                val = self.decimal_to_type(val)
            SubElement(root, tag).text = str(val)

    def _to_xml_characters(self, root):
        characters = self.metadata.get("characters", [])
        for character in sorted(characters):
            SubElement(root, "character").text = character

    def _to_xml_date(self, root):
        date_str = ""
        year = self.metadata.get("year")
        if year:
            date_str = str(year).zfill(4)
            month = self.metadata.get("month")
            if month:
                date_str += "-" + str(month).zfill(2)
                day = self.metadata.get("day")
                if day:
                    date_str += "-" + str(day).zfill(2)
        SubElement(root, "date").text = date_str

    def _to_xml_credits(self, root):
        for credit in self.metadata["credits"]:
            for key, synonyms in self.CREDIT_TAGS.items():
                if credit["role"].lower() in synonyms:
                    SubElement(root, key).text = credit["person"]

    def _to_xml_page_count(self, root):
        page_count = self.metadata.get("page_count")
        if page_count is None:
            page_count = self.get_num_pages()
        SubElement(root, "pages").text = str(page_count)

    def _to_xml(self):
        root = self._to_xml_root()
        self._to_xml_tags(root)
        self._to_xml_characters(root)
        self._to_xml_date(root)
        self._to_xml_credits(root)
        self._to_xml_page_count(root)
        tree = ElementTree(root)
        return tree
