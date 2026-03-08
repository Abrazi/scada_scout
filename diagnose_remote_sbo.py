#!/usr/bin/env python3
"""
Diagnostic script to identify why SBO fails from remote connections.

This script tests:
1. Network reachability
2. Server binding configuration  
3. Request/SBO timeout settings
4. SELECT/OPERATE workflow with timing measurements
"""

import sys
import os
import time
import socket
import struct
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceConfig, DeviceType


def check_server_binding(ip: str, port: int) -> bool:
    """Check if server is actually listening on the specified IP."""
    print(f"\n[TEST] Checking if server is listening on {ip}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            print(f"✓ Server IS listening on {ip}:{port}")
            return True
        else:
            print(f"✗ Server NOT listening on {ip}:{port}")
            return False
    except Exception as e:
        print(f"✗ Error checking connection: {e}")
        return False


def measure_remote_latency(ip: str, port: int) -> float:
    """Measure network latency to remote server."""
    print(f"\n[TEST] Measuring network latency to {ip}:{port}...")
    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        sock.close()
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        print(f"✓ Connection latency: {elapsed:.2f}ms")
        
        # Check if timeout might be a problem
        if elapsed > 1000:
            print(f"  ⚠️ WARNING: Latency is high ({elapsed:.2f}ms). SBO may timeout with default 5000ms limit.")
        elif elapsed > 2000:
            print(f"  ⚠️ WARNING: Latency is very high ({elapsed:.2f}ms). SBO SELECT/OPERATE might fail.")
        
        return elapsed
    except socket.timeout:
        print(f"✗ Connection TIMED OUT (>5s) - remote server may not be accessible")
        return None
    except Exception as e:
        print(f"✗ Error measuring latency: {e}")
        return None


def test_sbo_workflow(device_name: str, server_ip: str, server_port: int, client_ip: str, scd_file: str):
    """Test full SBO workflow from remote client."""
    print(f"\n[TEST] Testing SBO workflow: client from {client_ip} → server {server_ip}:{server_port}")
    
    manager = DeviceManagerCore()
    
    # Add server
    print(f"\n  1️⃣  Starting server on {server_ip}:{server_port}...")
    server_config = DeviceConfig(
        name=f"{device_name}_Server",
        ip_address=server_ip,
        port=server_port,
        device_type=DeviceType.IEC61850_SERVER,
        scd_file_path=scd_file,
        protocol_params={"ied_name": device_name},
    )
    
    try:
        server_device = manager.add_device(server_config)
        if not server_device:
            print("  ✗ Failed to add server device")
            return False
        
        if not manager.connect_device(f"{device_name}_Server"):
            print("  ✗ Failed to start server")
            return False
        
        print("  ✓ Server started")
        time.sleep(1)
    except Exception as e:
        print(f"  ✗ Server error: {e}")
        return False
    
    # Verify server is actually listening
    if not check_server_binding(server_ip, server_port):
        print("  ⚠️  Server not bindable - may be a firewall or network issue")
        return False
    
    # Add client connecting from different IP (if possible)
    print(f"\n  2️⃣  Starting client connecting to {server_ip}:{server_port}...")
    client_config = DeviceConfig(
        name=f"{device_name}_Client",
        ip_address=server_ip,
        port=server_port,
        device_type=DeviceType.IEC61850_IED,
    )
    
    try:
        client_device = manager.add_device(client_config)
        if not client_device:
            print("  ✗ Failed to add client device")
            return False
        
        if not manager.connect_device(f"{device_name}_Client"):
            print("  ✗ Failed to connect client")
            return False
        
        print("  ✓ Client connected")
    except Exception as e:
        print(f"  ✗ Client connection error: {e}")
        return False
    
    # Try device discovery
    print(f"\n  3️⃣  Running device discovery...")
    try:
        client_protocol = manager._device_map[f"{device_name}_Client"].protocol
        if hasattr(client_protocol, 'discover'):
            start = time.time()
            discovered = client_protocol.discover()
            elapsed = (time.time() - start) * 1000
            
            if discovered:
                print(f"  ✓ Discovery succeeded ({elapsed:.2f}ms)")
            else:
                print(f"  ✗ Discovery failed ({elapsed:.2f}ms)")
                return False
        else:
            print("  ⚠️  discover() not available")
    except Exception as e:
        print(f"  ✗ Discovery error: {e}")
        return False
    
    # Try SBO control
    print(f"\n  4️⃣  Testing SBO control workflow...")
    try:
        from src.models.device_models import Signal, SignalType
        
        # Find a control address from discovery
        client_device = manager._device_map[f"{device_name}_Client"]
        control_signals = [
            sig for sig in client_device.all_signals()
            if any(x in sig.address for x in [".SBOw", ".SBO", "Pos.ctlVal"])
        ]
        
        if not control_signals:
            print("  ⚠️  No control signals found in discovery - SBO test skipped")
            return True
        
        sig = control_signals[0]
        print(f"     Using control signal: {sig.address}")
        
        # Attempt SBO
        start = time.time()
        result = client_protocol.send_command(sig, True)
        elapsed = (time.time() - start) * 1000
        
        if result:
            print(f"  ✓ SBO control succeeded ({elapsed:.2f}ms)")
        else:
            print(f"  ✗ SBO control FAILED ({elapsed:.2f}ms)")
            
            # Check if event logger has error info
            if hasattr(client_protocol, 'event_logger') and client_protocol.event_logger:
                print(f"     Last error: {getattr(client_protocol, '_last_control_error', 'No error info')}")
            
            return False
    except Exception as e:
        print(f"  ✗ SBO test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"\n  ✓ All tests passed!")
    return True


def main():
    print("=" * 70)
    print("SCADA Scout Remote SBO Diagnostic Tool")
    print("=" * 70)
    
    # Check for required SCD file
    scd_file = Path(__file__).parent / "test.icd"
    if not scd_file.exists():
        print(f"\n❌ ERROR: SCD file not found: {scd_file}")
        print("   Please ensure test.icd exists in the scada_scout directory")
        return 1
    
    # Use localhost for now (proper remote test would use different IPs)
    # In a real scenario, use: server_ip="192.168.1.100", client_ip="192.168.1.200"
    server_ip = "127.0.0.1"  # For local testing
    server_port = 10002
    client_ip = "127.0.0.1"
    
    print(f"\nTest Configuration:")
    print(f"  Server IP: {server_ip}:{server_port}")
    print(f"  SCD File: {scd_file}")
    
    # Measure baseline latency
    latency_ms = measure_remote_latency(server_ip, server_port) or 1.0
    
    # Test SBO workflow
    success = test_sbo_workflow("TestIED", server_ip, server_port, client_ip, str(scd_file))
    
    print("\n" + "=" * 70)
    if success:
        print("✓ Remote SBO workflow PASSED")
    else:
        print("✗ Remote SBO workflow FAILED")
        print("\nPossible causes:")
        print("  1. Network latency too high for default 5000ms timeout")
        print("  2. Server not binding to the correct interface (use 0.0.0.0)")
        print("  3. Firewall blocking IEC 61850 port")
        print("  4. Control object not properly initialized on server")
    print("=" * 70)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
