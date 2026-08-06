import asyncio
import gc
import hashlib

import numpy as np
import pytest
from sdk.protocol.messages import DataChannelMessage
from sdk.slave import SlaveContext

from app.errors import CaeError, ProtocolError
from app.handlers import cae_simulation_next, cae_simulation_start
from app.kernels import stable_hash
from app.runtime import SimulationApi


def payload():
    descriptor = {"name": "dc-current-density", "version": "0.0.0"}
    descriptor_hash = stable_hash(descriptor)
    total_current_schema = {
        "dtype": "float64",
        "unit": "A",
        "quantityKind": "electromagnetism.ElectricCurrent",
    }
    recorded_data = {"totalCurrent": total_current_schema}
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        "    result = await sim.run(tasks[\"electric\"])\n"
        "    await sim.record(\"totalCurrent\", result[\"artifacts\"][\"totalCurrent\"])\n"
        "    return result[\"state\"]\n"
    )
    scene = {
        "sceneHash": "c" * 64,
        "lengthUnit": "m",
        "parts": [],
        "tree": {"key": "root", "label": "root", "children": []},
        "geometryGroups": [],
        "surfaceGroups": [],
    }
    return {
        "sample": {
            "kind": "sample",
            "structure": {
                "kind": "structure",
                "sourceHash": "d" * 64,
                "seed": 1,
                "variables": {},
                "varsSchema": {},
                "scene": scene,
            },
            "materialParameters": {"schemaVersion": 1, "materials": {}},
            "materialWarnings": [],
        },
        "setup": {
            "kind": "setup",
            "experiment": {
                "kind": "experiment",
                "scene": scene,
                "variables": {},
                "varsSchema": {},
                "seed": 1,
                "sourceHash": "a" * 64,
                "simulationProgram": {
                    "formatVersion": 2,
                    "simulationApiVersion": "1",
                    "programHash": "a" * 64,
                    "pythonSource": source,
                    "pythonSourceHash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "recordedDataSchemaHash": stable_hash(recorded_data),
                    "kernelDescriptors": [
                        {
                            "descriptor": descriptor,
                            "descriptorHash": descriptor_hash,
                        }
                    ],
                    "tasks": {
                        "electric": {
                            "kernel": {
                                "name": "dc-current-density",
                                "version": "0.0.0",
                                "descriptorHash": descriptor_hash,
                            },
                            "descriptor": {
                                **descriptor,
                                "inputPorts": {},
                            },
                            "config": {},
                            "configHash": stable_hash({}),
                            "outputArtifacts": {
                                "totalCurrent": {
                                    "artifactType": "caemble.dc/total-current@1",
                                    "data": total_current_schema,
                                }
                            },
                        }
                    },
                    "recordedData": recorded_data,
                },
            },
            "materialParameters": {"schemaVersion": 1, "materials": {}},
            "materialWarnings": [],
        },
    }


def artifact_chain_payload(
    artifact_expression,
    *,
    input_name="carry",
    artifact_types=None,
    producer_schema=None,
    consumer_schema=None,
):
    request = payload()
    program = request["setup"]["experiment"]["simulationProgram"]
    producer = program["tasks"].pop("electric")
    output_spec = producer["outputArtifacts"]["totalCurrent"]
    if producer_schema is not None:
        output_spec = {**output_spec, "data": producer_schema}
        producer = {
            **producer,
            "outputArtifacts": {"totalCurrent": output_spec},
        }
    program["tasks"] = {
        "producer": producer,
        "consumer": {
            **producer,
            "descriptor": {
                **producer["descriptor"],
                "inputPorts": {
                    "carry": {
                        "artifactTypes": artifact_types
                        or [output_spec["artifactType"]],
                        "minimumOccurrences": 1,
                        "maximumOccurrences": 1,
                        "data": consumer_schema or output_spec["data"],
                    }
                },
            },
        },
    }
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        '    produced = await sim.run(tasks["producer"])\n'
        f'    await sim.run(tasks["consumer"], inputs={{"{input_name}": {artifact_expression}}})\n'
        "    return None\n"
    )
    program["pythonSource"] = source
    program["pythonSourceHash"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return request


@pytest.mark.asyncio
async def test_start_does_not_compute_and_next_applies_record_ack_backpressure(monkeypatch):
    calls = 0

    async def fake_kernel(task, state, inputs, world, progress):
        nonlocal calls
        calls += 1
        return {
            "state": {"done": True},
            "artifacts": {"totalCurrent": {"value": 14.9}},
            "observations": {},
        }

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    assert start.payload["kind"] == "started"
    assert calls == 0
    run_id = start.payload["runId"]

    first = await cae_simulation_next(
        DataChannelMessage(
            id="next-1",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-1"),
    )

    assert calls == 1
    assert first.payload == {
        "kind": "record",
        "sequence": 1,
        "name": "totalCurrent",
        "tensor": {
            "shape": [],
            "storage": {"kind": "inline", "value": 14.9},
        },
    }
    assert run_id in memory["runs"]
    run = memory["runs"][run_id]
    previous_heartbeat = run.heartbeat_task
    assert previous_heartbeat is not None
    assert not previous_heartbeat.done()
    assert run.active_context.call_id == "next-1"

    final = await cae_simulation_next(
        DataChannelMessage(
            id="next-2",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": 1},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-2"),
    )

    assert final.payload["kind"] == "complete"
    assert final.payload["recordSequences"] == [1]
    assert final.payload["finalState"] == {"done": True}
    assert previous_heartbeat.cancelled()
    assert run.heartbeat_task is None
    assert run.active_context is None
    assert run_id not in memory["runs"]


@pytest.mark.asyncio
async def test_run_timeout_while_record_is_pending_remains_reachable_after_ack(monkeypatch):
    async def fake_kernel(task, state, inputs, world, progress):
        return {
            "state": {"done": True},
            "artifacts": {"totalCurrent": {"value": 14.9}},
            "observations": {},
        }

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    run_id = start.payload["runId"]
    memory["runs"][run_id].max_run_seconds = 0.01

    record = await cae_simulation_next(
        DataChannelMessage(
            id="next-1",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-1"),
    )
    assert record.payload["kind"] == "record"
    await asyncio.sleep(0.05)

    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next-2",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": record.payload["sequence"]},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-2"),
    )

    assert failed.payload["kind"] == "failed"
    assert failed.payload["error"]["code"] == "run_timeout"
    assert run_id not in memory["runs"]


@pytest.mark.asyncio
async def test_record_ack_watchdog_cleans_up_after_outer_run_timeout(monkeypatch):
    async def fake_kernel(task, state, inputs, world, progress):
        return {
            "state": None,
            "artifacts": {"totalCurrent": {"value": 14.9}},
            "observations": {},
        }

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    monkeypatch.setattr("app.runtime.RECORD_ACK_TIMEOUT_SECONDS", 0.04)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    run_id = start.payload["runId"]
    run = memory["runs"][run_id]
    run.max_run_seconds = 0.01

    record = await cae_simulation_next(
        DataChannelMessage(
            id="next-1",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-1"),
    )
    assert record.payload["kind"] == "record"
    await asyncio.sleep(0.08)

    assert run.closed
    assert run.pending is None
    assert run.heartbeat_task is None
    assert run_id not in memory["runs"]


@pytest.mark.asyncio
async def test_sim_run_rejects_equal_but_unregistered_task(monkeypatch):
    request = payload()
    program = request["setup"]["experiment"]["simulationProgram"]
    rogue_task = repr(program["tasks"]["electric"])
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        f"    task = {rogue_task}\n"
        "    return await sim.run(task)\n"
    )
    program["pythonSource"] = source
    program["pythonSourceHash"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    calls = 0

    async def fake_kernel(task, state, inputs, world, progress):
        nonlocal calls
        calls += 1
        return {"state": None, "artifacts": {}, "observations": {}}

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next",
            type="cae.simulation.next",
            payload={"runId": start.payload["runId"], "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
    )

    assert failed.payload["kind"] == "failed"
    assert failed.payload["error"] == {
        "code": "invalid_input",
        "message": "sim.run only accepts a task registered by this BuiltSetup",
    }
    assert calls == 0


@pytest.mark.asyncio
async def test_sim_run_validates_actual_kernel_output_against_resolved_data_schema(monkeypatch):
    async def fake_kernel(task, state, inputs, world, progress):
        return {
            "state": None,
            "artifacts": {"totalCurrent": {"value": np.asarray([1.0, 2.0])}},
            "observations": {},
        }

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next",
            type="cae.simulation.next",
            payload={"runId": start.payload["runId"], "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
    )

    assert failed.payload["kind"] == "failed"
    assert failed.payload["error"]["code"] == "invalid_tensor"
    assert "tensor rank" in failed.payload["error"]["message"]


@pytest.mark.parametrize(
    "mutation",
    [
        'tasks["electric"] = tasks["electric"]',
        'tasks["electric"]["config"]["rogue"] = 1',
        'vars["rogue"] = 1',
        'world["setup"]["experiment"]["seed"] = 2',
        'world["setup"]["experiment"]["simulationProgram"]["tasks"]["electric"]["config"]["rogue"] = 1',
    ],
)
@pytest.mark.asyncio
async def test_simulation_rejects_mutation_assignment_targets(mutation, monkeypatch):
    request = payload()
    program = request["setup"]["experiment"]["simulationProgram"]
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        f"    {mutation}\n"
        '    return await sim.run(tasks["electric"])\n'
    )
    program["pythonSource"] = source
    program["pythonSourceHash"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    calls = 0

    async def fake_kernel(task, state, inputs, world, progress):
        nonlocal calls
        calls += 1
        return {"state": None, "artifacts": {}, "observations": {}}

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    assert start.payload["kind"] == "failed"
    assert start.payload["error"]["code"] == "invalid_program"
    assert "local names" in start.payload["error"]["message"]
    assert calls == 0


@pytest.mark.asyncio
async def test_world_manifest_task_is_not_an_alias_of_registered_task(monkeypatch):
    request = payload()
    program = request["setup"]["experiment"]["simulationProgram"]
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        '    task = world["setup"]["experiment"]["simulationProgram"]["tasks"]["electric"]\n'
        "    return await sim.run(task)\n"
    )
    program["pythonSource"] = source
    program["pythonSourceHash"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    calls = 0

    async def fake_kernel(task, state, inputs, world, progress):
        nonlocal calls
        calls += 1
        return {"state": None, "artifacts": {}, "observations": {}}

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next",
            type="cae.simulation.next",
            payload={"runId": start.payload["runId"], "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
    )

    assert failed.payload["error"]["code"] == "invalid_input"
    assert calls == 0


@pytest.mark.parametrize(
    "second_arguments",
    [
        'state=coarse["state"], inputs={"carry": coarse["artifacts"]["totalCurrent"]}',
        '{"state": coarse["state"], "inputs": {"carry": coarse["artifacts"]["totalCurrent"]}}',
    ],
)
@pytest.mark.asyncio
async def test_sim_run_forwards_state_and_owned_artifact_to_registered_kernel(
    second_arguments,
    monkeypatch,
):
    request = payload()
    program = request["setup"]["experiment"]["simulationProgram"]
    electric = program["tasks"].pop("electric")
    program["tasks"] = {
        "solveCoarse": electric,
        "solveFine": {
            **electric,
            "descriptor": {
                **electric["descriptor"],
                "inputPorts": {
                    "carry": {
                        "artifactTypes": ["caemble.dc/total-current@1"],
                        "minimumOccurrences": 1,
                        "maximumOccurrences": 1,
                        "data": electric["outputArtifacts"]["totalCurrent"]["data"],
                    }
                },
            },
        },
    }
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        '    coarse = await sim.run(tasks["solveCoarse"])\n'
        f'    fine = await sim.run(tasks["solveFine"], {second_arguments})\n'
        '    await sim.record("totalCurrent", fine["artifacts"]["totalCurrent"])\n'
        '    return fine["state"]\n'
    )
    program["pythonSource"] = source
    program["pythonSourceHash"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    calls = []
    produced = []

    async def fake_kernel(task, state, inputs, world, progress):
        calls.append({"task": task, "state": state, "inputs": inputs})
        artifact = {"value": 14.9}
        produced.append(artifact)
        return {
            "state": {"step": len(calls)},
            "artifacts": {"totalCurrent": artifact},
            "observations": {},
        }

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    run_id = start.payload["runId"]

    record = await cae_simulation_next(
        DataChannelMessage(
            id="next-1",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-1"),
    )
    complete = await cae_simulation_next(
        DataChannelMessage(
            id="next-2",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": record.payload["sequence"]},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-2"),
    )

    assert calls[0]["state"] is None
    assert calls[0]["inputs"] == {}
    assert calls[1]["state"] == {"step": 1}
    assert calls[1]["inputs"]["carry"] is produced[0]
    assert [entry["task"] for entry in complete.payload["trace"]] == [
        "solveCoarse",
        "solveFine",
    ]
    assert complete.payload["trace"][0]["inputStateRevision"] == 0
    assert complete.payload["trace"][0]["outputStateRevision"] == 1
    assert complete.payload["trace"][0]["inputArtifacts"] == {}
    assert complete.payload["trace"][1]["inputStateRevision"] == 1
    assert complete.payload["trace"][1]["outputStateRevision"] == 2
    assert complete.payload["trace"][1]["inputArtifacts"] == {
        "carry": {
            "id": "artifact-1",
            "artifactType": "caemble.dc/total-current@1",
        }
    }
    assert complete.payload["finalStateRevision"] == 2
    assert complete.payload["finalState"] == {"step": 2}


@pytest.mark.asyncio
async def test_sim_run_rejects_fabricated_state_before_kernel_execution(monkeypatch):
    request = payload()
    program = request["setup"]["experiment"]["simulationProgram"]
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        '    return await sim.run(tasks["electric"], state={"forged": True})\n'
    )
    program["pythonSource"] = source
    program["pythonSourceHash"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    calls = 0

    async def fake_kernel(task, state, inputs, world, progress):
        nonlocal calls
        calls += 1
        return {"state": None, "artifacts": {}, "observations": {}}

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next",
            type="cae.simulation.next",
            payload={"runId": start.payload["runId"], "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
    )

    assert failed.payload["kind"] == "failed"
    assert failed.payload["error"]["code"] == "invalid_state"
    assert calls == 0


@pytest.mark.parametrize(
    "case_payload, expected",
    [
        (
            artifact_chain_payload(
                '{"value": 14.9, "unit": "V"}',
            ),
            "live artifact returned by sim.run",
        ),
        (
            artifact_chain_payload(
                'produced["artifacts"]["totalCurrent"]',
                input_name="wrongPort",
            ),
            "is not declared",
        ),
        (
            artifact_chain_payload(
                'produced["artifacts"]["totalCurrent"]',
                artifact_types=["caemble.other/value@1"],
            ),
            "rejects artifact type",
        ),
        (
            artifact_chain_payload(
                'produced["artifacts"]["totalCurrent"]',
                producer_schema={
                    "dtype": "float64",
                    "unit": "m",
                    "quantityKind": "Length",
                },
                consumer_schema={
                    "dtype": "float64",
                    "unit": "cm",
                    "quantityKind": "Length",
                },
            ),
            "DataSchema is incompatible",
        ),
    ],
)
@pytest.mark.asyncio
async def test_sim_run_rejects_unowned_or_incompatible_artifacts_before_consumer_kernel(
    case_payload,
    expected,
    monkeypatch,
):
    calls = 0

    async def fake_kernel(task, state, inputs, world, progress):
        nonlocal calls
        calls += 1
        return {
            "state": None,
            "artifacts": {"totalCurrent": {"value": 14.9}},
            "observations": {},
        }

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=case_payload),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next",
            type="cae.simulation.next",
            payload={"runId": start.payload["runId"], "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
    )

    assert failed.payload["kind"] == "failed"
    assert failed.payload["error"]["code"] == "invalid_input"
    assert expected in failed.payload["error"]["message"]
    assert calls == 1


@pytest.mark.asyncio
async def test_sim_run_rejects_an_artifact_after_release(monkeypatch):
    request = artifact_chain_payload('produced["artifacts"]["totalCurrent"]')
    program = request["setup"]["experiment"]["simulationProgram"]
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        '    produced = await sim.run(tasks["producer"])\n'
        '    artifact = produced["artifacts"]["totalCurrent"]\n'
        "    sim.release(artifact)\n"
        '    await sim.run(tasks["consumer"], inputs={"carry": artifact})\n'
        "    return None\n"
    )
    program["pythonSource"] = source
    program["pythonSourceHash"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    calls = 0

    async def fake_kernel(task, state, inputs, world, progress):
        nonlocal calls
        calls += 1
        return {
            "state": None,
            "artifacts": {"totalCurrent": {"value": 14.9}},
            "observations": {},
        }

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next",
            type="cae.simulation.next",
            payload={"runId": start.payload["runId"], "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
    )

    assert failed.payload["kind"] == "failed"
    assert failed.payload["error"]["code"] == "invalid_input"
    assert "live artifact returned by sim.run" in failed.payload["error"]["message"]
    assert calls == 1


@pytest.mark.asyncio
async def test_duplicate_record_name_returns_terminal_domain_failure(monkeypatch):
    request = payload()
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        "    result = await sim.run(tasks[\"electric\"])\n"
        "    await sim.record(\"totalCurrent\", result[\"artifacts\"][\"totalCurrent\"])\n"
        "    await sim.record(\"totalCurrent\", result[\"artifacts\"][\"totalCurrent\"])\n"
        "    return result[\"state\"]\n"
    )
    request["setup"]["experiment"]["simulationProgram"]["pythonSource"] = source
    request["setup"]["experiment"]["simulationProgram"]["pythonSourceHash"] = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()

    async def fake_kernel(task, state, inputs, world, progress):
        return {
            "state": {"done": True},
            "artifacts": {"totalCurrent": {"value": 1.0}},
            "observations": {},
        }

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    run_id = start.payload["runId"]

    first = await cae_simulation_next(
        DataChannelMessage(
            id="next-1",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-1"),
    )
    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next-2",
            type="cae.simulation.next",
            payload={"runId": run_id, "ackSequence": first.payload["sequence"]},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next-2"),
    )

    assert failed.payload == {
        "kind": "failed",
        "sequence": 2,
        "error": {
            "code": "invalid_record",
            "message": "RecordedData 'totalCurrent' was already recorded",
        },
    }


@pytest.mark.asyncio
async def test_failed_record_encoding_does_not_consume_a_protocol_sequence(monkeypatch):
    request = payload()
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        '    await sim.record("totalCurrent", {"value": [1.0]})\n'
        "    return None\n"
    )
    program = request["setup"]["experiment"]["simulationProgram"]
    program["pythonSource"] = source
    program["pythonSourceHash"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    failed = await cae_simulation_next(
        DataChannelMessage(
            id="next",
            type="cae.simulation.next",
            payload={"runId": start.payload["runId"], "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
    )

    assert failed.payload["kind"] == "failed"
    assert failed.payload["sequence"] == 1
    assert failed.payload["error"]["code"] == "invalid_tensor"


@pytest.mark.asyncio
async def test_start_rejects_incomplete_built_realizations(monkeypatch):
    emitted = []
    monkeypatch.setattr("app.handlers.emit", emitted.append)
    memory = {"runs": {}}
    response = await cae_simulation_start(
        DataChannelMessage(
            id="start",
            type="cae.simulation.start",
            payload={"sample": {"kind": "sample"}, "setup": {"kind": "setup"}},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    assert response.payload["kind"] == "failed"
    assert response.payload["sequence"] == 0
    assert response.payload["error"]["code"] == "invalid_input"
    assert emitted == [{"type": "cae.run.cleaned", "job_id": "session", "run_id": None}]


@pytest.mark.parametrize(
    "variables, schema",
    [
        ({"width": 11}, {"width": {"min": 1, "max": 10}}),
        ({"width": [4]}, {"width": {"min": 1, "max": 10}}),
        ({"width": 4, "extra": 1}, {"width": {"min": 1, "max": 10}}),
        ({"width": True}, {"width": {"min": 1, "max": 10}}),
    ],
)
@pytest.mark.asyncio
async def test_start_validates_variables_against_vars_schema(variables, schema):
    request = payload()
    request["sample"]["structure"]["variables"] = variables
    request["sample"]["structure"]["varsSchema"] = schema

    response = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        {"runs": {}},
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    assert response.payload["kind"] == "failed"
    assert response.payload["error"]["code"] == "invalid_input"


@pytest.mark.parametrize(
    "field, value",
    [
        ("source", 7),
        ("materialId", True),
        (
            "value",
            {"dtype": "float16", "value": [[70000, 0, 0], [0, 70000, 0], [0, 0, 70000]], "unit": "S.m-1"},
        ),
    ],
)
@pytest.mark.asyncio
async def test_start_validates_material_value_and_provenance(field, value):
    request = payload()
    entry = {
        "origin": "source",
        "value": {
            "dtype": "float64",
            "value": [[5.96e7, 0, 0], [0, 5.96e7, 0], [0, 0, 5.96e7]],
            "unit": "S.m-1",
        },
        "source": "reference",
        "version": "1",
        "materialId": None,
        "materialParameterId": None,
    }
    entry[field] = value
    request["sample"]["materialParameters"]["materials"] = {
        "Copper": {"electrical.conductivity": entry}
    }

    response = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        {"runs": {}},
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    assert response.payload["kind"] == "failed"
    assert response.payload["error"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_start_accepts_canonical_variables_and_material_snapshot(monkeypatch):
    request = payload()
    request["sample"]["structure"]["variables"] = {"width": [4, 5]}
    request["sample"]["structure"]["varsSchema"] = {
        "width": {"min": 1, "max": [10, 12]}
    }
    request["sample"]["materialParameters"]["materials"] = {
        "Copper": {
            "electrical.conductivity": {
                "origin": "source",
                "value": {
                    "dtype": "float64",
                    "value": [[5.96e7, 0, 0], [0, 5.96e7, 0], [0, 0, 5.96e7]],
                    "unit": "S.m-1",
                },
                "source": "reference",
                "version": "1",
                "materialId": None,
                "materialParameterId": None,
            }
        }
    }
    request["sample"]["materialParameters"]["materialColors"] = {
        "Copper": {"color": "#d97706", "materialId": 7}
    }
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}

    response = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    assert response.payload["kind"] == "started"
    memory["runs"][response.payload["runId"]].abort()


@pytest.mark.asyncio
async def test_sim_random_matches_caemble_seeded_generator(monkeypatch):
    emitted = []
    monkeypatch.setattr("app.runtime.emit", emitted.append)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    run = memory["runs"][start.payload["runId"]]

    assert [run.random() for _ in range(4)] == [
        0.6270739405881613,
        0.002735721180215478,
        0.5274470399599522,
        0.9810509674716741,
    ]
    run.abort()
    assert emitted == [
        {
            "type": "cae.run.cleaned",
            "job_id": "session",
            "run_id": start.payload["runId"],
        }
    ]


@pytest.mark.asyncio
async def test_sim_release_clears_owned_numpy_buffers_and_rejects_views(monkeypatch):
    monkeypatch.setattr("app.runtime.emit", lambda *_args: None)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    run = memory["runs"][start.payload["runId"]]
    owned = np.arange(12, dtype=np.float64)
    artifact = {"value": owned, "axes": [{"ticks": [0, 1, 2]}]}

    run.release(artifact)

    assert artifact == {}
    assert owned.shape == (0,)

    base = np.arange(8, dtype=np.float64)
    view = base[::2]
    with pytest.raises(CaeError, match="NumPy view") as error:
        run.release(view)
    assert error.value.code == "invalid_release"
    assert base.shape == (8,)
    assert view.shape == (4,)
    run.abort()


@pytest.mark.asyncio
async def test_sim_release_rejects_values_not_returned_by_sim_run(monkeypatch):
    request = payload()
    source = (
        "async def simulate(*, sim, tasks, vars, world):\n"
        "    sim.release(tasks[\"electric\"])\n"
        "    return None\n"
    )
    request["setup"]["experiment"]["simulationProgram"]["pythonSource"] = source
    request["setup"]["experiment"]["simulationProgram"]["pythonSourceHash"] = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()
    monkeypatch.setattr("app.runtime.emit", lambda *_args: None)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=request),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )

    response = await cae_simulation_next(
        DataChannelMessage(
            id="next",
            type="cae.simulation.next",
            payload={"runId": start.payload["runId"], "ackSequence": None},
        ),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
    )

    assert response.payload["kind"] == "failed"
    assert response.payload["error"]["code"] == "invalid_release"


@pytest.mark.asyncio
async def test_sim_release_keeps_owned_graphs_alive_and_rejects_injected_descendants(monkeypatch):
    monkeypatch.setattr("app.runtime.emit", lambda *_args: None)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    run = memory["runs"][start.payload["runId"]]
    sim = SimulationApi(run, {})
    owned = np.arange(4, dtype=np.float64)
    output = {"artifacts": {"value": owned}}
    output_id = id(output)
    sim._register_releasable(output)

    del output
    gc.collect()

    retained = sim._releasable[output_id]
    injected = np.arange(3, dtype=np.float64)
    retained["artifacts"]["injected"] = injected
    with pytest.raises(CaeError, match="not returned by sim.run") as error:
        sim.release(retained)

    assert error.value.code == "invalid_release"
    assert owned.shape == (4,)
    assert injected.shape == (3,)
    run.abort()


@pytest.mark.asyncio
async def test_rejects_duplicate_or_stale_ack(monkeypatch):
    gate = asyncio.Event()

    async def fake_kernel(task, state, inputs, world, progress):
        await gate.wait()
        return {"state": None, "artifacts": {}, "observations": {}}

    monkeypatch.setattr("app.runtime.run_kernel", fake_kernel)
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    start = await cae_simulation_start(
        DataChannelMessage(id="start", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="session", ttl_seconds=10, call_id="start"),
    )
    run_id = start.payload["runId"]

    with pytest.raises(ProtocolError, match="unexpected ACK"):
        await cae_simulation_next(
            DataChannelMessage(
                id="next",
                type="cae.simulation.next",
                payload={"runId": run_id, "ackSequence": 1},
            ),
            memory,
            SlaveContext(session_id="session", ttl_seconds=10, call_id="next"),
        )

    assert run_id not in memory["runs"]


@pytest.mark.asyncio
async def test_run_is_owned_by_one_job_and_new_job_cleans_stale_run(monkeypatch):
    monkeypatch.setattr("app.runtime.validate_kernel_tasks", lambda *_args: None)
    memory = {"runs": {}}
    first = await cae_simulation_start(
        DataChannelMessage(id="start-1", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="job-1", ttl_seconds=10, call_id="start-1"),
    )
    first_run_id = first.payload["runId"]

    with pytest.raises(ProtocolError, match="different GPStation job"):
        await cae_simulation_next(
            DataChannelMessage(
                id="next",
                type="cae.simulation.next",
                payload={"runId": first_run_id, "ackSequence": None},
            ),
            memory,
            SlaveContext(session_id="job-2", ttl_seconds=10, call_id="next"),
        )

    second = await cae_simulation_start(
        DataChannelMessage(id="start-2", type="cae.simulation.start", payload=payload()),
        memory,
        SlaveContext(session_id="job-2", ttl_seconds=10, call_id="start-2"),
    )

    assert first_run_id not in memory["runs"]
    assert second.payload["runId"] in memory["runs"]
    memory["runs"][second.payload["runId"]].abort()
