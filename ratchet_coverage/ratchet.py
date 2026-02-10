#!/usr/bin/env python


"""
Read a recent coverage.py output database (.coverage) from coverage.py or pytest-cov,
and ratchet up the pyproject.toml configuration [tool.coverage.report] fail_under value.
"""

from typing import TypedDict, cast
from coverage import Coverage
from coverage.control import DEFAULT_DATAFILE
from argparse import ArgumentParser
from pathlib import Path
from io import StringIO

import tomlkit
import tomlkit.toml_file

def update_pyproject_toml(config_file: Path, expected_config_value: float, acceptable_coverage: float) -> None:
    # model the relevant structure of pyproject.toml
    ConfChunkReport = TypedDict('ConfChunkReport', {'fail_under': float})
    ConfChunkCoverage = TypedDict('ConfChunkCoverage', {'report': ConfChunkReport})
    ConfChunkTool = TypedDict('ConfChunkTool', {'coverage': ConfChunkCoverage})
    ConfChunkDoc = TypedDict('ConfChunkDoc', {'tool': ConfChunkTool})

    file = tomlkit.toml_file.TOMLFile(config_file)
    doc: ConfChunkDoc = cast(ConfChunkDoc, file.read())

    report_section = doc["tool"]["coverage"]["report"]
    if float(report_section['fail_under']) != float(expected_config_value):
        raise ValueError("Configured fail_under changed during run, aborting write.")

    if expected_config_value > acceptable_coverage:
        raise ValueError(f"Refusing to reduce fail_under ({expected_config_value} > {acceptable_coverage})")

    # set new value and write the file back
    report_section['fail_under'] = acceptable_coverage
    file.write(cast(tomlkit.TOMLDocument, doc))


def percentage(argument: str) -> float:
    f = float(argument.removesuffix('%')) / 100.0
    if 0.0 <= f <= 1.0:
        return f
    raise ValueError("Percentage should be between 0-100")


def main() -> int:
    p = ArgumentParser()
    p.add_argument("--data-file", metavar="INFILE", type=Path, default=None, help="path to .coverage sqlite database file (default read from config)")
    p.add_argument("--cov-config", metavar="PATH", type=Path, default=True, help="path to configuration file (ref https://coverage.readthedocs.io/en/latest/config.html)")
    p.add_argument("--threshold", metavar="PCT", default="95%", type=percentage, help="Error if fail_under < threshold * last run report. 100%% fails on any discrepency (default %(default)s)")
    p.add_argument("--write", action="store_true", help="Automatically write back to pyproject.toml. Useful in pre-commit hook.")
    a = p.parse_args()

    c = Coverage(data_file=a.data_file or DEFAULT_DATAFILE, config_file=a.cov_config)
    c.load()

    # write a "total" report to get the percentage coverage as a float in the range 0-100
    devnull = StringIO()
    total_coverage_percentage_reported_last = c.report(output_format="total", file=devnull)

    acceptable_coverage: float = round(a.threshold * total_coverage_percentage_reported_last, ndigits=0)

    if c.config.fail_under == 100.0:
        print("fail_under cannot be ratcheted higher than 100%, this hook can be disabled!")
        return 0

    if c.config.fail_under >= acceptable_coverage:
        print(f"OK: last coverage run reported {total_coverage_percentage_reported_last:.0f}%, within {a.threshold:.0%} of fail_under={c.config.fail_under:.0f}%")
        return 0

    print(f"Last coverage run reported {total_coverage_percentage_reported_last:.0f}% covered, but coverage is configured to require only {c.config.fail_under:.0f}%: Set at least fail_under={acceptable_coverage:.0f} in {c.config.config_file}")

    if a.write:
        update_pyproject_toml(Path(cast(str, c.config.config_file)), c.config.fail_under, acceptable_coverage)

    return 1


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
