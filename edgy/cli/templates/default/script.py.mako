"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
<%
    from edgy.utils.hashing import hash_to_identifier, hash_to_identifier_as_string
    from edgy.core.utils.db import force_fields_nullable_as_list_string
    import json
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

${hash_to_identifier_as_string}
force_fields_nullable: list[tuple[str, str]] = ${force_fields_nullable_as_list_string()}

def upgrade(engine_name: str = "") -> None:
    # hash_to_identifier adds already an "_"
    fn = globals().get(f"upgrade{hash_to_identifier(engine_name)}")
    if fn is not None:
        fn()


def downgrade(engine_name: str = "") -> None:
    # hash_to_identifier adds already an "_"
    fn = globals().get(f"downgrade{hash_to_identifier(engine_name)}")
    if fn is not None:
        fn()
<%
    from edgy import monkay
    db_names = monkay.settings.migrate_databases
%>

## generate an "upgrade_<xyz>() / downgrade_<xyz>()" function
## according to edgy migrate settings

% for db_name in db_names:

def ${f"upgrade{hash_to_identifier(db_name or '')}"}():
    # Migration of:
    # ${f'"{db_name}"' if db_name else 'main database'}
    ${context.get(f"{db_name or ''}_upgrades", "pass")}
    if not context.is_offline_mode():
        try:
            with monkay.instance.registry.with_async_env():
                run_sync(
                    monkay.instance.registry.apply_default_force_nullable_fields(
                        force_fields_nullable=force_fields_nullable,
                        filter_db_name=${json.dumps(db_name or '')},
                        model_defaults={}
                    )
                )
        except Exception as exc:
            print("failure migrating defaults", exc)


def ${f"downgrade{hash_to_identifier(db_name or '')}"}():
    # Migration of:
    # ${f'"{db_name}"' if db_name else 'main database'}
    ${context.get(f"{db_name or ''}_downgrades", "pass")}

% endfor
