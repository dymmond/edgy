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

def upgrade(engine_name: str = "") -> None:
    fn = globals().get(f"upgrade_{hash_to_identifier(engine_name)}")
    if fn is not None:
        fn()


def downgrade(engine_name: str = "") -> None:
    fn = globals().get(f"downgrade_{hash_to_identifier(engine_name)}")
    if fn is not None:
        fn()


<%
    from edgy import monkay
    from edgy.utils.hashing import hash_to_identifier
    db_names = monkay.settings.migrate_databases
%>

## generate an "upgrade_<xyz>() / downgrade_<xyz>()" function
## according to edgy migrate settings

% for db_name in db_names:

def ${f"upgrade_{hash_to_identifier(db_name or '')}"}():
    # Migration of:
    # ${db_name or 'main database'}
    ${context.get(f"{db_name or ''}_upgrades", "pass")}


def ${f"downgrade_{hash_to_identifier(db_name or '')}"}():
    # Migration of:
    # ${db_name or 'main database'}
    ${context.get(f"{db_name or ''}_downgrades", "pass")}

% endfor
