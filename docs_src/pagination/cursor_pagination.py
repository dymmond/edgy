from __future__ import annotations

import datetime
import edgy
from edgy.contrib.pagination import CursorPaginator
from edgy import Registry

models = Registry(database="sqlite:///db.sqlite")


class BlogEntry(edgy.Model):
    title: str = edgy.fields.CharField(max_length=100)
    content: str = edgy.fields.CharField(max_length=100)
    created = edgy.fields.DateTimeField(auto_now_add=True)

    class Meta:
        registry = models


async def get_blogpost(cursor: datetime.datetime) -> BlogEntry | None:
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.order_by("-created"),
        page_size=1,
        next_item_attr="next_blogpost",
        previous_item_attr="last_blogpost",
    )
    page = await paginator.get_page(cursor)
    if page.content:
        return page.content[0]
    return None


async def get_next_blogpost_page(cursor: datetime.datetime):
    # order by is required for paginators
    paginator = CursorPaginator(BlogEntry.query.order_by("-created"), page_size=30)
    return await paginator.get_page(cursor), await paginator.get_amount_pages()


async def get_last_blogpost_page(cursor: datetime.datetime):
    # order by is required for paginators
    paginator = CursorPaginator(BlogEntry.query.order_by("-created"), page_size=30)
    return await paginator.get_page(cursor, backward=True), await paginator.get_amount_pages()


async def get_blogpost_pages(after: datetime.datetime | None = None):
    # order by is required for paginators
    paginator = CursorPaginator(BlogEntry.query.order_by("-created"), page_size=30)
    return [page async for page in paginator.paginate(start_cursor=after)]


async def search_blogpost(title: str, cursor: datetime.datetime | None = None):
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.filter(title__icontains=title).order_by("-created"), page_size=30
    )
    return await paginator.get_page(cursor), await paginator.get_amount_pages()
