"""Comic JSON superclass."""
import simplejson as json

from simplejson.errors import JSONDecodeError

from comicbox.metadata.comic_base import ComicBaseMetadata


class ComicJSON(ComicBaseMetadata):
    """JSON Comic Metadata class."""

    def _from_json(self, json_obj):
        raise NotImplementedError()

    def from_string(self, json_str):
        """Parse metadata from a JSON string."""
        try:
            json_str = json_str.strip()
            if not json_str:
                return
            json_obj = json.loads(json_str)
            self._from_json(json_obj)
        except JSONDecodeError as exc:
            print(exc)

    def from_file(self, filename):
        """Parse metadata from a JSON file."""
        with open(filename, "r") as json_file:
            self.from_string(json_file.read())

    def _to_json(self):
        raise NotImplementedError()

    def to_string(self):
        """Return metadata as a JSON string."""
        json_obj = self._to_json()
        json_str = json.dumps(json_obj)
        return json_str

    def to_file(self, filename):
        """Write metadata to a JSON file."""
        with open(filename, "w") as json_file:
            json_file.write(self.to_string())
