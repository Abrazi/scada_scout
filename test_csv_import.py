"""Test and Verify CSV Register Import
Tests the CSV register importer and displays configuration details.
Run this to verify your CSV is parsed correctly before adding devices.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.csv_register_importer import CSVRegisterImporter, import_csv_to_device_config


def test_csv_import(csv_path: str):
    """Test CSV import and display results"""
    
    print("=" * 80)
    print(f"Testing CSV Register Import: {csv_path}")
    print("=" * 80)
    
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV file not found: {csv_path}")
        return False
    
    # Create importer
    importer = CSVRegisterImporter()
    
    # Parse CSV
    print("\n1. Parsing CSV file...")
    if not importer.parse_csv(csv_path):
        print("ERROR: Failed to parse CSV")
        return False
    
    # Display summary
    summary = importer.export_summary()
    print(f"\n2. Register Summary:")
    print(f"   Total Registers: {summary['total_registers']}")
    print(f"   By Type:")
    for reg_type, count in summary['by_type'].items():
        print(f"     - {reg_type}: {count}")
    print(f"   Index Range: {summary['index_range']['min']} - {summary['index_range']['max']}")
    
    # Generate register blocks
    print("\n3. Generating Register Blocks...")
    blocks = importer.generate_register_blocks(block_size=100, gap_threshold=50)
    print(f"   Generated {len(blocks)} blocks:")
    for block in blocks:
        print(f"     - {block.name}: {block.register_type} @ {block.start_address} (count: {block.count})")
    
    # Generate signal mappings
    print("\n4. Generating Signal Mappings...")
    mappings = importer.generate_signal_mappings()
    print(f"   Generated {len(mappings)} mappings")
    if mappings:
        print(f"   First 5 mappings:")
        for mapping in mappings[:5]:
            print(f"     - {mapping.name} @ {mapping.address}: {mapping.data_type.value}")
    
    # Display sample registers
    print("\n5. Sample Register Definitions (first 10):")
    print(f"   {'Index':<8} {'Type':<12} {'Name':<15} {'DataType':<20} {'Description'}")
    print("   " + "-" * 75)
    
    type_names = {1: "Coil", 2: "Discrete", 3: "Input", 4: "Holding"}
    for reg in importer.registers[:10]:
        type_name = type_names.get(reg.point_type, "Unknown")
        desc = reg.description[:30] if reg.description else "(no description)"
        print(f"   {reg.index:<8} {type_name:<12} {reg.name:<15} {reg.data_type.value:<20} {desc}")
    
    if len(importer.registers) > 10:
        print(f"   ... and {len(importer.registers) - 10} more")
    
    print("\n" + "=" * 80)
    print("✓ CSV Import Test Successful")
    print("=" * 80)
    
    return True


def main():
    """Main entry point"""
    
    # Default CSV path
    default_csv = os.path.join(os.path.dirname(__file__), 'Gen_Registers.csv')
    
    # Get CSV path from command line or use default
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = default_csv
    
    # Run test
    success = test_csv_import(csv_path)
    
    if success:
        print("\nYou can now run the device setup scripts to add Modbus servers")
        print("with these register definitions.")
    else:
        print("\nPlease fix the CSV file and try again.")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
