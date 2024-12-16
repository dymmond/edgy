"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import TYPE_CHECKING, Optional

from alembic import op
import sqlalchemy as sa
from edgy.utils.hashing import hash_to_identifier
${imports if imports else ""}

if TYPE_CHECKING:
    from edgy.core.connection import DatabaseURL

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade(url: Optional["DatabaseURL"] = None) -> None:
    urlstring = "" if url is None else f"{url.username}:{url.netloc}"
    fn = globals().get(f"upgrade_{hash_to_identifier(urlstring)}")
    if fn is not None:
        fn()


def downgrade(url: Optional["DatabaseURL"] = None) -> None:
    urlstring = "" if url is None else f"{url.username}:{url.netloc}"
    fn = globals().get(f"downgrade_{hash_to_identifier(urlstring)}")
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
        return f"{url.username}:{url.netloc}"
%>

## generate an "upgrade_<xyz>() / downgrade_<xyz>()" function
## according to edgy migrate settings

% for db_name in db_names:

def ${f"upgrade_{hash_to_identifier(url_for_name(db_name))}"}():
    # Migration of:
    # ${url_for_name(db_name)} (${db_name or 'main database'})
    ${context.get(f"{db_name or ''}_upgrades", "pass")}


def ${f"downgrade_{hash_to_identifier(url_for_name(db_name))}"}():
    # Migration of:
    # ${url_for_name(db_name)} (${db_name or 'main database'})
    ${context.get(f"{db_name or ''}_downgrades", "pass")}

% endfor
