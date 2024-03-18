"""Serializer Base class for inheritable metaclass."""

from rest_framework.serializers import ModelSerializer, SerializerMetaclass


class BaseModelSerializer(ModelSerializer):
    """BaseModel Serializer for inheritance."""

    class Meta(SerializerMetaclass):  # type: ignore
        """Use explicit metaclass instead of python 3 method."""

        abstract = True
