"""Utility validation helpers."""

from urllib.parse import urlparse


ALLOWED_DATASET_SCHEMES = {"http", "https", "s3", "file", "nfs"}


def is_valid_dataset_uri(uri: str) -> bool:
    """Return True if the dataset URI is valid and uses an allowed scheme."""
    if not uri:
        return False
    parsed = urlparse(uri)
    if parsed.scheme not in ALLOWED_DATASET_SCHEMES:
        return False
    # For file/nfs allow empty netloc but require path
    if parsed.scheme in {"file", "nfs"}:
        return bool(parsed.path)
    # For http/https/s3 require network location
    return bool(parsed.netloc)