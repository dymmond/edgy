"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
<%
    from edgy.core.utils.db import force_fields_nullable_as_list_string
%>
from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from edgy import monkay, run_sync
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

force_fields_nullable: list[tuple[str, str]] = ${force_fields_nullable_as_list_string()}

def upgrade(engine_name: str = "") -> None:
    fn = globals().get(f"upgrade_{engine_name}")
    if fn is not None:
        fn()


def downgrade(engine_name: str = "") -> None:
    fn = globals().get(f"downgrade_{engine_name}")
    if fn is not None:
        fn()
<%
    from edgy import monkay
    db_names = monkay.settings.migrate_databases
%>

## generate an "upgrade_<xyz>() / downgrade_<xyz>()" function
## according to edgy migrate settings

% for db_name in db_names:

def ${f"upgrade_{db_name or ''}"}(db_name: str=""):
    ${context.get(f"{db_name or ''}_upgrades", "pass")}
    if force_fields_nullable and not context.is_offline_mode():
        try:
            with monkay.instance.registry.with_async_env():
                run_sync(
                    monkay.instance.registry.apply_default_force_nullable_fields(
                        force_fields_nullable=force_fields_nullable,
                        filter_db_name="${db_name or ''}",
                        model_defaults={}
                    )
                )
        except Exception as exc:
            print("failure migrating defaults", exc)


def ${f"downgrade_{db_name or ''}"}():
    ${context.get(f"{db_name or ''}_downgrades", "pass")}

% endfor
