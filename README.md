Ratchet up a coverage.py configuration's fail_under to prevent coverage regressions.

Usable with coverage.py directly, or with pytest-cov.

Intended to be run in [pre-commit](https://pre-commit.com/) or CI.

Exits with status `1` when changes need to be made.
If `--write` is passed, also make the changes.


```yaml
# .pre-commit-config.yaml

- repo: https://github.com/ellieayla/ratchet-coverage-fail-under
  rev: v1.0.0
  hooks:
    - id: ratchet-coverage
      #args: [--write]  # whether to automatically write pyproject.toml
```
