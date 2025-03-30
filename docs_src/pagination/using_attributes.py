from __future__ import annotations
import edgy
from edgy.contrib.pagination import Paginator
from edgy import Registry

models = Registry(database="sqlite:///db.sqlite")


class BlogEntry(edgy.Model):
    title: str = edgy.fields.CharField(max_length=100)
    content: str = edgy.fields.CharField(max_length=100)
    created = edgy.fields.DateTimeField(auto_now_add=True)

    class Meta:
        registry = models


async def get_blogpost(id: int) -> BlogEntry | None:
    # order by is required for paginators
    paginator = Paginator(
        User.query.order_by("-created", "-id"),
        page_size=30,
        next_item_attr="next_blogpost",
        previous_item_attr="last_blogpost",
    )
    # this is maybe a bit imperformant
    async for page in paginator.paginate():
        for blogpost in page:
            if blogpost.id == id:
                return blogpost
    # get first page
    fallback_page = await paginator.get_page()
    if fallback_page.content:
        return fallback_page.content[0]
    return None
