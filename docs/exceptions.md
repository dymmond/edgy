# Exceptions

All **Edgy** custom exceptions derive from the base `EdgyException`.

## ObjectNotFound

Raised when querying a model instance and it does not exist.

```python
from edgy.exceptions import ObjectNotFound
```

Or simply:

```python
from edgy import ObjectNotFound
```

## MultipleObjectsReturned

Raised when querying a model and returns multiple results for the given query result.

```python
from edgy.exceptions import MultipleObjectsReturned
```

Or simply:

```python
from edgy import MultipleObjectsReturned
```

## ValidationError

Raised when a validation error is thrown.

```python
from edgy.exceptions import ValidationError
```

Or simply:

```python
from edgy import ValidationError
```

## ImproperlyConfigured

Raised when misconfiguration in the models and metaclass is passed.

```python
from edgy.exceptions import ImproperlyConfigured
```

Or simply:

```python
from edgy import ImproperlyConfigured
```
