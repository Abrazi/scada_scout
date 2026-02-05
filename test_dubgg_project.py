#!/usr/bin/env python3
"""
Test script for IED Project Orchestrator - DUBGG.scd workflow.

This script demonstrates the complete workflow:
1. Load DUBGG/DUBGG.scd
2. Extract all IED definitions
3. Instantiate IEC 61850 servers for each IED
4. Generate PLC programs
5. Save complete project as DUBGG.mss

Run this in headless mode to test the core functionality without GUI.
"""

import sys
import logging
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_dubgg_workflow():
    """Test complete DUBGG workflow."""
    
    print("\n" + "="*80)
    print("IED Project Orchestrator - DUBGG Test")
    print("="*80 + "\n")
    
    # Import required modules
    from src.core.device_manager_core import DeviceManagerCore
    from src.core.ied_project_orchestrator import IEDProjectOrchestrator
    from src.core.event_logger import EventLogger
    
    # Initialize components
    print("1. Initializing components...")
    device_manager = DeviceManagerCore()
    event_logger = EventLogger()
    device_manager.event_logger = event_logger
    
    orchestrator = IEDProjectOrchestrator(device_manager)
    
    # Path to DUBGG.scd
    dubgg_scd = project_root / "dubgg" / "DUBGG.scd"
    
    if not dubgg_scd.exists():
        print(f"\n❌ ERROR: DUBGG.scd not found at {dubgg_scd}")
        print("Please ensure the file exists in the dubgg/ directory")
        return False
        
    print(f"   ✓ Found SCD file: {dubgg_scd}")
    print(f"   ✓ File size: {dubgg_scd.stat().st_size / (1024*1024):.1f} MB")
    
    # Step 1: Load SCD file
    print("\n2. Loading SCD file...")
    try:
        success = orchestrator.load_from_scd(
            scd_file_path=str(dubgg_scd),
            project_name="DUBGG"
        )
        
        if not success:
            print("   ❌ Failed to load SCD file")
            return False
            
        print(f"   ✓ Successfully parsed SCD")
        print(f"   ✓ Found {len(orchestrator.ied_definitions)} IED(s)")
        
        # Check for multiple SubNetworks
        subnets = orchestrator.get_available_subnets()
        if subnets:
            print(f"\n   📡 SubNetworks detected: {len(subnets)}")
            for subnet_name, ied_count in subnets:
                print(f"      • {subnet_name}: {ied_count} IED(s)")
                
            if len(subnets) > 1:
                print("\n   ℹ️  Multiple SubNetworks found!")
                print("      Each IED may have different IP addresses per SubNetwork.")
                print("      Current IPs are from the first SubNetwork found.")
                print("\n      To use a specific SubNetwork, re-load with subnet parameter:")
                print("      orchestrator.load_from_scd(scd_path, subnet_name='...')")
        
    except Exception as e:
        print(f"   ❌ Error loading SCD: {e}")
        logger.exception("SCD load error")
        return False
    
    # Display IED summary
    print("\n3. IED Summary:")
    print("   " + "-"*90)
    print(f"   {'IED Name':<30} {'IP Address':<20} {'SubNet':<20} {'Manufacturer':<19}")
    print("   " + "-"*90)
    
    for ied in orchestrator.ied_definitions:
        ip = ied.network_config.ip_address if ied.network_config else "NO_IP"
        subnet = ied.network_config.subnet_name if ied.network_config else ""
        manufacturer = ied.manufacturer[:17] + "..." if len(ied.manufacturer) > 17 else ied.manufacturer
        print(f"   {ied.name:<30} {ip:<20} {subnet:<20} {manufacturer:<19}")
    
    print("   " + "-"*90)
    
    # Ask user confirmation
    print("\n4. Ready to instantiate IED servers")
    print("   This will:")
    print("   • Create IEC 61850 server for each IED")
    print("   • Generate PLC program for each device")
    print("   • Start PLC runtime engines")
    print("   • Bind to IP addresses from SCD")
    
    response = input("\n   Proceed? (y/n): ").strip().lower()
    if response != 'y':
        print("\n   Cancelled by user")
        return False
    
    # Step 2: Instantiate all IEDs
    print("\n5. Instantiating IED servers...")
    try:
        success = orchestrator.instantiate_all_ieds(
            auto_connect=True,  # Auto-connect servers
            start_plc=True      # Auto-start PLC programs
        )
        
        if not success:
            print("   ⚠️  Some IEDs failed to instantiate (check logs)")
        else:
            print("   ✓ All IEDs instantiated successfully")
            
    except Exception as e:
        print(f"   ❌ Error during instantiation: {e}")
        logger.exception("Instantiation error")
        return False
    
    # Display instantiated servers
    print("\n6. Instantiated Servers:")
    print("   " + "-"*76)
    
    for name, instance in orchestrator.instantiated_servers.items():
        plc_status = "PLC Running" if instance.plc_metadata else "No PLC"
        print(f"   • {name}: {instance.status} - {plc_status}")
    
    print("   " + "-"*76)
    
    # Display PLC programs
    print("\n7. PLC Programs:")
    plc_statuses = orchestrator.plc_runtime.get_all_statuses()
    
    if plc_statuses:
        print("   " + "-"*76)
        for prog_name, status in plc_statuses.items():
            running = "✓ Running" if status['running'] else "✗ Stopped"
            cycles = status['cycle_count']
            print(f"   • {prog_name}: {running} ({cycles} cycles)")
        print("   " + "-"*76)
    else:
        print("   No PLC programs running")
    
    # Step 3: Save as MSS project
    print("\n8. Saving project...")
    mss_path = project_root / "DUBGG.mss"
    
    try:
        success = orchestrator.save_project(str(mss_path))
        
        if success:
            print(f"   ✓ Project saved: {mss_path}")
            print(f"   ✓ File size: {mss_path.stat().st_size / 1024:.1f} KB")
        else:
            print("   ❌ Failed to save project")
            return False
            
    except Exception as e:
        print(f"   ❌ Error saving project: {e}")
        logger.exception("Save error")
        return False
    
    # Display project summary
    print("\n9. Project Summary:")
    summary = orchestrator.get_project_summary()
    
    print("   " + "-"*76)
    print(f"   Project Name:       {summary['project_name']}")
    print(f"   SCD File:           {Path(summary['scd_file']).name if summary['scd_file'] else 'N/A'}")
    print(f"   IEDs Defined:       {summary['ied_count']}")
    print(f"   Servers Running:    {summary['instantiated_count']}")
    print(f"   PLC Programs:       {summary['plc_programs']}")
    print("   " + "-"*76)
    
    # Show PLC program locations
    print("\n10. Generated Files:")
    print("    " + "-"*76)
    print(f"    MSS Project:     {mss_path}")
    print(f"    PLC Programs:    {project_root / 'plc_programs'}/")
    
    plc_dir = project_root / "plc_programs"
    if plc_dir.exists():
        plc_files = list(plc_dir.glob("*.st"))
        for plc_file in plc_files:
            print(f"                     - {plc_file.name}")
    
    print("    " + "-"*76)
    
    print("\n" + "="*80)
    print("✓ DUBGG Project Setup Complete!")
    print("="*80)
    
    print("\nNext steps:")
    print("  1. Open DUBGG.mss in the GUI to see all devices")
    print("  2. Edit PLC programs in plc_programs/ directory")
    print("  3. Connect clients to IED IP addresses")
    print("  4. Monitor signals in Device Explorer")
    
    # Keep running for a bit to show PLC execution
    print("\nPLC programs are now running. Press Ctrl+C to exit...\n")
    
    try:
        import time
        while True:
            time.sleep(5)
            # Show cycle counts
            statuses = orchestrator.plc_runtime.get_all_statuses()
            if statuses:
                print("PLC Status:", end=" ")
                for name, status in list(statuses.items())[:3]:  # Show first 3
                    print(f"{name.split('_')[-1]}:{status['cycle_count']}", end=" ")
                print("...")
                
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        orchestrator.shutdown()
        print("✓ Graceful shutdown complete")
    
    return True


if __name__ == '__main__':
    try:
        success = test_dubgg_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.exception("Fatal error")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
