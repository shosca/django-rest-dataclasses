# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import unittest

from django.core.exceptions import ValidationError

from rest_dataclasses.utils import _django_to_drf


class TestUtils(unittest.TestCase):
    def test_django_to_drf(self):
        self.assertEqual(_django_to_drf("hello"), "hello")
        self.assertEqual(_django_to_drf(["hello"]), ["hello"])
        self.assertEqual(_django_to_drf({"hello": "world"}), {"hello": "world"})
        self.assertEqual(_django_to_drf(ValidationError("hello")), ["hello"])
        self.assertEqual(_django_to_drf(ValidationError({"hello": "world"})), {"hello": ["world"]})
