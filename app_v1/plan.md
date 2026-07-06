# GP Station v1 MVP Implementation Plan

## Completed MVP Status
- [x] Foundation: repository-local `app_v1/` layout, protocol contracts, config examples, and run notes.
- [x] Server orchestration: FastAPI server, DB-backed worker/session state, static bearer auth, TTL cleanup, and signaling relay.
- [x] Slave launcher runtime: control WebSocket client, slave subprocess lifecycle, JSON-lines IPC, and `aiortc` DataChannel handler calls.
- [x] Master path: TypeScript SDK and example web client.
- [x] Hardening and verification: tests and build/type checks.
- [x] Tutorial docs: end-to-end code walkthrough, local run guide, and implementation troubleshooting notes.
- [x] Poetry migration: Python packages, lockfiles, and run scripts use Poetry.

## Next Implementation Targets
- [ ] Replace demo static bearer tokens with the real user/auth model.
- [ ] Extend slave app DataChannel protocols from `echo` to real job messages: start, cancel, progress, result, and error.
- [ ] Add Python master SDK WebRTC support, not only REST session creation.
- [ ] Define worker capacity policy for multiple concurrent sessions.
- [ ] Add deployment docs and production runtime configuration.

## MVP Scope
- A user connects only to worker sessions owned by that same user.
- The master client explicitly selects `worker_session_id` and `slave_app_id`.
- The v1 server stores durable worker, slave, and session state in Postgres; live WebSocket handles stay in process memory.
- The first successful end-to-end scenario is the `echo` slave app WebRTC DataChannel handler call.
- Billing, marketplace matching, persistent session storage, and quota enforcement are out of scope.

## Local Demo Defaults
- Client token: `demo-client-token`
- Worker token: `demo-worker-token`
- Demo user id: deterministic UUID seeded into the `users` table
- Server URL: `http://127.0.0.1:8100`
- DataChannel label: `gpstation.v1`

## Milestone Notes
- Keep this file updated after each implementation milestone.
- Existing `apps/` code is style reference only; v1 implementation lives under `app_v1/`.

## Verification Notes
- Python tests cover protocol validation, token auth, worker ownership checks, session creation, and TTL cleanup.
- Launcher tests cover control WebSocket URL derivation, executable registry loading, launch command selection, and missing executable environment errors.
- Package tests cover protocol validation, server state, slave launcher registry, and slave SDK runtime behavior.
- Browser verification uses `app_v1/master/examples/echo` after starting the server and slave launcher.
- Python dependencies are installed and executed through separate Poetry projects for server, slave launcher, and each slave executable.

## Documentation Notes
- `tutorial.md` explains the full v1 architecture for readers with shallow background knowledge.
- The tutorial includes the implementation pitfalls discovered during this milestone: Pydantic settings parsing, PowerShell `PYTHONPATH` quoting, Next/Turbopack local package resolution, React ref linting, subprocess readiness races, and `aiortc` callback/Future wake-up behavior.
