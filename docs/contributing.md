# Contributing

Thank you for showing interes in contributing to EdgyORM. There are many ways you can help and contribute to the
project.

* Try EdgyORM and [report bugs and issues](https://github.com/tarsil/edgy/issues/new) you find.
* [Implement new features](https://github.com/tarsil/edgy/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
* Help othes by [reviewing pull requests](https://github.com/tarsil/edgy/pulls)
* Help writting documentation
* Use the discussions and actively participate on them.
* Become an contributor by helping EdgyORM growing and spread the words across small, medium, large or any company
size.

## Reporting possible bugs and issues

It is natural that you might find something that EdgyORM should support or even experience some sorte of unexpected
behaviour that needs addressing.

The way we love doing things is very simple, contributions should start out with a
[discussion](https://github.com/tarsil/edgy/discussions). The potential bugs shall be raised as "Potential Issue"
in the discussions, the feature requests may be raised as "Ideas".

We can then decide if the discussion needs to be escalated into an "Issue" or not.

When reporting something you should always try to:

* Be as more descriptive as possible
* Provide as much evidence as you can, something like:
    * OS platform
    * Python version
    * Installed dependencies
    * Code snippets
    * Tracebacks

Avoid putting examples extremely complex to understand and read. Simplify the examples as much as possible to make
it clear to understand and get the required help.

## Development

To develop for EdgyORM, create a fork of the [EdgyORM repository](https://github.com/tarsil/edgy) on GitHub.

After, clone your fork with the follow command replacing `YOUR-USERNAME` wih your GitHub username:

```shell
$ git clone https://github.com/YOUR-USERNAME/edgy
```

### Install the project dependencies

```shell
$ cd edgy
$ scripts/install
```

### Enable pre-commit

The project comes with a pre-commit hook configuration. To enable it, just run inside the clone:

```shell
$ pre-commit
```

### Run the tests

To run the tests, use:

```shell
$ scripts/test
```

Because EdgyORM uses pytest, any additional arguments will be passed. More info within the
[pytest documentation](https://docs.pytest.org/en/latest/how-to/usage.html)

For example, to run a single test_script:

```shell
$ scripts/test tests/test_apiviews.py
```

To run the linting, use:

```shell
$ scripts/format
```

### Documentation

Improving the documentation is quite easy and it is placed inside the `edgy/docs` folder.

To start the docs, run:

```shell
$ scripts/docs
```

## Building EdgyORM

To build a package locally, run:

```shell
$ scripts/build
```

Alternatively running:

```
$ scripts/install
```

It will install the requirements and create a local build in your virtual environment.

## Releasing

*This section is for the maintainers of `EdgyORM`*.

### Building the EdgyORM for release

Before releasing a new package into production some considerations need to be taken into account.

* **Changelog**
    * Like many projects, we follow the format from [keepchangelog](https://keepachangelog.com/en/1.0.0/).
    * [Compare](https://github.com/tarsil/edgy/compare/) `main` with the release tag and list of the entries
that are of interest to the users of the framework.
        * What **must** go in the changelog? added, changed, removed or deprecated features and the bug fixes.
        * What is **should not go** in the changelog? Documentation changes, tests or anything not specified in the
point above.
        * Make sure the order of the entries are sorted by importance.
        * Keep it simple.

* *Version bump*
    * The version should be in `__init__.py` of the main package.

#### Releasing

Once the `release` PR is merged, create a new [release](https://github.com/tarsil/edgy/releases/new)
that includes:

Example:

There will be a release of the version `0.2.3`, this is what it should include.

* Release title: `Version 0.2.3`.
* Tag: `0.2.3`.
* The description should be copied from the changelog.

Once the release is created, it should automatically upload the new version to PyPI. If something
does not work with PyPI the release can be done by running `scripts/release`.
