#!/usr/bin/env python3
"""Headless IEC 61850 server/client simulation check."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
from src.protocols.iec61850.adapter import IEC61850Adapter
from src.models.device_models import DeviceConfig, DeviceType


def main() -> int:
    icd_path = Path(__file__).parent / "test.icd"
    if not icd_path.exists():
        print("❌ Missing test.icd")
        return 1

    server_config = DeviceConfig(
        name="SimulatedIED",
        ip_address="127.0.0.1",
        port=10002,
        device_type=DeviceType.IEC61850_SERVER,
        scd_file_path=str(icd_path),
        protocol_params={"ied_name": "SimulatedIED"},
    )

    print("=== START SERVER ===")
    server = IEC61850ServerAdapter(server_config, event_logger=None)
    if not server.connect():
        print("❌ Server failed to start")
        return 1
    print("✅ Server started")

    time.sleep(1)

    print("=== CONNECT CLIENT ===")
    client_config = DeviceConfig(
        name="ClientIED",
        ip_address="127.0.0.1",
        port=10002,
        device_type=DeviceType.IEC61850_IED,
    )
    client = IEC61850Adapter(client_config, event_logger=None)
    if not client.connect():
        print("❌ Client failed to connect")
        server.disconnect()
        return 1
    print("✅ Client connected")

    root = client.discover()
    if root and root.children:
        print(f"✅ Discovery OK: {len(root.children)} logical devices")
    else:
        print("⚠️ Discovery returned no logical devices")

    client.disconnect()
    server.disconnect()
    print("=== DONE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
