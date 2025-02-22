# Building a Tagged Index (or Replacing Elasticsearch)

## Introduction

Elasticsearch is a widely used tool for comparing data across domains, but it comes at a significant cost. It is resource-intensive and requires moving away from the relational SQL world to TCP, which introduces latency due to additional network round-trips.

In short, Elasticsearch is only beneficial for very large, high-performance shared setups—most likely, not for yours. This guide explains how to achieve similar functionality much more efficiently using a relational database, reducing hardware costs and lowering electricity consumption.

## Setup

First, we need a generic table that maps to all other tables. With `ContentType`, this is already handled.

Next, we need a tagging mechanism. There are multiple approaches:

- Tags with separate key and value fields.
- Tags with merged key-value fields.
- Tags with unique key-value pairs, either separate or merged. *(Note: Some databases impose a 255-character limit.)*

The choice depends on whether MySQL and similar databases need to be supported.

For storing tags, we can use text fields with a key-value syntax. A simple syntax like `key=value` works well. However, it's important to split only on the first `=` character, which can be tricky in some programming languages. Using a regular expression, such as `/^([^=]+)=(.*)/` in JavaScript, helps handle this correctly.

### Detecting Collisions (Optional)

To detect duplicate data across different tables, we use a `collision_key`. A hashing method adapted from RDF techniques can be applied:

1. Merge keys and values using a separator like `=` (or just use the tags) into an array.
2. Sort the array.
3. Hash each entry individually.
4. Generate a final hash from all individual hashes as if they were a single byte string.

```python
{!> ../docs_src/contenttypes/contenttype_tags.py !}
```

!!! Note
    Each entry must be processed (either via hashing or another encoding method) to prevent malicious users from injecting `=` in value fields, which could cause collisions.

!!! Note
    The separator is up to you. I use `=` because it was used in the Secretgraph project, but any character is valid. You can find additional logic in that project.

## Alternative Implementations

If you prefer not to use a shared field for key-value operations, you can separate keys and values into distinct fields. Additionally, more powerful databases like PostgreSQL allow enforcing uniqueness constraints on tag fields.

## Operations

### Searching for a Key

```python
registry.content_type.query.filter(tags__tag__startswith='key=')
```

### Searching for a Key with a Value Prefix

```python
registry.content_type.query.filter(tags__tag__startswith='key=value_start')
```

## References

[Secretgraph](https://github.com/secretgraph/secretgraph)
