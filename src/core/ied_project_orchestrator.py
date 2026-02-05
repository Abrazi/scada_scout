"""
IED Project Orchestrator - Integrates SCD loading, device instantiation, and PLC runtime.

This module provides high-level orchestration for:
1. Loading SCD files and extracting IED definitions
2. Creating IEC 61850 server instances for each IED
3. Generating and starting PLC programs
4. Saving/loading complete projects as .mss files

This serves as the main integration point between all components.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from src.core.scd_project_loader import SCDProjectLoader, IEDDefinition
from src.core.plc_program_generator import PLCProgramGenerator, PLCProgramMetadata
from src.core.plc_runtime_engine import PLCRuntimeEngine
from src.core.mss_project_manager import MSSProjectManager
from src.models.device_models import DeviceConfig, DeviceType

logger = logging.getLogger(__name__)


@dataclass
class IEDServerInstance:
    """Represents an instantiated IED server with PLC program."""
    device_name: str
    ied_name: str
    device_config: DeviceConfig
    plc_metadata: Optional[PLCProgramMetadata]
    status: str  # 'created', 'connecting', 'connected', 'error'


class IEDProjectOrchestrator:
    """
    Orchestrates the complete workflow for IED project management.
    
    This class ties together:
    - SCD parsing and IED extraction
    - Device manager integration for server instantiation
    - PLC program generation and runtime
    - MSS project file persistence
    
    Typical workflow:
    1. load_from_scd(scd_path) -> extracts IEDs
    2. instantiate_all_ieds() -> creates servers and PLC programs
    3. save_project(mss_path) -> persists complete state
    4. [Later] load_project(mss_path) -> restores everything
    """
    
    def __init__(self, device_manager=None):
        """
        Initialize orchestrator.
        
        Args:
            device_manager: Reference to application's DeviceManager
        """
        self.device_manager = device_manager
        self.plc_generator = PLCProgramGenerator()
        self.plc_runtime = PLCRuntimeEngine(device_manager)
        self.mss_manager = MSSProjectManager()
        
        self.current_scd_path: Optional[str] = None
        self.ied_definitions: List[IEDDefinition] = []
        self.instantiated_servers: Dict[str, IEDServerInstance] = {}
        self.current_loader: Optional[SCDProjectLoader] = None
        self.selected_subnet: Optional[str] = None
        
    def get_available_subnets(self) -> List[Tuple[str, int]]:
        """
        Get list of available SubNetworks from loaded SCD.
        
        Returns:
            List of tuples (subnet_name, ied_count)
        """
        if not self.current_loader:
            return []
        return self.current_loader.get_subnetworks()
        
    def load_from_scd(self, scd_file_path: str, project_name: Optional[str] = None, subnet_name: Optional[str] = None) -> bool:
        """
        Load and parse SCD file, extract all IED definitions.
        
        Args:
            scd_file_path: Path to .scd file
            project_name: Optional project name (defaults to SCD filename)
            subnet_name: Optional SubNetwork name to use for IP addresses
            
        Returns:
            True on success
        """
        try:
            logger.info(f"Loading SCD file: {scd_file_path}")
            
            # Parse SCD
            loader = SCDProjectLoader(scd_file_path)
            self.current_loader = loader
            self.selected_subnet = subnet_name
            
            # Extract IEDs (optionally filtered by subnet)
            self.ied_definitions = loader.extract_ieds(subnet_name=subnet_name)
            
            if not self.ied_definitions:
                logger.error("No IEDs found in SCD file")
                return False
                
            self.current_scd_path = scd_file_path
            
            # Create MSS project
            if not project_name:
                project_name = Path(scd_file_path).stem
                
            self.mss_manager.create_project(
                project_name=project_name,
                description=f"Project loaded from {Path(scd_file_path).name}",
                scd_file_path=scd_file_path
            )
            
            logger.info(f"Successfully loaded {len(self.ied_definitions)} IED(s) from SCD")
            
            # Log IED summary
            for ied in self.ied_definitions:
                ip = ied.network_config.ip_address if ied.network_config else "NO_IP"
                logger.info(f"  - {ied.name}: {ied.desc} @ {ip}")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to load SCD file: {e}", exc_info=True)
            return False
            
    def instantiate_all_ieds(self, auto_connect: bool = True, start_plc: bool = True) -> bool:
        """
        Instantiate all IEDs as IEC 61850 servers with PLC programs.
        
        Args:
            auto_connect: Auto-connect servers after creation
            start_plc: Auto-start PLC programs
            
        Returns:
            True if all instantiated successfully
        """
        if not self.ied_definitions:
            logger.error("No IED definitions loaded")
            return False
            
        if not self.device_manager:
            logger.error("No device manager available")
            return False
            
        success_count = 0
        
        for ied in self.ied_definitions:
            try:
                if self._instantiate_ied(ied, auto_connect, start_plc):
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to instantiate IED {ied.name}: {e}", exc_info=True)
                
        logger.info(f"Instantiated {success_count}/{len(self.ied_definitions)} IED(s)")
        return success_count == len(self.ied_definitions)
        
    def _instantiate_ied(self, ied: IEDDefinition, auto_connect: bool, start_plc: bool) -> bool:
        """
        Instantiate single IED as server with PLC program.
        
        Args:
            ied: IED definition
            auto_connect: Auto-connect server
            start_plc: Auto-start PLC
            
        Returns:
            True on success
        """
        # Validate network config
        if not ied.network_config:
            logger.error(f"No network configuration for IED {ied.name}")
            return False
            
        # Create device name (sanitize)
        device_name = ied.name.replace(' ', '_')
        
        logger.info(f"Instantiating IED: {ied.name} as {device_name}")
        
        # Create DeviceConfig for IEC 61850 server
        device_config = DeviceConfig(
            name=device_name,
            device_type=DeviceType.IEC61850_SERVER,
            ip_address=ied.network_config.ip_address,
            port=ied.network_config.port,
            scd_file_path=self.current_scd_path,  # Required for server adapter
            protocol_params={
                'ied_name': ied.name,
                'scd_file_path': self.current_scd_path
            },
            description=f"{ied.desc} [{ied.manufacturer}]"
        )
        
        # Add device to device manager
        if not self.device_manager:
            logger.error("Device manager not available")
            return False
            
        device = self.device_manager.add_device(device_config)
        if not device:
            logger.error(f"Failed to add device: {device_name}")
            return False
            
        logger.info(f"Added device to Device Explorer: {device_name}")
        
        # Generate PLC program
        plc_metadata = None
        try:
            plc_metadata = self.plc_generator.generate_program_for_ied(
                ied_name=ied.name,
                device_name=device_name,
                logical_devices=ied.logical_devices
            )
            
            logger.info(f"Generated PLC program: {plc_metadata.program_name}")
            
            # Load into runtime
            if start_plc:
                self.plc_runtime.load_program(
                    program_name=plc_metadata.program_name,
                    device_name=device_name,
                    file_path=plc_metadata.file_path,
                    cycle_time_ms=plc_metadata.cycle_time_ms,
                    auto_start=True
                )
                logger.info(f"Started PLC runtime for {device_name}")
                
        except Exception as e:
            logger.error(f"Failed to create PLC program: {e}")
            # Continue without PLC - server still functional
            
        # Connect device if requested
        if auto_connect and self.device_manager:
            try:
                success = self.device_manager.connect_device(device_name)
                if success:
                    logger.info(f"Connected IEC 61850 server: {device_name}")
                else:
                    logger.warning(f"Failed to connect server: {device_name}")
            except Exception as e:
                logger.error(f"Error connecting device: {e}")
                
        # Create server instance record
        instance = IEDServerInstance(
            device_name=device_name,
            ied_name=ied.name,
            device_config=device_config,
            plc_metadata=plc_metadata,
            status='connected' if auto_connect else 'created'
        )
        
        self.instantiated_servers[device_name] = instance
        
        # Add to MSS project
        self.mss_manager.add_device(
            device_name=device_name,
            ied_name=ied.name,
            ip_address=ied.network_config.ip_address,
            port=ied.network_config.port,
            plc_program=plc_metadata.file_path if plc_metadata else None
        )
        
        return True
        
    def save_project(self, file_path: str) -> bool:
        """
        Save current project to .mss file.
        
        Args:
            file_path: Path for .mss file (e.g., "DUBGG.mss")
            
        Returns:
            True on success
        """
        if not self.mss_manager.current_project:
            logger.error("No active project to save")
            return False
            
        return self.mss_manager.save_project(file_path)
        
    def load_project(self, file_path: str, auto_connect: bool = True, start_plc: bool = True) -> bool:
        """
        Load project from .mss file and restore all state.
        
        Args:
            file_path: Path to .mss file
            auto_connect: Auto-connect all servers
            start_plc: Auto-start all PLC programs
            
        Returns:
            True on success
        """
        try:
            logger.info(f"Loading MSS project: {file_path}")
            
            # Load MSS file
            project = self.mss_manager.load_project(file_path)
            if not project:
                return False
                
            # Load SCD file reference
            scd_path = project.metadata.scd_file_path
            if not Path(scd_path).exists():
                logger.error(f"SCD file not found: {scd_path}")
                return False
                
            self.current_scd_path = scd_path
            
            # Parse SCD for reference (not strictly needed, but good for consistency)
            loader = SCDProjectLoader(scd_path)
            self.ied_definitions = loader.extract_ieds()
            
            # Restore each device
            success_count = 0
            for dev_config in project.devices:
                try:
                    if self._restore_device(dev_config, auto_connect, start_plc):
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to restore device {dev_config.device_name}: {e}")
                    
            logger.info(f"Restored {success_count}/{len(project.devices)} device(s)")
            
            return success_count == len(project.devices)
            
        except Exception as e:
            logger.error(f"Failed to load project: {e}", exc_info=True)
            return False
            
    def _restore_device(self, dev_config, auto_connect: bool, start_plc: bool) -> bool:
        """
        Restore single device from MSS project.
        
        Args:
            dev_config: MSSDeviceConfig from project
            auto_connect: Auto-connect server
            start_plc: Auto-start PLC
            
        Returns:
            True on success
        """
        logger.info(f"Restoring device: {dev_config.device_name}")
        
        # Create DeviceConfig
        device_config = DeviceConfig(
            name=dev_config.device_name,
            device_type=DeviceType.IEC61850_SERVER,
            ip_address=dev_config.ip_address,
            port=dev_config.port,
            scd_file_path=self.current_scd_path,  # Required for server adapter
            protocol_params={
                'ied_name': dev_config.ied_name,
                'scd_file_path': self.current_scd_path
            }
        )
        
        # Add device
        if not self.device_manager:
            return False
            
        device = self.device_manager.add_device(device_config)
        if not device:
            return False
            
        # Load PLC program if exists
        if dev_config.plc_program and Path(dev_config.plc_program).exists():
            try:
                if start_plc:
                    self.plc_runtime.load_program(
                        program_name=f"PRG_{dev_config.device_name}",
                        device_name=dev_config.device_name,
                        file_path=dev_config.plc_program,
                        auto_start=True
                    )
            except Exception as e:
                logger.error(f"Failed to load PLC program: {e}")
                
        # Connect if requested
        if auto_connect and dev_config.auto_connect and self.device_manager:
            self.device_manager.connect_device(dev_config.device_name)
            
        return True
        
    def get_project_summary(self) -> Dict[str, Any]:
        """
        Get summary of current project state.
        
        Returns:
            Dictionary with project information
        """
        project = self.mss_manager.current_project
        
        return {
            'project_loaded': project is not None,
            'project_name': project.metadata.project_name if project else None,
            'scd_file': self.current_scd_path,
            'ied_count': len(self.ied_definitions),
            'instantiated_count': len(self.instantiated_servers),
            'plc_programs': len(self.plc_runtime.get_all_statuses()),
            'devices': [
                {
                    'name': inst.device_name,
                    'ied': inst.ied_name,
                    'status': inst.status
                }
                for inst in self.instantiated_servers.values()
            ]
        }
        
    def shutdown(self):
        """Gracefully shutdown all components."""
        logger.info("Shutting down IED Project Orchestrator")
        
        # Stop all PLC programs
        self.plc_runtime.stop_all()
        
        # Disconnect all devices (via device manager)
        if self.device_manager:
            for device_name in self.instantiated_servers.keys():
                try:
                    self.device_manager.disconnect_device(device_name)
                except Exception as e:
                    logger.error(f"Error disconnecting {device_name}: {e}")
