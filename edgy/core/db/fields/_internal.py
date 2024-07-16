import ipaddress
from abc import abstractmethod
from typing import Any

import sqlalchemy

from edgy.conf import settings

DIALECTS = {"postgres": "postgres"}


class BaseFieldProtocol(sqlalchemy.TypeDecorator):
    """
    When implementing a field representation from SQLAlchemy, the protocol will be enforced
    """

    impl: Any
    cache_ok: bool

    @abstractmethod
    def load_dialect_impl(self, dialect: Any) -> Any:
        raise NotImplementedError("load_dialect_impl must be implemented")

    @abstractmethod
    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        raise NotImplementedError("process_bind_param must be implemented")

    @abstractmethod
    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """
        Processes the value coming from the database in a column-row style.
        """
        raise NotImplementedError("process_result_value must be implemented")


class IPAddress(BaseFieldProtocol):
    impl: str = sqlalchemy.CHAR  # type: ignore
    cache_ok: bool = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name not in settings.dialects:
            return dialect.type_descriptor(sqlalchemy.CHAR(45))
        return dialect.type_descriptor(sqlalchemy.dialects.postgresql.INET())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is not None:
            return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            value = ipaddress.ip_address(value)
        return value
