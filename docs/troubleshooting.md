# Troubleshooting

This page collects common Edgy issues and the fastest way to fix them.

## Quick Diagnostic Checklist

Before diving into specific errors, check these first:

1. Confirm app discovery: `edgy --app path.to.module shell`
2. Confirm migration state: `edgy current`, `edgy heads`
3. Confirm lifecycle scope in code (`async with registry:` or `with registry.with_async_env():`)
4. Confirm test isolation settings when running tests (`EDGY_TESTCLIENT_*`)

For the command context itself, see [CLI Commands](./cli/commands.md) and [Discovery](./migrations/discovery.md).

## `Could not find edgy application via autodiscovery`

**What it means:** Edgy could not resolve your app context automatically.

**Why it happens:** No valid preload/app module set, or working directory/path is wrong.

**How to fix:**

* Run commands with `--app path.to.module`.
* Or set `EDGY_DEFAULT_APP=path.to.module`.
* Or configure `preloads` in [Settings](./settings.md).

```shell
$ edgy --app myproject.main shell
```

See [Discovery](./migrations/discovery.md).

## `DatabaseNotConnectedWarning`

**What it means:** Query/model operation was executed without an active database scope.

**Why it happens:** Registry/database lifecycle is not kept open.

**How to fix:**

* In async code: keep `async with registry:` around operation scope.
* In sync code: use `with registry.with_async_env():`.

See [Connection Management](./connection.md) and [Debugging](./debugging.md).

## `No such command "makemigration"`

**What it means:** Old command name was used.

**How to fix:** Use `makemigrations`.

```shell
$ edgy makemigrations
```

## Migration Says Multiple Heads

**What it means:** Branching histories produced more than one head.

**How to fix:**

1. Inspect heads:
   ```shell
   $ edgy heads
   ```
2. Merge heads:
   ```shell
   $ edgy merge -m "Merge heads" <rev_a> <rev_b>
   ```

## Schema Operations Raise `SchemaError`

**What it means:** Schema already exists / does not exist, or backend rejected operation.

**How to fix:**

* Use `if_not_exists=True` when creating.
* Use `if_exists=True` when dropping.
* Verify schema names for the targeted database(s).

See [Registry Schemas](./registry.md#schemas).

## Queries with `only()` and `defer()` Fail

**What it means:** `only()` and `defer()` were combined in one QuerySet chain.

**How to fix:** Use one strategy per query chain: either include-only or exclude-fields.

See [Queries](./queries/queries.md#only).

## Test Suite Touches the Wrong Database

**What it means:** Test database isolation is not configured as expected.

**How to fix:**

* Use `DatabaseTestClient`.
* Verify testclient settings/env vars such as:
  `EDGY_TESTCLIENT_TEST_PREFIX`, `EDGY_TESTCLIENT_FORCE_ROLLBACK`,
  `EDGY_TESTCLIENT_DROP_DATABASE`.

See [Test Client](./testing/test-client.md).

## `edgy check` Finds Changes Repeatedly

**What it means:** Model metadata and migration state are out of sync, or your model imports are incomplete during discovery.

**How to fix:**

* Ensure all model modules are loaded (via `preloads` or explicit imports).
* Regenerate with `edgy makemigrations` and inspect generated revision.
* Confirm the same settings/app module is used in local and CI runs.

See [Settings](./settings.md), [Discovery](./migrations/discovery.md), and [Migrations](./migrations/migrations.md).

## Admin Login/Path Issues

**What it means:** Auth credentials/path/prefix mismatches, often behind reverse proxies.

**How to fix:**

* Check generated password output (when `--auth-pw` is omitted).
* Set `--admin-path` and `--admin-prefix-url` consistently for proxy setups.

See [Admin](./admin/admin.md).

## Need More Detail?

* [Architecture Overview](./concepts/architecture.md)
* [Connection Management](./connection.md)
* [Migrations](./migrations/migrations.md)
* [Debugging](./debugging.md)
