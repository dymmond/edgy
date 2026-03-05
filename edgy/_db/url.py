from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class DatabaseURL:
    """Small compatibility wrapper around SQLAlchemy's URL object."""

    _sqla_url: URL

    def __init__(self, url: str | URL | DatabaseURL) -> None:
        if isinstance(url, DatabaseURL):
            object.__setattr__(self, "_sqla_url", url._sqla_url)
            return
        if isinstance(url, URL):
            object.__setattr__(self, "_sqla_url", url)
            return
        if isinstance(url, str):
            object.__setattr__(self, "_sqla_url", make_url(url))
            return
        raise TypeError("Invalid type for DatabaseURL.")

    @property
    def sqla_url(self) -> URL:
        return self._sqla_url

    @property
    def dialect(self) -> str:
        return self._sqla_url.drivername.split("+", 1)[0]

    @property
    def driver(self) -> str | None:
        parts = self._sqla_url.drivername.split("+", 1)
        return parts[1] if len(parts) == 2 else None

    @property
    def username(self) -> str | None:
        return self._sqla_url.username

    @property
    def password(self) -> str | None:
        return self._sqla_url.password

    @property
    def hostname(self) -> str | None:
        host = self._sqla_url.host
        if host is not None:
            return host
        query_host = self._sqla_url.query.get("host")
        if isinstance(query_host, tuple):
            return query_host[0]
        return query_host

    @property
    def port(self) -> int | None:
        return self._sqla_url.port

    @property
    def database(self) -> str | None:
        return self._sqla_url.database

    @property
    def options(self) -> dict[str, str]:
        options: dict[str, str] = {}
        for key, value in self._sqla_url.query.items():
            if isinstance(value, tuple):
                options[key] = str(value[0])
            else:
                options[key] = str(value)
        return options

    @property
    def userinfo(self) -> bytes | None:
        if self.username is None:
            return None
        username = quote(self.username, safe="")
        if self.password is None:
            return username.encode()
        password = quote(self.password, safe="")
        return f"{username}:{password}".encode()

    def replace(self, **kwargs: Any) -> DatabaseURL:
        drivername = kwargs.pop("drivername", None)
        dialect = kwargs.pop("dialect", None)
        driver = kwargs.pop("driver", None)

        if drivername is None and dialect is not None:
            drivername = dialect if driver is None else f"{dialect}+{driver}"

        new_url = self._sqla_url.set(drivername=drivername, **kwargs)
        return DatabaseURL(new_url)

    def __str__(self) -> str:
        return self._sqla_url.render_as_string(hide_password=False)

    def __repr__(self) -> str:
        hidden = self._sqla_url.render_as_string(hide_password=True)
        return f"DatabaseURL('{hidden}')"

    def __hash__(self) -> int:
        return hash(self._sqla_url)


__all__ = ["DatabaseURL"]
