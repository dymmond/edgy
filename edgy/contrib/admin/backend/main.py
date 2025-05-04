from lilya.apps import ChildLilya, Lilya
from lilya.middleware.base import DefineMiddleware
from lilya.middleware.cors import CORSMiddleware
from lilya.routing import Include, Path
from lilya.staticfiles import StaticFiles

from edgy.contrib.admin.backend.api import (
    create,
    delete,
    list_all,
    list_registered_models,
    model_schema,
    retrieve,
    update,
)

admin_group_app = ChildLilya(
    routes=[
        Path(path="/models/{model_name}/schema", handler=model_schema, methods=["GET"]),
        Path(path="/models/{model_name}", handler=list_all, methods=["GET"]),
        Path(path="/models/{model_name}", handler=create, methods=["POST"]),
        Path(path="/models/{model_name}/{pk}", handler=retrieve, methods=["GET"]),
        Path(path="/models/{model_name}/{pk}", handler=update, methods=["PUT"]),
        Path(path="/models/{model_name}/{pk}", handler=delete, methods=["DELETE"]),
        Path(path="/models", handler=list_registered_models, methods=["GET"]),
    ]
)

admin_app = Lilya(routes=[
    Include(path="/api/admin", app=admin_group_app),
    Include(path="/", app=StaticFiles(directory="static", html=True))
],
middleware=[
        DefineMiddleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ], )
