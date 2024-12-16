# Custom mako template
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade(edgy_dbname: str = "") -> None:
    globals()[f"upgrade_{edgy_dbname}"]()


def downgrade(edgy_dbname: str = "") -> None:
    globals()[f"downgrade_{edgy_dbname}"]()


<%
    from edgy import monkay
    db_names = monkay.settings.migrate_databases
%>

## generate an "upgrade_<xyz>() / downgrade_<xyz>()" function
## according to edgy migrate settings

% for db_name in db_names:

def ${f"upgrade_{db_name or ''}"}():
    ${context.get(f"{db_name or ''}_upgrades", "pass")}


def ${f"downgrade_{db_name or ''}"}():
    ${context.get(f"{db_name or ''}_downgrades", "pass")}

% endfor
