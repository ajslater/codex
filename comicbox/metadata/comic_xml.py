"""XML Metadata parser superclass."""
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

from comicbox.metadata.comic_base import ComicBaseMetadata


class ComicXml(ComicBaseMetadata):
    """XML Comic Metadata super class."""

    XML_HEADER = '<?xml version="1.0"?>\n'
    CREDIT_TAGS = {
        "Colorist": set(["colorist", "colourist", "colorer", "colourer"]),
        "Cover": set(
            ["cover", "covers", "coverartist", "cover artist", "coverDesigner"]
        ),
        "Editor": set(["editor"]),
        "Inker": set(["inker", "artist", "finishes"]),
        "Letterer": set(["letterer"]),
        "Penciller": set(["artist", "penciller", "penciler", "breakdowns"]),
        "Writer": set(["writer", "plotter", "scripter", "creator"]),
    }

    @property
    def ROOT_TAG(self):  # noqa: N802
        raise NotImplementedError()

    def _get_xml_root(self, tree):
        root = tree.getroot()
        if root.tag != self.ROOT_TAG:
            raise ValueError(f"Not a {self.ROOT_TAG} XMLTree")
        return root

    def _from_xml(self, tree):
        raise NotImplementedError()

    def from_string(self, xml_str):
        """Parse an xml string into metadata."""
        try:
            element = ElementTree.fromstring(xml_str)
            tree = ElementTree.ElementTree(element)
            self._from_xml(tree)
        except ParseError as exc:
            print(exc)

    def from_file(self, filename):
        """Read metadata from a file."""
        tree = ElementTree.parse(filename)
        self._from_xml(tree)

    def _to_xml(self):
        raise NotImplementedError()

    def to_string(self):
        """Return metadata as an xml string."""
        tree = self._to_xml()
        root = self._get_xml_root(tree)
        tree_str = ElementTree.tostring(root).decode()
        xml_str = self.XML_HEADER + tree_str
        return xml_str

    def to_file(self, filename):
        """Write metadata to a file."""
        tree = self._to_xml()
        tree.write(filename, encoding="utf-8")
