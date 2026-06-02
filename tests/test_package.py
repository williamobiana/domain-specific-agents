"""Smoke tests verifying the package structure is correct."""

from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src" / "lloyds_expense"


def test_package_directory_exists() -> None:
    assert SRC_DIR.is_dir()


def test_init_module_exists() -> None:
    assert (SRC_DIR / "__init__.py").is_file()


def test_main_module_exists() -> None:
    assert (SRC_DIR / "__main__.py").is_file()


def test_fixtures_directory_exists() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    assert fixtures.is_dir()
