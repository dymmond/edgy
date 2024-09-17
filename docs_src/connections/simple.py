from contextlib import asynccontextmanager
from esmerald import Esmerald

from edgy import Registry

models = Registry(database="sqlite:///db.sqlite", echo=True)


@asynccontextmanager
async def lifespan(app: Esmerald):
    async with models:
        yield


app = Esmerald(
    routes=[...],
    lifespan=lifespan,
)
