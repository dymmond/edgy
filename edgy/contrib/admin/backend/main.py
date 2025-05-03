from lilya.apps import ChildLilya, Lilya
from lilya.routing import Include, Path

from edgy.contrib.admin.backend.api import (
    create_route,
    delete_route,
    list_route,
    model_schema,
    retrieve_route,
    update_route,
)

admin_group_app = ChildLilya(
    routes=[
        Path(path="/models/{model_name}/schema", handler=model_schema, methods=["GET"]),
        Path(path="/models/{model_name}", handler=list_route, methods=["GET"]),
        Path(path="/models/{model_name}", handler=create_route, methods=["POST"]),
        Path(path="/models/{model_name}/{pk}", handler=retrieve_route, methods=["GET"]),
        Path(path="/models/{model_name}/{pk}", handler=update_route, methods=["PUT"]),
        Path(path="/models/{model_name}/{pk}", handler=delete_route, methods=["DELETE"]),
    ]
)

admin_app = Lilya(routes=[Include(path="/admin", app=admin_group_app)])
