# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import dataclasses as da

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import SimpleTestCase

from rest_framework import fields
from rest_framework.exceptions import ValidationError

from rest_dataclasses.serializers import DataclassSerializer


@da.dataclass
class User:
    id: int = da.field(default=None)
    name: str = da.field(default=None)
    email: str = da.field(default=None)


@da.dataclass
class Point:
    x: int = da.field(default=None)
    y: int = da.field(default=None)


@da.dataclass
class Line:
    a: Point = da.field(default=None)
    b: Point = da.field(default=None)


class TestModelSerializer(SimpleTestCase):
    def test_happy_path(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = "__all__"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": 1, "name": "shosca", "email": "some@email.com"})

    def test_bad_fields(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = "id,name"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        with self.assertRaisesMessage(TypeError, 'The `fields` option must be a list or tuple or "__all__". Got str.'):
            serializer.is_valid(raise_exception=True)

    def test_bad_exclude(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                exclude = "id,name"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        with self.assertRaisesMessage(TypeError, "The `exclude` option must be a list or tuple. Got str."):
            serializer.is_valid(raise_exception=True)

    def test_exclude(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                exclude = ("name",)

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": 1, "name": None, "email": "some@email.com"})

    def test_read_only_fields_bad(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = "__all__"
                read_only_fields = "name"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        with self.assertRaisesMessage(TypeError, "The `read_only_fields` option must be a list or tuple. Got str."):
            serializer.is_valid(raise_exception=True)

    def test_read_only_fields(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = "__all__"
                read_only_fields = ("name",)

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": 1, "name": None, "email": "some@email.com"})

    def test_with_fields(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = ("id", "name")

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid(raise_exception=True)
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
            serializer.is_valid(raise_exception=True)

    def test_custom_setter(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = ("name",)

            def set_name(self, instance, field_name, value):
                instance.name = value

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": None, "name": "shosca", "email": None})

    def test_declared_field(self):
        class Serializer(DataclassSerializer):
            name = fields.CharField(required=False)

            class Meta:
                model = User
                fields = "__all__"

        serializer = Serializer(data={"id": 1, "name": "shosca", "email": "some@email.com"})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": 1, "name": "shosca", "email": "some@email.com"})

    def test_nested_create(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = Line
                fields = "__all__"

        serializer = Serializer(data={"a": {"x": 1, "y": 2}, "b": {"x": 3, "y": 4}})
        serializer.is_valid(raise_exception=True)
        line = serializer.save()

        self.assertDictEqual(da.asdict(line), {"a": {"x": 1, "y": 2}, "b": {"x": 3, "y": 4}})

    def test_nested_inplace_update(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = Line
                fields = "__all__"

        instance = Line(a=Point(x=1, y=2), b=Point(x=3, y=4))

        serializer = Serializer(instance, data={"a": {"x": 5, "y": 6}, "b": {"x": 7, "y": 8}}, partial=True)
        serializer.is_valid(raise_exception=True)
        line = serializer.save()

        self.assertIs(instance, line)
        self.assertIs(instance.a, line.a)
        self.assertIs(instance.b, line.b)
        self.assertDictEqual(da.asdict(line), {"a": {"x": 5, "y": 6}, "b": {"x": 7, "y": 8}})

    def test_nested_inplace_with_create(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = Line
                fields = "__all__"

        instance = Line()

        serializer = Serializer(instance, data={"a": {"x": 1, "y": 2}, "b": {"x": 3, "y": 4}}, partial=True)
        serializer.is_valid(raise_exception=True)
        line = serializer.save()

        self.assertIs(instance, line)
        self.assertIsInstance(line.a, Point)
        self.assertIsInstance(line.b, Point)
        self.assertDictEqual(da.asdict(line), {"a": {"x": 1, "y": 2}, "b": {"x": 3, "y": 4}})

    def test_nested_none(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = Line
                fields = "__all__"
                extra_kwargs = {"a": {"allow_null": True}, "b": {"allow_null": True}}

        instance = Line(a=Point(x=1, y=2), b=Point(x=3, y=4))

        serializer = Serializer(instance, data={"a": None, "b": None}, partial=True)
        serializer.is_valid(raise_exception=True)
        line = serializer.save()

        self.assertIs(instance, line)
        self.assertIsNone(line.a)
        self.assertIsNone(line.b)
        self.assertDictEqual(da.asdict(line), {"a": None, "b": None})

    def test_nested_none_allow_create_false(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = Line
                fields = "__all__"
                extra_kwargs = {"a": {"allow_null": False, "allow_create": False}, "b": {"allow_null": False}}

        instance = Line()

        serializer = Serializer(instance, data={"a": {}, "b": {}}, partial=True)
        serializer.is_valid(raise_exception=True)

        with self.assertRaises(ValidationError):
            serializer.save()

    def test_create_star_source(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = ["name"]

        class StarSerializer(DataclassSerializer):
            user = Serializer(source="*")

            class Meta:
                model = User
                fields = ["id", "user"]

        serializer = StarSerializer(data={"user": {"name": "shosca"}, "id": 1})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        self.assertDictEqual(da.asdict(user), {"id": 1, "name": "shosca", "email": None})

    def test_create_source_not_in_validated_data(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = Line
                fields = "__all__"

        serializer = Serializer(data={})
        serializer.is_valid(raise_exception=True)
        line = serializer.save()

        self.assertDictEqual(da.asdict(line), {"a": None, "b": None})

    def test_validation_error_on_save(self):
        class Serializer(DataclassSerializer):
            class Meta:
                model = User
                fields = ["name"]

            def perform_update(self, instance, validated_data, errors):
                raise DjangoValidationError("test")

        class StarSerializer(DataclassSerializer):
            user = Serializer(source="*")

            class Meta:
                model = User
                fields = ["id", "user"]

        serializer = StarSerializer(data={"user": {"name": "shosca"}, "id": 1})
        serializer.is_valid(raise_exception=True)

        with self.assertRaises(ValidationError):
            serializer.save()
