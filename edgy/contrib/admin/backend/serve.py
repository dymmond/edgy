from lilya.apps import Lilya
from lilya.routing import Include

from edgy.contrib.admin.backend.main import admin_app

app = Lilya(routes=[
    Include(path="/", app=admin_app),
])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("serve:app", host="0.0.0.0", port=8000, reload=True)
