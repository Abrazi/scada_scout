"""
Simple Modbus RTU Example
Demonstrates basic master-slave communication
"""
import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.models.device_models import DeviceConfig, DeviceType
from src.protocols.modbus.rtu.master_adapter import ModbusRTUMasterAdapter
from src.protocols.modbus.rtu.transport import list_serial_ports

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def list_ports():
    """List available serial ports"""
    print("\n" + "="*60)
    print("AVAILABLE SERIAL PORTS")
    print("="*60)
    
    ports = list_serial_ports()
    if ports:
        for device, description in ports:
            print(f"  {device}: {description}")
    else:
        print("  No serial ports found")
    
    print("="*60 + "\n")


def example_master():
    """
    Example: Connect as Modbus RTU Master and read from slave
    
    Before running:
    1. Connect RTU slave device or simulator
    2. Update serial_port below to match your system
    3. Verify baud rate and slave address
    """
    print("\n" + "="*60)
    print("MODBUS RTU MASTER EXAMPLE")
    print("="*60 + "\n")
    
    # Show available ports
    list_ports()
    
    # Configuration - UPDATE THESE VALUES
    config = DeviceConfig(
        name="RTU Slave Device",
        ip_address="",  # Not used for serial
        port=0,
        device_type=DeviceType.MODBUS_RTU_MASTER,
        rtu_transport="serial",
        serial_port="COM3",  # <-- CHANGE THIS to your port
        serial_baudrate=9600,
        serial_bytesize=8,
        serial_parity='N',
        serial_stopbits=1.0,
        serial_timeout=1.0,
        rtu_slave_address=1  # <-- CHANGE THIS if your slave has different address
    )
    
    print(f"Connecting to: {config.serial_port}")
    print(f"Baud rate: {config.serial_baudrate}")
    print(f"Slave address: {config.rtu_slave_address}\n")
    
    # Create master adapter
    master = ModbusRTUMasterAdapter(config)
    
    try:
        # Connect
        if not master.connect():
            print("❌ Failed to connect!")
            print("Check:")
            print("  - Serial port exists and is correct")
            print("  - No other program is using the port")
            print("  - Slave device is powered and connected")
            print("  - Cable wiring is correct (A-A, B-B)")
            return
        
        print("✓ Connected successfully!\n")
        
        # Read coils (FC01)
        print("Reading coils (FC01)...")
        coils = master.read_coils(
            slave_address=config.rtu_slave_address,
            start_address=0,
            count=10
        )
        if coils:
            print(f"  Coils 0-9: {coils}")
        else:
            print("  No response (check slave address and register range)")
        
        time.sleep(0.1)
        
        # Read holding registers (FC03)
        print("\nReading holding registers (FC03)...")
        registers = master.read_holding_registers(
            slave_address=config.rtu_slave_address,
            start_address=0,
            count=10
        )
        if registers:
            print(f"  Registers 0-9: {registers}")
        else:
            print("  No response (check slave address and register range)")
        
        time.sleep(0.1)
        
        # Write single register (FC06)
        print("\nWriting single register (FC06)...")
        test_value = 12345
        success = master.write_single_register(
            slave_address=config.rtu_slave_address,
            address=0,
            value=test_value
        )
        if success:
            print(f"  ✓ Wrote {test_value} to register 0")
            
            # Read back
            time.sleep(0.1)
            registers = master.read_holding_registers(
                slave_address=config.rtu_slave_address,
                start_address=0,
                count=1
            )
            if registers:
                print(f"  ✓ Read back: {registers[0]}")
                if registers[0] == test_value:
                    print("  ✓ Value matches!")
                else:
                    print(f"  ⚠ Value mismatch: expected {test_value}, got {registers[0]}")
        else:
            print("  ❌ Write failed")
        
        time.sleep(0.1)
        
        # Write multiple registers (FC16)
        print("\nWriting multiple registers (FC16)...")
        test_values = [100, 200, 300, 400, 500]
        success = master.write_multiple_registers(
            slave_address=config.rtu_slave_address,
            start_address=10,
            values=test_values
        )
        if success:
            print(f"  ✓ Wrote {len(test_values)} registers starting at 10")
            
            # Read back
            time.sleep(0.1)
            registers = master.read_holding_registers(
                slave_address=config.rtu_slave_address,
                start_address=10,
                count=len(test_values)
            )
            if registers:
                print(f"  ✓ Read back: {registers}")
                if registers == test_values:
                    print("  ✓ All values match!")
        else:
            print("  ❌ Write failed")
        
        print("\n✓ Example completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    except Exception as e:
        logger.exception("Error in example")
        print(f"\n❌ Error: {e}")
    
    finally:
        # Disconnect
        master.disconnect()
        print("\n✓ Disconnected")


def example_rtu_over_tcp():
    """
    Example: Connect to RTU-over-TCP device
    
    RTU-over-TCP encapsulates RTU frames (with CRC) over TCP socket
    This is different from Modbus TCP which uses MBAP header
    """
    print("\n" + "="*60)
    print("MODBUS RTU-OVER-TCP EXAMPLE")
    print("="*60 + "\n")
    
    # Configuration - UPDATE THESE VALUES
    config = DeviceConfig(
        name="RTU over TCP Device",
        ip_address="192.168.1.100",  # <-- CHANGE THIS
        port=502,
        device_type=DeviceType.MODBUS_RTU_MASTER,
        rtu_transport="rtu_over_tcp",
        rtu_slave_address=1
    )
    
    print(f"Connecting to: {config.ip_address}:{config.port}")
    print(f"Slave address: {config.rtu_slave_address}\n")
    
    master = ModbusRTUMasterAdapter(config)
    
    try:
        if not master.connect():
            print("❌ Failed to connect!")
            return
        
        print("✓ Connected successfully!\n")
        
        # Read holding registers
        registers = master.read_holding_registers(
            slave_address=config.rtu_slave_address,
            start_address=0,
            count=10
        )
        
        if registers:
            print(f"Registers 0-9: {registers}")
        else:
            print("No response")
        
        print("\n✓ Example completed!")
        
    except Exception as e:
        logger.exception("Error in RTU-over-TCP example")
        print(f"\n❌ Error: {e}")
    
    finally:
        master.disconnect()
        print("\n✓ Disconnected")


def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("MODBUS RTU EXAMPLES")
    print("="*60)
    print("\nChoose an example:")
    print("  1. RTU Master (serial)")
    print("  2. RTU-over-TCP Master")
    print("  3. List Serial Ports")
    print("  q. Quit")
    
    choice = input("\nEnter choice [1-3, q]: ").strip().lower()
    
    if choice == '1':
        example_master()
    elif choice == '2':
        example_rtu_over_tcp()
    elif choice == '3':
        list_ports()
    elif choice == 'q':
        print("Goodbye!")
        return
    else:
        print(f"Invalid choice: {choice}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
