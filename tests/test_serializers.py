# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import dataclasses as da

from rest_dataclasses.serializers import DataclassSerializer

from django.test import SimpleTestCase

from rest_framework import fields


@da.dataclass
class User:
    id: int = da.field(default=None)
    name: str = da.field(default=None)
    email: str = da.field(default=None)


class TestModelSerializer(SimpleTestCase):
    def test_happy_path(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = "__all__"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid()
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": 1, "name": "shosca", "email": "some@email.com"})

    def test_bad_fields(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = "id,name"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        with self.assertRaisesMessage(TypeError, 'The `fields` option must be a list or tuple or "__all__". Got str.'):
            serializer.is_valid()

    def test_bad_exclude(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                exclude = "id,name"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        with self.assertRaisesMessage(TypeError, "The `exclude` option must be a list or tuple. Got str."):
            serializer.is_valid()

    def test_with_fields(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = ("id", "name")

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid()
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": 1, "name": "shosca", "email": None})

    def test_with_missing_declared_field(self):
        class Serializer(DataclassSerializer):
            name = fields.CharField(required=False)

            class Meta:
                model = User
                fields = ("id", "email")

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        with self.assertRaisesMessage(
            AssertionError,
            "The field 'name' was declared on serializer Serializer, but has not been included in the 'fields' option.",
        ):
            serializer.is_valid()

    def test_declared_field(self):
        class Serializer(DataclassSerializer):
            name = fields.CharField(required=False)

            class Meta:
                model = User
                fields = "__all__"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid()
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": 1, "name": "shosca", "email": "some@email.com"})
