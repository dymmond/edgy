from edgy.conf.global_settings import EdgySettings


class AppTestSettings(EdgySettings):
    """
    Settings for running tests.
    """

    orm_concurrency_enabled: bool = True
    orm_concurrency_limit: int | None = 10
    orm_row_prefetch_limit: int | None = 5
    orm_clauses_concurrency_limit: int | None = 5
