from pathlib import Path

import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)
models = edgy.Registry(database=database)

BASE_PATH = Path(__file__).absolute().parent.parent.parent


class MyModel(edgy.Model):
    ifield: edgy.files.ImageFieldFile = edgy.fields.ImageField(
        with_approval=False,
        null=True,
        mime_use_magic=True,
        image_formats=("JPEG",),
        approved_image_formats=("PNG",),
    )

    class Meta:
        registry = models


class MyModelApproval(edgy.Model):
    ifield: edgy.files.ImageFieldFile = edgy.fields.ImageField(
        with_approval=True, null=True, image_formats=("JPEG",), approved_image_formats=("PNG",)
    )

    class Meta:
        registry = models


@pytest.fixture()
async def create_test_database():
    async with database:
        await models.create_all()
        yield


async def test_save_file_create(create_test_database):
    for image in [
        BASE_PATH / "tests/images/mini_image.jpg",
        BASE_PATH / "tests/images/mini_image.png",
    ]:
        model = await MyModel.query.create(
            ifield=edgy.files.File(open(image, mode="rb"), name=str(image.name))
        )
        assert (
            model.ifield.metadata["mime"] == "image/jpeg"
            if str(image).endswith(".jpg")
            else "image/png"
        )
        assert model.ifield.metadata["height"] == 1
        assert model.ifield.metadata["width"] == 1


async def test_save_file_create_approved(create_test_database):
    for image in [
        BASE_PATH / "tests/images/mini_image.jpg",
        BASE_PATH / "tests/images/mini_image.png",
    ]:
        model = await MyModelApproval.query.create(
            ifield=edgy.files.File(open(image, mode="rb"), name=str(image.name))
        )
        if str(image).endswith(".png"):
            assert model.ifield.metadata["mime"] == "image/png"
            assert "height" not in model.ifield.metadata
            assert "width" not in model.ifield.metadata
            model.ifield.set_approved(True)
            await model.save(values={"ifield": model.ifield})
        else:
            assert model.ifield.metadata["mime"] == "image/jpeg"

        assert model.ifield.metadata["height"] == 1
        assert model.ifield.metadata["width"] == 1
