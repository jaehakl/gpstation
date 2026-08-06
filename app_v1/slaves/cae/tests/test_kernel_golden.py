import numpy as np
import pytest

from app.errors import CaeError
from app.kernels import run_kernel


def box_world():
    x0, x1 = -0.05, 0.05
    y0, y1 = -0.0025, 0.0025
    z0, z1 = -0.0025, 0.0025
    polygons = [
        [[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]],
        [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]],
        [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]],
        [[x0, y1, z0], [x0, y1, z1], [x1, y1, z1], [x1, y1, z0]],
        [[x0, y0, z0], [x0, y1, z0], [x1, y1, z0], [x1, y0, z0]],
        [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]],
    ]
    positions = np.asarray([point for polygon in polygons for point in polygon], dtype=np.float64)
    offsets = np.arange(0, positions.shape[0] + 1, 4, dtype=np.uint32)
    part = {
        "id": "conductor",
        "geometry": {
            "kind": "mesh",
            "positions": positions,
            "polygonOffsets": offsets,
        },
        "material": {"name": "Copper", "variables": {}},
        "surfaces": [
            {"id": "source", "name": "source", "polygonIndices": [0]},
            {"id": "reference", "name": "reference", "polygonIndices": [1]},
        ],
    }
    scene = {
        "lengthUnit": "m",
        "parts": [part],
        "geometryGroups": [
            {
                "name": "conductor",
                "geometryIds": ["conductor"],
                "surfaceIds": [],
            }
        ],
        "surfaceGroups": [
            {"name": "sourceTerminal", "geometryIds": [], "surfaceIds": ["source"]},
            {"name": "referenceTerminal", "geometryIds": [], "surfaceIds": ["reference"]},
        ],
    }
    return {
        "structure": scene,
        "experiment": {},
        "sample": {
            "materialParameters": {
                "schemaVersion": 1,
                "materials": {
                    "Copper": {
                        "electrical.conductivity": {
                            "value": {
                                "dtype": "float64",
                                "value": (np.eye(3) * 5.96e7).tolist(),
                                "unit": "S.m-1",
                            }
                        },
                        "thermal.conductivity": {
                            "value": {
                                "dtype": "float64",
                                "value": (np.eye(3) * 401.0).tolist(),
                                "unit": "W.m-1.K-1",
                            }
                        },
                    }
                },
            }
        },
        "setup": {},
    }


def descriptor(value, unit=None, quantity_kind=None):
    return {
        "dtype": "float64",
        "value": value,
        **({"unit": unit} if unit else {}),
        **({"quantityKind": quantity_kind} if quantity_kind else {}),
    }


def dc_task():
    return {
        "kernel": {"name": "dc-current-density", "version": "0.0.0"},
        "config": {
            "parameters": {
                "relativeTolerance": descriptor(1e-10, "{fraction}", "DimensionlessRatio"),
                "maxIterations": 1000,
            },
            "initializations": [
                {
                    "target": ["structure.geometry.conductor"],
                    "methodId": "dc.voxel-grid",
                    "parameters": {
                        "gridShape": {"dtype": "int32", "axes": [{"length": 3}], "value": [20, 11, 11]}
                    },
                }
            ],
            "boundaryConditions": [
                {
                    "target": ["structure.surface.sourceTerminal"],
                    "methodId": "dc.source-potential",
                    "parameters": {"voltage": descriptor(0.001, "V", "electromagnetism.Voltage")},
                },
                {
                    "target": ["structure.surface.referenceTerminal"],
                    "methodId": "dc.reference-potential",
                    "parameters": {"voltage": descriptor(0.0, "V", "electromagnetism.Voltage")},
                },
            ],
            "outputs": [
                {
                    "key": "totalCurrent",
                    "target": ["structure.geometry.conductor"],
                    "methodId": "dc.total-current",
                    "parameters": {
                        "crossSectionPosition": descriptor(0.5, "{fraction}", "DimensionlessRatio")
                    },
                },
                {
                    "key": "jouleHeating",
                    "target": ["structure.geometry.conductor"],
                    "methodId": "dc.joule-heating",
                    "parameters": {},
                },
            ],
        },
    }


def heat_task():
    return {
        "kernel": {"name": "steady-state-heat", "version": "0.0.0"},
        "config": {
            "parameters": {
                "relativeTolerance": descriptor(1e-10, "{fraction}", "DimensionlessRatio"),
                "maxIterations": 1000,
            },
            "initializations": [
                {
                    "target": ["structure.geometry.conductor"],
                    "methodId": "heat.voxel-grid",
                    "parameters": {
                        "gridShape": {"dtype": "int32", "axes": [{"length": 3}], "value": [20, 11, 11]}
                    },
                }
            ],
            "boundaryConditions": [
                {
                    "target": ["structure.surface.sourceTerminal"],
                    "methodId": "heat.fixed-temperature",
                    "parameters": {
                        "temperature": descriptor(293.15, "K", "thermodynamics.Temperature")
                    },
                },
                {
                    "target": ["structure.surface.referenceTerminal"],
                    "methodId": "heat.fixed-temperature",
                    "parameters": {
                        "temperature": descriptor(293.15, "K", "thermodynamics.Temperature")
                    },
                },
            ],
            "outputs": [
                {
                    "key": "temperature",
                    "target": ["structure.geometry.conductor"],
                    "methodId": "heat.temperature",
                    "parameters": {},
                },
                {
                    "key": "maximumTemperature",
                    "target": ["structure.geometry.conductor"],
                    "methodId": "heat.maximum-temperature",
                    "parameters": {},
                },
            ],
        },
    }


@pytest.mark.asyncio
async def test_dc_and_heat_match_existing_uniform_bar_golden():
    progress = []

    async def report(value):
        progress.append(value)

    world = box_world()
    electric = await run_kernel(dc_task(), None, {}, world, report)
    thermal = await run_kernel(
        heat_task(),
        electric["state"],
        {"heatSource": electric["artifacts"]["jouleHeating"]},
        world,
        report,
    )

    assert electric["artifacts"]["totalCurrent"]["value"] == pytest.approx(14.9, abs=1e-6)
    assert np.mean(electric["artifacts"]["jouleHeating"]["value"]) == pytest.approx(5960.0, abs=1e-5)
    assert electric["state"] is None
    assert thermal["artifacts"]["temperature"]["value"].shape == (20, 11, 11)
    assert thermal["artifacts"]["maximumTemperature"]["value"] == pytest.approx(293.16857855, abs=2e-7)
    assert thermal["state"] is None
    assert any(item["stage"] == "solve" for item in progress)


@pytest.mark.asyncio
async def test_solver_rejects_noncanonical_geometry_unit():
    async def report(_value):
        return None

    world = box_world()
    world["structure"]["lengthUnit"] = "[ft_us]"

    with pytest.raises(CaeError, match="solver unit m") as error:
        await run_kernel(dc_task(), None, {}, world, report)
    assert error.value.code == "invalid_unit"


@pytest.mark.asyncio
async def test_dc_resolution_study_preserves_supplied_state_for_stateless_kernels():
    async def report(_value):
        return None

    state = {"revision": 7, "study": "dcResolutionStudy"}
    coarse_task = dc_task()
    coarse_task["config"]["initializations"][0]["parameters"]["gridShape"]["value"] = [6, 5, 5]
    fine_task = dc_task()
    fine_task["config"]["initializations"][0]["parameters"]["gridShape"]["value"] = [8, 7, 7]
    world = box_world()

    coarse = await run_kernel(coarse_task, state, {}, world, report)
    fine = await run_kernel(fine_task, coarse["state"], {}, world, report)

    assert coarse["state"] is state
    assert fine["state"] is state
    assert coarse["artifacts"]["totalCurrent"]["value"] == pytest.approx(14.9, abs=1e-6)
    assert fine["artifacts"]["totalCurrent"]["value"] == pytest.approx(14.9, abs=1e-6)


@pytest.mark.parametrize(
    "descriptor, expected",
    [
        (
            {"dtype": "float64", "value": (np.eye(3) * 5.96e7).tolist(), "unit": "W.m-1.K-1"},
            "canonical float64 in S.m-1",
        ),
        (
            {"dtype": "float64", "value": 5.96e7, "unit": "S.m-1"},
            "component shape",
        ),
    ],
)
@pytest.mark.asyncio
async def test_dc_rejects_noncanonical_material_descriptor(descriptor, expected):
    async def report(_value):
        return None

    world = box_world()
    world["sample"]["materialParameters"]["materials"]["Copper"]["electrical.conductivity"]["value"] = descriptor

    with pytest.raises(CaeError, match=expected) as error:
        await run_kernel(dc_task(), None, {}, world, report)
    assert error.value.code == "invalid_material"
