from typing import TYPE_CHECKING, Any

import sqlalchemy

import edgy  # noqa I100

if TYPE_CHECKING:  # pragma no cover
    pass


def or_(*args: Any, **kwargs: Any) -> Any:
    """
    Creates a SQL Alchemy OR clause for the expressions being passed.
    """
    return sqlalchemy.or_(*args, **kwargs)


def and_(*args: Any, **kwargs: Any) -> Any:
    """
    Creates a SQL Alchemy AND clause for the expressions being passed.
    """
    return sqlalchemy.and_(*args, **kwargs)


def not_(*args: Any, **kwargs: Any) -> Any:
    """
    Creates a SQL Alchemy NOT clause for the expressions being passed.
    """
    return sqlalchemy.not_(*args, **kwargs)
