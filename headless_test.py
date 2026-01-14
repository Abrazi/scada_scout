import time
import sys
import logging
import os

# Ensure src is in path
sys.path.append(os.getcwd())

from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceConfig, DeviceType, Signal

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HeadlessTest")

def test_headless():
    logger.info("Starting Headless Test...")
    
    # Initialize Core
    manager = DeviceManagerCore("test_devices.json")
    
    # Check if we can create a mock device
    config = DeviceConfig(
        name="MockIED",
        ip_address="127.0.0.1",
        port=102,
        device_type=DeviceType.IEC61850_IED # Use a type that triggers adapter logic
    )
    
    # Add Device
    logger.info("Adding device...")
    device = manager.add_device(config)
    
    if not device:
        logger.error("Failed to create device")
        return
        
    # Listen to events
    def on_progress(name, msg, pct):
        logger.info(f"PROGRESS [{name}]: {msg} ({pct}%)")
        
    def on_connected(name, status):
        logger.info(f"STATUS [{name}]: Connected={status}")
        
    def on_signal(name, sig):
        logger.info(f"SIGNAL [{name}]: {sig.address} = {sig.value}")

    manager.on("connection_progress", on_progress)
    manager.on("device_status_changed", on_connected)
    manager.on("signal_updated", on_signal)
    
    # Connect
    logger.info("Connecting...")
    manager.connect_device("MockIED")
    
    # Wait a bit for connection worker
    time.sleep(2)
    
    # Note: Since this is a "Mock" or real connection attempt, it might fail if no device exists,
    # but the point is to verify the infrastructure runs without crashing and emits events.
    # The pure python worker should be running in a thread.
    
    logger.info("Test finished.")

if __name__ == "__main__":
    test_headless()
