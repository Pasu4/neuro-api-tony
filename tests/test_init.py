import neuro_api_tony.constants


def test_version() -> None:
    assert isinstance(neuro_api_tony.constants.VERSION, str)
