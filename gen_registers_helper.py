"""Register Mapping Helper for SCADA Scout
Parses Gen_Registers.csv and provides mapping utilities for converting
Triangle MicroWorks register references to SCADA Scout format.

This script helps you understand how to map registers from the original
GenRun_Edited.js simulation to SCADA Scout Modbus addresses.

Original format (Triangle MW): R000, R001, R002, etc.
SCADA Scout format: DeviceName::unit:function:address

Example usage:
  python gen_registers_helper.py
"""

import csv
import os

# Path to the register CSV file
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'Gen_Registers.csv')

# Modbus function codes
FUNC_READ_COILS = 1
FUNC_READ_DISCRETE_INPUTS = 2
FUNC_READ_HOLDING = 3
FUNC_READ_INPUT = 4
FUNC_WRITE_COIL = 5
FUNC_WRITE_REGISTER = 6
FUNC_WRITE_MULTIPLE_COILS = 15
FUNC_WRITE_MULTIPLE_REGISTERS = 16


def parse_gen_registers():
    """Parse Gen_Registers.csv and return register definitions."""
    registers = []
    
    if not os.path.exists(CSV_PATH):
        print(f"Warning: {CSV_PATH} not found")
        return registers
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip disabled registers
            if row.get('IsEnabled', 'True').lower() != 'true':
                continue
            
            reg = {
                'index': int(row['Index']),
                'name': row['Name'],
                'point_type': int(row['PointType']),
                'description': row.get('Description', ''),
                'direction': row.get('Direction', 'None'),
                'default_value': row.get('Value', '0'),
                'default_quality': row.get('Quality', '0')
            }
            registers.append(reg)
    
    return registers


def get_modbus_function(point_type, direction='None'):
    """Map point type to Modbus function code.
    
    Point types from CSV:
    1 = Coil (read/write)
    2 = Discrete Input (read-only)
    3 = Input Register (read-only)
    4 = Holding Register (read/write)
    """
    if point_type == 1:  # Coil
        return FUNC_READ_COILS if direction == 'Input' else FUNC_WRITE_COIL
    elif point_type == 2:  # Discrete Input
        return FUNC_READ_DISCRETE_INPUTS
    elif point_type == 3:  # Input Register
        return FUNC_READ_INPUT
    elif point_type == 4:  # Holding Register
        return FUNC_READ_HOLDING
    else:
        return FUNC_READ_HOLDING  # Default


def format_scada_scout_address(device_name, unit_id, index, point_type, direction='None'):
    """Format a SCADA Scout Modbus address.
    
    Returns: "DeviceName::unit:function:address"
    """
    func = get_modbus_function(point_type, direction)
    
    # Modbus address mapping (common convention)
    # Coils: 0-9999 (00001-09999)
    # Discrete Inputs: 10000-19999 (10001-19999)
    # Input Registers: 30000-39999 (30001-39999)
    # Holding Registers: 40000-49999 (40001-49999)
    
    if point_type == 1:  # Coil
        address = index
    elif point_type == 2:  # Discrete Input
        address = 10000 + index
    elif point_type == 3:  # Input Register
        address = 30000 + index
    elif point_type == 4:  # Holding Register
        address = 40000 + index
    else:
        address = 40000 + index  # Default to holding
    
    return f"{device_name}::{unit_id}:{func}:{address}"


def print_register_mapping(device_name='G1', unit_id=1):
    """Print a complete mapping table for reference."""
    registers = parse_gen_registers()
    
    if not registers:
        print("No registers found. Check Gen_Registers.csv")
        return
    
    print("=" * 80)
    print(f"Register Mapping for Device: {device_name}, Unit: {unit_id}")
    print("=" * 80)
    print(f"{'Index':<6} {'Name':<8} {'Type':<12} {'SCADA Scout Address':<40} {'Description'}")
    print("-" * 80)
    
    point_type_names = {
        1: "Coil",
        2: "DiscreteIn",
        3: "InputReg",
        4: "HoldingReg"
    }
    
    for reg in registers:
        addr = format_scada_scout_address(
            device_name, 
            unit_id, 
            reg['index'], 
            reg['point_type'],
            reg['direction']
        )
        
        type_name = point_type_names.get(reg['point_type'], 'Unknown')
        desc = reg['description'] if reg['description'] else '(no description)'
        
        print(f"{reg['index']:<6} {reg['name']:<8} {type_name:<12} {addr:<40} {desc}")
    
    print("=" * 80)
    print(f"Total registers: {len(registers)}")
    print()
    print("Usage in SCADA Scout scripts:")
    print("  # Read a value")
    print(f"  value = ctx.get('{device_name}::1:3:40000')")
    print()
    print("  # Write a value")
    print(f"  ctx.set('{device_name}::1:3:40010', 1500)")
    print()


def generate_python_constants():
    """Generate Python constants for register addresses."""
    registers = parse_gen_registers()
    
    print("# Auto-generated register constants for SCADA Scout")
    print("# Based on Gen_Registers.csv")
    print()
    print("class RegisterMap:")
    print('    """Modbus register addresses for generator devices."""')
    print()
    
    for reg in registers:
        # Generate constant name from register name
        const_name = reg['name'].upper()
        if not const_name.startswith('R'):
            const_name = 'R' + const_name
        
        desc = reg['description'] if reg['description'] else 'No description'
        index = reg['index']
        address = 40000 + index  # Assuming holding registers
        
        print(f"    {const_name} = {address}  # Index {index}: {desc}")
    
    print()
    print("    @staticmethod")
    print("    def get_address(device_name: str, register: int, unit: int = 1) -> str:")
    print('        """Format full SCADA Scout address."""')
    print('        return f"{device_name}::{unit}:3:{register}"')
    print()
    print("# Example usage:")
    print("# addr = RegisterMap.get_address('G1', RegisterMap.R000)")
    print("# value = ctx.get(addr)")


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--constants':
            generate_python_constants()
        elif sys.argv[1] == '--help':
            print(__doc__)
            print()
            print("Options:")
            print("  --constants    Generate Python constants")
            print("  --help         Show this help")
            print("  <device_name>  Show mapping for specific device (default: G1)")
        else:
            device_name = sys.argv[1]
            print_register_mapping(device_name)
    else:
        # Default: show mapping for G1
        print_register_mapping('G1')


if __name__ == '__main__':
    main()
