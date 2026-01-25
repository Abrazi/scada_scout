# OPC Integration — Design & Implementation for SCADA Scout ✅

Summary
-------
This document specifies a professional, non-invasive OPC integration that:
- Fully supports OPC UA (client + server)
- Provides a clear path for legacy OPC DA on Windows (isolated bridge)
- Is cross-platform (Win / Linux / macOS) and opt-in
- Keeps existing Modbus and IEC 61850 code untouched

Goals
-----
- Modular, testable, production-ready OPC UA support
- Windows-only legacy-DA bridge that does not affect other platforms
- Simulator and diagnostics for QA and field testing

High-level architecture (ASCII)
------------------------------
  +---------------------+      +----------------------+      +------------------+
  | DeviceManager &    | <--> | OPC Adapter Layer     | <--> | Third-party OPC   |
  | Core protocols     |      | (opc/ua, opc/da)      |      | Servers (UA/DA)   |
  | (Modbus, IEC61850) |      +----------------------+      +------------------+
  +---------------------+
            ^
            | (mirror)
            v
     +----------------+
     | OPC UA Server  |  <- exposed by SCADA Scout (simulator, live mirror)
     +----------------+

Design principles
-----------------
- Non-invasive: add new modules and registration hooks; no changes to stable protocol code.
- Optional deps: `python-opcua` for UA; Windows-only COM bridge for DA.
- Secure by-default: certificate management, PKI guidance, secure transport (TLS).

Module breakdown (proposed)
---------------------------
- src/protocols/opc/
  - base_opc.py         — stable interfaces used by rest of app
  - ua_client.py        — OPC UA client wrapper (python-opcua)
  - ua_server.py        — OPC UA server wrapper + mirroring helpers
  - da_windows.py       — Windows-only OPC DA bridge (wrapper/adapter)
  - simulator.py        — lightweight OPC UA simulator for QA
  - integration.md      — usage + registration instructions
- scripts/
  - opc_server.py       — CLI demo / local simulator
- docs/opc_integration.md — architecture, security, packaging
- tests/
  - test_opc_basic.py   — import/smoke tests (skip when deps missing)

OPC Client workflow 🔁
---------------------
1. Instantiate an `UAClient` (or platform-specific DA adapter).
2. Validate endpoint and certificates (if configured).
3. Connect -> browse -> map nodeIds to DeviceManager signals.
4. Optionally subscribe for updates and forward into DeviceManager via
   the existing signal update callback.
5. Graceful disconnect and error reporting.

OPC Server workflow 🛰️
---------------------
1. Create `UAServer` instance and configure application certificate (auto-generate
   in dev; use signed cert in production).
2. Mirror DeviceManager signals by creating variables under a configurable
   namespace (e.g. `SCADAScout/Devices/<device>/<signal>`).
3. Support write callbacks to translate OPC writes into control requests
   through the existing control APIs (no direct protocol-level changes).
4. Provide a simulator mode that drives values without connecting to hardware.

Legacy OPC DA (Windows) strategy ⚠️
---------------------------------
- OPC DA is COM-based and Windows-only. Do NOT attempt to reimplement DA on
  Linux/macOS.
- Provide two options:
  1) Lightweight Python COM adapter using `pywin32`/`comtypes` (fast to ship,
     but Python+COM is fragile across Windows versions).
  2) Recommended: small .NET Windows service (C#) that exposes a well-documented
     JSON/HTTP or local socket API and hosts the OPC-DA endpoint. Ship as an
     optional Windows-only companion installer.
- Keep the DA bridge isolated and communicate with it over localhost APIs.

Security & Certificates 🔐
-------------------------
- OPC UA: mandatory TLS. Use application instance certificates (store path
  configurable). Provide tooling to generate self-signed certs for QA and
  documentation for production PKI onboarding.
- User authentication: support Anonymous, Username/Password, and Certificate
  authentication. Integrate with product-level user management if available.
- Certificate validation: allow configurable trusted store + auto-accept for
  dev with explicit audit log.
- Hardening: enforce minimum TLS versions and secure cipher suites.

UI integration note
-------------------
- The application exposes an **opt-in** UI toggle (Settings → Network) named
  **"Expose DeviceManager as OPC UA server (mirror)"**. Enabling it will
  start an in-process OPC UA server that mirrors DeviceManager signals under
  the `SCADAScout/Devices/...` namespace.
- The mirror uses **server-side write callbacks** when the installed
  `python-opcua` supports them (preferred, immediate). If the UA library
  version does not expose native write hooks the mirror falls back to a
  short-interval poll to detect external writes. Both behaviors are
  functionally identical from the user's perspective.

Operational tip
----------------
- The UI toggle is purely opt-in and safe to enable in production. If the
  optional `opcua` package is not installed the toggle is inert and the
  application will continue to function normally.
Scalability & Performance 📈
---------------------------
- Use efficient subscription model (monitoring) rather than aggressive polling.
- Pool OPC UA clients for many endpoints; share sessions where server permits.
- For high-throughput, run OPC UA operations on dedicated worker threads or
  an asyncio loop isolated from the UI thread.

Testing & Validation 🧪
---------------------
- Unit: interface conformance, config parsing, simulator-only tests.
- Integration: run python-opcua based simulator + in-process client to validate
  mirror and control paths (CI job with optional markers).
- E2E: Windows-only tests for OPC DA using the companion bridge (run in
  Windows CI matrix).
- Add diagnostic commands: list endpoints, show certs, simulate bad certs,
  measure round-trip latency.

Packaging & Deployment 📦
------------------------
- Keep OPC optional: do not force `opcua` on every install. Provide an
  extras_require entry: `pip install scadascout[opc]`.
- Windows: bundle the DA bridge installer as an optional component in the
  Windows installer (MSI/NSIS).
- Container images: run UA server/client in Linux containers for headless
  deployments; expose only necessary ports and mount certs.

Developer integration plan (step-by-step)
-----------------------------------------
1. Add `src/protocols/opc/` (interfaces + guarded UA wrappers + simulator).
2. Add docs and examples (`scripts/opc_server.py`).
3. Add opt-in registration in `DeviceManagerCore` (pull request): a small
   factory registration that does not change defaults.
4. Implement end-to-end tests (Linux/macOS: UA; Windows: DA bridge smoke tests).
5. Ship as opt-in feature with packaging notes and security documentation.

Quickstart (dev)
-----------------
# install optional dependency
pip install opcua

# run a local simulator (example)
python scripts/opc_server.py --port 4840 --simulator

# run smoke test that uses in-process client+server
pytest -k opc -q

Next steps I can do for you ✅
- Create the initial non-invasive OPC code + simulator + smoke tests (I have
  already scaffolded these files in the codebase).
- Open a focused PR that adds optional dependency, docs, and CI job
  recommendations.

References & further reading
---------------------------
- OPC Foundation: OPC UA specification
- python-opcua (FreeOpcUa): https://github.com/FreeOpcUa/python-opcua
- Windows OPC DA: importance of isolating COM surface in a managed bridge

