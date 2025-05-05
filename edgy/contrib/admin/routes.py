from lilya.apps import Lilya
from lilya.routing import RoutePath

from edgy.contrib.admin.views import AdminDashboard

app = Lilya(
    routes=[
        RoutePath("/", handler=AdminDashboard, name="admin"),
    ]
)
