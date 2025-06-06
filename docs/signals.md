# Signals

In Edgy, signals provide a mechanism to "listen" to model events, triggering specific actions when events like saving or deleting occur. This is similar to Django's signals but also draws inspiration from Ormar's implementation, and leverages the `blinker` library for anonymous signals.

## What are Signals?

Signals are used to execute custom logic when certain events happen within Edgy models. They enable decoupling of concerns, allowing you to perform actions like sending notifications, updating related data, or logging events without cluttering your model definitions.

## Default Signals

Edgy provides default signals for common model lifecycle events, which you can use out of the box.

### How to Use Them

The default signals are located in `edgy.core.signals`. Import them as follows:

```python
from edgy.core.signals import (
    post_delete,
    post_save,
    post_update,
    post_migrate,
    pre_delete,
    pre_save,
    pre_update,
    pre_migrate,
)
```

#### pre_save

Triggered before a model is saved (during `Model.save()` and `Model.query.create()`).

```python
pre_save(send: Type["Model"], instance: Union["Model", "QuerySet"], model_instance: "Model", values: dict, column_values: dict, is_update: bool)
```

Only the `EXPLICIT_SPECIFIED_VALUES` contextvar is available.

#### post_save

Triggered after a model is saved (during `Model.save()` and `Model.query.create()`).

```python
post_save(send: Type["Model"], instance: Union["Model", "QuerySet"], model_instance: "Model", values: dict, column_values: dict, is_update: bool)
```

#### pre_update

Triggered before a model is updated (during `Model.update()` and `Model.query.update()`).

```python
pre_update(sender: Type["Model"], instance: Union["Model", "QuerySet"], model_instance: Optional["Model"], values: dict, column_values: dict)
```

#### post_update

Triggered after a model is updated (during `Model.update()` and `Model.query.update()`).

```python
post_update(sender: Type["Model"], instance: Union["Model", "QuerySet"], model_instance: Optional["Model"], values: dict, column_values: dict)
```

#### pre_save, post_save, pre_update, post_update parameters

The receiver function receives following parameters:

- instance - The model or QuerySet instance.
- model_instance -The model instance if available. For save signals always available
- values - The passed values.
- column_values - The parsed values which are used for the db.
- is_update - Is it an update? This is also set for `*_update` to match the save parameters.
- is_migration - Called from `apply_default_force_nullable_fields` which is mostly for migrations. Here we have model instances.

#### pre_delete

Triggered before a model is deleted (during `Model.delete()` and `Model.query.delete()`).

```python
pre_delete(send: Type["Model"], instance: Union["Model", "QuerySet"], model_instance: Optional["Model"])
```

##### pre_delete parameters

- instance - The model or QuerySet instance.
- model_instance -The model instance if available.

#### post_delete

Triggered after a model is deleted (during `Model.delete()` and `Model.query.delete()`).

```python
post_delete(send: Type["Model"], instance: Union["Model", "QuerySet"], model_instance: Optional["Model"], row_count: Optional[int])
```

##### post_delete parameters

- instance - The model or QuerySet instance.
- row_count - How many rows are deleted (only some dbs can be None).
- model_instance -The model instance if available.

#### pre_migrate

Triggered before upgrading, downgrading or creating a migration.
This signal is sync but can be used with async receivers too.

It has following senders:

- "upgrade"
- "downgrade"
- "revision"

#### post_migrate

Triggered after upgrading, downgrading or creating a migration.
This signal is sync but can be used with async receivers too.

It has following senders:

- "upgrade"
- "downgrade"
- "revision"

#### pre_migrate & post_migrate parameters

Basically all parameters which are passed to the alembic function

That are for upgrade/downgrade:

- config - The configuration object.
- revision - The revision to use (relative or absolute).
- sql - Is offline mode (outputs sql).
- tag -Parameters for env.py script.

And for revision:

- config - The configuration object.
- message - The message.
- autogenerate - Shall the migration file be autogenerated?
- sql - Offline mode.
- head - Head parameter of alembic.
- splice - Splice parameter of alembic.
- branch_label
- version_path
- revision_id - Revision id of the migration.

## Receiver

A receiver is a function that executes when a signal is triggered. It "listens" for a specific event.

Example: Given the following model:

```python
{!> ../docs_src/signals/receiver/model.py !}
```

You can send an email to a user upon creation using the `post_save` signal:

```python hl_lines="11-12"
{!> ../docs_src/signals/receiver/post_save.py !}
```

The `@post_save` decorator specifies the `User` model, indicating it listens for events on that model.

### Requirements

Receivers must meet the following criteria:

* Must be a callable (function).
* Must have `sender` as the first argument (the model class).
* Must have `**kwargs` to accommodate changes in model attributes.
* Must be `async` to match Edgy's async operations.

### Multiple Receivers

You can use the same receiver for multiple models:

```python
{!> ../docs_src/signals/receiver/multiple.py !}
```

```python hl_lines="11"
{!> ../docs_src/signals/receiver/post_multiple.py !}
```

### Multiple Receivers for the Same Model

You can have multiple receivers for the same model:

```python
{!> ../docs_src/signals/receiver/multiple_receivers.py !}
```

### Disconnecting Receivers

You can disconnect a receiver to prevent it from running:

```python hl_lines="20 23"
{!> ../docs_src/signals/receiver/disconnect.py !}
```

## Custom Signals

Edgy allows you to define custom signals, extending beyond the default ones.

Continuing with the `User` model example:

```python
{!> ../docs_src/signals/receiver/model.py !}
```

Create a custom signal named `on_verify`:

```python hl_lines="21"
{!> ../docs_src/signals/custom.py !}
```

The `on_verify` signal is now available for the `User` model.

!!! Danger
    Signals are class-level attributes, affecting all derived instances. Use caution when creating custom signals.

Create a receiver for the custom signal:

```python hl_lines="21 30"
{!> ../docs_src/signals/register.py !}
```

The `trigger_notifications` receiver is now connected to the `on_verify` signal.

### Rewire Signals

To prevent default lifecycle signals from being called, you can overwrite them per class or use the `set_lifecycle_signals_from` method of the Broadcaster:

```python
{!> ../docs_src/signals/rewire.py !}
```

### How to Use It

Use the custom signal in your logic:

```python hl_lines="17"
{!> ../docs_src/signals/logic.py !}
```

The `on_verify` signal is triggered only when the user is verified.

### Disconnect the Signal

Disconnecting a custom signal is the same as disconnecting a default signal:

```python hl_lines="10"
{!> ../docs_src/signals/disconnect.py !}
```
