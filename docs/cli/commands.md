# CLI Commands

Edgy ships with a full CLI for migrations, shell usage, inspection, and admin serving.

This page is a practical map of the commands, when to use them, and typical call patterns.

## Before Running Commands

Edgy needs an application context (`edgy.monkay.instance`) for most commands.

You can provide it by:

* `--app path.to.module`
* `EDGY_DEFAULT_APP=path.to.module`
* preloads in settings (for automatic discovery)

See [Discovery](../migrations/discovery.md) for details.

## Migration Bootstrap

### `edgy list_templates`

**What:** Show available migration repository templates.

**When:** Before `edgy init`, when choosing a template.

```shell
$ edgy list_templates
```

### `edgy init`

**What:** Create migration repository files (`alembic.ini`, env scripts, versions folder).

**When:** First-time migration setup.

```shell
$ edgy init
$ edgy init -t plain
```

## Migration Generation

### `edgy revision`

**What:** Create a new revision script.

**When:** Manual revision creation or fine-grained control.

```shell
$ edgy revision -m "Add status field"
$ edgy revision --autogenerate -m "Sync models"
```

### `edgy makemigrations`

**What:** Alias for `edgy revision --autogenerate`.

**When:** Standard model-to-migration workflow.

```shell
$ edgy makemigrations
$ edgy makemigrations -m "Initial schema"
```

### `edgy merge`

**What:** Merge multiple heads into one revision.

**When:** Branching migration histories create multiple heads.

```shell
$ edgy merge -m "Merge heads" <rev_a> <rev_b>
```

### `edgy edit`

**What:** Open/edit a revision file from the CLI.

**When:** Quick script edits without manual path lookup.

```shell
$ edgy edit head
```

## Migration Execution

### `edgy migrate`

**What:** Upgrade database to a target revision (defaults to `head`).

**When:** Apply migrations.

```shell
$ edgy migrate
$ edgy migrate <revision>
```

### `edgy downgrade`

**What:** Roll back to an earlier revision.

**When:** Revert schema changes.

```shell
$ edgy downgrade -1
$ edgy downgrade <revision>
```

### `edgy stamp`

**What:** Mark revision table without running migration operations.

**When:** Align revision metadata with an already-synced database.

```shell
$ edgy stamp head
```

## Migration Introspection

### `edgy current`

**What:** Show current revision state.

```shell
$ edgy current
```

### `edgy heads`

**What:** Show current head revisions.

```shell
$ edgy heads
```

### `edgy branches`

**What:** Show migration branch points.

```shell
$ edgy branches
```

### `edgy history`

**What:** Show migration history.

```shell
$ edgy history
$ edgy history -r base:head
```

### `edgy show`

**What:** Show one revision script summary/details.

```shell
$ edgy show head
```

### `edgy check`

**What:** Check for model changes that would generate operations.

```shell
$ edgy check
```

## Runtime and Utilities

### `edgy shell`

**What:** Start interactive shell with imported models and defaults.

```shell
$ edgy shell
$ edgy shell --kernel ptpython
```

### `edgy inspectdb`

**What:** Reflect an existing database and emit `ReflectModel` definitions.

```shell
$ edgy inspectdb --database "postgres+asyncpg://user:pass@localhost:5432/my_db"
```

### `edgy admin_serve`

**What:** Run the Edgy admin development server.

```shell
$ edgy admin_serve
$ edgy admin_serve --auth-name=admin --auth-pw='<strong-password>'
```

## Recommended Flow

1. `edgy init` (once)
2. `edgy makemigrations`
3. `edgy migrate`
4. repeat 2-3 as models evolve

## See Also

* [Migrations](../migrations/migrations.md)
* [Discovery](../migrations/discovery.md)
* [Shell Support](../shell.md)
* [Inspect DB](../inspectdb.md)
* [Admin](../admin/admin.md)
