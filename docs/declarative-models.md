# Declarative Models

When you need to generate a `declarative_model` from an SQLAlchemy ORM type, you can easily do so by calling `Model.declarative()`. For example, `User.declarative()`. This method automatically generates the declarative model type for you, allowing seamless integration with SQLAlchemy's ecosystem.

```python hl_lines="23"
{!> ../docs_src/models/declarative/example.py !}
```

It's crucial to understand the implications of using a declarative model, especially when dealing with [ForeignKey](./relationships.md#foreignkey) or [OneToOneField](./relationships.md#onetoone) relationships. Edgy automatically generates an [SQLAlchemy Relationship](https://docs.sqlalchemy.org/en/20/orm/relationships.html) and appends `_relation` to the end of the declared field.

Let's illustrate this with a practical example.

```python hl_lines="20-29"
{!> ../docs_src/models/declarative/fk_relationship.py !}
```

In the `Thread` model, you'll notice two foreign keys, `sender` and `receiver`. In standard Edgy ORM operations, these fields remain as declared. However, when you generate the `declarative()` model from Edgy, it automatically creates the following additional fields:

* `sender_relation`
* `receiver_relation`

These auto-generated `_relation` fields are SQLAlchemy relationships that provide a more direct way to interact with related data within the SQLAlchemy context.

## Why are these `_relation` fields generated?

The primary reason for this behavior is to facilitate compatibility and interoperability with tools and libraries that rely on SQLAlchemy's declarative models. While Edgy focuses on providing a high-level, asynchronous ORM, there are scenarios where deeper integration with SQLAlchemy's features is necessary.

For instance, libraries like [Esmerald Admin](https://esmerald-admin.tarsild.io) leverage Edgy's declarative models to provide admin interfaces that can efficiently manage related data. These tools expect SQLAlchemy relationships to be available, and Edgy's `declarative()` method ensures that these relationships are generated automatically.

## Impact on Edgy's Core Functionality

It's important to note that these `_relation` fields do not alter or impact Edgy's core functionality. They are purely for compatibility with SQLAlchemy-based tools. When you use Edgy's querysets and model methods, you interact with the original `sender` and `receiver` fields as you normally would.

## Practical Implications and Use Cases

* **Integration with SQLAlchemy-based tools:** If you're using tools or libraries that rely on SQLAlchemy's declarative models, generating `declarative()` models from Edgy ensures seamless integration.
* **Admin interfaces:** Tools like Esmerald Admin, which utilize Edgy's declarative models, can efficiently manage related data through the generated SQLAlchemy relationships.
* **Advanced SQLAlchemy features:** If you need to leverage advanced SQLAlchemy features that require direct access to relationships, generating `declarative()` models provides the necessary access.

## When to Use `declarative()`

In most cases, you won't need to explicitly generate `declarative()` models. Edgy's ORM provides a comprehensive set of features for managing data without requiring direct access to SQLAlchemy's declarative models.

However, if you're working with tools or libraries that require SQLAlchemy relationships, or if you need to leverage advanced SQLAlchemy features, generating `declarative()` models can be beneficial.

## Key Takeaways

* Edgy's `declarative()` method generates SQLAlchemy declarative models, providing compatibility with SQLAlchemy-based tools.
* ForeignKey and OneToOneField relationships result in the automatic generation of `_relation` fields, which are SQLAlchemy relationships.
* These `_relation` fields do not impact Edgy's core functionality and are primarily for compatibility with external tools.
