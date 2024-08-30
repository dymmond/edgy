import os
from typing import Any

import pytest
import sqlalchemy

import edgy
from edgy.exceptions import FileOperationError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)
models = edgy.Registry(database=database)


class MyModel(edgy.Model):
    file_field: edgy.files.FieldFile = edgy.fields.FileField(null=True)
    file_field_size: int = edgy.fields.IntegerField(null=True)

    class Meta:
        registry = models


class MyModelOverwrittenMetadata(edgy.Model):
    file_field: edgy.files.FieldFile = edgy.fields.FileField(max_length=80, with_approval=True)
    file_field_metadata: str = edgy.fields.TextField()

    class Meta:
        registry = models


class MyModelApproval(edgy.Model):
    file_field: edgy.files.FieldFile = edgy.fields.FileField(
        with_approval=True, with_size=False, with_metadata=False
    )

    class Meta:
        registry = models


@pytest.fixture()
async def create_test_database():
    async with database:
        await models.create_all()
        yield


def test_field_specs():
    assert "id" in MyModel.pkcolumns
    assert "id" in MyModel.pknames
    assert len(MyModel.meta.fields["file_field"].composite_fields) == 3
    for key, val in MyModel.meta.fields["file_field"].composite_fields.items():
        assert val.owner is MyModel
        if key == "file_field":
            assert val.field_type is Any
            assert isinstance(val.column_type, sqlalchemy.String)
            assert val.column_type.length == 255
        elif key == "file_field_size":
            assert val.column_type.__class__ is sqlalchemy.Integer
        elif key == "file_field_metadata":
            assert val.column_type.__class__ is sqlalchemy.JSON


def test_field_specs_overwritten():
    assert "id" in MyModelOverwrittenMetadata.pkcolumns
    assert "id" in MyModelOverwrittenMetadata.pknames
    assert len(MyModelOverwrittenMetadata.meta.fields["file_field"].composite_fields) == 4
    for key, val in MyModelOverwrittenMetadata.meta.fields["file_field"].composite_fields.items():
        assert val.owner is MyModelOverwrittenMetadata
        if key == "file_field":
            assert val.field_type is Any
            assert isinstance(val.column_type, sqlalchemy.String)
            assert val.column_type.length == 80
        elif key == "file_field_size":
            assert val.column_type.__class__ is sqlalchemy.BigInteger
        elif key == "file_field_metadata":
            assert val.column_type.__class__ is sqlalchemy.Text
            assert val.field_type is str
        elif key == "file_field_approval":
            assert val.column_type.__class__ is sqlalchemy.Boolean


def test_field_specs_approval():
    assert "id" in MyModelApproval.pkcolumns
    assert "id" in MyModelApproval.pknames
    assert len(MyModelApproval.meta.fields["file_field"].composite_fields) == 2
    for key, val in MyModelApproval.meta.fields["file_field"].composite_fields.items():
        assert val.owner is MyModelApproval
        if key == "file_field":
            assert val.field_type is Any
            assert isinstance(val.column_type, sqlalchemy.String)
            assert val.column_type.length == 255
        elif key == "file_field_approval":
            assert val.column_type.__class__ is sqlalchemy.Boolean


async def test_save_file_create(create_test_database):
    model = await MyModel.query.create(file_field=edgy.files.ContentFile(b"foo", name="foo.bytes"))
    assert model.__dict__["file_field"].__dict__["size"] == 3
    assert model.file_field.approved
    with model.file_field.open() as rob:
        assert rob.read() == b"foo"
        path = model.file_field.path
    assert os.path.exists(path)
    assert model.file_field.storage.exists(model.file_field.name)
    model.file_field.delete()
    assert os.path.exists(path)
    await model.save()
    assert not os.path.exists(path)


async def test_save_file_reject_replace(create_test_database):
    model = await MyModelOverwrittenMetadata.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    assert not model.file_field.approved
    with pytest.raises(FileOperationError):
        model.file_field.delete()
    model.file_field.save(b"bar", name="k")
    await model.save()
    with model.file_field.open() as rob:
        assert rob.read() == b"bar"


async def test_save_file_approved(create_test_database):
    model = await MyModelApproval.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    assert not model.file_field.approved
    model = await MyModelApproval.query.first()
    assert not model.file_field.approved
    model.file_field.set_approved(True)
    assert model.file_field.approved
    await model.save()
    model = await MyModelApproval.query.first()
    assert model.file_field.approved
