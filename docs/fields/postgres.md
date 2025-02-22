# PostgreSQL Fields

Here are some PostgreSQL-specific fields that extend the capabilities of relational databases with advanced data types and structures.

## PGArrayField

The `PGArrayField` allows storing arrays of a given SQLAlchemy type in a single column. This is particularly useful for scenarios where you need to store lists of values without creating additional tables or using JSON fields.

### How It Works

`PGArrayField` takes an SQLAlchemy type and creates an array of that type. This provides efficiency and flexibility when handling structured data that belongs to a single entity.

### Example Usage

```python
from typing import List
import sqlalchemy
import edgy

class MyModel(edgy.Model):
    data: List[str] = edgy.fields.PGArrayField(sqlalchemy.String(), default=list)
    ...
```

### Explanation

- `PGArrayField(sqlalchemy.String())` defines an array of strings stored in a single column.
- The `default=list` ensures that new instances of `MyModel` have an empty list if no value is provided.
- This field is useful for cases where an entity naturally contains multiple values, such as a list of tags, keywords, or user preferences.

### Benefits of Using `PGArrayField`

- **Efficiency**: Avoids the need for additional tables and foreign key relationships when handling lists.
- **Query Performance**: PostgreSQL provides optimized operators for querying arrays, making searches and filtering more efficient.
- **Flexibility**: Can store various types (integers, strings, etc.) while still leveraging PostgreSQL's indexing and query capabilities.

### Considerations

- **Indexing**: PostgreSQL supports `GIN` indexes for array fields, which can significantly improve search performance.
- **Normalization**: If an array contains frequently changing data or requires complex relationships, it might be better to store it in a separate table.

By using `PGArrayField`, you can efficiently manage structured data in PostgreSQL while maintaining the power and simplicity of relational models.
