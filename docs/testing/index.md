# Testing

Testing in Edgy is split into two practical tools:

* [DatabaseTestClient](./test-client.md) for isolated database tests.
* [ModelFactory](./model-factory.md) for fast model stubbing with faker-backed values.

## Which One Should You Use?

* Use **DatabaseTestClient** when you need integration tests that hit a real database engine.
* Use **ModelFactory** when you need fast, readable test data generation for unit/integration tests.
* Use both together when you want realistic fixtures plus isolated DB lifecycle.

## Recommended Learning Flow

1. Start with [Test Client](./test-client.md) and make one CRUD integration test pass.
2. Add [ModelFactory](./model-factory.md) to remove repetitive fixture boilerplate.
3. Review [Connection Management](../connection.md) if you see lifecycle warnings.
4. Keep [Troubleshooting](../troubleshooting.md) nearby for environment and DB isolation issues.

## Minimal Test Client Setup

```python
import edgy
from edgy.testclient import DatabaseTestClient

database = DatabaseTestClient(
    "postgresql+asyncpg://postgres:postgres@localhost:5432/my_db",
    drop_database=True,
)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


async def test_query_roundtrip():
    async with database:
        async with models:
            # run your model operations here
            ...
```

This pattern keeps tests isolated and avoids touching your development database.

## Minimal ModelFactory Setup

```python
import edgy
from edgy.testing.factory import ModelFactory, FactoryField


# assuming User model already exists
class UserFactory(ModelFactory):
    class Meta:
        model = User

    language = FactoryField(callback="language_code")
```

With this, you can quickly build model instances and override only what matters in each test.

## See Also

* [Test Client](./test-client.md)
* [ModelFactory](./model-factory.md)
* [Connection Management](../connection.md)
* [Troubleshooting](../troubleshooting.md)
