import hashlib

from aigc._internal.audit import checksum
from aigc._internal.utils import canonical_json_bytes


def test_canonical_json_bytes_stable_for_dict_order():
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert canonical_json_bytes(a) == canonical_json_bytes(b)


def test_checksum_stable_for_nested_structures():
    first = {"nested": {"z": 1, "a": 2}, "arr": [{"b": 2, "a": 1}]}
    second = {"arr": [{"a": 1, "b": 2}], "nested": {"a": 2, "z": 1}}
    assert checksum(first) == checksum(second)
    assert len(checksum(first)) == 64


def test_checksum_uses_sha256():
    payload = {"k": "v"}
    digest = checksum(payload)
    assert digest == hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
