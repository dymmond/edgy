# Postgresql fields

Here are some postgres specific fields.

## PGArrayField

This field takes an sqlalchemy type and makes an array from it.

```python
from typing import Dict, Any
import sqlalchemy
import edgy


class MyModel(edgy.Model):
    data: list[str] = edgy.fields.PGArrayField(sqlalchemy.String(), default=list)
    ...

```
