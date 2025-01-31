from semver import Version

from neuro_api_tony import constants


def test_version_exists() -> None:
    assert isinstance(constants.VERSION, str)


def test_version_is_semantic() -> None:
    assert Version.is_valid(constants.VERSION)


def test_package_name_exists() -> None:
    assert isinstance(constants.PACKAGE_NAME, str)
