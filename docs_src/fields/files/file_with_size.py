import os
from typing import Any
from sqlalchemy import func

import edgy
from edgy.exceptions import FileOperationError

models = edgy.Registry(database=...)


class Document(edgy.StrictModel):
    file: edgy.files.FieldFile = edgy.fields.FileField(with_size=True)

    class Meta:
        registry = models


async def main():
    document = await Document.query.create(file=b"abc")
    document2 = await Document.query.create(file=b"aabc")
    document3 = await Document.query.create(file=b"aabcc")

    sum_of_size = await Document.database.fetch_val(func.sum(Document.columns.file_size))
