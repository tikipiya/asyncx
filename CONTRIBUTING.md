# Contributing to AsyncX Tools

Contributions are welcome. Bug reports should include the Python version, operating
system, a minimal reproduction, and the expected and actual behavior.

Security vulnerabilities must be reported privately as described in
[SECURITY.md](SECURITY.md).

## Development setup

```powershell
git clone https://github.com/tikipiya/asyncx.git
cd asyncx
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Quality checks

Run all checks before opening a pull request:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy asyncx
python -m pytest
python -m build --sdist --wheel
python -m twine check dist/*
```

New behavior and bug fixes should include regression tests. Public API changes should
also update README.md and CHANGELOG.md.

## Pull requests

1. Create a focused branch from `main`.
2. Keep unrelated changes in separate pull requests.
3. Explain the motivation, user impact, and validation performed.
4. Wait for all required CI checks to pass.
5. Merge through a pull request; do not push directly to `main`.

## Versioning

AsyncX Tools follows semantic versioning:

- Patch releases (`1.0.1`) contain backward-compatible fixes.
- Minor releases (`1.1.0`) contain backward-compatible features.
- Major releases (`2.0.0`) may contain breaking API changes.
