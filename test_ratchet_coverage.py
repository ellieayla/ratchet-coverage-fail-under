import argparse
import pyexpat
import pytest
import ratchet_coverage
from pathlib import Path
import textwrap
import coverage
import subprocess
import sys
from unittest import mock


@pytest.fixture
def coverage_database_80_percent(tmp_path):
    """Generate a real .coverage run database with 80% coverage"""
    data_file = Path(tmp_path) / Path(".coverage")
    d = coverage.CoverageData(basename=data_file)

    python_file = Path(tmp_path) / Path("example.py")
    with open(python_file, 'w', encoding='utf-8') as f:
        f.write(textwrap.dedent(
            """
            import sys

            def uncalled():
                "This function is not called"
                return 1
            def main():
                if 1 == 2:
                   raise ValueError("uncalled")
                return C()
            class C():
                ...
                def _uncalled(self): ...
            if __name__ == '__main__':
                main()
            """
        ))

    assert not data_file.exists()
    subprocess.check_call(
        args=[sys.executable, "-m", "coverage", "run", "example.py"],
        cwd=tmp_path,
    )
    assert data_file.exists()

    c = coverage.Coverage(data_file=data_file, source_dirs=tmp_path)
    c.load()

    with open("/dev/null", 'w') as devnull:
        total_coverage_percentage_reported_last = c.report(output_format="total", file=devnull)

    assert total_coverage_percentage_reported_last == 80.0

    yield data_file


def make_toml_config_file(tmp_path, fail_under: float) -> Path:
    filename = Path(tmp_path) / "pyproject.toml"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(textwrap.dedent(
            f"""
            [project]
            name = "sut"
            version = "0.1.0"
            description = "Add your description here"
            readme = "README.md"
            requires-python = ">=3.11"
            dependencies = [
                "setuptools>=50.1.2",
                "tomlkit>=0.14.0",
            ]

            [tool.pytest.ini_options]
            addopts = "--cov"

            [tool.coverage.report]
            format = "markdown"
            fail_under = {fail_under}  # comment on fail_under
            # comment under
            """
        ))
    return filename


def test_toml_file_helper(tmp_path) -> None:
    config_file = make_toml_config_file(tmp_path, 123.456789)

    with open(config_file, 'r') as f:
        s = f.read()

    assert "fail_under = 123.456789" in s


def test_rewrite_pyproject_toml_file(tmp_path) -> None:
    toml_config_file = make_toml_config_file(tmp_path, 51)

    # backup
    original_config_file = toml_config_file.with_suffix(".backup.toml")
    toml_config_file.copy(original_config_file)

    ratchet_coverage.update_pyproject_toml(
        config_file=toml_config_file,
        expected_config_value=51.0,
        acceptable_coverage=80.20,
    )

    # ensure the only one line difference
    with open(original_config_file) as orig_f:
        original_lines = list(orig_f.readlines())
    with open(toml_config_file) as changed_f:
        changed_lines = list(changed_f.readlines())

    for row in zip(original_lines, changed_lines, strict=True):
        if 'fail_under' in row[0]:
            assert row[0] == 'fail_under = 51  # comment on fail_under\n'
            assert row[1] == 'fail_under = 80.2  # comment on fail_under\n'
        else:
            assert row[0] == row[1]  # identical

    # read config back in using coverage
    cov = coverage.Coverage(config_file=toml_config_file)
    assert cov.config.fail_under == 80.2



def test_fail_to_rewrite_ini_config_file(tmp_path) -> None:
    ini_contents = textwrap.dedent(
        """
        [coverage:run]
        branch = true

        [coverage:report]
        format = "markdown"
        fail_under = 90
        """
    )
    ini_config_file = Path(tmp_path) / Path("tox.ini")

    with open(ini_config_file, 'w', encoding='utf-8') as f:
        f.write(ini_contents)

    cov = coverage.Coverage(config_file=ini_config_file)
    assert cov.config.fail_under == 90.0

    with pytest.raises(ValueError):
        ratchet_coverage.update_pyproject_toml(
            config_file=ini_config_file,
            expected_config_value=90.0,
            acceptable_coverage=95.0,
        )


def test_error_on_low_fail_under(tmp_path, coverage_database_80_percent, capsys) -> None:
    toml_config_file = make_toml_config_file(tmp_path=tmp_path, fail_under=10)

    with mock.patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            data_file=coverage_database_80_percent,
            cov_config=toml_config_file,
            threshold=0.95,
            write=False,
            )
    ):
        result = ratchet_coverage.main()

    captured = capsys.readouterr()

    assert result == 1
    assert 'but coverage is configured to require only 10%' in captured.out


def test_warning_on_close_fail_under(tmp_path, coverage_database_80_percent, capsys) -> None:
    toml_config_file = make_toml_config_file(tmp_path=tmp_path, fail_under=79)

    with mock.patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            data_file=coverage_database_80_percent,
            cov_config=toml_config_file,
            threshold=0.95,
            write=False,
        )
    ):
        result = ratchet_coverage.main()

    captured = capsys.readouterr()

    assert result == 0
    assert 'OK: last coverage run reported 80%, within 95% of fail_under=79' in captured.out


def test_ratcheted_config_file(tmp_path, coverage_database_80_percent, capsys) -> None:
    toml_config_file = make_toml_config_file(tmp_path=tmp_path, fail_under=10)

    original_config_file = toml_config_file.with_suffix(".backup.toml")
    toml_config_file.copy(original_config_file)

    with mock.patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            data_file=coverage_database_80_percent,
            cov_config=toml_config_file,
            threshold=0.95,
            write=True
        )
    ):
        result = ratchet_coverage.main()

    captured = capsys.readouterr()

    assert result == 1
    assert 'Set at least fail_under=76 in' in captured.out

    # ensure the only one line difference
    with open(original_config_file) as orig_f:
        original_lines = list(orig_f.readlines())
    with open(toml_config_file) as changed_f:
        changed_lines = list(changed_f.readlines())

    for row in zip(original_lines, changed_lines, strict=True):
        if 'fail_under' in row[0]:
            assert row[0] == 'fail_under = 10  # comment on fail_under\n'
            assert row[1] == 'fail_under = 76.0  # comment on fail_under\n'
        else:
            assert row[0] == row[1]  # identical

    # read config back in using coverage
    cov = coverage.Coverage(config_file=toml_config_file)
    assert cov.config.fail_under == 76.0


@pytest.mark.parametrize("percent_string", ["1", "1.5", "0", "0.0", "100.0", "5%", "5.5%", "12.34567%"])
def test_argparse_percentage_successful(percent_string):
    p = argparse.ArgumentParser()
    p.add_argument("--percent", required=True, type=ratchet_coverage.percentage)

    a = p.parse_args(["--percent", percent_string])

    assert isinstance(a.percent, float)
    assert 0 <= a.percent
    assert a.percent <= 1

@pytest.mark.parametrize("percent_string", ["-1", "-1.5%", "200%", "100.0001"])
def test_argparse_percentage_errors(percent_string, capsys):
    p = argparse.ArgumentParser()
    p.add_argument("--percent", required=True, type=ratchet_coverage.percentage)

    with pytest.raises(SystemExit) as e:
        _ = p.parse_args(["--percent", percent_string])

    captured = capsys.readouterr()
    assert 'invalid percentage value' in captured.err


def test_100_percent_coverage_recommend_removing_hook(tmp_path, coverage_database_80_percent, capsys):
    toml_config_file = make_toml_config_file(tmp_path=tmp_path, fail_under=100.0)

    with mock.patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            data_file=coverage_database_80_percent,
            cov_config=toml_config_file,
            threshold=0.95,
            write=False
        )
    ):
        result = ratchet_coverage.main()

    assert result == 0
    captured = capsys.readouterr()

    assert 'this hook can be disabled' in captured.out


def test_unexpected_fail_under_configuration(tmp_path, capsys):
    toml_config_file = make_toml_config_file(tmp_path=tmp_path, fail_under=99.0)

    with pytest.raises(ValueError) as e:
        ratchet_coverage.update_pyproject_toml(toml_config_file, expected_config_value=1, acceptable_coverage=2)
    assert 'fail_under changed during run' in str(e)
