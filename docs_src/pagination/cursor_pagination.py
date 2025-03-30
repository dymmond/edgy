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


async def get_last_blogpost_page():
    # order by is required for paginators
    paginator = CursorPaginator(User.query.order_by("-created"), page_size=30)
    return await paginator.get_page(reverse=True), await paginator.get_amount_pages()


async def get_next_blogpost_page(cursor: datetime.datetime):
    # order by is required for paginators
    paginator = CursorPaginator(User.query.order_by("-created"), page_size=30)
    return await paginator.get_page(cursor), await paginator.get_amount_pages()


async def get_last_blogpost_page(cursor: datetime.datetime):
    # order by is required for paginators
    paginator = CursorPaginator(User.query.order_by("-created"), page_size=30)
    return await paginator.get_page(cursor, reverse=True), await paginator.get_amount_pages()


async def get_blogpost_pages(after: datetime.datetime):
    # order by is required for paginators, CursorPaginator supports only one criteria
    paginator = CursorPaginator(User.query.order_by("-created"), page_size=30)
    return [page async for page in paginator.paginate(start_cursor=after)]


async def search_blogpost(title: str, cursor: datetime.datetime):
    # order by is required for paginators, CursorPaginator supports only one criteria
    paginator = CursorPaginator(
        User.query.filter(title__icontains=title).order_by("created", "id"), page_size=30
    )
    return await paginator.get_page(page), await paginator.get_amount_pages()
