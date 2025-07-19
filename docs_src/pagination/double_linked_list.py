from __future__ import annotations
import datetime
import edgy
from edgy.contrib.pagination import NumberedPaginator, CursorPaginator
from edgy import Registry

models = Registry(database="sqlite:///db.sqlite")


class BlogEntry(edgy.Model):
    title: str = edgy.fields.CharField(max_length=100)
    content: str = edgy.fields.CharField(max_length=100)
    created = edgy.fields.DateTimeField(auto_now_add=True)

    class Meta:
        registry = models


async def get_blogposts_with_partners() -> list[BlogEntry]:
    # order by is required for paginators
    paginator = NumberedPaginator(
        BlogEntry.query.order_by("-created", "-id"),
        page_size=0,
        next_item_attr="next_blogpost",
        previous_item_attr="last_blogpost",
    )
    return (await paginator.get_page()).content


async def get_blogposts_with_partners_after(after: datetime.datetime) -> list[BlogEntry]:
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.order_by("-created"),
        page_size=0,
        next_item_attr="next_blogpost",
        previous_item_attr="last_blogpost",
    )
    return (await paginator.get_page(after)).content
