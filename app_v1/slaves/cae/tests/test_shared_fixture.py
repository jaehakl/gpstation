import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from app.errors import CaeError
from app.kernels import stable_hash, validate_normalized_parameter_value
from app.tensor import dtype_for, encode_tensor

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data-schema-golden.v1.json"
FIXTURE_SHA256 = "cbaf9e7fde0fd96fe2d90eaf0e23ab2acf3e2231bf9b0ce9d02ceec7531cfd4f"


def fixture():
    raw = FIXTURE_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256
    return json.loads(raw.decode("utf-8"))


@pytest.mark.parametrize("case", fixture()["cases"], ids=lambda case: case["name"])
def test_tensor_codec_matches_shared_typescript_fixture(case):
    tensor, attachments, _byte_length = encode_tensor(
        case["name"],
        case["schema"],
        case["input"],
        1,
    )
    assert stable_hash(case["schema"]) == case["schemaHash"]
    assert tensor["shape"] == case["expected"]["shape"]

    actual_axes = tensor.get("axes")
    if actual_axes is None and case["schema"].get("axes"):
        actual_axes = [
            {
                "ticks": axis.get("ticks", list(range(tensor["shape"][index]))),
            }
            for index, axis in enumerate(case["schema"]["axes"])
        ]
    assert actual_axes == case["expected"].get("axes")

    if attachments:
        raw = b"".join(attachment.data for attachment in attachments)
    elif case["schema"]["dtype"] == "string":
        raw = json.dumps(
            tensor["storage"]["value"],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    else:
        dtype = np.dtype("u1") if case["schema"]["dtype"] == "bool" else dtype_for(case["schema"]["dtype"])
        raw = np.asarray(tensor["storage"]["value"], dtype=dtype, order="C").tobytes(order="C")
    assert raw.hex() == case["expected"]["rawHex"]
    assert tensor["storage"]["value"] == case["expected"]["materialized"]


@pytest.mark.parametrize("case", fixture()["valueSpecCases"], ids=lambda case: case["name"])
def test_parameter_constraints_match_shared_typescript_fixture(case):
    spec = case["spec"]
    assert stable_hash(spec) == case["specHash"]

    for value in case["valid"]:
        canonical = _canonical_fixture_value(value, spec)
        validate_normalized_parameter_value(canonical, spec)

    for invalid in case["invalid"]:
        canonical = _canonical_fixture_value(invalid["value"], spec)
        with pytest.raises(CaeError, match=_message_pattern(invalid["issue"])):
            validate_normalized_parameter_value(canonical, spec)


def _canonical_fixture_value(value, spec):
    if (
        isinstance(value, dict)
        and value.get("unit") == "%"
        and spec.get("unit") == "{fraction}"
    ):
        return {
            **value,
            "unit": "{fraction}",
            "value": _scale(value["value"], 0.01),
        }
    return value


def _scale(value, factor):
    if isinstance(value, list):
        return [_scale(item, factor) for item in value]
    return value * factor


def _message_pattern(message):
    return message.replace("[", r"\[").replace("]", r"\]")
