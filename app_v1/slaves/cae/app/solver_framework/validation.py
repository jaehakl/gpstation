from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.errors import CaeError

def validate_normalized_task_config(
    descriptor: dict[str, Any],
    config: Any,
    task_name: str,
) -> dict[str, Any]:
    path = f"task {task_name}"
    if not isinstance(config, dict) or set(config) != {
        "parameters",
        "initializations",
        "boundaryConditions",
        "outputs",
    }:
        raise CaeError("invalid_task", f"{path} must contain normalized task configuration fields")
    _validate_parameter_values(config["parameters"], descriptor.get("parameters"), f"{path}.parameters")
    methods = descriptor.get("methods")
    if not isinstance(methods, dict):
        raise CaeError("descriptor_mismatch", f"{path} descriptor methods are invalid")
    resolved_outputs: dict[str, Any] = {}
    for category in ("initializations", "boundaryConditions", "outputs"):
        calls = config[category]
        declared = methods.get(category)
        if not isinstance(calls, list) or not isinstance(declared, list):
            raise CaeError("invalid_task", f"{path}.{category} must be a normalized array")
        by_id = {
            method.get("methodId"): method
            for method in declared
            if isinstance(method, dict) and isinstance(method.get("methodId"), str)
        }
        for method_id, method in by_id.items():
            count = sum(isinstance(call, dict) and call.get("methodId") == method_id for call in calls)
            minimum = method.get("minimumOccurrences")
            maximum = method.get("maximumOccurrences")
            if not isinstance(minimum, int) or not isinstance(maximum, int) or not minimum <= count <= maximum:
                raise CaeError("invalid_task", f"{path}.{category} has invalid {method_id} occurrence count")
        for index, call in enumerate(calls):
            call_path = f"{path}.{category}[{index}]"
            expected_keys = {"methodId", "target", "parameters"}
            if category == "outputs":
                expected_keys.add("key")
            if not isinstance(call, dict) or set(call) != expected_keys:
                raise CaeError("invalid_task", f"{call_path} has invalid fields")
            method = by_id.get(call.get("methodId"))
            if method is None:
                raise CaeError("invalid_task", f"{call_path}.methodId is not declared")
            target = call.get("target")
            target_spec = method.get("target")
            if not isinstance(target, list) or not isinstance(target_spec, dict):
                raise CaeError("invalid_task", f"{call_path}.target is invalid")
            minimum_targets = target_spec.get("minimumTargets")
            maximum_targets = target_spec.get("maximumTargets")
            if (
                not isinstance(minimum_targets, int)
                or not isinstance(maximum_targets, int)
                or not minimum_targets <= len(target) <= maximum_targets
                or len(set(target)) != len(target)
            ):
                raise CaeError("invalid_task", f"{call_path}.target cardinality is invalid")
            prefix = f"{target_spec.get('source')}.{target_spec.get('kind')}."
            if any(not isinstance(item, str) or not item.startswith(prefix) or item == prefix for item in target):
                raise CaeError("invalid_task", f"{call_path}.target is not canonical")
            _validate_parameter_values(call.get("parameters"), method.get("parameters"), f"{call_path}.parameters")
            if category == "outputs":
                key = call.get("key")
                if not isinstance(key, str) or not key.strip() or key in resolved_outputs:
                    raise CaeError("invalid_task", f"{call_path}.key must be unique and non-empty")
                resolved_outputs[key] = {
                    "artifactType": method.get("artifactType"),
                    "data": method.get("data"),
                }
    minimum_outputs = descriptor.get("minimumOutputs", 0)
    if not isinstance(minimum_outputs, int) or len(config["outputs"]) < minimum_outputs:
        raise CaeError("invalid_task", f"{path}.outputs does not meet minimumOutputs")
    return resolved_outputs


def _validate_parameter_values(values: Any, specs: Any, path: str) -> None:
    if not isinstance(values, dict) or not isinstance(specs, dict):
        raise CaeError("invalid_task", f"{path} must be an object")
    if any(name not in specs for name in values):
        raise CaeError("invalid_task", f"{path} contains an undeclared parameter")
    for name, parameter in specs.items():
        if not isinstance(parameter, dict) or not isinstance(parameter.get("data"), dict):
            raise CaeError("descriptor_mismatch", f"{path}.{name} descriptor is invalid")
        if name not in values:
            if parameter.get("required", True):
                raise CaeError("invalid_task", f"{path}.{name} is required")
            continue
        validate_normalized_parameter_value(values[name], parameter["data"], f"{path}.{name}")


def validate_normalized_parameter_value(value: Any, spec: dict[str, Any], path: str = "parameter") -> None:
    dtype_name = spec.get("dtype")
    if not isinstance(dtype_name, str):
        raise CaeError("descriptor_mismatch", f"{path} dtype is invalid")
    descriptor = value if isinstance(value, dict) else None
    if (dtype_name.startswith("float") or spec.get("axes") is not None) and descriptor is None:
        raise CaeError("invalid_task", f"{path} must be a normalized dtype descriptor")
    if descriptor is not None:
        if descriptor.get("dtype") != dtype_name or "value" not in descriptor:
            raise CaeError("invalid_task", f"{path} dtype does not match the descriptor")
        raw = descriptor["value"]
        if dtype_name.startswith("float"):
            if (
                descriptor.get("unit") != spec.get("unit")
                or descriptor.get("quantityKind") != spec.get("quantityKind")
                or descriptor.get("basis") != spec.get("basis")
            ):
                raise CaeError("invalid_task", f"{path} quantity metadata is not canonical")
        elif any(name in descriptor for name in ("unit", "quantityKind", "basis")):
            raise CaeError("invalid_task", f"{path} non-float data must not contain quantity metadata")
    else:
        raw = value

    spec_axes = spec.get("axes")
    if spec_axes is None:
        if descriptor is not None and descriptor.get("axes") is not None:
            raise CaeError("invalid_task", f"{path}.axes must be omitted")
        outer_shape: list[int] = []
    else:
        actual_axes = descriptor.get("axes") if descriptor is not None else None
        if not isinstance(spec_axes, list) or not isinstance(actual_axes, list) or len(actual_axes) != len(spec_axes):
            raise CaeError("invalid_task", f"{path}.axes do not match the descriptor")
        outer_shape = []
        for index, (expected, actual) in enumerate(zip(spec_axes, actual_axes)):
            if not isinstance(expected, dict) or not isinstance(actual, dict):
                raise CaeError("invalid_task", f"{path}.axes[{index}] is invalid")
            length = expected.get("length")
            if not isinstance(length, int):
                raise CaeError("descriptor_mismatch", f"{path}.axes[{index}].length is invalid")
            if actual.get("length") != length:
                raise CaeError("invalid_task", f"{path}.axes[{index}].length must be {length}")
            if (
                actual.get("unit") != expected.get("unit")
                or actual.get("quantityKind") != expected.get("quantityKind")
            ):
                raise CaeError("invalid_task", f"{path}.axes[{index}] is not canonical")
            if expected.get("name") is not None and actual.get("name") != expected.get("name"):
                raise CaeError("invalid_task", f"{path}.axes[{index}].name is not canonical")
            if expected.get("ticks") is not None and actual.get("ticks") != expected.get("ticks"):
                raise CaeError("invalid_task", f"{path}.axes[{index}].ticks are not canonical")
            outer_shape.append(length)

    component_order = spec.get("tensorOrder", 0)
    if not isinstance(component_order, int) or isinstance(component_order, bool) or component_order < 0:
        raise CaeError("descriptor_mismatch", f"{path} tensorOrder is invalid")
    expected_shape = [*outer_shape, *([3] * component_order)]
    leaves: list[Any] = []

    def visit(item: Any, depth: int) -> None:
        if depth == len(expected_shape):
            if isinstance(item, list):
                raise CaeError("invalid_task", f"{path} must have shape {expected_shape}")
            leaves.append(item)
            return
        if not isinstance(item, list) or len(item) != expected_shape[depth]:
            raise CaeError("invalid_task", f"{path} must have shape {expected_shape}")
        for child in item:
            visit(child, depth + 1)

    visit(raw, 0)
    for item in leaves:
        comparable = _validate_parameter_element(item, dtype_name, path)
        if dtype_name == "string":
            minimum_length = spec.get("minimumLength")
            if isinstance(minimum_length, int) and len(item) < minimum_length:
                raise CaeError("invalid_task", f"{path} must contain strings of at least {minimum_length} characters")
            values = spec.get("values")
            if isinstance(values, list) and item not in values:
                raise CaeError("invalid_task", f"{path} must contain only {', '.join(values)}")
            continue
        if dtype_name == "bool":
            continue
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        if isinstance(minimum, (int, float)) and (
            comparable <= minimum if spec.get("exclusiveMinimum") else comparable < minimum
        ):
            relation = "greater than" if spec.get("exclusiveMinimum") else "at least"
            raise CaeError("invalid_task", f"{path} must be {relation} {minimum}")
        if isinstance(maximum, (int, float)) and (
            comparable >= maximum if spec.get("exclusiveMaximum") else comparable > maximum
        ):
            relation = "less than" if spec.get("exclusiveMaximum") else "at most"
            raise CaeError("invalid_task", f"{path} must be {relation} {maximum}")


def _validate_parameter_element(value: Any, dtype_name: str, path: str) -> int | float | str | bool:
    if dtype_name == "bool":
        if not isinstance(value, bool):
            raise CaeError("invalid_task", f"{path} must contain bool values")
        return value
    if dtype_name == "string":
        if not isinstance(value, str):
            raise CaeError("invalid_task", f"{path} must contain string values")
        return value
    try:
        finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise CaeError("invalid_task", f"{path} must contain finite numeric values")
    if dtype_name.startswith("int") or dtype_name.startswith("uint"):
        if not isinstance(value, int) and value != math.trunc(value):
            raise CaeError("invalid_task", f"{path} must contain integer values")
        bits = int(dtype_name.removeprefix("uint").removeprefix("int"))
        minimum = 0 if dtype_name.startswith("uint") else -(1 << (bits - 1))
        maximum = (1 << bits) - 1 if dtype_name.startswith("uint") else (1 << (bits - 1)) - 1
        minimum = max(minimum, -((1 << 53) - 1))
        maximum = min(maximum, (1 << 53) - 1)
        if value < minimum or value > maximum:
            raise CaeError("invalid_task", f"{path} exceeds {dtype_name} safe range")
    elif dtype_name == "float16" and abs(value) > 65504:
        raise CaeError("invalid_task", f"{path} exceeds float16 range")
    elif dtype_name == "float32" and not math.isfinite(float(np.float32(value))):
        raise CaeError("invalid_task", f"{path} exceeds float32 range")
    elif dtype_name != "float64":
        raise CaeError("descriptor_mismatch", f"{path} uses unsupported dtype {dtype_name}")
    return value
