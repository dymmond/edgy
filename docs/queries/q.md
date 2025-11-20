# Q Objects in Edgy

Edgy provides a powerful `Q` object system inspired by Django that enables you to build
complex logical filtering expressions using natural Python boolean syntax. Q objects
integrate directly with Edgy's enhanced clause engine (`and_`, `or_`, `not_`), support
related-field lookups, wrap raw SQLAlchemy expressions, and work everywhere standard
filtering clauses are accepted.

This document explains how Q objects work, why they exist, and how to use them
effectively in real-world queries.

## What Are Q Objects?

A **Q object** represents a logical filtering expression. Unlike standard keyword-based
filters, which must be combined using `.filter()`, `.and_()`, or `.or_()`, Q objects can be
combined using Python boolean operators:

- `&` → logical AND
- `|` → logical OR
- `~` → logical NOT

Example:

```python
expr = Q(name="Adam") & ~Q(email__icontains="spam")
results = await User.query.filter(expr)
```

Q objects allow you to express complex filtering logic concisely and readably.

## Basic Usage

### Using kwargs

```python
expr = Q(name="Adam", email__icontains="edgy")
results = await User.query.filter(expr)
```

Equivalent to:

```python
await User.query.filter(and_.from_kwargs(name="Adam", email__icontains="edgy"))
```

### Using raw column expressions

```python
expr = Q(User.columns.name == "Adam")
results = await User.query.filter(expr)
```

### Combining Q objects

```python
expr = Q(name="Adam") & Q(email__icontains="edgy")
results = await User.query.filter(expr)
```

## Boolean Operators

### AND (`&`)

```python
expr = Q(active=True) & Q(email__icontains="edgy")
```

### OR (`|`)

```python
expr = Q(name="Adam") | Q(name="Edgy")
```

### NOT (`~`)

```python
expr = ~Q(language="PT")
```

### Precedence

Just like Python:

- `&` binds **tighter** than `|`
- Always use parentheses for clarity

Example:

```python
expr = Q(name="Adam") | Q(name="Edgy") & Q(language="EN")
```

interprets as:

```python
Q(name="Adam") | (Q(name="Edgy") & Q(language="EN"))
```

## Complex Expressions

Q objects are tree structures. This allows nesting:

```python
expr = (Q(name="Adam") | Q(name="Edgy")) & ~Q(email__icontains="domain")
results = await User.query.filter(expr)
```

This example returns all users named Adam or Edgy, excluding those with an email from
`domain`.

## Using Q Inside QuerySets

### filter()

```python
await User.query.filter(Q(name="Adam") | Q(name="Edgy"))
```

### or_(Q(...)) — global OR

`or_` supports [global OR](./queries.md#or) mode when passing a *single* Q operand:

```python
results = await User.query.or_(Q(name="Adam"))
```

Equivalent to:

```python
results = await User.query.or_(name="Adam")
```

### local_or(Q(...))

[local_or](./queries.md#local-only-or) keeps previous filters mandatory:

```python
await User.query.filter(active=True).local_or(Q(email__icontains="gmail"))
```

SQL equivalent:

```
active = TRUE AND (email ILIKE '%gmail%')
```

## Using Q With Related Fields

Any field lookup you can use in normal filtering also works with Q:

```python
expr = Q(user__id=product.user_id)
await Product.query.filter(expr)
```

Negation works too:

```python
expr = ~Q(user__name="Banned")
await Product.query.filter(expr)
```

You can combine related lookups with boolean logic:

```python
expr = Q(user__language="EN") | Q(user__language="PT")
```

## Q vs. Chained and_/or_ Calls

These two are equivalent:

### Q object expression

```python
expr = Q(name="Adam") | Q(name="Edgy")
results = await User.query.filter(expr)
```

### Long-form query builder

```python
results = await User.query.or_(name="Adam").or_(name="Edgy")
```

Both generate the same SQL, but Q is easier to read and more expressive.

## Q With SQLAlchemy Expressions

Q objects can wrap SQLAlchemy comparison expressions:

```python
expr = Q(User.columns.email.contains("edgy"))
results = await User.query.filter(expr)
```

Or combine them:

```python
expr = Q(User.columns.id > 10) & Q(User.columns.name.ilike("%edgy%"))
```

## Edge Cases & Notes

### Q() — empty Q

`Q()` is treated as a neutral AND expression.

```python
results = await User.query.filter(Q())  # returns all rows
```

### Q(Q(...))

Wrapping Q inside Q flattens automatically:

```python
inner = Q(name="Adam")
expr = Q(inner) & Q(language="EN")
```

### Select-related propagation

If a Q object wraps a clause requiring JOINs, Edgy automatically propagates the
required `select_related` information.

## Real-World Examples

### Search engine style

```python
expr = (
    Q(name__icontains="adam") |
    Q(email__icontains="adam") |
    Q(language__icontains="adam")
) & ~Q(status="banned")

results = await User.query.filter(expr)
```

### Multi-model filtering

```python
expr = Q(products__price__gt=100) & ~Q(language="PT")
results = await User.query.filter(expr)
```

### Combine Q with or_ for cross-query OR

```python
expr = Q(name="Adam")
results = await User.query.or_(expr)
```

## Performance Notes

- Q expressions are compiled to optimized SQLAlchemy boolean trees.
- Edgy automatically flattens redundant AND/OR layers.
- Prefer grouping with Q rather than chaining many `.or_()` calls for readability.
- For large OR groups, consider using `in_` lookups when possible:

```python
Q(id__in=[1, 2, 3, 4])
```

## Summary

Q objects make it easy to build readable, expressive, and powerful logical filtering
conditions in Edgy. They integrate deeply with the query compiler, support related
fields, wrap raw SQL expressions, and make complex filtering more maintainable.

Use Q whenever your logic requires more than a simple AND chain, or whenever you
prefer a more declarative, readable style.
