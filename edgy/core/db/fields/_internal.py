import ipaddress
from typing import Any

import sqlalchemy


class IPAddress(sqlalchemy.TypeDecorator):
    impl: Any = sqlalchemy.String
    cache_ok: bool = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name not in {"postgres", "postgresql"}:
            return dialect.type_descriptor(sqlalchemy.String(length=45))
        return dialect.type_descriptor(sqlalchemy.dialects.postgresql.INET())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            value = ipaddress.ip_address(value)
        return value
