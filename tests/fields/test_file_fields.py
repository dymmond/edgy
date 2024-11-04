import os
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy

import edgy
from edgy.exceptions import FileOperationError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)
models = edgy.Registry(database=database)


class MyModäl(edgy.StrictModel):
    ä: edgy.files.FieldFile = edgy.fields.FileField(null=True, column_name="a")

    class Meta:
        registry = models


class MyModel(edgy.StrictModel):
    file_field: edgy.files.FieldFile = edgy.fields.FileField(null=True)
    file_field_size: int = edgy.fields.IntegerField(null=True)

    class Meta:
        registry = models


class MyModelOverwrittenMetadata(edgy.StrictModel):
    file_field: edgy.files.FieldFile = edgy.fields.FileField(max_length=80, with_approval=True)
    file_field_metadata: str = edgy.fields.TextField()

    class Meta:
        registry = models


class MyModelApproval(edgy.StrictModel):
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
    model = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"!# /bin/sh", name="foo.sh")
    )
    # get cached
    assert model.__dict__["file_field"].__dict__["size"] == 10
    assert model.file_field.size == 10
    # distro specific
    assert model.file_field.metadata["mime"].endswith("x-sh")

    assert model.file_field.approved
    with model.file_field.open() as rob:
        assert rob.read() == b"!# /bin/sh"
    path = model.file_field.path
    assert os.path.exists(path)
    assert model.file_field.storage.exists(model.file_field.name)
    model.file_field.delete()
    assert os.path.exists(path)
    await model.save()
    assert not os.path.exists(path)


async def test_save_file_create_specal(create_test_database):
    model = await MyModäl.query.create(ä=edgy.files.ContentFile(b"!# /bin/sh", name="foo.sh"))
    # get cached
    assert model.__dict__["ä"].__dict__["size"] == 10
    assert model.ä.size == 10
    # distro specific
    assert model.ä.metadata["mime"].endswith("x-sh")

    assert model.ä.approved
    with model.ä.open() as rob:
        assert rob.read() == b"!# /bin/sh"
    path = model.ä.path
    assert os.path.exists(path)
    assert model.ä.storage.exists(model.ä.name)
    model.ä.delete()
    assert os.path.exists(path)
    await model.save()
    assert not os.path.exists(path)


async def test_save_file_available_overwrite(create_test_database):
    model1 = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    model2 = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    assert model1.file_field.name != model2.file_field.name
    await model2.delete()
    # file of model1 was not deleted
    assert os.path.exists(model1.file_field.path)
    path = model1.file_field.path
    # overwrite1
    model1.file_field.save(
        edgy.files.ContentFile(b"foo", name="foo.bytes"),
        name=model1.file_field.name,
        overwrite=True,
    )
    assert path == model1.file_field.path
    # overwrite2
    model1.file_field.save(edgy.files.ContentFile(b"foo", name="foo.bytes"), overwrite=True)
    assert model1.file_field.name == "foo.bytes"
    # reset
    model1.file_field.reset()


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
    path = model.file_field.path
    model.file_field.delete(instant=True)
    assert not os.path.exists(path)


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
    path = model.file_field.path
    model.file_field.delete(instant=True)
    assert not os.path.exists(path)
    # remove approval after save is set
    assert not model.file_field.approved


async def test_delete_queryset(create_test_database):
    model1 = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    model2 = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="foobar.bytes")
    )
    model3 = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="test.bytes")
    )
    seen = set()
    for obj in [model1, model2, model3]:
        assert obj.file_field.path not in seen
        seen.add(obj.file_field.path)
    assert await MyModel.query.delete() == 3
    for path in seen:
        assert not os.path.exists(path)


async def test_bulk_create(create_test_database):
    obj_list = [
        {"file_field": edgy.files.ContentFile(b"foo", name=f"{uuid4()}.bytes")},
        {"file_field": edgy.files.ContentFile(b"foo", name=f"{uuid4()}.bytes")},
        {"file_field": edgy.files.ContentFile(b"foo", name=f"{uuid4()}.bytes")},
    ]
    await MyModel.query.bulk_create(obj_list)
    for num, obj in enumerate(await MyModel.query.all()):
        assert obj_list[num]["file_field"].name in obj.file_field.name
        assert os.path.exists(obj.file_field.path)


async def test_bulk_create2(create_test_database, mocker):
    obj_list = [
        {},
        {},
        {},
    ]
    spy = mocker.spy(MyModel, "execute_post_save_hooks")
    await MyModel.query.bulk_create(obj_list)
    spy.assert_not_called()


async def test_update_bulk(create_test_database):
    model1 = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="foo.bytes")
    )
    model2 = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="foobar.bytes")
    )
    model3 = await MyModel.query.create(
        file_field=edgy.files.ContentFile(b"foo", name="test.bytes")
    )
    seen = set()
    for obj in [model1, model2, model3]:
        assert obj.file_field.path not in seen
        seen.add(obj.file_field.path)
        obj.file_field = None
    await MyModel.query.bulk_update([model1, model2, model3], fields=["file_field"])
    for path in seen:
        assert not os.path.exists(path)
