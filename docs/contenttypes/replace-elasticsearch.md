# Building a tagged index (or replace elasticsearch)

## Introduction
Elasticsearch is a commonly used software for comparing data across domains.
It comes at a hefty price:
It is resource hungry and you have to leave the relational sql world for TCP which introduces round-trips on a by magnitudes
slower lane.

In short: it is only useful for very big shared high performance setups. Not for yours, most probably.
Here I explain how to do it much simpler and with way less resources in a relational db (this saves you hardware costs and shorts your electricity bill).

## Setup

First we need a generic table which maps to all other tables. We have ContentType. Done.

Second we need a Tag. Here are many flavors possible:

- Tags with seperate key, value fields.
- Tags with merged key, value fields.
- Tags with unique key, values; seperate or merged. Note: some dbs have 255 char limit.

Depending if  mysql and others shall be supported

Secondly we need tags, that are text fields with a key value syntax.
We can use TextFields for this. In my projects I use a syntax: `key=value`. Stupidly simple but you have to check that you only seperate on the first
`=` which is a bit hard in some programming languages (use regex, e.g. `/^([^=]+)=(.*)/` for seperating in js).

Third (optionally): It would be nice to detect collisions among data of different tables --> collision_key.
For building a hash for a collision key we can leverage an hash method adapted from the rdf guys.

First merge the keys with values with a seperator like `=` (or just use the tags) into an array. Sort the array.
The entries are now hashed (each entry) and afterwards a hash is build from all the hashes as if they would be a long bytestring.


```python
{!> ../docs_src/contenttypes/contenttype_tags.py !}
```


!!! Note
    It is crucial that each entry is mangled (either by hash or an other mangling method) because otherwise malicious users could inject `=` in the value data and provoke
collisions.

!!! Note
    The seperator is up to you. I just `=` because I used this in the secretgraph project, but all chars are elligable. More logic you can lookup there.


## Alternative implementations

If you don't like the shared field for key value operations you may want seperate fields for both.
Also it would be possible (for postgres and other more powerful dbs) to make the tag field unique.

## Operations

Searching for a key:

use `registry.content_type.query.filter(tags__tag__startswith='key=')`

Searching for a key and a value starting with:

use `registry.content_type.query.filter(tags__tag__startswith='key=value_start')`



## References

[secretgraph](https://github.com/secretgraph/secretgraph)
