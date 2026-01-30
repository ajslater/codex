"""Choices for fields."""

from collections.abc import Mapping
from enum import Enum

from comicbox.enums.comicbox import FileTypeEnum, ReadingDirectionEnum
from django.db.models import Choices, TextChoices
from django.db.models.enums import (
    ChoicesType,  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-import]
)


def text_choices_from_enum(
    enum_cls: type[Enum], class_name: str = ""
) -> type[TextChoices]:
    """Create TextChoices from an enum."""
    if not class_name:
        class_name = enum_cls.__name__.removesuffix("Enum") + "Choices"

    cls_dict = ChoicesType.__prepare__(class_name, (TextChoices,))

    for member in enum_cls:
        cls_dict[member.name] = member.value

    return ChoicesType(class_name, (TextChoices,), cls_dict)


def text_choices_from_map(choices_map: Mapping, class_name: str) -> type[TextChoices]:
    """Create TextChoices from an Mapping."""
    cls_dict = ChoicesType.__prepare__(class_name, (TextChoices,))

    for name, value in choices_map.items():
        cls_dict[name] = value

    return ChoicesType(class_name, (TextChoices,), cls_dict)


def text_choices_from_string(string: str, class_name: str) -> type[TextChoices]:
    """Create TextChoices from an enum."""
    cls_dict = ChoicesType.__prepare__(class_name, (TextChoices,))

    for c in string:
        cls_dict[c.upper()] = c

    return ChoicesType(class_name, (TextChoices,), cls_dict)


def max_choices_len(choices: type[Choices]):
    """Return the maximum possible size for a Choice's key."""
    if not choices.choices:
        return 0
    return max(len(choice[0]) for choice in choices.choices)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]


FileTypeChoices = text_choices_from_enum(FileTypeEnum)
ReadingDirectionChoices = text_choices_from_enum(ReadingDirectionEnum)
