"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
from edgy.utils.hashing import hash_to_identifier
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade(url: str = "") -> None:
    fn = globals().get(f"upgrade_{hash_to_identifier(url)}")
    if fn is not None:
        fn()


def downgrade(url: str = "") -> None:
    fn = globals().get(f"downgrade_{hash_to_identifier(url)}")
    if fn is not None:
        fn()


<%
    from edgy import monkay
    from edgy.utils.hashing import hash_to_identifier
    db_names = monkay.settings.migrate_databases

    def url_for_name(name):
        if name:
            return str(monkay.instance.registry.extra[name].url)
        else:
            return str(monkay.instance.registry.database.url)
%>

## generate an "upgrade_<xyz>() / downgrade_<xyz>()" function
## according to edgy migrate settings

% for db_name in db_names:

def ${f"upgrade_{hash_to_identifier(url_for_name(db_name))}"}():
    ${context.get(f"{db_name or ''}_upgrades", "pass")}


def ${f"downgrade_{hash_to_identifier(url_for_name(db_name))}"}():
    ${context.get(f"{db_name or ''}_downgrades", "pass")}

% endfor
