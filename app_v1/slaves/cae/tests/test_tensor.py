import json

import numpy as np
import pytest
from sdk.protocol.messages import DataChannelAttachment

from app.errors import CaeError
from app.quantity_kind_orders import (
    QUANTITY_KIND_APPLICABLE_UNITS,
    QUANTITY_KIND_SOURCE_SHA256,
    QUANTITY_KIND_TENSOR_ORDERS,
)
from app.tensor import (
    ATTACHMENT_SHARD_BYTES,
    MAX_RECORDED_BYTES,
    decode_attachment_tensors,
    encode_tensor,
    quantity_tensor_order,
)


def test_encodes_little_endian_float_tensor_and_dynamic_ticks():
    tensor, attachments, byte_length = encode_tensor(
        "temperature",
        {
            "dtype": "float64",
            "axes": [{"name": "x"}, {"name": "y"}],
            "unit": "K",
            "quantityKind": "thermodynamics.Temperature",
        },
        {
            "value": np.arange(12, dtype=np.float64).reshape(3, 4),
            "axes": [{"ticks": [0, 1, 2]}, {"ticks": [0, 1, 2, 3]}],
        },
        1,
    )

    assert tensor["shape"] == [3, 4]
    assert tensor["storage"]["kind"] == "inline"
    assert attachments == []
    assert byte_length == 12 * 8


def test_shards_large_tensor_at_16_mib():
    values = np.zeros((ATTACHMENT_SHARD_BYTES // 8 + 1,), dtype=np.float64)

    tensor, attachments, byte_length = encode_tensor(
        "large",
        {
            "dtype": "float64",
            "unit": "{fraction}",
            "quantityKind": "DimensionlessRatio",
            "axes": [{"length": len(values)}],
        },
        values,
        3,
    )

    assert tensor["storage"]["kind"] == "attachments"
    assert tensor["storage"]["ids"] == ["record-3-0", "record-3-1"]
    assert [len(attachment.data) for attachment in attachments] == [ATTACHMENT_SHARD_BYTES, 8]
    assert byte_length == ATTACHMENT_SHARD_BYTES + 8


def test_large_numeric_tensor_never_materializes_a_python_list(monkeypatch):
    class NoListArray(np.ndarray):
        def tolist(self):
            raise AssertionError("large attachment tensors must not call ndarray.tolist()")

    original_asarray = np.asarray

    def guarded_asarray(*args, **kwargs):
        array = original_asarray(*args, **kwargs)
        return array.view(NoListArray) if array.nbytes > 64 * 1024 else array

    monkeypatch.setattr("app.tensor.np.asarray", guarded_asarray)
    values = np.arange(64 * 1024 // 8 + 1, dtype=np.float64)

    tensor, attachments, _byte_length = encode_tensor(
        "large",
        {
            "dtype": "float64",
            "unit": "{fraction}",
            "quantityKind": "DimensionlessRatio",
            "axes": [{"length": len(values)}],
        },
        values,
        1,
    )

    assert tensor["storage"]["kind"] == "attachments"
    assert attachments


def test_record_budget_is_checked_before_dtype_expansion_and_raw_encoding():
    length = (MAX_RECORDED_BYTES // 8) + 1
    value = np.zeros(length, dtype=np.uint8)

    with pytest.raises(CaeError, match="64 MiB") as error:
        encode_tensor(
            "oversized",
            {
                "dtype": "float64",
                "unit": "K",
                "quantityKind": "thermodynamics.Temperature",
                "axes": [{"name": "cell", "length": length}],
            },
            value,
            1,
            max_byte_length=MAX_RECORDED_BYTES,
        )

    assert error.value.code == "resource_limit"


def test_validates_fixed_axes_ticks_and_component_shape():
    with pytest.raises(CaeError, match="length"):
        encode_tensor(
            "bad",
            {
                "dtype": "float32",
                "unit": "{fraction}",
                "quantityKind": "DimensionlessRatio",
                "axes": [{"length": 2}],
            },
            [1, 2, 3],
            1,
        )
    with pytest.raises(CaeError, match="ticks"):
        encode_tensor(
            "bad",
            {
                "dtype": "float32",
                "unit": "{fraction}",
                "quantityKind": "DimensionlessRatio",
                "axes": [{}],
            },
            {"value": [1, 2], "axes": [{"ticks": [0]}]},
            1,
        )
    with pytest.raises(CaeError, match="component"):
        encode_tensor(
            "vector",
            {
                "dtype": "float64",
                "unit": "A.m-2",
                "quantityKind": "electromagnetism.ElectricCurrentDensity",
                "basis": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "axes": [{"length": 2}],
            },
            np.zeros((2, 2)),
            1,
        )
    with pytest.raises(CaeError, match="required for a dynamic"):
        encode_tensor(
            "dynamic",
            {
                "dtype": "float32",
                "unit": "{fraction}",
                "quantityKind": "DimensionlessRatio",
                "axes": [{"name": "position"}],
            },
            [1, 2],
            1,
        )
    with pytest.raises(CaeError, match="do not match DataSchema"):
        encode_tensor(
            "fixed-ticks",
            {
                "dtype": "float32",
                "unit": "{fraction}",
                "quantityKind": "DimensionlessRatio",
                "axes": [{"length": 2, "ticks": ["left", "right"]}],
            },
            {"value": [1, 2], "axes": [{"ticks": ["right", "left"]}]},
            1,
        )


def test_round_trips_bool_and_korean_string_inline_values():
    boolean, _, _ = encode_tensor(
        "mask",
        {"dtype": "bool", "axes": [{"length": 3}]},
        [True, False, True],
        1,
    )
    korean, _, _ = encode_tensor(
        "labels",
        {"dtype": "string", "axes": [{"length": 2}]},
        ["온도", "전류"],
        2,
    )

    assert boolean["storage"]["value"] == [True, False, True]
    assert korean["storage"]["value"] == ["온도", "전류"]


def test_rejects_int64_values_outside_javascript_safe_range():
    with pytest.raises(CaeError, match="int64 range"):
        encode_tensor(
            "unsafe",
            {"dtype": "int64"},
            2**53,
            1,
        )


def test_uses_complete_generated_quantity_kind_tensor_orders():
    assert QUANTITY_KIND_SOURCE_SHA256 == "7f9a6ed1f2f4c2fac2b48da170afebc545faa0118c6c6c8eba6138df80ee9030"
    assert len(QUANTITY_KIND_TENSOR_ORDERS) == 1216
    assert len(QUANTITY_KIND_APPLICABLE_UNITS) == 1216
    assert quantity_tensor_order("acoustics.SoundIntensity") == 1
    assert quantity_tensor_order("coupledPhenomena.PiezoelectricChargeCoefficient") == 3
    assert quantity_tensor_order("mechanics.ElasticStiffnessTensor") == 4

    with pytest.raises(CaeError, match="unknown QuantityKind"):
        quantity_tensor_order("not-a-real-quantity-kind")
    with pytest.raises(CaeError, match="not applicable"):
        encode_tensor(
            "bad-unit",
            {
                "dtype": "float64",
                "unit": "s",
                "quantityKind": "thermodynamics.Temperature",
            },
            300,
            1,
        )


def test_decodes_request_attachment_with_surrounding_descriptor_dtype():
    raw = np.asarray([1.25, 2.5], dtype="<f4").tobytes()
    decoded = decode_attachment_tensors(
        {
            "parameter": {
                "dtype": "float32",
                "value": {
                    "shape": [2],
                    "storage": {
                        "kind": "attachments",
                        "ids": ["input-0"],
                        "byteLength": len(raw),
                    },
                },
            },
        },
        [
            DataChannelAttachment(
                id="input-0",
                name="parameter.bin",
                mimeType="application/octet-stream",
                data=raw,
            )
        ],
    )

    assert decoded["parameter"]["value"].dtype == np.dtype("<f4")
    assert decoded["parameter"]["value"].tolist() == [1.25, 2.5]


def test_decodes_sharded_start_json_before_tensor_attachments():
    raw_values = np.asarray([1.25, 2.5], dtype="<f4").tobytes()
    payload = {
        "parameter": {
            "dtype": "float32",
            "value": {
                "shape": [2],
                "storage": {
                    "kind": "attachments",
                    "ids": ["value-0"],
                    "byteLength": len(raw_values),
                },
            },
        }
    }
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    decoded = decode_attachment_tensors(
        {
            "kind": "cae.start.payload-attachments",
            "storage": {
                "kind": "attachments",
                "ids": ["payload-0"],
                "byteLength": len(raw_payload),
            },
        },
        [
            DataChannelAttachment(id="payload-0", data=raw_payload),
            DataChannelAttachment(id="value-0", data=raw_values),
        ],
    )

    assert decoded["parameter"]["value"].dtype == np.dtype("<f4")
    assert decoded["parameter"]["value"].tolist() == [1.25, 2.5]


def test_rejects_malformed_or_oversized_request_attachments():
    with pytest.raises(CaeError, match="unused request attachment"):
        decode_attachment_tensors(
            {},
            [
                DataChannelAttachment(
                    id="unused",
                    name="unused.bin",
                    mimeType="application/octet-stream",
                    data=b"x",
                )
            ],
        )
    with pytest.raises(CaeError, match="must not exceed 16 MiB"):
        decode_attachment_tensors(
            {},
            [
                DataChannelAttachment(
                    id="large",
                    name="large.bin",
                    mimeType="application/octet-stream",
                    data=b"\0" * (ATTACHMENT_SHARD_BYTES + 1),
                )
            ],
        )
