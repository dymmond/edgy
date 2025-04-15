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


async def get_last_blogpost_page():
    # order by is required for paginators
    paginator = Paginator(BlogEntry.query.order_by("-created", "-id"), page_size=30)
    return await paginator.get_page(-1), await paginator.get_amount_pages()


async def get_blogpost_pages():
    # order by is required for paginators
    paginator = Paginator(BlogEntry.query.order_by("-created", "-id"), page_size=30)
    return [page async for page in paginator.paginate()]


async def search_blogpost(title: str, page: int):
    # order by is required for paginators
    paginator = Paginator(
        BlogEntry.query.filter(title__icontains=title).order_by("-created", "-id"), page_size=30
    )
    return await paginator.get_page(page), await paginator.get_amount_pages()
