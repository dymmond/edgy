# Contributing

Thank you for showing interes in contributing to Edgy. There are many ways you can help and contribute to the
project.

* Try Edgy and [report bugs and issues](https://github.com/dymmond/edgy/issues/new) you find.
* [Implement new features](https://github.com/dymmond/edgy/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
* Help othes by [reviewing pull requests](https://github.com/dymmond/edgy/pulls)
* Help writting documentation
* Use the discussions and actively participate on them.
* Become an contributor by helping Edgy growing and spread the words across small, medium, large or any company
size.

## Reporting possible bugs and issues

It is natural that you might find something that Edgy should support or even experience some sorte of unexpected
behaviour that needs addressing.

The way we love doing things is very simple, contributions should start out with a
[discussion](https://github.com/dymmond/edgy/discussions). The potential bugs shall be raised as "Potential Issue"
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

To develop for Edgy, create a fork of the [Edgy repository](https://github.com/dymmond/edgy) on GitHub.

After, clone your fork with the follow command replacing `YOUR-USERNAME` wih your GitHub username:

```shell
$ git clone https://github.com/YOUR-USERNAME/edgy
```

### Install the project dependencies

Not necessary because the dependencies are automatically installed by hatch.
But if environments should be pre-initialized it can be done with `hatch env`

```shell
$ cd edgy
$ hatch env create
$ hatch env create test
$ hatch env create docs
```

!!! Tip
    This is the recommended way but if you still feel you want your own virtual environment and
    all the packages installed there, you can always run `scripts/install`.

### Enable pre-commit

The project comes with a pre-commit hook configuration. To enable it, just run inside the clone:

```shell
$ hatch run  pre-commit install
```

### Run the tests

First you have to prepare the setup via:

``` shell
# only once required until stopped or db leftovers clogging up
$ docker compose up -d
# required for every terminal session the tests are executed in, except for setups with higher file descriptor limits
$ ulimit -n 10000
```
Note: currently we need to increase the file descriptor limit otherwise later tests cannot execute anymore because of missing file descriptors.
Exact reasons are unknown but we may recreate the engine too often and the filedecriptors close too slow.
This only affects user systems with low file descriptor limits.

To run the tests, use:

```shell
$ hatch test
```

To run a single test_script:

```shell
$ hatch test tests/test_apiviews.py
```

Pytest native arguments can be passed after passing `--`.

To run the linting, use:

```shell
$ hatch fmt
```


#### Tests especially wanted

We have still too few tests for multiple registries, databases and reflection. Adding more tests
would be a good first issue.
Additionally it would be nice to have more tests for fields in action. E.g. IPAddressField and other dbs
than postgres.

### Documentation

Improving the documentation is quite easy and it is placed inside the `edgy/docs` folder.

To start the docs, run:

```shell
$ hatch run docs:serve
```

## Building Edgy

To build a package locally, run:

```shell
$ hatch build
```

Alternatively running:

```shell
$ hatch shell
```

It will install the requirements and create a local build in your virtual environment.


## Releasing

*This section is for the maintainers of `Edgy`*.

### Building the Edgy for release

Before releasing a new package into production some considerations need to be taken into account.

* **Changelog**
    * Like many projects, we follow the format from [keepchangelog](https://keepachangelog.com/en/1.0.0/).
    * [Compare](https://github.com/dymmond/edgy/compare/) `main` with the release tag and list of the entries
that are of interest to the users of the framework.
        * What **must** go in the changelog? added, changed, removed or deprecated features and the bug fixes.
        * What is **should not go** in the changelog? Documentation changes, tests or anything not specified in the
point above.
        * Make sure the order of the entries are sorted by importance.
        * Keep it simple.

* *Version bump*
    * The version should be in `__init__.py` of the main package.

#### Releasing

Once the `release` PR is merged, create a new [release](https://github.com/dymmond/edgy/releases/new)
that includes:

Example:

There will be a release of the version `0.2.3`, this is what it should include.

* Release title: `Version 0.2.3`.
* Tag: `0.2.3`.
* The description should be copied from the changelog.

Once the release is created, it should automatically upload the new version to PyPI. If something
does not work with PyPI the release can be done by running `scripts/release`.
