from __future__ import annotations

import asyncio
import math
import struct
from typing import Any, Awaitable, Callable

import numpy as np

from app.errors import CaeError
from app.tensor import quantity_tensor_order, validate_data_schema
from app.ucum import ucum_scale

MAXIMUM_VOXEL_COUNT = 250_000
_NEIGHBOR_OFFSETS = ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1))
_IMPLEMENTATIONS = {
    ("dc-current-density", "0.0.0"): "ec79ace3",
    ("steady-state-heat", "0.0.0"): "a955fbb5",
}
_MATERIAL_KERNEL_SPECS = {
    "electrical.conductivity": (
        "electromagnetism.ElectricConductivity",
        "S.m-1",
    ),
    "thermal.conductivity": (
        "thermodynamics.ThermalConductivity",
        "W.m-1.K-1",
    ),
}


def validate_kernel_tasks(tasks: dict[str, Any], manifest: dict[str, Any]) -> None:
    descriptors = manifest.get("kernelDescriptors")
    for task_name, task in tasks.items():
        if not isinstance(task_name, str) or not task_name.strip():
            raise CaeError("invalid_program", "task names must be non-empty strings")
        if not isinstance(task, dict) or not isinstance(task.get("kernel"), dict) or not isinstance(task.get("config"), dict):
            raise CaeError("invalid_program", f"task {task_name} is not a normalized kernel task")
        kernel = task["kernel"]
        identity = (kernel.get("name"), kernel.get("version"))
        if identity not in _IMPLEMENTATIONS:
            raise CaeError("kernel_not_found", f"CAE kernel {identity[0]}@{identity[1]} is not registered")
        descriptor_hash = kernel.get("descriptorHash", task.get("descriptorHash"))
        if not isinstance(descriptor_hash, str) or not descriptor_hash:
            raise CaeError("invalid_program", f"task {task_name} has no descriptorHash")
        descriptor = task.get("descriptor")
        if descriptor is None:
            descriptor = _find_descriptor(descriptors, identity)
        if descriptor is None:
            raise CaeError("invalid_program", f"descriptor for {identity[0]}@{identity[1]} is missing")
        body = descriptor.get("descriptor", descriptor)
        declared_hash = descriptor.get("descriptorHash", descriptor.get("hash", descriptor_hash))
        actual_hash = stable_hash(body)
        if descriptor_hash != declared_hash or descriptor_hash != actual_hash:
            raise CaeError("descriptor_mismatch", f"descriptor hash mismatch for {identity[0]}@{identity[1]}")
        if descriptor_hash != _IMPLEMENTATIONS[identity]:
            raise CaeError(
                "descriptor_mismatch",
                f"descriptor hash is not registered for {identity[0]}@{identity[1]}",
            )
        if body.get("name") != identity[0] or body.get("version") != identity[1]:
            raise CaeError("descriptor_mismatch", f"descriptor identity mismatch for task {task_name}")
        config_hash = task.get("configHash")
        if not isinstance(config_hash, str) or config_hash != stable_hash(task["config"]):
            raise CaeError("program_hash_mismatch", f"config hash mismatch for task {task_name}")
        _validate_normalized_task_config(body, task["config"], task.get("outputArtifacts"), task_name)


async def run_kernel(
    task: dict[str, Any],
    state: Any,
    inputs: dict[str, Any],
    world: dict[str, Any],
    progress: Callable[[Any], Awaitable[None]],
) -> dict[str, Any]:
    kernel = task.get("kernel") or {}
    config = task.get("config")
    if not isinstance(config, dict):
        raise CaeError("invalid_task", "kernel task has no normalized config")
    identity = (kernel.get("name"), kernel.get("version"))
    if identity == ("dc-current-density", "0.0.0"):
        result = await _run_dc(config, state, inputs, world, progress)
    elif identity == ("steady-state-heat", "0.0.0"):
        result = await _run_heat(config, state, inputs, world, progress)
    else:
        raise CaeError("kernel_not_found", f"CAE kernel {identity[0]}@{identity[1]} is not registered")
    return result if "state" in result else {"state": state, **result}


def stable_hash(value: Any) -> str:
    result = 0x811C9DC5
    ancestors: set[int] = set()

    def append_bytes(data: bytes) -> None:
        nonlocal result
        for byte in data:
            result ^= byte
            result = (result * 0x01000193) & 0xFFFFFFFF

    def append_length(length: int) -> None:
        if length < 0 or length > 0xFFFFFFFF:
            raise CaeError("invalid_program", "canonical data length exceeds uint32")
        append_bytes(struct.pack("<I", length))

    def string_bytes(text: str) -> bytes:
        try:
            return text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise CaeError("invalid_program", "canonical data contains invalid Unicode") from exc

    def append_string(data: bytes) -> None:
        append_bytes(b"\x04")
        append_length(len(data))
        append_bytes(data)

    def append(current: Any) -> None:
        if current is None:
            append_bytes(b"\x00")
            return
        if current is False:
            append_bytes(b"\x01")
            return
        if current is True:
            append_bytes(b"\x02")
            return
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            try:
                number = float(current)
            except (OverflowError, ValueError) as exc:
                raise CaeError("invalid_program", "canonical data number is invalid") from exc
            if not math.isfinite(number):
                raise CaeError("invalid_program", "canonical data numbers must be finite")
            append_bytes(b"\x03")
            append_bytes(struct.pack("<d", 0.0 if number == 0 else number))
            return
        if isinstance(current, str):
            append_string(string_bytes(current))
            return
        if isinstance(current, list):
            identity = id(current)
            if identity in ancestors:
                raise CaeError("invalid_program", "canonical data must not be circular")
            ancestors.add(identity)
            append_bytes(b"\x05")
            append_length(len(current))
            for item in current:
                append(item)
            ancestors.remove(identity)
            return
        if isinstance(current, dict):
            identity = id(current)
            if identity in ancestors:
                raise CaeError("invalid_program", "canonical data must not be circular")
            ancestors.add(identity)
            entries: list[tuple[bytes, Any]] = []
            for key, item in current.items():
                if not isinstance(key, str):
                    raise CaeError("invalid_program", "canonical data object keys must be strings")
                entries.append((string_bytes(key), item))
            entries.sort(key=lambda entry: entry[0])
            append_bytes(b"\x06")
            append_length(len(entries))
            for key, item in entries:
                append_string(key)
                append(item)
            ancestors.remove(identity)
            return
        raise CaeError(
            "invalid_program",
            "canonical data must contain only null, booleans, finite numbers, strings, arrays, and objects",
        )

    append(value)
    return f"{result:08x}"


def _validate_normalized_task_config(
    descriptor: dict[str, Any],
    config: Any,
    output_artifacts: Any,
    task_name: str,
) -> None:
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
    if output_artifacts != resolved_outputs:
        raise CaeError("program_hash_mismatch", f"{path}.outputArtifacts do not match normalized outputs")


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

    component_order = quantity_tensor_order(spec.get("quantityKind"))
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


def _find_descriptor(descriptors: Any, identity: tuple[Any, Any]) -> dict[str, Any] | None:
    if isinstance(descriptors, list):
        candidates = descriptors
    elif isinstance(descriptors, dict):
        candidates = list(descriptors.values())
    else:
        return None
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        body = candidate.get("descriptor", candidate)
        if isinstance(body, dict) and (body.get("name"), body.get("version")) == identity:
            return candidate
    return None


async def _run_dc(
    config: dict[str, Any],
    state: Any,
    inputs: dict[str, Any],
    world: dict[str, Any],
    progress: Callable[[Any], Awaitable[None]],
) -> dict[str, Any]:
    del state
    if inputs:
        raise CaeError("invalid_input", "dc-current-density does not accept artifact inputs")
    scene = _structure_scene(world)
    grid_rule = _single_method(config, "initializations", "dc.voxel-grid")
    group_name = _target_group(grid_rule, "geometry")
    part = _geometry_part(scene, group_name)
    source_rule = _single_method(config, "boundaryConditions", "dc.source-potential")
    reference_rule = _single_method(config, "boundaryConditions", "dc.reference-potential")
    source = _surface(scene, _target_group(source_rule, "surface"), part["id"])
    reference = _surface(scene, _target_group(reference_rule, "surface"), part["id"])
    shape = _grid_shape(grid_rule)
    domain = await _build_domain(scene, part, source, reference, shape, progress, "DC conductor")
    conductivity = _material_scalar(world, part, "electrical.conductivity")
    source_voltage = _number(source_rule["parameters"]["voltage"])
    reference_voltage = _number(reference_rule["parameters"]["voltage"])
    tolerance = _number(config["parameters"]["relativeTolerance"])
    max_iterations = int(_number(config["parameters"]["maxIterations"]))
    system = _create_system(domain, source_voltage, reference_voltage)
    solution, iterations, residual = await _solve(system, tolerance, max_iterations, progress, "DC")
    ticks = _ticks(domain)
    outputs = config.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise CaeError("invalid_task", "dc-current-density requires outputs")
    artifacts: dict[str, Any] = {}
    cross_sections: dict[float, tuple[np.ndarray[Any, Any], float]] = {}
    density_positions = {
        _number(output["parameters"]["crossSectionPosition"])
        for output in outputs
        if output.get("methodId") == "dc.current-density"
    }
    joule: dict[str, Any] | None = None
    for index, output in enumerate(outputs):
        method = output.get("methodId")
        key = output.get("key")
        if not isinstance(key, str):
            raise CaeError("invalid_task", "DC output key must be a string")
        if method == "dc.joule-heating":
            if joule is None:
                active_values = np.empty(solution.size, dtype=np.float64)
                for active, global_index in enumerate(system["active_cells"]):
                    gradient = _gradient(
                        domain,
                        system,
                        solution,
                        int(global_index),
                        source_voltage,
                        reference_voltage,
                    )
                    active_values[active] = conductivity * float(np.dot(gradient, gradient))
                joule = {
                    "value": _dense_values(domain, system, active_values),
                    "axes": [{"ticks": ticks[0]}, {"ticks": ticks[1]}, {"ticks": ticks[2]}],
                }
            artifacts[key] = joule
        elif method in {"dc.current-density", "dc.total-current"}:
            position = _number(output["parameters"]["crossSectionPosition"])
            if position not in cross_sections:
                cross_sections[position] = _cross_section(
                    solution,
                    system,
                    domain,
                    position,
                    conductivity,
                    source_voltage,
                    reference_voltage,
                    position in density_positions,
                )
            values, total = cross_sections[position]
            if method == "dc.total-current":
                artifacts[key] = {"value": total}
            else:
                artifacts[key] = {
                    "value": values[..., None] * domain["axis"],
                    "axes": [{"ticks": ticks[1]}, {"ticks": ticks[2]}],
                }
        else:
            raise CaeError("invalid_task", f"unsupported DC output method: {method}")
        await progress({"stage": "output", "completed": index + 1, "total": len(outputs)})
    return {
        "artifacts": artifacts,
        "observations": {"iterations": iterations, "relativeResidual": residual},
    }


async def _run_heat(
    config: dict[str, Any],
    state: Any,
    inputs: dict[str, Any],
    world: dict[str, Any],
    progress: Callable[[Any], Awaitable[None]],
) -> dict[str, Any]:
    del state
    if any(name != "heatSource" for name in inputs):
        raise CaeError("invalid_input", "steady-state-heat received an undeclared artifact input")
    scene = _structure_scene(world)
    grid_rule = _single_method(config, "initializations", "heat.voxel-grid")
    group_name = _target_group(grid_rule, "geometry")
    part = _geometry_part(scene, group_name)
    boundaries = [
        rule
        for rule in config.get("boundaryConditions", [])
        if isinstance(rule, dict) and rule.get("methodId") == "heat.fixed-temperature"
    ]
    if len(boundaries) != 2:
        raise CaeError("invalid_task", "steady-state-heat requires two fixed-temperature boundaries")
    source = _surface(scene, _target_group(boundaries[0], "surface"), part["id"])
    reference = _surface(scene, _target_group(boundaries[1], "surface"), part["id"])
    shape = _grid_shape(grid_rule)
    domain = await _build_domain(scene, part, source, reference, shape, progress, "Heat domain")
    conductivity = _material_scalar(world, part, "thermal.conductivity")
    source_temperature = _number(boundaries[0]["parameters"]["temperature"])
    reference_temperature = _number(boundaries[1]["parameters"]["temperature"])
    tolerance = _number(config["parameters"]["relativeTolerance"])
    max_iterations = int(_number(config["parameters"]["maxIterations"]))
    volume_source = _volume_source(inputs.get("heatSource"), domain, conductivity)
    system = _create_system(domain, source_temperature, reference_temperature, volume_source)
    solution, iterations, residual = await _solve(system, tolerance, max_iterations, progress, "Heat")
    ticks = _ticks(domain)
    outputs = config.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise CaeError("invalid_task", "steady-state-heat requires outputs")
    artifacts: dict[str, Any] = {}
    temperature: dict[str, Any] | None = None
    maximum: float | None = None
    for index, output in enumerate(outputs):
        method = output.get("methodId")
        key = output.get("key")
        if not isinstance(key, str):
            raise CaeError("invalid_task", "Heat output key must be a string")
        if method == "heat.temperature":
            if temperature is None:
                temperature = {
                    "value": _dense_values(domain, system, solution),
                    "axes": [{"ticks": ticks[0]}, {"ticks": ticks[1]}, {"ticks": ticks[2]}],
                }
            artifacts[key] = temperature
        elif method == "heat.maximum-temperature":
            maximum = float(np.max(solution)) if maximum is None else maximum
            artifacts[key] = {"value": maximum}
        else:
            raise CaeError("invalid_task", f"unsupported Heat output method: {method}")
        await progress({"stage": "output", "completed": index + 1, "total": len(outputs)})
    return {
        "artifacts": artifacts,
        "observations": {"iterations": iterations, "relativeResidual": residual},
    }


def _structure_scene(world: dict[str, Any]) -> dict[str, Any]:
    scene = world.get("structure")
    if not isinstance(scene, dict):
        raise CaeError("invalid_input", "BuiltSample Structure scene is missing")
    return scene


def _single_method(config: dict[str, Any], category: str, method: str) -> dict[str, Any]:
    matches = [
        item
        for item in config.get(category, [])
        if isinstance(item, dict) and item.get("methodId") == method
    ]
    if len(matches) != 1:
        raise CaeError("invalid_task", f"{method} must occur exactly once")
    return matches[0]


def _target_group(rule: dict[str, Any], kind: str) -> str:
    target = rule.get("target")
    prefix = f"structure.{kind}."
    if not isinstance(target, list) or len(target) != 1 or not isinstance(target[0], str) or not target[0].startswith(prefix):
        raise CaeError("invalid_task", f"target must match {prefix}<group>")
    return target[0][len(prefix) :]


def _geometry_part(scene: dict[str, Any], group_name: str) -> dict[str, Any]:
    groups = [
        group
        for group in scene.get("geometryGroups", [])
        if isinstance(group, dict) and group.get("name") == group_name
    ]
    ids = groups[0].get("geometryIds") if len(groups) == 1 else None
    if not isinstance(ids, list) or len(ids) != 1:
        raise CaeError("invalid_task", f"geometry group {group_name!r} must resolve to one part")
    for part in scene.get("parts", []):
        if isinstance(part, dict) and part.get("id") == ids[0]:
            return part
    raise CaeError("invalid_input", f"geometry part {ids[0]!r} is missing")


def _surface(
    scene: dict[str, Any],
    group_name: str,
    expected_part_id: str,
) -> dict[str, Any]:
    groups = [
        group
        for group in scene.get("surfaceGroups", [])
        if isinstance(group, dict) and group.get("name") == group_name
    ]
    ids = groups[0].get("surfaceIds") if len(groups) == 1 else None
    if not isinstance(ids, list) or len(ids) != 1:
        raise CaeError("invalid_task", f"surface group {group_name!r} must resolve to one surface")
    for part in scene.get("parts", []):
        for surface in part.get("surfaces", []) if isinstance(part, dict) else []:
            if isinstance(surface, dict) and surface.get("id") == ids[0]:
                if part.get("id") != expected_part_id:
                    raise CaeError("invalid_task", "terminal surface must belong to the kernel geometry")
                return surface
    raise CaeError("invalid_input", f"surface {ids[0]!r} is missing")


def _grid_shape(rule: dict[str, Any]) -> tuple[int, int, int]:
    parameters = rule.get("parameters")
    value = parameters.get("gridShape") if isinstance(parameters, dict) else None
    value = value.get("value") if isinstance(value, dict) else value
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(not isinstance(item, int) or isinstance(item, bool) or item < 3 for item in value)
    ):
        raise CaeError("invalid_task", "voxel gridShape must contain three integers >= 3")
    if math.prod(value) > MAXIMUM_VOXEL_COUNT:
        raise CaeError("resource_limit", "voxel grid may contain at most 250000 cells")
    return value[0], value[1], value[2]


def _number(value: Any) -> float:
    if isinstance(value, dict):
        value = value.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise CaeError("invalid_task", "kernel parameter must be a finite scalar")
    return float(value)


def _material_scalar(world: dict[str, Any], part: dict[str, Any], property_name: str) -> float:
    material = part.get("material")
    material_name = material.get("name") if isinstance(material, dict) else None
    sample = world.get("sample")
    frozen = sample.get("materialParameters") if isinstance(sample, dict) else None
    materials = frozen.get("materials") if isinstance(frozen, dict) else None
    entry = materials.get(material_name, {}).get(property_name) if isinstance(materials, dict) else None
    descriptor = entry.get("value") if isinstance(entry, dict) else None
    if not isinstance(descriptor, dict) or set(descriptor) != {"dtype", "value", "unit"}:
        raise CaeError(
            "invalid_material",
            f"{property_name} must come from the validated material snapshot",
        )
    quantity_kind, expected_unit = _MATERIAL_KERNEL_SPECS[property_name]
    try:
        validate_data_schema(
            {
                "dtype": descriptor.get("dtype"),
                "unit": descriptor.get("unit"),
                "quantityKind": quantity_kind,
                "basis": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            },
            f"Material {property_name}",
        )
    except CaeError as exc:
        raise CaeError("invalid_material", str(exc)) from exc
    try:
        conversion_scale = ucum_scale(descriptor["unit"], expected_unit)
    except (OverflowError, ValueError, ZeroDivisionError) as exc:
        raise CaeError(
            "invalid_material",
            f"{property_name} unit cannot be converted to {expected_unit}",
        ) from exc
    value = descriptor["value"]
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (3, 3):
        raise CaeError("invalid_material", f"{property_name} must have component shape [3,3]")
    scale = float(np.max(np.abs(array)))
    if scale <= 0 or not np.allclose(array, np.eye(3) * array[0, 0], rtol=1e-12, atol=1e-12):
        raise CaeError("invalid_material", f"{property_name} must be positive and isotropic")
    scalar = float(np.trace(array) / 3) * conversion_scale
    if not math.isfinite(scalar) or scalar <= 0:
        raise CaeError("invalid_material", f"{property_name} must be positive and finite")
    return scalar


async def _build_domain(
    scene: dict[str, Any],
    part: dict[str, Any],
    source_surface: dict[str, Any],
    reference_surface: dict[str, Any],
    shape: tuple[int, int, int],
    progress: Callable[[Any], Awaitable[None]],
    label: str,
) -> dict[str, Any]:
    positions, polygons = _mesh(part, _length_scale(scene.get("lengthUnit")))
    source = _surface_plane(source_surface, polygons, label)
    reference = _surface_plane(reference_surface, polygons, label)
    displacement = reference["center"] - source["center"]
    length = float(np.linalg.norm(displacement))
    if not math.isfinite(length) or length <= 0:
        raise CaeError("invalid_geometry", f"{label} terminal centers must be separated")
    axis = displacement / length
    if (
        float(np.dot(source["normal"], reference["normal"])) > -1 + 1e-7
        or float(np.dot(source["normal"], axis)) > -1 + 1e-7
        or float(np.dot(reference["normal"], axis)) < 1 - 1e-7
    ):
        raise CaeError("invalid_geometry", f"{label} terminals must be parallel, opposite, and normal to their axis")
    projected_y = np.array([0.0, 1.0, 0.0]) - axis * float(np.dot([0.0, 1.0, 0.0], axis))
    projected_z = np.array([0.0, 0.0, 1.0]) - axis * float(np.dot([0.0, 0.0, 1.0], axis))
    u_axis = projected_y if np.linalg.norm(projected_y) > 1e-8 else projected_z
    u_axis = u_axis / np.linalg.norm(u_axis)
    v_axis = np.cross(axis, u_axis)
    v_axis = v_axis / np.linalg.norm(v_axis)
    origin = (source["center"] + reference["center"]) / 2
    offsets = positions - origin
    axial = offsets @ axis
    tolerance = max(length * 1e-8, np.max(np.ptp(positions, axis=0)) * 2e-12, 1e-9)
    if np.any(axial < -length / 2 - tolerance) or np.any(axial > length / 2 + tolerance):
        raise CaeError("invalid_geometry", f"{label} must remain between its terminal planes")
    u_values = offsets @ u_axis
    v_values = offsets @ v_axis
    minimum_u, maximum_u = float(np.min(u_values)), float(np.max(u_values))
    minimum_v, maximum_v = float(np.min(v_values)), float(np.max(v_values))
    if maximum_u <= minimum_u or maximum_v <= minimum_v:
        raise CaeError("invalid_geometry", f"{label} cross-section bounds must be positive")
    axial_spacing = length / shape[0]
    u_spacing = (maximum_u - minimum_u) / shape[1]
    v_spacing = (maximum_v - minimum_v) / shape[2]
    triangles = _triangles(polygons)
    occupancy = np.zeros(math.prod(shape), dtype=np.uint8)
    occupied = 0
    for i in range(shape[0]):
        s = -length / 2 + (i + 0.5) * axial_spacing
        for j in range(shape[1]):
            u = minimum_u + (j + 0.5) * u_spacing
            for k in range(shape[2]):
                v = minimum_v + (k + 0.5) * v_spacing
                index = _voxel_index(i, j, k, shape)
                point = origin + axis * s + u_axis * u + v_axis * v
                if _contains(point, triangles):
                    occupancy[index] = 1
                    occupied += 1
                if (index + 1) % 4096 == 0:
                    await progress({"stage": "occupancy", "completed": index + 1, "total": occupancy.size})
                    await asyncio.sleep(0)
    if occupied == 0:
        raise CaeError("invalid_geometry", f"{label} did not occupy any cells")
    await progress({"stage": "occupancy", "completed": occupancy.size, "total": occupancy.size})
    await _validate_connectivity(occupancy, occupied, shape, progress, label)
    return {
        "shape": shape,
        "axis": axis,
        "length": length,
        "minimum_u": minimum_u,
        "minimum_v": minimum_v,
        "axial_spacing": axial_spacing,
        "u_spacing": u_spacing,
        "v_spacing": v_spacing,
        "occupancy": occupancy,
        "occupied_count": occupied,
    }


def _mesh(part: dict[str, Any], scale: float) -> tuple[np.ndarray[Any, Any], list[np.ndarray[Any, Any]]]:
    geometry = part.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("kind") != "mesh":
        raise CaeError("invalid_geometry", "CAE kernels require a serialized mesh")
    positions = np.asarray(geometry.get("positions"), dtype=np.float64).reshape(-1, 3) * scale
    offsets = np.asarray(geometry.get("polygonOffsets"), dtype=np.int64).reshape(-1)
    if positions.size == 0 or offsets.size < 2 or offsets[0] != 0 or offsets[-1] != positions.shape[0]:
        raise CaeError("invalid_geometry", "serialized mesh offsets are invalid")
    polygons = [positions[offsets[index] : offsets[index + 1]] for index in range(offsets.size - 1)]
    if any(polygon.shape[0] < 3 for polygon in polygons):
        raise CaeError("invalid_geometry", "mesh polygons require at least three vertices")
    return positions, polygons


def _surface_plane(surface: dict[str, Any], polygons: list[np.ndarray[Any, Any]], label: str) -> dict[str, Any]:
    indices = surface.get("polygonIndices")
    if not isinstance(indices, list) or not indices:
        raise CaeError("invalid_geometry", f"{label} terminal has no polygons")
    first = polygons[indices[0]]
    normal = np.cross(first[1] - first[0], first[2] - first[0])
    normal_length = float(np.linalg.norm(normal))
    if normal_length <= 0:
        raise CaeError("invalid_geometry", f"{label} terminal has an invalid normal")
    normal /= normal_length
    weighted = np.zeros(3)
    total_area = 0.0
    points: list[np.ndarray[Any, Any]] = []
    for index in indices:
        try:
            polygon = polygons[index]
        except IndexError as exc:
            raise CaeError("invalid_geometry", f"{label} terminal references a missing polygon") from exc
        points.append(polygon)
        anchor = polygon[0]
        for triangle_index in range(1, polygon.shape[0] - 1):
            second, third = polygon[triangle_index], polygon[triangle_index + 1]
            area = float(np.linalg.norm(np.cross(second - anchor, third - anchor)) / 2)
            weighted += ((anchor + second + third) / 3) * area
            total_area += area
    if total_area <= 0:
        raise CaeError("invalid_geometry", f"{label} terminal has no positive area")
    center = weighted / total_area
    tolerance = 1e-8
    if any(np.any(np.abs((polygon - first[0]) @ normal) > tolerance) for polygon in points):
        raise CaeError("invalid_geometry", f"{label} terminal must be planar")
    return {"center": center, "normal": normal}


def _triangles(polygons: list[np.ndarray[Any, Any]]) -> np.ndarray[Any, Any]:
    result = []
    for polygon in polygons:
        for index in range(1, polygon.shape[0] - 1):
            result.append([polygon[0], polygon[index], polygon[index + 1]])
    return np.asarray(result, dtype=np.float64)


def _contains(point: np.ndarray[Any, Any], triangles: np.ndarray[Any, Any]) -> bool:
    direction = np.array([1.0, 0.3713906763541037, 0.5291502622129182])
    direction /= np.linalg.norm(direction)
    hits: list[float] = []
    for triangle in triangles:
        edge1 = triangle[1] - triangle[0]
        edge2 = triangle[2] - triangle[0]
        pvec = np.cross(direction, edge2)
        determinant = float(np.dot(edge1, pvec))
        if abs(determinant) < 1e-12:
            continue
        inverse = 1 / determinant
        tvec = point - triangle[0]
        u = float(np.dot(tvec, pvec) * inverse)
        if u < -1e-10 or u > 1 + 1e-10:
            continue
        qvec = np.cross(tvec, edge1)
        v = float(np.dot(direction, qvec) * inverse)
        if v < -1e-10 or u + v > 1 + 1e-10:
            continue
        distance = float(np.dot(edge2, qvec) * inverse)
        if distance > 1e-10 and all(abs(distance - previous) > 1e-8 for previous in hits):
            hits.append(distance)
    return len(hits) % 2 == 1


async def _validate_connectivity(
    occupancy: np.ndarray[Any, Any],
    occupied_count: int,
    shape: tuple[int, int, int],
    progress: Callable[[Any], Awaitable[None]],
    label: str,
) -> None:
    source_cells = []
    reference_cells = []
    for j in range(shape[1]):
        for k in range(shape[2]):
            source = _voxel_index(0, j, k, shape)
            reference = _voxel_index(shape[0] - 1, j, k, shape)
            if occupancy[source]:
                source_cells.append(source)
            if occupancy[reference]:
                reference_cells.append(reference)
    if not source_cells or not reference_cells:
        raise CaeError("invalid_geometry", f"{label} must occupy both terminal planes")
    visited = np.zeros(occupancy.size, dtype=np.uint8)
    queue = np.empty(occupied_count, dtype=np.int64)
    queue[0] = source_cells[0]
    visited[source_cells[0]] = 1
    head, tail = 0, 1
    while head < tail:
        index = int(queue[head])
        head += 1
        k = index % shape[2]
        j = (index // shape[2]) % shape[1]
        i = index // (shape[1] * shape[2])
        for di, dj, dk in _NEIGHBOR_OFFSETS:
            ni, nj, nk = i + di, j + dj, k + dk
            if ni < 0 or ni >= shape[0] or nj < 0 or nj >= shape[1] or nk < 0 or nk >= shape[2]:
                continue
            neighbor = _voxel_index(ni, nj, nk, shape)
            if not occupancy[neighbor] or visited[neighbor]:
                continue
            visited[neighbor] = 1
            queue[tail] = neighbor
            tail += 1
        if head % 8192 == 0:
            await progress({"stage": "connectivity", "completed": head, "total": occupied_count})
            await asyncio.sleep(0)
    if tail != occupied_count or not any(visited[index] for index in reference_cells):
        raise CaeError("invalid_geometry", f"{label} cells must form one connected domain")
    await progress({"stage": "connectivity", "completed": occupied_count, "total": occupied_count})


def _create_system(
    domain: dict[str, Any],
    source_value: float,
    reference_value: float,
    volume_source: np.ndarray[Any, Any] | None = None,
) -> dict[str, Any]:
    occupancy = domain["occupancy"]
    shape = domain["shape"]
    active_cells = np.flatnonzero(occupancy).astype(np.int64)
    active_index = np.full(occupancy.size, -1, dtype=np.int64)
    active_index[active_cells] = np.arange(active_cells.size)
    spacings = (domain["axial_spacing"], domain["u_spacing"], domain["v_spacing"])
    weights = tuple(1 / (spacing * spacing) for spacing in spacings)
    neighbor_weights = np.array([weights[0], weights[0], weights[1], weights[1], weights[2], weights[2]])
    neighbors = np.full((active_cells.size, 6), -1, dtype=np.int64)
    diagonal = np.zeros(active_cells.size)
    right_hand_side = np.zeros(active_cells.size)
    initial = np.zeros(active_cells.size)
    for active, index_value in enumerate(active_cells):
        index = int(index_value)
        k = index % shape[2]
        j = (index // shape[2]) % shape[1]
        i = index // (shape[1] * shape[2])
        initial[active] = source_value + (reference_value - source_value) * ((i + 0.5) / shape[0])
        if volume_source is not None:
            right_hand_side[active] = volume_source[index]
        for slot, (di, dj, dk) in enumerate(_NEIGHBOR_OFFSETS):
            ni, nj, nk = i + di, j + dj, k + dk
            if ni < 0 or ni >= shape[0] or nj < 0 or nj >= shape[1] or nk < 0 or nk >= shape[2]:
                continue
            global_neighbor = _voxel_index(ni, nj, nk, shape)
            if not occupancy[global_neighbor]:
                continue
            diagonal[active] += neighbor_weights[slot]
            neighbors[active, slot] = active_index[global_neighbor]
        if i == 0:
            diagonal[active] += 2 * weights[0]
            right_hand_side[active] += 2 * weights[0] * source_value
        if i == shape[0] - 1:
            diagonal[active] += 2 * weights[0]
            right_hand_side[active] += 2 * weights[0] * reference_value
        if not math.isfinite(diagonal[active]) or diagonal[active] <= 0:
            raise CaeError("invalid_geometry", "finite-volume matrix contains an isolated cell")
    return {
        "active_cells": active_cells,
        "active_index": active_index,
        "neighbors": neighbors,
        "neighbor_weights": neighbor_weights,
        "diagonal": diagonal,
        "rhs": right_hand_side,
        "initial": initial,
    }


def _apply_matrix(system: dict[str, Any], values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    result = system["diagonal"] * values
    for slot in range(6):
        neighbors = system["neighbors"][:, slot]
        mask = neighbors >= 0
        result[mask] -= system["neighbor_weights"][slot] * values[neighbors[mask]]
    return result


async def _solve(
    system: dict[str, Any],
    tolerance: float,
    max_iterations: int,
    progress: Callable[[Any], Awaitable[None]],
    label: str,
) -> tuple[np.ndarray[Any, Any], int, float]:
    solution = system["initial"].copy()
    residual = system["rhs"] - _apply_matrix(system, solution)
    preconditioned = residual / system["diagonal"]
    direction = preconditioned.copy()
    residual_preconditioned = float(np.dot(residual, preconditioned))
    rhs_norm = float(np.linalg.norm(system["rhs"])) or 1
    relative_residual = float(np.linalg.norm(residual) / rhs_norm)
    if relative_residual <= tolerance:
        await progress({"stage": "solve", "completed": 0, "total": max_iterations})
        return solution, 0, relative_residual
    for iteration in range(1, max_iterations + 1):
        product = _apply_matrix(system, direction)
        denominator = float(np.dot(direction, product))
        if not math.isfinite(denominator) or denominator <= 0:
            raise CaeError("solver_error", f"{label} finite-volume matrix is not positive definite")
        alpha = residual_preconditioned / denominator
        solution += alpha * direction
        residual -= alpha * product
        relative_residual = float(np.linalg.norm(residual) / rhs_norm)
        if relative_residual <= tolerance:
            await progress({"stage": "solve", "completed": iteration, "total": max_iterations})
            return solution, iteration, relative_residual
        preconditioned = residual / system["diagonal"]
        next_residual_preconditioned = float(np.dot(residual, preconditioned))
        direction = preconditioned + (next_residual_preconditioned / residual_preconditioned) * direction
        residual_preconditioned = next_residual_preconditioned
        if iteration % 8 == 0:
            await progress({"stage": "solve", "completed": iteration, "total": max_iterations})
            await asyncio.sleep(0)
    raise CaeError(
        "solver_convergence",
        f"{label} solve did not converge within {max_iterations} iterations (relative residual {relative_residual})",
    )


def _cross_section(
    solution: np.ndarray[Any, Any],
    system: dict[str, Any],
    domain: dict[str, Any],
    position: float,
    conductivity: float,
    source_voltage: float,
    reference_voltage: float,
    include_values: bool,
) -> tuple[np.ndarray[Any, Any], float]:
    shape = domain["shape"]
    face_index = min(shape[0], max(0, _js_round(position * shape[0])))
    values = np.zeros((shape[2], shape[1]), dtype=np.float64)
    total_density = 0.0
    for row in range(shape[2]):
        k = shape[2] - row - 1
        for j in range(shape[1]):
            current_density = 0.0
            if face_index == 0:
                right_global = _voxel_index(0, j, k, shape)
                if domain["occupancy"][right_global]:
                    current_density = (
                        2
                        * conductivity
                        * (source_voltage - solution[system["active_index"][right_global]])
                        / domain["axial_spacing"]
                    )
            elif face_index == shape[0]:
                left_global = _voxel_index(shape[0] - 1, j, k, shape)
                if domain["occupancy"][left_global]:
                    current_density = (
                        2
                        * conductivity
                        * (solution[system["active_index"][left_global]] - reference_voltage)
                        / domain["axial_spacing"]
                    )
            else:
                left_global = _voxel_index(face_index - 1, j, k, shape)
                right_global = _voxel_index(face_index, j, k, shape)
                if domain["occupancy"][left_global] and domain["occupancy"][right_global]:
                    current_density = (
                        conductivity
                        * (
                            solution[system["active_index"][left_global]]
                            - solution[system["active_index"][right_global]]
                        )
                        / domain["axial_spacing"]
                    )
            if include_values:
                values[row, j] = current_density
            total_density += current_density
    total_current = abs(total_density * domain["u_spacing"] * domain["v_spacing"])
    return values, float(total_current)


def _gradient(
    domain: dict[str, Any],
    system: dict[str, Any],
    values: np.ndarray[Any, Any],
    global_index: int,
    source_value: float,
    reference_value: float,
) -> np.ndarray[Any, Any]:
    shape = domain["shape"]
    k = global_index % shape[2]
    j = (global_index // shape[2]) % shape[1]
    i = global_index // (shape[1] * shape[2])
    center = values[system["active_index"][global_index]]
    coordinates = (i, j, k)
    spacings = (domain["axial_spacing"], domain["u_spacing"], domain["v_spacing"])
    result = np.zeros(3)
    for axis in range(3):
        minus_coordinates = list(coordinates)
        plus_coordinates = list(coordinates)
        minus_coordinates[axis] -= 1
        plus_coordinates[axis] += 1
        minus = (
            system["active_index"][_voxel_index(*minus_coordinates, shape)]
            if coordinates[axis] > 0
            else -1
        )
        plus = (
            system["active_index"][_voxel_index(*plus_coordinates, shape)]
            if coordinates[axis] < shape[axis] - 1
            else -1
        )
        minus_gradient = (
            (center - values[minus]) / spacings[axis]
            if minus >= 0
            else 2 * (center - source_value) / spacings[axis]
            if axis == 0 and coordinates[axis] == 0
            else 0
        )
        plus_gradient = (
            (values[plus] - center) / spacings[axis]
            if plus >= 0
            else 2 * (reference_value - center) / spacings[axis]
            if axis == 0 and coordinates[axis] == shape[axis] - 1
            else 0
        )
        result[axis] = (minus_gradient + plus_gradient) / 2
    return result


def _volume_source(
    artifact: Any,
    domain: dict[str, Any],
    conductivity: float,
) -> np.ndarray[Any, Any]:
    source = np.zeros(domain["occupancy"].size)
    if artifact is None:
        return source
    if not isinstance(artifact, dict) or "value" not in artifact:
        raise CaeError("invalid_input", "heatSource must be a three-dimensional tensor artifact")
    values = np.asarray(artifact["value"], dtype=np.float64)
    expected_shape = (domain["shape"][0], domain["shape"][2], domain["shape"][1])
    if values.shape != expected_shape or np.any(~np.isfinite(values)) or np.any(values < 0):
        raise CaeError("invalid_input", "heatSource shape/value does not match heat.voxel-grid")
    expected_ticks = _ticks(domain)
    axes = artifact.get("axes")
    if not isinstance(axes, list) or len(axes) != 3:
        raise CaeError("invalid_input", "heatSource must include three voxel axes")
    for axis_index, expected in enumerate(expected_ticks):
        actual = axes[axis_index].get("ticks") if isinstance(axes[axis_index], dict) else None
        if actual is None or not np.allclose(np.asarray(actual, dtype=np.float64), expected, rtol=1e-10, atol=1e-12):
            raise CaeError("invalid_input", f"heatSource axis {axis_index} does not match heat.voxel-grid")
    for i in range(domain["shape"][0]):
        for row in range(domain["shape"][2]):
            k = domain["shape"][2] - row - 1
            for j in range(domain["shape"][1]):
                global_index = _voxel_index(i, j, k, domain["shape"])
                if domain["occupancy"][global_index]:
                    source[global_index] = values[i, row, j] / conductivity
    return source


def _ticks(domain: dict[str, Any]) -> tuple[list[float], list[float], list[float]]:
    shape = domain["shape"]
    axial = [
        -domain["length"] / 2 + (index + 0.5) * domain["axial_spacing"]
        for index in range(shape[0])
    ]
    u = [
        domain["minimum_u"] + (index + 0.5) * domain["u_spacing"]
        for index in range(shape[1])
    ]
    v = [
        domain["minimum_v"] + (shape[2] - row - 0.5) * domain["v_spacing"]
        for row in range(shape[2])
    ]
    return axial, v, u


def _dense_values(
    domain: dict[str, Any],
    system: dict[str, Any],
    active_values: np.ndarray[Any, Any],
) -> np.ndarray[Any, Any]:
    shape = domain["shape"]
    values = np.zeros((shape[0], shape[2], shape[1]), dtype=np.float64)
    for i in range(shape[0]):
        for row in range(shape[2]):
            k = shape[2] - row - 1
            for j in range(shape[1]):
                active = system["active_index"][_voxel_index(i, j, k, shape)]
                if active >= 0:
                    values[i, row, j] = active_values[active]
    return values


def _voxel_index(i: int, j: int, k: int, shape: tuple[int, int, int]) -> int:
    return (i * shape[1] + j) * shape[2] + k


def _js_round(value: float) -> int:
    return math.floor(value + 0.5)


def _length_scale(unit: Any) -> float:
    try:
        return ucum_scale(unit, "m")
    except (OverflowError, ValueError, ZeroDivisionError) as exc:
        raise CaeError("invalid_unit", f"unsupported Structure length unit: {unit}") from exc
