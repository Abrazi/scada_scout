#!/usr/bin/env python3
"""
Headless test for IEC61850 server simulation
"""

import sys
import os
import logging
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.device_manager_core import DeviceManagerCore
from models.device_models import DeviceConfig, DeviceType

def test_iec61850_server():
    """Test IEC61850 server creation and startup"""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    print("=" * 60)
    print("IEC 61850 Server Test")
    print("=" * 60)
    
    try:
        # Create device manager
        manager = DeviceManagerCore()
        
        # Create server configuration
        config = DeviceConfig(
            name="TestSimulator",
            device_type=DeviceType.IEC61850_SERVER,
            ip_address="127.0.0.1", 
            port=10102,  # Different port to avoid conflicts
            file_path="/home/majid/Documents/scada_scout/dubgg/IEC station 1.scd",
            extra_params={"ied_name": "GPS01GPC01UPM01FCB01"}
        )
        
        print(f"Creating IEC 61850 server:")
        print(f"  IED Name: {config.extra_params['ied_name']}")
        print(f"  Listen: {config.ip_address}:{config.port}")
        print(f"  SCD File: {config.file_path}")
        print()
        
        # Event handlers
        def on_progress(name, message, percent):
            print(f"[{name}] Progress: {message} ({percent}%)")
        
        def on_status_change(name, connected):
            status = "Connected" if connected else "Disconnected" 
            print(f"[{name}] Status: {status}")
        
        def on_signal_update(name, signal):
            print(f"[{name}] Signal: {signal.address} = {signal.value}")
        
        # Register event handlers
        manager.on("connection_progress", on_progress)
        manager.on("device_status_changed", on_status_change)
        manager.on("signal_updated", on_signal_update)
        
        # Add device
        print("Adding server device...")
        device = manager.add_device(config)
        
        if not device:
            print("❌ Failed to create device")
            return False
        
        print(f"✅ Device created: {device.config.name}")
        print()
        
        # Try to connect (start server)
        print("Starting IEC 61850 server...")
        success = manager.connect_device(config.name)
        
        if success:
            print("✅ Server started successfully!")
            print(f"Server is listening on {config.ip_address}:{config.port}")
            print()
            print("Testing with IEC 61850 client connection...")
            
            # Try to connect as a client to verify server is running
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                result = s.connect_ex((config.ip_address, config.port))
                s.close()
                
                if result == 0:
                    print("✅ Port is open and server is listening")
                else:
                    print(f"❌ Cannot connect to port {config.port}")
            except Exception as e:
                print(f"❌ Socket test failed: {e}")
            
            print()
            print("Server is running. Press Ctrl+C to stop...")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping server...")
                manager.disconnect_device(config.name)
                print("✅ Server stopped")
                return True
        else:
            print("❌ Failed to start server")
            return False
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_iec61850_server()
    sys.exit(0 if success else 1)