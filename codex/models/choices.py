"""Choices for fields."""

from collections.abc import Mapping
from enum import Enum, _EnumDict
from typing import cast

from comicbox.enums.comicbox import FileTypeEnum, ReadingDirectionEnum
from django.db.models import Choices, TextChoices
from django.db.models.enums import ChoicesType


def _prepare_text_choices_class_dict(class_name: str) -> _EnumDict:
    """Class dict."""
    return ChoicesType.__prepare__(class_name, (TextChoices,))


def _create_text_choices_class(
    class_name: str, cls_dict: _EnumDict
) -> type[TextChoices]:
    """Create the metaclass and cast it into the proper type."""
    new_cls = ChoicesType(class_name, (TextChoices,), cls_dict)
    return cast("type[TextChoices]", new_cls)


def text_choices_from_enum(
    enum_cls: type[Enum], class_name: str = ""
) -> type[TextChoices]:
    """Create TextChoices from an enum."""
    if not class_name:
        class_name = enum_cls.__name__.removesuffix("Enum") + "Choices"

    cls_dict = _prepare_text_choices_class_dict(class_name)
    for member in enum_cls:
        cls_dict[member.name] = member.value
    return _create_text_choices_class(class_name, cls_dict)


def text_choices_from_map(choices_map: Mapping, class_name: str) -> type[TextChoices]:
    """Create TextChoices from an Mapping."""
    cls_dict = _prepare_text_choices_class_dict(class_name)
    for name, value in choices_map.items():
        cls_dict[name] = value
    return _create_text_choices_class(class_name, cls_dict)


def text_choices_from_string(string: str, class_name: str) -> type[TextChoices]:
    """Create TextChoices from an enum."""
    cls_dict = _prepare_text_choices_class_dict(class_name)
    for c in string:
        cls_dict[c.upper()] = c
    return _create_text_choices_class(class_name, cls_dict)


def max_choices_len(choices: type[Choices]):
    """Return the maximum possible size for a Choice's key."""
    if not choices.choices:
        return 0
    return max(len(choice[0]) for choice in choices.choices)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]


FileTypeChoices = text_choices_from_enum(FileTypeEnum)
ReadingDirectionChoices = text_choices_from_enum(ReadingDirectionEnum)
