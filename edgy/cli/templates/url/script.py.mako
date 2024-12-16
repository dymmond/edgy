"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
<%
    from edgy.utils.hashing import hash_to_identifier, hash_to_identifier_as_string
%>
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

if TYPE_CHECKING:
    from edgy.core.connection import DatabaseURL

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


${hash_to_identifier_as_string}


def upgrade(url: Optional[DatabaseURL] = None) -> None:
    urlstring = "" if url is None else f"{url.username}@{url.hostname}:{url.port}/{url.database}"
    # hash_to_identifier adds already an "_"
    fn = globals().get(f"upgrade{hash_to_identifier(urlstring)}")
    if fn is not None:
        fn()


def downgrade(url: Optional[DatabaseURL] = None) -> None:
    urlstring = "" if url is None else f"{url.username}@{url.hostname}:{url.port}/{url.database}"
    # hash_to_identifier adds already an "_"
    fn = globals().get(f"downgrade{hash_to_identifier(urlstring)}")
    if fn is not None:
        fn()


<%
    from edgy import monkay
    from edgy.utils.hashing import hash_to_identifier
    db_names = monkay.settings.migrate_databases

    def url_for_name(name):
        if name:
            url = monkay.instance.registry.extra[name].url
        else:
            url = monkay.instance.registry.database.url
        return f"{url.username}@{url.hostname}:{url.port}/{url.database}"
%>

## generate an "upgrade_<xyz>() / downgrade_<xyz>()" function
## according to edgy migrate settings

% for db_name in db_names:

def ${f"upgrade{hash_to_identifier(url_for_name(db_name))}"}():
    # Migration of:
    # ${url_for_name(db_name)} (${f'"{db_name}"' if db_name else 'main database'})
    ${context.get(f"{db_name or ''}_upgrades", "pass")}


def ${f"downgrade{hash_to_identifier(url_for_name(db_name))}"}():
    # Migration of:
    # ${url_for_name(db_name)} (${f'"{db_name}"' if db_name else 'main database'})
    ${context.get(f"{db_name or ''}_downgrades", "pass")}

% endfor
