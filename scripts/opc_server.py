"""Simple CLI to run an OPC UA simulator (dev/test only).

Usage examples:
  python scripts/opc_server.py --port 4840 --simulator

The script is optional and guarded — it prints clear guidance if
`python-opcua` is not installed.
"""
from __future__ import annotations

import argparse
import logging

log = logging.getLogger("opc_server")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4840)
    parser.add_argument("--simulator", action="store_true")
    args = parser.parse_args()

    endpoint = f"opc.tcp://0.0.0.0:{args.port}"

    try:
        from src.protocols.opc.simulator import OPCSimulator
    except Exception as exc:
        print("OPC UA support is not available in this environment.")
        print("Install the optional dependency: pip install opcua")
        raise SystemExit(1) from exc

    sim = OPCSimulator(endpoint=endpoint)
    try:
        print(f"Starting OPC UA simulator on {endpoint} — press Ctrl-C to stop")
        sim.start()
        # add a couple of demo points
        sim.set_point("Device1.Temperature", 42.0)
        sim.set_point("Device1.Status", True)
        while True:
            pass
    except KeyboardInterrupt:
        print("Stopping simulator...")
    finally:
        sim.stop()
