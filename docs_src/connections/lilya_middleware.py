from lilya.apps import Lilya
from lilya.middleware import DefineMiddleware

from edgy import Registry
from edgy.contrib.lilya.middleware import EdgyMiddleware

models = Registry(database="sqlite:///db.sqlite", echo=True)


app = Lilya(routes=[...], middleware=[DefineMiddleware(EdgyMiddleware, registry=models)])
