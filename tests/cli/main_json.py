import os

import edgy
from edgy import Instance

models = edgy.Registry(
    database=os.environ["TEST_DATABASE"],
)


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    data = edgy.fields.JSONField(null=True, no_jsonb=os.environ.get("TEST_NO_JSONB") == "true")

    class Meta:
        registry = models


edgy.monkay.set_instance(Instance(registry=models))
