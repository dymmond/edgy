from typing import Optional
from esmerald import Esmerald, Gateway, get, post
from pydantic import BaseModel

import edgy
from edgy.testing.factory import ModelFactory
from edgy.contrib.pagination import CursorPaginator
from edgy.core.marshalls import Marshall
from edgy.core.marshalls.config import ConfigMarshall

models = edgy.Registry(database="DATABASE_URL")


class BlogEntryBase(edgy.Model):
    # explicit required, otherwise the id is not found because the model is abstract
    id: int = edgy.fields.BigIntegerField(autoincrement=True, primary_key=True)
    title: str = edgy.fields.CharField(max_length=100)
    content: str = edgy.fields.TextField()

    class Meta:
        abstract = True


class BlogEntry(BlogEntryBase):
    # get rid of nested next and last when serializing otherwise we have loops
    next: Optional["BlogEntryBase"] = None
    last: Optional["BlogEntryBase"] = None

    class Meta:
        registry = models


class BlogEntryMarshall(Marshall):
    marshall_config = ConfigMarshall(model=BlogEntry, exclude=["next", "last"])


class BlogEntryFactory(ModelFactory):
    class Meta:
        model = BlogEntry


class BlogPage(BaseModel):
    content: list[BlogEntry]
    is_first: bool
    is_last: bool
    current_cursor: Optional[int]
    next_cursor: Optional[int]
    pages: int


@get("/blog/item/{id}")
async def get_blogpost(id: int) -> Optional["BlogEntry"]:
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.order_by("-id"),
        page_size=1,
        next_item_attr="next",
        previous_item_attr="last",
    )
    page = await paginator.get_page(id)
    if page.content:
        return page.content[0]
    return None


@get("/")
async def index() -> BlogPage:
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.order_by("-id"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="last",
    )
    p, amount = await paginator.get_page(), await paginator.get_amount_pages()
    # model_dump would also serialize the BlogEntries, so use __dict__ which should be also faster
    return BlogPage(**p.__dict__, pages=amount)


@get("/blog/nextpage/{advance_cursor}")
async def get_next_blogpost_page(advance_cursor: int) -> BlogPage:
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.order_by("-id"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="last",
    )
    p, amount = await paginator.get_page(advance_cursor), await paginator.get_amount_pages()
    # model_dump would also serialize the BlogEntries, so use __dict__ which should be also faster
    return BlogPage(**p.__dict__, pages=amount)


@get("/blog/lastpage/{reverse_cursor}")
async def get_last_blogpost_page(reverse_cursor: int) -> BlogPage:
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.order_by("-id"),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="last",
    )
    p, amount = (
        await paginator.get_page(reverse_cursor, backward=True),
        await paginator.get_amount_pages(),
    )
    # model_dump would also serialize the BlogEntries, so use __dict__ which should be also faster
    return BlogPage(**p.__dict__, pages=amount)


@post("/search")
async def search_blogpost(string: str, cursor: Optional[int] = None) -> BlogPage:
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.or_({"title__icontains": string}, {"content__icontains": string}).order_by(
            "-id"
        ),
        page_size=30,
        next_item_attr="next",
        previous_item_attr="last",
    )
    p, amount = await paginator.get_page(cursor), await paginator.get_amount_pages()
    # model_dump would also serialize the BlogEntries, so use __dict__ which should be also faster
    return BlogPage(**p.__dict__, pages=amount)


@post("/create")
async def create_blog_entry(data: BlogEntryMarshall) -> BlogEntryMarshall:
    await data.save()
    return data


def get_application():
    app = Esmerald(
        routes=[
            Gateway(handler=create_blog_entry),
            index,
            get_blogpost,
            search_blogpost,
            get_last_blogpost_page,
            get_next_blogpost_page,
        ],
        on_startup=[models.__aenter__],
        on_shutdown=[models.__aexit__],
    )
    return app
