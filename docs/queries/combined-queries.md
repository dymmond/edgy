# Combining QuerySets

Edgy's `QuerySet` API supports SQL-style set operations such as `UNION`, `UNION ALL`, `INTERSECT`, and `EXCEPT`.

## Overview

| Operation       | Description                                 | SQL Equivalent |
|-----------------|---------------------------------------------|----------------|
| `.union(qs2)`     | Combines both querysets, removing duplicates. | `UNION`        |
| `.union_all(qs2)` | Combines both querysets, keeping duplicates.   | `UNION ALL`    |
| `.intersect(qs2)` | Returns only rows appearing in both querysets. | `INTERSECT`    |
| `.except_(qs2)`   | Returns rows from the first queryset that aren't in the second. | `EXCEPT`       |

All methods return a `CombinedQuerySet`, which behaves just like a normal queryset.

You can continue chaining methods such as:

```python
.order_by()
.limit()
.offset()
.only()
.defer()
.values()
.exists()
.count()
.first()
.last()
```

## Example Models

```python
import edgy

class Customer(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    country = edgy.CharField(max_length=2)

    class Meta:
        registry = models


class Order(edgy.StrictModel):
    customer = edgy.ForeignKey(Customer, related_name="orders")
    total = edgy.DecimalField(max_digits=10, decimal_places=2)
    status = edgy.CharField(max_length=20)

    class Meta:
        registry = models
```

## Union — Combine QuerySets

Combine multiple querysets of the same model.

```python
# Customers from Switzerland and Germany
swiss = Customer.query.filter(country="CH")
german = Customer.query.filter(country="DE")

# Combine them into a single queryset
european = swiss.union(german).order_by("name")
customers = await european.all()
```

**Generated SQL:**

```sql
SELECT * FROM customer WHERE country = 'CH'
UNION
SELECT * FROM customer WHERE country = 'DE'
ORDER BY name;
```

This deduplicates automatically, preserving unique customers.

## Union All — Keep Duplicates

```python
recent_orders = Order.query.filter(status="recent")
priority_orders = Order.query.filter(status="priority")

combined_orders = recent_orders.union_all(priority_orders)
orders = await combined_orders.order_by("-total").limit(10)
```

This returns all matching rows, even duplicates.

## Intersect — Shared Records Between Sets

```python
active_customers = Customer.query.filter(status="active")
premium_customers = Customer.query.filter(plan="premium")

shared = active_customers.intersect(premium_customers)
customers = await shared.order_by("name")
```

Returns only customers that satisfy both filters.

## Except — Subtract One Set from Another

```python
all_customers = Customer.query.all()
has_orders = Customer.query.filter(orders__isnull=False)

new_customers = all_customers.except_(has_orders)
await new_customers.count()
```

Returns only customers without any orders.

## Chaining and Nesting

You can freely chain set operations — Edgy handles them as combined SQL subqueries.

```python
# (CH ∪ DE) ∪ FR
union_3 = (
    Customer.query.filter(country="CH")
    .union(Customer.query.filter(country="DE"))
    .union(Customer.query.filter(country="FR"))
)

customers = await union_3.order_by("name")
```

You can also mix operations:

```python
# (CH ∪ DE) - FR
qs = (
    Customer.query.filter(country="CH")
    .union(Customer.query.filter(country="DE"))
    .except_(Customer.query.filter(country="FR"))
)
```

## Behavior Details

### Ordering, Limit, and Offset

Outer modifiers apply to the entire combined result:

```python
top_customers = (
    swiss.union(german)
    .order_by("-id")
    .limit(10)
)
```

### Deferred Fields and `only()`

These propagate safely across combined querysets:

```python
qs1 = Customer.query.only("id", "name")
qs2 = Customer.query.defer("country")

combined = qs1.union(qs2).order_by("name")
rows = await combined.values(["id", "name"])
```

### Counting and Existence

```python
await combined.exists()
await combined.count()
await combined.offset(5).limit(5)
```

### Model and Registry Safety

Both sides of the operation must come from the same model and registry.

```python
from edgy.exceptions import QuerySetError

with pytest.raises(QuerySetError):
    await Customer.query.union(Order.query)
```

## Complex Example — Filtering for Reporting

```python
eu_customers = (
    Customer.query.filter(country="DE")
    .union(Customer.query.filter(country="CH"))
    .except_(Customer.query.filter(orders__isnull=False))
    .order_by("name")
    .limit(20)
)

for c in await eu_customers:
    print(c.name, c.country)
```

Find customers in the EU who are German or Swiss but haven't ordered yet.

!!! tip
    Always include `.order_by()` when comparing lists to ensure deterministic results.

## Summary

| Feature                   | Supported              |
|---------------------------|------------------------|
| `union()`                 | Deduplicates results   |
| `union_all()`             | Keeps duplicates       |
| `intersect()`             | Common records       |
| `except_()`               | Subtracts records    |
| Cross-model operations    | ❌ Raises `QuerySetError` |
