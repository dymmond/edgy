# Declarative models

If you need to generate a `declarative_model` from SQLAlchemy ORM type, you can simply call
`Model.declarative()`. Example, `User.declarative()`. This will automatically generate the
declarative model type for you.

```python hl_lines="23"
{!> ../docs_src/models/declarative/example.py !}
```

Be mindful that when using a declarative model if you have a [ForeignKey](./relationships.md#foreignkey) or
a [OneToOneField](./relationships.md#onetoone), Edgy will generate a [SQLAlchemy Relationship](https://docs.sqlalchemy.org/en/20/orm/relationships.html)
for you automatically and append `relation` at the end of the declared field.

Let us see an example.

```python hl_lines="20-29"
{!> ../docs_src/models/declarative/fk_relationship.py !}
```

As you can see, the model `Thread` has two foreign keys, `sender` and `receiver`. In a normal
Edgy ORM operation, this remains as is but if you generate the `declarative()` model from Edgy
then it will create automatically the following fields:

* `sender_relation`
* `receiver_relation`

For the core use of Edgy, this doesn't do anything and does not impact anything but if you
are using a third party package like [Esmerald Admin](https://esmerald-admin.tarsild.io) where it
uses the Edgy declarative models, then this makes the whole difference to interact with.

!!! Info
    In general you don't need to worry about this. This is mainly used by third parties that need
    to use declarative models from Edgy, like [Esmerald Admin](https://esmerald-admin.tarsild.io).
