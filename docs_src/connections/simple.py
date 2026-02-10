from contextlib import asynccontextmanager
from ravyn import Ravyn

from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


@asynccontextmanager
async def lifespan(app: Ravyn):
    async with models:
        yield


app = Ravyn(
    routes=[...],
    lifespan=lifespan,
)
# now required
monkay.evaluate_settings()
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(app=app, registry=models))
