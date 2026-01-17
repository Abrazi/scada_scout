#!/usr/bin/env python3
"""
Test script for the IEC 61850 minimal simulator functionality.
This tests the server adapter with a minimal model creation.
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models.device_models import DeviceConfig, DeviceType
from protocols.iec61850.server_adapter import IEC61850ServerAdapter
from core.logging_handler import EventLogger

def test_minimal_simulator():
    """Test the minimal IEC61850 simulator"""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # Create event logger
    event_logger = EventLogger()
    
    print("=" * 60)
    print("Testing IEC 61850 Minimal Simulator")
    print("=" * 60)
    
    try:
        # Create a test configuration
        config = DeviceConfig(
            name="TestIED",
            device_type=DeviceType.IEC61850_SERVER,
            ip_address="127.0.0.1",
            port=10002,  # Use different port to avoid conflicts
            file_path="/home/majid/Documents/scada_scout/dubgg/IEC station 1.scd",  # We'll fall back to minimal
            extra_params={"ied_name": "GPS01GPC01UPM01FCB01"}
        )
        
        print(f"Creating simulator for IED: {config.extra_params['ied_name']}")
        print(f"Listen address: {config.ip_address}:{config.port}")
        print(f"SCD file: {config.file_path}")
        print()
        
        # Create the server adapter
        server = IEC61850ServerAdapter(config, event_logger=event_logger)
        
        # Try to connect (start the server)
        print("Starting server...")
        success = server.connect()
        
        if success and server.connected:
            print("✅ Server started successfully!")
            print(f"Server is listening on {config.ip_address}:{config.port}")
            print()
            print("You can now test connection with:")
            print(f"  • IEC 61850 client tools")
            print(f"  • SCADA Scout client connection")
            print(f"  • telnet {config.ip_address} {config.port}")
            print()
            print("Press Ctrl+C to stop the server...")
            
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping server...")
        else:
            print("❌ Failed to start server")
            print("Check the logs above for error details")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"❌ Test failed: {e}")
    finally:
        # Clean up
        try:
            server.disconnect()
        except:
            pass
        print("Test completed.")

if __name__ == "__main__":
    test_minimal_simulator()