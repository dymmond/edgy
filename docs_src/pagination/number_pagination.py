from __future__ import annotations

import edgy
from edgy.contrib.pagination import NumberedPaginator
from edgy import Registry

models = Registry(database="sqlite:///db.sqlite")


class BlogEntry(edgy.Model):
    title: str = edgy.fields.CharField(max_length=100)
    content: str = edgy.fields.CharField(max_length=100)
    created = edgy.fields.DateTimeField(auto_now_add=True)

    class Meta:
        registry = models


async def get_numbered_paginator(page: int = 1, size: int = 10) -> dict:
    queryset = await BlogEntry.query.all()
    paginator = NumberedPaginator(queryset, page, size)
    return paginator.get_paginated_response()
