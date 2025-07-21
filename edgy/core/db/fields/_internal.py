import ipaddress
from typing import Any

import sqlalchemy


class IPAddress(sqlalchemy.TypeDecorator):
    """
    A SQLAlchemy custom type for handling IP addresses (IPv4 and IPv6).

    This `TypeDecorator` maps Python's `ipaddress.IPv4Address` and
    `ipaddress.IPv6Address` objects to database string types,
    specifically leveraging PostgreSQL's native INET type for optimized storage
    and querying. For other dialects, it falls back to a VARCHAR.
    """

    impl: Any = sqlalchemy.String
    # Indicate that this type decorator is safe to be cached, as its
    # behavior does not depend on per-instance state.
    cache_ok: bool = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        """
        Loads the appropriate database-specific type implementation based on the dialect.

        For PostgreSQL, it uses the native `INET` type. For other dialects, it
        defaults to a `VARCHAR` with a length sufficient to store IPv6 addresses.

        Args:
            dialect: The SQLAlchemy dialect being used for the database connection.

        Returns:
            The dialect-specific type descriptor.
        """
        # Check if the current dialect is PostgreSQL or postgres.
        if dialect.name not in {"postgres", "postgresql"}:
            # If not PostgreSQL, return a SQLAlchemy String type with a length of 45,
            # which is sufficient for IPv6 addresses.
            return dialect.type_descriptor(sqlalchemy.String(length=45))
        # If it is PostgreSQL, return the PostgreSQL INET type for efficient IP address storage.
        return dialect.type_descriptor(sqlalchemy.dialects.postgresql.INET())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        """
        Processes the Python value before it's bound to a database parameter.

        Converts `ipaddress.IPv4Address` or `ipaddress.IPv6Address` objects
        into their string representation for storage in the database.
        `None` values are passed through unchanged.

        Args:
            value: The Python object (an `ipaddress` object or `None`) to be
                   bound to the database.
            dialect: The SQLAlchemy dialect being used.

        Returns:
            The string representation of the IP address, or `None` if the input
            value was `None`.
        """
        # If the value is None, return it directly without processing.
        if value is None:
            return value
        # Convert the ipaddress object to its string representation.
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """
        Processes the value retrieved from the database before it's returned to Python.

        Converts the database's string representation of an IP address back into
        an `ipaddress.IPv4Address` or `ipaddress.IPv6Address` object.
        `None` values are passed through unchanged.

        Args:
            value: The value retrieved from the database (typically a string or `None`).
            dialect: The SQLAlchemy dialect being used.

        Returns:
            An `ipaddress.IPv4Address` or `ipaddress.IPv6Address` object, or `None`
            if the database value was `None`.
        """
        # If the value is None, return it directly without processing.
        if value is None:
            return value
        # Check if the value is already an IPv4Address or IPv6Address object.
        if not isinstance(value, ipaddress.IPv4Address | ipaddress.IPv6Address):
            # If not, convert the string value from the database into an ipaddress object.
            value = ipaddress.ip_address(value)
        # Return the processed ipaddress object.
        return value
