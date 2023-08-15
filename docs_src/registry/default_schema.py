from edgy import Database, Registry

database = Database("<YOUR-CONNECTION-STRING>")
registry = Registry(database=database)


async def get_default_schema() -> str:
    """
    Returns the default schema name of the given database
    """
    await registry.schema.get_default_schema()
