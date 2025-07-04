import pytest

from simulation_bridge.src.utils.validation import is_valid_dataset_uri


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("https://example.com/data", True),
        ("s3://bucket/key", True),
        ("file:///tmp/data.csv", True),
        ("nfs:///server/share/data", True),
        ("sftp://example.com/data", False),
        ("just_a_string", False),
        ("", False),
    ],
)
def test_is_valid_dataset_uri(uri, expected):
    assert is_valid_dataset_uri(uri) is expected
