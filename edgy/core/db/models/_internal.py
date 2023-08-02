class DescriptiveMeta:
    """
    The `Meta` class used to configure each metadata of the model.
    Abstract classes are not generated in the database, instead, they are simply used as
    a reference for field generation.

    Usage:

    .. code-block:: python3

        class User(Model):
            ...

            class Meta:
                registry = models
                tablename = "users"

    """

    ...  # pragama: no cover
