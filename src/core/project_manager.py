import logging
import json
import os
import zipfile
import shutil
import tempfile
from typing import Optional, List
from PySide6.QtCore import QObject, Signal as QtSignal

logger = logging.getLogger(__name__)

class ProjectManager(QObject):
    """
    Orchestrates saving and loading of the entire application state.
    Bundles configuration and resources into a .mss compressed file.
    """
    
    # Signals for UI feedback
    progress_updated = QtSignal(int, str)  # percentage, message
    project_loaded = QtSignal()
    project_saved = QtSignal(str) # filepath
    error_occurred = QtSignal(str)

    def __init__(self, device_manager, watch_list_manager, event_logger=None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.watch_list_manager = watch_list_manager
        self.event_logger = event_logger
        self.current_project_path = None
        
    def save_project(self, filepath: str, window_state=None, window_geometry=None, app_settings=None):
        """
        Bundles all project data into a compressed .mss file.
        """
        try:
            self.progress_updated.emit(10, "Creating temporary bundle...")
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                # 1. Prepare directory structure
                resources_dir = os.path.join(tmp_dir, "resources")
                os.makedirs(resources_dir, exist_ok=True)
                
                # 2. Export Watchlist
                self.progress_updated.emit(20, "Exporting watch list...")
                watchlist_path = os.path.join(tmp_dir, "watchlist.json")
                self.watch_list_manager.save_to_file(watchlist_path)
                
                # 3. Export Devices and Bundle Resources
                self.progress_updated.emit(40, "Packaging device resources...")
                # We need to copy SCD/ICD files to resources/ and update paths in devices.json
                devices_data = self._package_devices(resources_dir)
                devices_path = os.path.join(tmp_dir, "devices.json")
                with open(devices_path, 'w') as f:
                    json.dump(devices_data, f, indent=4)
                
                # 4. Export Event History
                if self.event_logger:
                    self.progress_updated.emit(50, "Exporting event history...")
                    events_path = os.path.join(tmp_dir, "events.json")
                    self.event_logger.save_to_file(events_path)
                
                # 5. Save Window State and Metadata
                self.progress_updated.emit(60, "Saving layout and metadata...")
                metadata = {
                    'name': os.path.basename(filepath),
                    'version': '1.0',
                    'app_settings': app_settings or {}
                }
                
                with open(os.path.join(tmp_dir, "project.json"), 'w') as f:
                    json.dump(metadata, f, indent=4)
                    
                if window_state:
                    with open(os.path.join(tmp_dir, "window_state.bin"), 'wb') as f:
                        f.write(window_state)
                if window_geometry:
                    with open(os.path.join(tmp_dir, "window_geometry.bin"), 'wb') as f:
                        f.write(window_geometry)
                
                # 5. Compress into .mss
                self.progress_updated.emit(80, "Compressing project file...")
                if not filepath.endswith('.mss'):
                    filepath += '.mss'
                    
                with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(tmp_dir):
                        for file in files:
                            abs_path = os.path.join(root, file)
                            rel_path = os.path.relpath(abs_path, tmp_dir)
                            zipf.write(abs_path, rel_path)
                            
                self.current_project_path = filepath
                self.progress_updated.emit(100, "Project saved successfully.")
                self.project_saved.emit(filepath)
                return True
                
        except Exception as e:
            logger.exception(f"Failed to save project: {e}")
            self.error_occurred.emit(f"Failed to save project: {str(e)}")
            return False

    def load_project(self, filepath: str):
        """
        Unbundles and restores project state from a .mss file.
        """
        try:
            self.progress_updated.emit(10, "Extracting project file...")
            
            # Use a persistent extraction directory for resources
            # We'll use a hidden folder in the user's home or local app data
            extract_base = os.path.expanduser("~/.scada_scout/projects/active")
            if os.path.exists(extract_base):
                shutil.rmtree(extract_base)
            os.makedirs(extract_base, exist_ok=True)
            
            with zipfile.ZipFile(filepath, 'r') as zipf:
                zipf.extractall(extract_base)
            
            # 1. Load Metadata
            self.progress_updated.emit(30, "Restoring configuration...")
            project_json = os.path.join(extract_base, "project.json")
            metadata = {}
            if os.path.exists(project_json):
                with open(project_json, 'r') as f:
                    metadata = json.load(f)
            
            # 2. Restore Devices
            self.progress_updated.emit(50, "Restoring devices...")
            devices_path = os.path.join(extract_base, "devices.json")
            if os.path.exists(devices_path):
                # Update paths in devices.json to point to the current extraction dir
                # This ensures portability even if the project was moved
                self._fix_device_paths(devices_path, extract_base)
                self.device_manager.load_configuration(devices_path)
            
            # 3. Restore Watchlist
            self.progress_updated.emit(70, "Restoring watch list...")
            watchlist_path = os.path.join(extract_base, "watchlist.json")
            if os.path.exists(watchlist_path):
                self.watch_list_manager.load_from_file(watchlist_path)
            
            # 4. Restore Event History
            events_path = os.path.join(extract_base, "events.json")
            if os.path.exists(events_path) and self.event_logger:
                self.event_logger.load_from_file(events_path)
            
            # 5. Prepare UI data (to be retrieved by MainWindow)
            self.ui_data = {
                'metadata': metadata,
                'window_state': None,
                'window_geometry': None
            }
            
            state_path = os.path.join(extract_base, "window_state.bin")
            if os.path.exists(state_path):
                with open(state_path, 'rb') as f:
                    self.ui_data['window_state'] = f.read()
            
            geom_path = os.path.join(extract_base, "window_geometry.bin")
            if os.path.exists(geom_path):
                with open(geom_path, 'rb') as f:
                    self.ui_data['window_geometry'] = f.read()
            
            self.current_project_path = filepath
            self.progress_updated.emit(100, "Project loaded successfully.")
            self.project_loaded.emit()
            return True
            
        except Exception as e:
            logger.exception(f"Failed to load project: {e}")
            self.error_occurred.emit(f"Failed to load project: {str(e)}")
            return False

    def _package_devices(self, resources_dir: str) -> dict:
        """
        Collects all device configs and copies referenced files to resources dir.
        Returns a dict structure suitable for devices.json.
        """
        devices = self.device_manager.get_all_devices()
        configs = []
        
        for device in devices:
            cfg_dict = device.config.to_dict()
            scd_path = device.config.scd_file_path
            
            if scd_path and os.path.exists(scd_path):
                # Copy file to resources
                filename = os.path.basename(scd_path)
                dest_path = os.path.join(resources_dir, filename)
                
                # Avoid collision if multiple devices use different files with same name
                # (Simple overwrite for now, or could use hash)
                shutil.copy2(scd_path, dest_path)
                
                # Update path in exported config to be relative to the bundle root
                cfg_dict['scd_file_path'] = os.path.join("resources", filename)
            
            # Also handle any extra Modbus mapping files if they existed as external files
            # (Currently they seem to be embedded in JSON, but good to keep in mind)
            
            configs.append(cfg_dict)
            
        return {
            'devices': configs,
            'folders': getattr(self.device_manager, 'folder_descriptions', {})
        }

    def _fix_device_paths(self, devices_json_path: str, bundle_root: str):
        """
        Relocates relative paths in loaded config to absolute paths in the extraction dir.
        """
        with open(devices_json_path, 'r') as f:
            data = json.load(f)
            
        configs = data.get('devices', [])
        for cfg in configs:
            scd_path = cfg.get('scd_file_path')
            if scd_path and not os.path.isabs(scd_path):
                # It's a bundle-relative path like "resources/file.scd"
                abs_path = os.path.abspath(os.path.join(bundle_root, scd_path))
                cfg['scd_file_path'] = abs_path
                
        with open(devices_json_path, 'w') as f:
            json.dump(data, f, indent=4)
