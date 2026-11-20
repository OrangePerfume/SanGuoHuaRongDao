[简体中文](../../CONTRIBUTING.md) · [繁體中文](../../docs/zh-TW/CONTRIBUTING.md) · [English](../../docs/en/CONTRIBUTING.md)

# Contributing and reporting issues

Issues and pull requests are welcome. Please report the Windows version, exact reproduction steps, actual behavior, and expected behavior. Redact sensitive information from screenshots and logs.

## Development and testing

Python 3.12 x64 is recommended:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m unittest discover -s tests -v
```

## Contribution requirements

- Keep pull requests focused, and describe the changes, risks, and test results.
- Cover boundaries, collisions, undo, step counting, and winning conditions when adding movement controls. Do not remove existing tests or suppress failing assertions.
- Update the Simplified Chinese, Traditional Chinese, and English documentation together when editing READMEs, changelogs, or release notes.
- Do not commit `dist/`, `build/`, `.venv/`, private logs, credentials, or assets without redistribution rights.
- Run GUI tests with PySide6 installed on Windows. Passing pure-Python tests is not the same as Windows EXE acceptance testing.

See [LICENSE](../../LICENSE) and [Third-party notices](THIRD_PARTY_NOTICES.md).
