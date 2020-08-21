"""A class to encapsulate ComicRack's ComicInfo.xml data."""
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ElementTree
from xml.etree.ElementTree import SubElement

from .comic_xml import ComicXml


class ComicInfoXml(ComicXml):
    """Comic Rack Metadata."""

    class PageType(object):
        """CIX Page Type Schema."""

        FRONT_COVER = "FrontCover"
        INNER_COVER = "InnerCover"
        ROUNDUP = "Roundup"
        STORY = "Story"
        ADVERTISEMENT = "Advertisement"
        EDITORIAL = "Editorial"
        LETTERS = "Letters"
        PREVIEW = "Preview"
        BACK_COVER = "BackCover"
        OTHER = "Other"
        DELETED = "Deleted"

    class MangaType(object):
        """CIX Manga Type."""

        YES = "Yes"
        YES_RTL = "YesRtl"
        NO = "No"
        YES_VALUES = (YES.lower(), YES_RTL.lower())

    FILENAME = "comicinfo.xml"
    ROOT_TAG = "ComicInfo"
    BW_YES_VALUES = ("yes", "true", "1")
    XML_TAGS = {
        "Number": "issue",
        "Series": "series",
        "Title": "title",
        "Year": "year",
        "Month": "month",
        "Day": "day",
        "Count": "issue_count",
        "Volume": "volume",
        "Publisher": "publisher",
        "Genre": "genre",
        "LanguageISO": "language",  # two letter in the lang list
        "AlternateNumber": "alternate_issue",
        "AlternateCount": "alternate_issue_count",
        "AlternateSeries": "alternate_series",
        "AgeRating": "maturity_rating",
        "Imprint": "imprint",
        "SeriesGroup": "series_group",
        "StoryArc": "story_arc",
        "Manga": "manga",  # type(MangaType),  # Yes, YesRTL, No
        "Format": "format",
        "BlackAndWhite": "black_and_white",
        # "Credits": "credits",
        "ScanInformation": "scan_info",
        "Notes": "notes",
        "Web": "web",
        "Characters": "characters",
        "Teams": "teams",
        "Locations": "locations",
        "Summary": "summary",
    }
    CREDIT_TAGS = {
        "Colorist": ComicXml.CREDIT_TAGS["Colorist"],
        "CoverArtist": ComicXml.CREDIT_TAGS["Cover"],
        "Editor": ComicXml.CREDIT_TAGS["Editor"],
        "Inker": ComicXml.CREDIT_TAGS["Inker"],
        "Letterer": ComicXml.CREDIT_TAGS["Letterer"],
        "Penciller": ComicXml.CREDIT_TAGS["Penciller"],
        "Writer": ComicXml.CREDIT_TAGS["Writer"],
    }

    def _from_xml_credits(self, root):
        for role in self.CREDIT_TAGS.keys():
            for element in root.findall(role):
                for name in element.text.split(","):
                    self._add_credit(name, role)

    def _from_xml_manga(self, tag, val):
        val = val.lower()
        if val == self.MangaType.YES_RTL.lower():
            self.metadata["reading_direction"] = self.ReadingDirection.RTL
        return val in self.MangaType.YES_VALUES

    def _from_xml_black_and_white(self, baw):
        return baw.lower() in self.BW_YES_VALUES

    def _from_xml_tags(self, root):
        for from_tag, to_tag in self.XML_TAGS.items():
            element = root.find(from_tag)
            if element is None or element.text is None:
                continue
            val = str(element.text).strip()
            if not val:
                continue

            if to_tag in self.INT_TAGS:
                val = int(val)
            if to_tag in self.DECIMAL_TAGS:
                val = self.parse_decimal(val)
            elif to_tag in self.STR_SET_TAGS:
                val = set([item.strip() for item in val.split(",")])
                if len(val) == 0:
                    continue
            # special bool tags
            elif to_tag == "black_and_white":
                val = self._from_xml_black_and_white(val)
            elif to_tag == "manga":
                val = self._from_xml_manga(to_tag, val)
            elif to_tag in self.PYCOUNTRY_TAGS:
                val = self._pycountry(to_tag, val)
                if not val:
                    continue
            self.metadata[to_tag] = val

    def _from_xml_pages(self, root):
        pages = root.find("Pages")
        if pages is not None:
            self.metadata["pages"] = []
            for page in pages.findall("Page"):
                self.metadata["pages"].append(page.attrib)

    def _from_xml(self, tree):
        root = self._get_xml_root(tree)
        self._from_xml_tags(root)
        self._from_xml_credits(root)
        self._from_xml_pages(root)

    def _to_xml_root(self):
        root = Element(self.ROOT_TAG)
        root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
        root.attrib["xmlns:xsd"] = "http://www.w3.org/2001/XMLSchema"
        return root

    def _to_xml_tags_black_and_white(self, val):
        return "Yes" if val in self.BW_YES_VALUES else "No"

    def _to_xml_manga(self, val):
        if val:
            if self.metadata["reading_direction"] == self.ReadingDirection.RTL:
                return self.MangaType.YES_RTL
            else:
                return self.MangaType.YES
        else:
            return self.MangaType.NO

    def _to_xml_tags(self, root):
        """Write tags to xml."""
        for xml_tag, md_key in self.XML_TAGS.items():
            val = self.metadata.get(md_key)
            if val:
                if xml_tag == "BlackAndWhite":
                    new_val = self._to_xml_tags_black_and_white(val)
                if xml_tag == "Manga":
                    new_val = self._to_xml_manga(val)
                if md_key in self.STR_SET_TAGS:
                    new_val = ",".join(sorted(val))
                else:
                    new_val = val
                SubElement(root, xml_tag).text = str(new_val)

    def _to_xml_pages(self, root):
        md_pages = self.metadata.get("pages")
        if md_pages:
            page_count = len(self.metadata["pages"])
            if page_count:
                pages = SubElement(root, "Pages")
                for page in self.metadata["pages"]:
                    SubElement(pages, "Page", attrib=page)
        else:
            page_count = self.get_num_pages()
        SubElement(root, "PageCount").text = str(page_count)

    def _to_xml_credits(self, root):
        consolidated_credits = {}
        # Extract credits and consolidate
        for credit in self.metadata["credits"]:
            for key, synonyms in self.CREDIT_TAGS.items():
                if credit["role"].lower() in synonyms:
                    cleaned_person = credit["person"].replace(",", "").strip()
                    if not cleaned_person:
                        continue
                    if key not in consolidated_credits:
                        consolidated_credits[key] = set()
                    consolidated_credits[key].add(cleaned_person)
        # write the consolidated tags to xml
        for tag, people in consolidated_credits.items():
            SubElement(root, tag).text = ", ".join(sorted(people))

    def _to_xml(self):
        """Translate comicbox metadata into a comicinfo xml tree."""
        root = self._to_xml_root()
        self._to_xml_tags(root)
        self._to_xml_pages(root)
        self._to_xml_credits(root)
        tree = ElementTree(root)
        return tree

    def _get_cover_page_filenames_tagged(self):
        coverlist = set()
        for page in self.metadata.get("pages", []):
            if page.get("Type") == self.PageType.FRONT_COVER:
                index = int(page["Image"])
                if index <= self.get_num_pages():
                    coverlist.add(self._page_filenames[index])
        return coverlist

    def compute_pages_tags(self, infolist):
        """Recompute the page tags with actual image sizes."""
        # Just store this integer data as strings becuase I don't
        # expect anyone will ever use it.
        new_pages = []
        index = 0
        old_pages = self.metadata.get("pages")
        front_cover_set = False
        for info in infolist:
            if old_pages and len(old_pages) > index:
                new_page = old_pages[index]
                if new_page.get("Type") == self.PageType.FRONT_COVER:
                    front_cover_set = True
            elif info.filename in self._page_filenames:
                new_page = {"Image": str(index)}
            else:
                continue
            new_page["ImageSize"] = str(info.file_size)
            new_pages.append(new_page)
            index += 1
        if not front_cover_set and len(new_pages) > 0:
            new_pages[0]["Type"] = self.PageType.FRONT_COVER
        self.metadata["pages"] = new_pages
