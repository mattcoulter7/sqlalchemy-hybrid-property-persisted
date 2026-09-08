<div align="center">

# Python Package Template

The template repository for creating Python packages.

![Python](https://img.shields.io/badge/Python-3.12-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![UV](https://img.shields.io/badge/UV-Fast-6E40C9?style=for-the-badge)
![Hatchling](https://img.shields.io/badge/Hatchling-PEP517-6E40C9?style=for-the-badge)
![Ruff](https://img.shields.io/badge/Ruff-Lint-000000?style=for-the-badge)
![Pre-commit](https://img.shields.io/badge/Pre--commit-Hooks-000000?style=for-the-badge)
![Pytest](https://img.shields.io/badge/Pytest-Unit%2BAsync-08979C?style=for-the-badge)
![Coverage](https://img.shields.io/badge/Cov-Reports-08979C?style=for-the-badge)
![GitHub Actions](https://img.shields.io/badge/Actions-CI%2FCD-F7B500?style=for-the-badge&logo=github-actions)
![PyPI](https://img.shields.io/badge/PyPI-Publish-3775A9?style=for-the-badge&logo=pypi&logoColor=white)
![Makefile](https://img.shields.io/badge/Makefile-Scripts-F7B500?style=for-the-badge)

[![CI](https://github.com/mattcoulter7/python-package-template/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/mattcoulter7/python-package-template/actions/workflows/ci.yaml)

</div>

---

## Template Checklist
- [ ] Create a repository using this template.
- [ ] Rename module `src/python_package_template` -> `src/your_package_name`
- [ ] Rename tests module `tests/python_package_template` -> `tests/your_package_name`
- [ ] Update `pyproject.toml`: `[project]` section based on your package name, versioning, and metadata.
- [ ] Update `README.md` references of `python-package-template` -> `your-package-name`
- [ ] Configure PyPI trusted publishing for the repository.
- [ ] Publish your package to PyPI by creating a release.
- [ ] Remove this section

---

## Table of Contents
<!-- toc -->

- [Introduction](#introduction)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Formatting and linting](#formatting-and-linting)
- [CICD](#cicd)
- [Credits](#credits)

<!-- tocstop -->

---

## Introduction

This template repository aims to streamline the creation, testing, and publishing of isolated Python packages.

---

## Quick Start
Since this is just a package, and not a service, there is no real "run" action. But you can run the tests immediately.

Here are a list of available commands via make.

### Bare Metal (i.e. your machine)
1. `make install` - install the required dependencies.
2. `make test` - runs the tests.

## Installation

### For Dev work on the repo

Install `uv`, (_if you haven't already_)
https://docs.astral.sh/uv/getting-started/installation/#installation-methods
```shell
brew install uv
```

Initialise pre-commit (validates ruff on commit.)
```shell
uv run pre-commit install
```

Install dependencies (including dev dependencies)
```shell
uv sync
```

If you are adding a new dev dependency, please run:
```shell
uv add --dev {your-new-package}
```

### Package module

Import this package into your project:

```python
from python_package_template.placeholder import placeholder_func
```

---

## Usage

### Adding the dependency to your project
The library is available on PyPI. You can install it using the following command:

**Using pip**:

```shell
pip install python-package-template
```

**Using UV**

Add the dependency:
```shell
uv add python-package-template
```

**Using poetry**:

```shell
poetry add python-package-template
```

### How tos

**Example Usage**

```python
# Please update this based on your package!

from python_package_template.placeholder import placeholder_func

if __name__ == "__main__":
    print("This is a placeholder: ", placeholder_func())
```

---

## Formatting and linting

We use Ruff as the formatter and linter.
The pre-commit has hooks which runs checking and applies linting automatically.
The CI validates the linting, ensuring main is always looking clean.

You can manually use these commands too:
1. `make lint` - check for linting issues.
2. `make format` - fix linting issues.

---

## CICD

### Publishing to PyPI

We publish to PyPI using GitHub releases and PyPI trusted publishing. Steps are as follows:

1. Manually update the version in `pyproject.toml` file using a PR and merge to main. Use `uv version --bump {patch/minor/major}` to update the version.
2. Create a new release in GitHub with the tag name as the version number. This will trigger the `publish` workflow. In the Release window, type in the version number and it will prompt to create a new tag.
3. Verify the release on PyPI.

---

## Credits
This template repository has taken inspiration from the following repositories.
- [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template)
