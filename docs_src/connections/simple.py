from contextlib import asynccontextmanager
from esmerald import Esmerald

from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


@asynccontextmanager
async def lifespan(app: Esmerald):
    async with models:
        yield


app = Esmerald(
    routes=[...],
    lifespan=lifespan,
)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(app=app, registry=registry))
