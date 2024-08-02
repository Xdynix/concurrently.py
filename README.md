# concurrently.py

A minimum Python port of Node.js's [`concurrently`][concurrently].

## Installation

```shell
pipx install git+https://github.com/Xdynix/concurrently.py.git
```

## Usage

```shell
concurrentlypy "python3 manage.py runserver" "python3 manage.py runworker"
```

## Development

Prerequisite: [PDM](https://pdm-project.org/latest/)

Environment setup: `pdm sync`

Run linters: `pdm lint`

[concurrently]: https://github.com/open-cli-tools/concurrently
