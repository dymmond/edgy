from databasez import Database as Databasez  # noqa
from databasez import DatabaseURL as DatabaseURL  # noqa


class Database(Databasez):
    """
    An abstraction on the top of the EncodeORM databases.Database object.

    This object allows to pass also a configuration dictionary in the format of

    ```python
    DATABASEZ_CONFIG = {
        "connection": {
            "credentials": {
                "scheme": 'sqlite', "postgres"...
                "host": ...,
                "port": ...,
                "user": ...,
                "password": ...,
                "database": ...,
                "options": {
                    "driver": ...
                    "ssl": ...
                }
            }
        }
    }
    ```
    """

    ...
