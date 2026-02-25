"""Performance benchmarks for edgy ORM core operations."""

import datetime
import uuid
from enum import Enum

import pytest

import edgy
from edgy.core.db import fields

database = edgy.Database("sqlite:///benchmarks.db")
models = edgy.Registry(database=database)


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class SimpleModel(edgy.StrictModel):
    id = fields.IntegerField(primary_key=True, autoincrement=True)
    name = fields.CharField(max_length=100)
    is_active = fields.BooleanField(default=False)

    class Meta:
        registry = models


class ComplexModel(edgy.StrictModel):
    id = fields.IntegerField(primary_key=True, autoincrement=True)
    uuid = fields.UUIDField(null=True)
    created = fields.DateTimeField(default=datetime.datetime.now, with_timezone=False)
    created_day = fields.DateField(default=datetime.date.today)
    data = fields.JSONField(default=dict)
    description = fields.CharField(null=True, max_length=255)
    huge_number = fields.BigIntegerField(default=0)
    price = fields.DecimalField(max_digits=9, decimal_places=2, null=True)
    status = fields.ChoiceField(StatusEnum, default=StatusEnum.DRAFT)
    value = fields.FloatField(null=True)

    class Meta:
        registry = models


class UserModel(edgy.StrictModel):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    name = fields.CharField(null=True, max_length=16)
    email = fields.EmailField(null=True, max_length=256)
    url = fields.URLField(null=True, max_length=2048)

    class Meta:
        registry = models


# -- Model instantiation benchmarks --


@pytest.mark.benchmark
def test_simple_model_instantiation():
    """Benchmark creating a simple model instance."""
    for _ in range(100):
        SimpleModel(name="test", is_active=True)


@pytest.mark.benchmark
def test_complex_model_instantiation():
    """Benchmark creating a complex model instance with many fields."""
    for _ in range(100):
        ComplexModel(
            description="A benchmark test product",
            huge_number=9999999,
            value=123.456,
            status=StatusEnum.RELEASED,
        )


@pytest.mark.benchmark
def test_user_model_instantiation():
    """Benchmark creating a user model instance with validated fields."""
    for _ in range(100):
        UserModel(
            name="Benchmark",
            email="bench@example.com",
            url="https://example.com",
        )


# -- Schema generation benchmarks --


@pytest.mark.benchmark
def test_simple_model_json_schema():
    """Benchmark JSON schema generation for a simple model."""
    for _ in range(100):
        SimpleModel.model_json_schema()


@pytest.mark.benchmark
def test_complex_model_json_schema():
    """Benchmark JSON schema generation for a complex model."""
    for _ in range(100):
        ComplexModel.model_json_schema()


# -- Serialization benchmarks --


@pytest.mark.benchmark
def test_simple_model_dump():
    """Benchmark model serialization to dict."""
    instance = SimpleModel(name="test", is_active=True)
    for _ in range(100):
        instance.model_dump()


@pytest.mark.benchmark
def test_complex_model_dump():
    """Benchmark complex model serialization to dict."""
    instance = ComplexModel(
        description="A benchmark test product",
        huge_number=9999999,
        value=123.456,
        status=StatusEnum.RELEASED,
    )
    for _ in range(100):
        instance.model_dump()


@pytest.mark.benchmark
def test_simple_model_dump_json():
    """Benchmark model serialization to JSON string."""
    instance = SimpleModel(name="test", is_active=True)
    for _ in range(100):
        instance.model_dump_json()


@pytest.mark.benchmark
def test_complex_model_dump_json():
    """Benchmark complex model serialization to JSON string."""
    instance = ComplexModel(
        description="A benchmark test product",
        huge_number=9999999,
        value=123.456,
        status=StatusEnum.RELEASED,
    )
    for _ in range(100):
        instance.model_dump_json()
