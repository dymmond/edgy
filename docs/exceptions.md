# Exceptions

All **Saffier** custom exceptions derive from the base `SaffierException`.

## DoesNotFound

Raised when querying a model instance and it does not exist.

```python
from saffier.exceptions import DoesNotFound
```

Or simply:

```python
from saffier import DoesNotFound
```

## MultipleObjectsReturned

Raised when querying a model and returns multiple results for the given query result.

```python
from saffier.exceptions import MultipleObjectsReturned
```

Or simply:

```python
from saffier import MultipleObjectsReturned
```

## ValidationError

Raised when a validation error is thrown.

```python
from saffier.exceptions import ValidationError
```

Or simply:

```python
from saffier import ValidationError
```

## ImproperlyConfigured

Raised when misconfiguration in the models and metaclass is passed.

```python
from saffier.exceptions import ImproperlyConfigured
```

Or simply:

```python
from saffier import ImproperlyConfigured
```
