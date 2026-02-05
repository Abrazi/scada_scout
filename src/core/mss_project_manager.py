"""
MSS Project File Format - Persistence for multi-IED simulation projects.

The .mss (Multi-Server Simulation) file format stores complete project state including:
- SCD file reference
- All instantiated IED servers with configurations
- PLC program associations
- Network bindings
- Runtime settings

This allows saving and loading complete simulation scenarios.
"""

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MSSDeviceConfig:
    """Device configuration in MSS project."""
    device_name: str
    ied_name: str
    ip_address: str
    port: int
    enabled: bool
    auto_connect: bool
    plc_program: Optional[str]  # Path to PLC program file


@dataclass
class MSSProjectMetadata:
    """MSS project metadata."""
    project_name: str
    description: str
    scd_file_path: str
    created: str
    modified: str
    version: str = "1.0"


@dataclass
class MSSProject:
    """Complete MSS project structure."""
    metadata: MSSProjectMetadata
    devices: List[MSSDeviceConfig]
    settings: Dict[str, Any]


class MSSProjectManager:
    """
    Manages .mss project files for IED simulation projects.
    
    The MSS format is JSON-based with the following structure:
    {
      "metadata": {
        "project_name": "...",
        "description": "...",
        "scd_file_path": "...",
        "created": "...",
        "modified": "...",
        "version": "1.0"
      },
      "devices": [
        {
          "device_name": "...",
          "ied_name": "...",
          "ip_address": "...",
          "port": 102,
          "enabled": true,
          "auto_connect": true,
          "plc_program": "..."
        }
      ],
      "settings": {
        "auto_start_plc": true,
        "default_cycle_time_ms": 100,
        ...
      }
    }
    """
    
    def __init__(self):
        """Initialize MSS project manager."""
        self.current_project: Optional[MSSProject] = None
        self.current_file_path: Optional[Path] = None
        
    def create_project(self, 
                      project_name: str,
                      description: str,
                      scd_file_path: str) -> MSSProject:
        """
        Create a new MSS project.
        
        Args:
            project_name: Project name
            description: Project description
            scd_file_path: Path to source SCD file
            
        Returns:
            New MSSProject instance
        """
        now = datetime.now().isoformat()
        
        metadata = MSSProjectMetadata(
            project_name=project_name,
            description=description,
            scd_file_path=scd_file_path,
            created=now,
            modified=now,
            version="1.0"
        )
        
        project = MSSProject(
            metadata=metadata,
            devices=[],
            settings={
                'auto_start_plc': True,
                'default_cycle_time_ms': 100,
                'auto_connect_on_load': True
            }
        )
        
        self.current_project = project
        logger.info(f"Created new MSS project: {project_name}")
        
        return project
        
    def add_device(self,
                  device_name: str,
                  ied_name: str,
                  ip_address: str,
                  port: int = 102,
                  plc_program: Optional[str] = None) -> bool:
        """
        Add device to current project.
        
        Args:
            device_name: Device name in application
            ied_name: IED name from SCD
            ip_address: IP address to bind
            port: MMS port (default 102)
            plc_program: Optional path to PLC program
            
        Returns:
            True on success
        """
        if not self.current_project:
            logger.error("No active project")
            return False
            
        device_config = MSSDeviceConfig(
            device_name=device_name,
            ied_name=ied_name,
            ip_address=ip_address,
            port=port,
            enabled=True,
            auto_connect=True,
            plc_program=plc_program
        )
        
        self.current_project.devices.append(device_config)
        self.current_project.metadata.modified = datetime.now().isoformat()
        
        logger.info(f"Added device to project: {device_name} ({ied_name})")
        return True
        
    def save_project(self, file_path: str) -> bool:
        """
        Save current project to .mss file.
        
        Args:
            file_path: Path to save .mss file
            
        Returns:
            True on success
        """
        if not self.current_project:
            logger.error("No active project to save")
            return False
            
        try:
            path = Path(file_path)
            
            # Ensure .mss extension
            if path.suffix.lower() != '.mss':
                path = path.with_suffix('.mss')
                
            # Update modified timestamp
            self.current_project.metadata.modified = datetime.now().isoformat()
            
            # Convert to dict
            project_dict = {
                'metadata': asdict(self.current_project.metadata),
                'devices': [asdict(d) for d in self.current_project.devices],
                'settings': self.current_project.settings
            }
            
            # Write JSON with pretty formatting
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(project_dict, f, indent=2, ensure_ascii=False)
                
            self.current_file_path = path
            logger.info(f"Saved MSS project: {path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save MSS project: {e}")
            return False
            
    def load_project(self, file_path: str) -> Optional[MSSProject]:
        """
        Load MSS project from file.
        
        Args:
            file_path: Path to .mss file
            
        Returns:
            MSSProject instance or None on failure
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"MSS file not found: {file_path}")
                return None
                
            with open(path, 'r', encoding='utf-8') as f:
                project_dict = json.load(f)
                
            # Validate structure
            if 'metadata' not in project_dict or 'devices' not in project_dict:
                logger.error("Invalid MSS file structure")
                return None
                
            # Reconstruct objects
            metadata = MSSProjectMetadata(**project_dict['metadata'])
            devices = [MSSDeviceConfig(**d) for d in project_dict['devices']]
            settings = project_dict.get('settings', {})
            
            project = MSSProject(
                metadata=metadata,
                devices=devices,
                settings=settings
            )
            
            self.current_project = project
            self.current_file_path = path
            
            logger.info(f"Loaded MSS project: {metadata.project_name} ({len(devices)} devices)")
            
            return project
            
        except Exception as e:
            logger.error(f"Failed to load MSS project: {e}")
            return None
            
    def get_current_project(self) -> Optional[MSSProject]:
        """Get current active project."""
        return self.current_project
        
    def get_project_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get project information without full load.
        
        Args:
            file_path: Path to .mss file
            
        Returns:
            Dictionary with basic project info
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                project_dict = json.load(f)
                
            metadata = project_dict.get('metadata', {})
            device_count = len(project_dict.get('devices', []))
            
            return {
                'project_name': metadata.get('project_name', 'Unknown'),
                'description': metadata.get('description', ''),
                'scd_file': metadata.get('scd_file_path', ''),
                'device_count': device_count,
                'created': metadata.get('created', ''),
                'modified': metadata.get('modified', '')
            }
            
        except Exception as e:
            logger.error(f"Failed to read MSS info: {e}")
            return None
            
    def export_devices_to_json(self) -> Optional[List[Dict[str, Any]]]:
        """
        Export devices to format compatible with devices.json.
        
        Returns:
            List of device configurations
        """
        if not self.current_project:
            return None
            
        devices_json = []
        
        for dev_config in self.current_project.devices:
            # Convert to DeviceConfig format used by application
            device_dict = {
                'name': dev_config.device_name,
                'device_type': 'IEC61850_SERVER',
                'ip_address': dev_config.ip_address,
                'port': dev_config.port,
                'enabled': dev_config.enabled,
                'protocol_params': {
                    'ied_name': dev_config.ied_name,
                    'scd_file_path': self.current_project.metadata.scd_file_path
                },
                'plc_program': dev_config.plc_program
            }
            devices_json.append(device_dict)
            
        return devices_json
