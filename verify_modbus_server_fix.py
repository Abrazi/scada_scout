
import sys
import os
import time
import logging
import asyncio

# Ensure src is in path
sys.path.append(os.getcwd())

# Patch missing pymodbus logging if needed (some versions warn)
logging.basicConfig(level=logging.INFO)

from src.protocols.modbus.slave_server import ModbusSlaveServer, ModbusSlaveConfig
from pymodbus.client import ModbusTcpClient

def verify_server_fix():
    print("Starting Modbus Slave Server verification...")
    
    # 1. Start Server
    config = ModbusSlaveConfig(
        port=5021, # Use different port to avoid conflict
        unit_id=1,
        holding_registers_count=100
    )
    
    server = ModbusSlaveServer(config=config)
    
    try:
        if not server.start():
            print("FAIL: Server failed to start")
            return False
            
        print("Server started. Connecting client...")
        time.sleep(1) # Wait for server thread
        
        # 2. Connect Client
        client = ModbusTcpClient('127.0.0.1', port=5021)
        if not client.connect():
            print("FAIL: Client failed to connect")
            server.stop()
            return False
            
        # 3. Read Registers (This triggered the crash)
        print("Reading registers...")
        try:
            # Read 10 registers from address 0
            # Read 10 registers from address 0
            # Simplify: Rely on default unit ID (usually 1 or 0)
            rr = client.read_holding_registers(0, 10)
            
            if rr.isError():
                print(f"FAIL: Read Error: {rr}")
                client.close()
                server.stop()
                return False
                
            print(f"SUCCESS: Read Result: {rr.registers}")
            
        except Exception as e:
            print(f"FAIL: Exception during read: {e}")
            client.close()
            server.stop()
            return False

        client.close()
        server.stop()
        print("Verification Passed!")
        return True
        
    except Exception as e:
        print(f"FAIL: Overall Exception: {e}")
        try:
            server.stop()
        except: pass
        return False

if __name__ == "__main__":
    success = verify_server_fix()
    sys.exit(0 if success else 1)
