import random
import string

import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.core.db.datastructures import Index
from edgy.testclient import DatabaseTestClient

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    return result_str


def test_raises_value_error_on_wrong_max_length():
    with pytest.raises(ValueError):

        class User(edgy.Model):
            name = edgy.CharField(max_length=255)
            title = edgy.CharField(max_length=255)

            class Meta:
                registry = models
                indexes = [Index(fields=["name", "title"], name=get_random_string(31))]


def test_raises_value_error_on_wrong_type_passed_fields():
    with pytest.raises(ValueError):

        class User(edgy.Model):
            name = edgy.CharField(max_length=255)
            title = edgy.CharField(max_length=255)

            class Meta:
                registry = models
                indexes = [Index(fields=2)]
