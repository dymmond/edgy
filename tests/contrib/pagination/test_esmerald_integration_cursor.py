from collections.abc import AsyncGenerator
from typing import Optional

import pytest
from esmerald import Esmerald, Gateway, get, post
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

import edgy
from edgy.contrib.pagination import CursorPaginator
from edgy.core.marshalls import Marshall
from edgy.core.marshalls.config import ConfigMarshall
from edgy.testing.client import DatabaseTestClient
from edgy.testing.factory import ModelFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database))

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    async with models:
        yield
    if not database.drop:
        await models.drop_all()


class BlogEntryBase(edgy.Model):
    id: int = edgy.fields.BigIntegerField(autoincrement=True, primary_key=True)
    title: str = edgy.fields.CharField(max_length=100)
    content: str = edgy.fields.TextField()

    class Meta:
        abstract = True


class BlogEntry(BlogEntryBase):
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
    next_cursor: Optional[int]
    pages: int


async def _get_blogpost(item: int) -> Optional[BlogEntry]:
    # order by is required for paginators
    paginator = CursorPaginator(
        BlogEntry.query.order_by("-id"),
        page_size=1,
        next_item_attr="next",
        previous_item_attr="last",
    )
    page = await paginator.get_page(item)
    if page.content:
        return page.content[0]
    return None

@get("/blog/item/{item}")
async def get_blogpost(item: int) -> Optional[BlogEntry]:
    return await _get_blogpost(item)


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
    return BlogPage(**p.model_dump(), pages=amount)


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
    return BlogPage(**p.model_dump(), pages=amount)


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
    return BlogPage(**p.model_dump(), pages=amount)


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
    return BlogPage(**p.model_dump(), pages=amount)


@post("/create")
async def create_blog_entry(data: BlogEntryMarshall) -> BlogEntryMarshall:
    await data.save()
    return data


@pytest.fixture()
def app():
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


@pytest.fixture()
async def async_client(app) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_pagination_misc(async_client):
    factory = BlogEntryFactory()
    for _ in range(100):
        response = await async_client.post("/create", json=factory.build().model_dump())
        assert response.status_code == 201
    page1 = (await async_client.get("/")).json()
    assert len(page1["content"]) == 30
    assert page1["content"][0]["id"] == 100
    assert page1["content"][0]["next"]["id"] == 99
    assert page1["content"][1]["last"]["id"] == 100
    assert page1["pages"] == 4
    assert page1["next_cursor"] == 71

    response = await async_client.get(f"/blog/nextpage/{page1['next_cursor']}")
    page2 = response.json()
    assert len(page2["content"]) == 30
    assert page2["content"][0]["id"] == 70
    assert page2["pages"] == 4

    response = await async_client.get(f"/blog/nextpage/{page2['next_cursor']}")
    page3 = response.json()
    assert len(page3["content"]) == 30
    assert page3["content"][0]["id"] == 40
    assert page3["pages"] == 4

    response = await async_client.get(f"/blog/nextpage/{page3['next_cursor']}")
    page4 = response.json()
    assert len(page4["content"]) == 10
    assert page4["content"][0]["id"] == 10
    assert page4["pages"] == 4
    assert page4["next_cursor"] == 1

    # reverse
    response = await async_client.get(f"/blog/lastpage/{page2['next_cursor']}")
    page2_1 = response.json()
    assert page2_1["content"][0]["id"] == 70
    assert page2_1["content"][-1]["id"] == page2["content"][-1]["id"]
    assert page2_1["pages"] == 4

    response = await async_client.get(f"/blog/lastpage/{page1['next_cursor']}")
    page1_1 = response.json()
    assert len(page1_1["content"]) == 30
    assert page1_1["content"][0]["id"] == 100
    assert page1_1["content"][-1]["id"] == page1["content"][-1]["id"]
    assert page1_1["pages"] == 4
    assert page1_1["next_cursor"] == 100

    assert page2_1["next_cursor"] == page1["next_cursor"]


async def test_pagination_search(async_client):
    factory = BlogEntryFactory()
    for i in range(50):
        response = await async_client.post(
            "/create", json=factory.build(overwrites={"title": "___" + "t" * i}).model_dump()
        )
        assert response.status_code == 201
    page1 = (await async_client.post("/search", json={"string": "___tt"})).json()
    assert len(page1["content"]) == 30
    assert page1["pages"] == 2

    page2 = (
        await async_client.post(
            "/search", json={"string": "___tt", "cursor": page1["next_cursor"]}
        )
    ).json()
    assert len(page2["content"]) == 18
    assert page2["pages"] == 2


async def test_pagination_get(async_client):
    factory = BlogEntryFactory()
    for _ in range(100):
        response = await async_client.post("/create", json=factory.build().model_dump())
        assert response.status_code == 201
    (await _get_blogpost(32)).model_dump_json()
    response = await async_client.get("/blog/item/32")
    item = response.json()
    assert item.get("next", None)
    assert item.get("last", None)
    assert item.get("id", None)
    assert item["next"].get("id", None)
    assert item["last"].get("id", None)
