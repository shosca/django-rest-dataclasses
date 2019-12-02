# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import copy
import dataclasses as da
import enum
import itertools
from collections import OrderedDict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import fields, serializers
from rest_framework.exceptions import ValidationError

from rest_enumfield import EnumField

from .utils import django_to_drf_validation_error


class DataclassSerializer(serializers.Serializer):

    serializer_field_mapping = {
        int: fields.IntegerField,
        str: fields.CharField,
        date: fields.DateField,
        datetime: fields.DateTimeField,
        Decimal: fields.DecimalField,
        time: fields.TimeField,
        timedelta: fields.DurationField,
        enum.Enum: EnumField,
    }

    def __init__(self, *args, **kwargs):
        self.allow_nested_updates = kwargs.pop("allow_nested_updates", True)
        self.allow_create = kwargs.pop("allow_create", True)
        super().__init__(*args, **kwargs)

    @property
    def model(self):
        assert hasattr(self.Meta, "model"), 'Class {serializer_class} missing "Meta.model" attribute'.format(
            serializer_class=self.__class__.__name__
        )
        return self.Meta.model

    def get_fields(self):

        declared_fields = copy.deepcopy(self._declared_fields)
        dataclass_fields = {f.name: f for f in da.fields(self.model)}
        depth = getattr(self.Meta, "depth", 0)

        if depth is not None:
            assert depth >= 0, "'depth' may not be negative."
            assert depth <= 5, "'depth' may not be greater than 5."

        field_names = self.get_field_names(declared_fields, dataclass_fields)

        extra_kwargs = self.get_extra_kwargs()

        fields = OrderedDict()
        for field_name in field_names:
            if field_name in declared_fields:
                fields[field_name] = declared_fields[field_name]
                continue

            extra_field_kwargs = extra_kwargs.get(field_name, {})
            source = extra_field_kwargs.get("source", "*")
            if source == "*":
                source = field_name

            fields[field_name] = self.build_field(source, dataclass_fields, self.model, depth)

        return fields

    def get_field_names(self, declared_fields, dataclass_fields):

        fields = getattr(self.Meta, "fields", None)
        exclude = getattr(self.Meta, "exclude", None)

        if fields and fields != serializers.ALL_FIELDS and not isinstance(fields, (list, tuple)):
            raise TypeError(
                'The `fields` option must be a list or tuple or "__all__". ' "Got %s." % type(fields).__name__
            )

        if exclude and not isinstance(exclude, (list, tuple)):
            raise TypeError("The `exclude` option must be a list or tuple. Got %s." % type(exclude).__name__)

        assert not (fields and exclude), (
            "Cannot set both 'fields' and 'exclude' options on "
            "serializer {serializer_class}.".format(serializer_class=self.__class__.__name__)
        )

        assert not (fields is None and exclude is None), (
            "Creating a DataclassSerializer without either the 'fields' attribute "
            "is not disallowed. Add an explicit fields = '__all__' to the "
            "{serializer_class} serializer.".format(serializer_class=self.__class__.__name__),
        )

        if fields == serializers.ALL_FIELDS:
            fields = None

        if fields is not None:
            # Ensure that all declared fields have also been included in the
            # `Meta.fields` option.

            # Do not require any fields that are declared in a parent class,
            # in order to allow serializer subclasses to only include
            # a subset of fields.
            required_field_names = set(declared_fields)
            for cls in self.__class__.__bases__:
                required_field_names -= set(getattr(cls, "_declared_fields", []))

            for field_name in required_field_names:
                assert field_name in fields, (
                    "The field '{field_name}' was declared on serializer "
                    "{serializer_class}, but has not been included in the "
                    "'fields' option.".format(field_name=field_name, serializer_class=self.__class__.__name__)
                )
            return fields

        # Use the default set of field names if `Meta.fields` is not specified.
        fields = self.get_default_field_names(declared_fields, dataclass_fields)

        if exclude is not None:
            # If `Meta.exclude` is included, then remove those fields.
            for field_name in exclude:
                assert field_name not in self._declared_fields, (
                    "Cannot both declare the field '{field_name}' and include "
                    "it in the {serializer_class} 'exclude' option. Remove the "
                    "field or, if inherited from a parent serializer, disable "
                    "with `{field_name} = None`.".format(
                        field_name=field_name, serializer_class=self.__class__.__name__
                    )
                )

                assert field_name in fields, (
                    "The field '{field_name}' was included on serializer "
                    "{serializer_class} in the 'exclude' option, but does "
                    "not match any model field.".format(field_name=field_name, serializer_class=self.__class__.__name__)
                )
                fields.remove(field_name)

        return fields

    def get_default_field_names(self, declared_fields, dataclass_fields):
        return list(dataclass_fields)

    def get_extra_kwargs(self):
        extra_kwargs = copy.deepcopy(getattr(self.Meta, "extra_kwargs", {}))

        read_only_fields = getattr(self.Meta, "read_only_fields", None)
        if read_only_fields is not None:
            if not isinstance(read_only_fields, (list, tuple)):
                raise TypeError(
                    "The `read_only_fields` option must be a list or tuple. "
                    "Got %s." % type(read_only_fields).__name__
                )
            for field_name in read_only_fields:
                kwargs = extra_kwargs.get(field_name, {})
                kwargs["read_only"] = True
                extra_kwargs[field_name] = kwargs

        else:
            assert not hasattr(self.Meta, "readonly_fields"), (
                "Serializer `%s.%s` has field `readonly_fields`; "
                "the correct spelling for the option is `read_only_fields`."
                % (self.__class__.__module__, self.__class__.__name__)
            )

        return extra_kwargs

    def build_field(self, field_name, dataclass_fields, model, depth):
        field_info = dataclass_fields[field_name]

        for typ in field_info.type.mro():
            if typ in self.serializer_field_mapping:
                field_type = self.serializer_field_mapping[typ]
                return self.build_standard_field(field_type, field_name, field_info)

        target_model = field_info.type
        if getattr(target_model, "__origin__", None) == list:
            return self.build_nested_list_field(field_name, field_info, depth)

        if getattr(target_model, "__origin__", None) == dict:
            return self.build_nested_dict_field(field_name, field_info, depth)

        return self.build_nested_field(field_name, field_info, depth)

    def build_standard_field(self, field_type, field_name, field_info):
        return field_type(**self.get_kwargs_for_field(field_info))

    def build_nested_field(self, field_name, field_info, nested_depth):
        target_model = field_info.type

        nested_serializer = self.build_nested_serializer_class(target_model, nested_depth)

        return type(target_model.__name__ + "Serializer", (nested_serializer,), {})(
            **self.get_kwargs_for_nested_field(field_info)
        )

    def build_nested_list_field(self, field_name, field_info, nested_depth):
        target_model = field_info.type
        if getattr(target_model, "__origin__", None) == list:
            assert len(target_model.__args__) == 1, "Nested list fields can only have one generic type"
            target_model = target_model.__args__[0]

        kwargs = self.get_kwargs_for_nested_field(field_info)
        kwargs["many"] = True

        nested_serializer = self.build_nested_serializer_class(target_model, nested_depth)
        return type(target_model.__name__ + "Serializer", (nested_serializer,), {})(**kwargs)

    def build_nested_dict_field(self, field_name, field_info, nested_depth):
        target_model = field_info.type
        if getattr(target_model, "__origin__", None) == dict:
            assert len(target_model.__args__) == 2, "Nested dict fields can only have one generic type"
            assert target_model.__args__[0] is str, "Nested dict key can only be string"
            target_model = target_model.__args__[1]

        kwargs = self.get_kwargs_for_nested_field(field_info)

        child_field = None
        if target_model in self.serializer_field_mapping:
            child_field = self.serializer_field_mapping[target_model](allow_null=True)
        else:
            child_field = type(
                target_model.__name__ + "Serializer",
                (self.build_nested_serializer_class(target_model, nested_depth),),
                {},
            )(**kwargs)

        assert target_model is not None, "Couldn't figure out nested dict value type"

        return fields.DictField(child=child_field, required=False)

    def build_nested_serializer_class(self, target_model, nested_depth):
        class NestedSerializer(self.__class__):
            class Meta:
                model = target_model
                fields = "__all__"  # TODO: figure out what fields
                depth = max(0, nested_depth - 1)

        return NestedSerializer

    def get_kwargs_for_field(self, field_info):
        kwargs = {"required": False}

        if enum.Enum in field_info.type.mro():
            kwargs["choices"] = field_info.type

        extra_kwargs = self.get_extra_kwargs()
        kwargs.update(extra_kwargs.get(field_info.name, {}))

        return kwargs

    def get_kwargs_for_nested_field(self, field_info):
        kwargs = {"required": False}

        extra_kwargs = self.get_extra_kwargs()
        kwargs.update(extra_kwargs.get(field_info.name, {}))

        return kwargs

    def update_attribute(self, instance, field, value):
        field_setter = getattr(self, "set_" + field.field_name, None)
        if field_setter:
            field_setter(instance, field.source, value)
        else:
            setattr(instance, field.source, value)

    def get_object(self, validated_data, instance=None):
        if validated_data is None:
            instance = None

        if instance is not None:
            return instance

        elif validated_data is not None and self.allow_create:
            return self.model()

        elif self.allow_null:
            return

        else:
            raise self.fail("required")

    def create(self, validated_data):
        if self.instance is None:
            # TODO: figure out required __init__ args here
            self.instance = self.model()

        return self.update(self.instance, validated_data)

    def update(self, instance, validated_data):
        errors = {}
        instance = self.perform_update(instance, validated_data, errors)

        if errors:
            raise ValidationError(errors)

        return instance

    def perform_update(self, instance, validated_data, errors):

        for field in self._writable_fields:
            try:
                if isinstance(field, DataclassSerializer):
                    if field.source == "*":
                        value = validated_data
                        child_instance = instance
                    else:
                        if field.source not in validated_data:
                            continue
                        value = validated_data.get(field.source)
                        child_instance = getattr(instance, field.source, None)
                        child_instance = field.get_object(value, child_instance)

                    if child_instance:
                        value = field.perform_update(child_instance, value, errors)
                    else:
                        value = child_instance

                elif isinstance(field, fields.DictField) and isinstance(field.child, DataclassSerializer):
                    value = {}
                    existing_value = getattr(instance, field.source, []) or {}
                    for key, item in validated_data.get(field.source, {}).items():
                        child_instance = field.child.get_object(item, existing_value.get(key))
                        if child_instance and (field.child.allow_create or field.child.allow_nested_updates):
                            v = field.child.perform_update(child_instance, item, errors)
                        else:
                            v = child_instance
                        if v:
                            value[key] = v

                elif isinstance(field, serializers.ListSerializer) and isinstance(field.child, DataclassSerializer):
                    value = []
                    existing_value = getattr(instance, field.source, []) or []

                    for item, child_instance in itertools.zip_longest(
                        validated_data.get(field.source, []), existing_value
                    ):
                        child_instance = field.child.get_object(item, child_instance)
                        if child_instance and (field.child.allow_create or field.child.allow_nested_updates):
                            v = field.child.perform_update(child_instance, item, errors)
                        else:
                            v = child_instance

                        if v:
                            value.append(v)

                else:
                    if field.source not in validated_data:
                        continue

                    value = validated_data.get(field.source)

                self.update_attribute(instance, field, value)

            except DjangoValidationError as e:
                errors.update(django_to_drf_validation_error(e).detail)

            except Exception as e:
                errors.setdefault(field.field_name, []).append(" ".join(map(str, e.args)))

        return instance
