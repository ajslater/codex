"""Comics field names variable."""
from codex.models import Comic

COMIC_M2M_FIELD_NAMES = set()
for field in Comic._meta.get_fields():
    if field.many_to_many and field.name != "folders":
        COMIC_M2M_FIELD_NAMES.add(field.name)
