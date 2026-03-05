# SQLAlchemy Compatibility Mode

Edgy already supports SQLAlchemy-style expressions via `Model.columns.<name>`.

For progressive migrations from legacy SQLAlchemy models, you can opt in to
class-attribute compatibility so `Model.<name>` resolves to SQLAlchemy columns.

## Enable Per Model

```python
import edgy
import sqlalchemy


class Workspace(edgy.SQLAlchemyModelMixin, edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=255)

    class Meta:
        registry = models


statement = sqlalchemy.select(Workspace.id).where(Workspace.id == 1)
```

## Enable Once On An Abstract Base

If many models need this mode, declare it once on an abstract base model:

```python
class SACompatBase(edgy.SQLAlchemyModelMixin, edgy.StrictModel):
    class Meta:
        abstract = True


class Workspace(SACompatBase):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=255)

    class Meta:
        registry = models
```

Concrete subclasses inherit the compatibility behavior automatically.

## What Works

On opted-in concrete models:

```python
sqlalchemy.select(Workspace.id)
sqlalchemy.select(Workspace.id).where(Workspace.id == some_value)
sqlalchemy.select(Workspace.id).order_by(Workspace.id)
```

Foreign keys are exposed as scalar aliases using SQLAlchemy-style names:

```python
# for `owner = edgy.ForeignKey(User, ...)`
Workspace.owner_id
```

## What Does Not Work

Relationship collections and reverse relations are not scalar columns:

* Many-to-many fields (for example `Workspace.tags`)
* Reverse relationship fields
* RefForeignKey helper fields

For these, continue using Edgy relationship/query APIs.

## Compatibility Notes

* This mode is explicit and opt-in only.
* Non-opted-in models keep existing behavior (`Model.id` still raises `AttributeError`).
* Existing Edgy query patterns keep working (`Model.columns.<name>`, kwargs filters, `Q`, etc.).

## FAQ

### Can I enable this once in an abstract base model?

Yes.

```python
class SACompatBase(edgy.SQLAlchemyModelMixin, edgy.StrictModel):
    class Meta:
        abstract = True


class Workspace(SACompatBase):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=255)

    class Meta:
        registry = models
```

All concrete subclasses inherit the compatibility mode. You do not need to
repeat `SQLAlchemyModelMixin` on every child model.

### Does this change normal Edgy query behavior?

No.

You can keep writing Edgy queries exactly as before:

```python
await Workspace.query.filter(name__icontains="acme")
await Workspace.query.filter(owner__name__icontains="john")
await Workspace.query.filter(edgy.Q(name__startswith="A") | edgy.Q(name__startswith="B"))
```

Compatibility mode only adds SQLAlchemy Core style class-attribute access for
opted-in concrete models:

```python
sqlalchemy.select(Workspace.id).where(Workspace.id == workspace_id)
```
