from __future__ import annotations
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


async def get_blogpost(id: int) -> BlogEntry | None:
    query = BlogEntry.query.order_by("-created", "-id")
    # order by is required for paginators
    paginator = CursorPaginator(
        query,
        page_size=1,
        next_item_attr="next_blogpost",
        previous_item_attr="last_blogpost",
    )
    try:
        created = (await query.get(id=id)).created
        # cursor must match order_by order
        page = await paginator.get_page(cursor=(created, id))
        if page.content:
            return page.content[0]
    except edgy.ObjectNotFound:
        ...
    # get first blogpost as fallback
    fallback_page = await paginator.get_page()
    if fallback_page.content:
        return fallback_page.content[0]
    return None
