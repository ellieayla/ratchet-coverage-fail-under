Ratchet up a `coverage.py` configuration's `fail_under` to prevent coverage regressions.


Usable with [coverage.py](https://coverage.readthedocs.io) directly, or with [pytest-cov](https://pytest-cov.readthedocs.io/).

Intended to be run in [pre-commit](https://pre-commit.com/) or CI.


If coverage from the last run does _not_ exceed `fail_under` at all,
`coverage run` and `coverage report` will normally fail.
Do nothing in that case.

If code coverage of the last test significantly _exceeds_ `fail_under`,
recommend increasing the configured `fail_under`.

Exits with status `1` when changes to configuration should be made.
If `--write` is passed, also make the changes.

Will not reduce configured `fail_under`; coverage requirements can only increase.

If `fail_under` ever reaches 100%, this hook becomes a no-op and can be safely removed.


```yaml
# .pre-commit-config.yaml

- repo: https://github.com/ellieayla/ratchet-coverage-fail-under
  rev: v1.0.2
  hooks:
    - id: ratchet-coverage
      #args: [--write]  # whether to automatically write pyproject.toml
```

## arguments

* `--cov-config PATH` - the [configuration file](https://coverage.readthedocs.io/en/latest/config.html), ideally `pyproject.toml` but defaults to letting `coverage.py` discover.
* `--data-file PATH` - the [.coverage sqlite database file](https://coverage.readthedocs.io/en/latest/config.html#run-data-file), if necessary to override from configuration file.
* `--threshold PERCENT` - recommend a new `fail_under` that's `PERCENT` of last run. Pass `100%` to ratchet up to last run exactly.
* `--write` - write recommendation back to `pyproject.toml`.
