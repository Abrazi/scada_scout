"""
AI Assistant - Context Collection and Data Interface
Safely extracts application state for AI analysis
"""

import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from src.models.device_models import Device, Signal, SignalQuality, DeviceType
from src.core.event_logger import EventLogger, EventType


class AIAssistantContext:
    """
    Collects and formats application context for AI analysis.
    All methods are read-only and safe.
    """
    
    MAX_LOG_ENTRIES = 200
    MAX_SIGNALS_PER_DEVICE = 100
    MAX_FILE_SIZE = 50_000  # 50KB per file
    
    def __init__(self, device_manager, watch_list_manager=None, protocol_gateway=None, event_logger=None):
        """
        Initialize with references to core application components.
        
        Args:
            device_manager: DeviceManager instance
            watch_list_manager: Optional WatchListManager instance
            protocol_gateway: Optional ProtocolGateway instance
            event_logger: Optional EventLogger instance
        """
        self.device_manager = device_manager
        self.watch_list_manager = watch_list_manager
        self.protocol_gateway = protocol_gateway
        self.event_logger = event_logger
    
    def get_devices_summary(self, device_names: Optional[List[str]] = None) -> str:
        """
        Get a summary of device configurations and connection states.
        
        Args:
            device_names: Optional list of specific devices to include (None = all)
        
        Returns:
            Formatted device summary string
        """
        devices = self.device_manager.get_all_devices()
        
        if device_names:
            devices = [d for d in devices if d.config.name in device_names]
        
        if not devices:
            return "No devices configured."
        
        lines = ["=== DEVICE CONFIGURATIONS ===\n"]
        
        for device in devices:
            lines.append(f"\nDevice: {device.config.name}")
            lines.append(f"  Type: {device.config.device_type.value}")
            lines.append(f"  IP: {device.config.ip_address}:{device.config.port}")
            lines.append(f"  Connected: {device.connected}")
            
            # Get signals if available
            signal_count = 0
            if hasattr(device, 'signals') and device.signals:
                signal_count = len(device.signals)
            elif device.root_node:
                # Recursively count signals in node tree
                def count_signals(node):
                    count = len(node.signals) if hasattr(node, 'signals') and node.signals else 0
                    if hasattr(node, 'children') and node.children:
                        for child in node.children:
                            count += count_signals(child)
                    return count
                signal_count = count_signals(device.root_node)
            lines.append(f"  Signal Count: {signal_count}")
            
            # Protocol-specific details
            if device.config.device_type == DeviceType.MODBUS_TCP:
                lines.append(f"  Unit ID: {device.config.modbus_unit_id}")
                if hasattr(device.config, 'endianness'):
                    lines.append(f"  Endianness: {device.config.endianness}")
            
            elif device.config.device_type in (DeviceType.IEC61850_IED, DeviceType.IEC61850_SERVER):
                if hasattr(device.config, 'ied_name'):
                    lines.append(f"  IED Name: {device.config.ied_name}")
                if hasattr(device.config, 'scd_file_path') and device.config.scd_file_path:
                    lines.append(f"  SCD File: {device.config.scd_file_path}")
            
            elif device.config.device_type == DeviceType.IEC104_RTU:
                if hasattr(device.config, 'asdu_address'):
                    lines.append(f"  ASDU Address: {device.config.asdu_address}")
            
            # Recent errors
            if hasattr(device, 'last_error') and device.last_error:
                lines.append(f"  Last Error: {device.last_error}")
        
        return "\n".join(lines)
    
    def get_signals_summary(self, device_name: str = None, limit: int = None) -> str:
        """
        Get current signal values, quality, and timestamps.
        
        Args:
            device_name: Optional specific device (None = all devices)
            limit: Maximum signals per device (None = use default MAX_SIGNALS_PER_DEVICE)
        
        Returns:
            Formatted signal summary string
        """
        if limit is None:
            limit = self.MAX_SIGNALS_PER_DEVICE
        
        devices = self.device_manager.get_all_devices()
        if device_name:
            devices = [d for d in devices if d.config.name == device_name]
        
        lines = ["=== SIGNAL STATUS ===\n"]
        
        for device in devices:
            # Get signals from device
            signals = []
            if hasattr(device, 'signals') and device.signals:
                signals = device.signals
            elif device.root_node:
                # Recursively collect signals from node tree
                def collect_signals(node):
                    collected = []
                    if hasattr(node, 'signals') and node.signals:
                        collected.extend(node.signals)
                    if hasattr(node, 'children') and node.children:
                        for child in node.children:
                            collected.extend(collect_signals(child))
                    return collected
                signals = collect_signals(device.root_node)
            
            if not signals:
                continue
            
            lines.append(f"\nDevice: {device.config.name}")
            
            # Sort by quality (errors first) then by name
            sorted_signals = sorted(
                signals,
                key=lambda s: (s.quality != SignalQuality.GOOD, s.name)
            )
            
            for signal in sorted_signals[:limit]:
                age = self._get_signal_age(signal)
                lines.append(
                    f"  {signal.name} [{signal.address}]: "
                    f"{signal.value} | Quality: {signal.quality.value} | Age: {age}"
                )
            
            if len(signals) > limit:
                lines.append(f"  ... ({len(signals) - limit} more signals)")
        
        return "\n".join(lines)
    
    def get_event_logs(self, 
                       device_name: str = None,
                       event_types: List[EventType] = None,
                       since: datetime = None,
                       limit: int = None) -> str:
        """
        Get filtered event logs with timestamps.
        
        Args:
            device_name: Optional device filter
            event_types: Optional event type filter (e.g., [EventType.ERROR, EventType.WARNING])
            since: Optional datetime to start from (None = last hour)
            limit: Maximum entries to return
        
        Returns:
            Formatted event log string
        """
        if not self.event_logger:
            return "Event logging not available."
        
        if since is None:
            since = datetime.now() - timedelta(hours=1)
        
        if limit is None:
            limit = self.MAX_LOG_ENTRIES
        
        # Get events from logger (assuming it has a get_events method)
        # This will need to match your actual EventLogger implementation
        try:
            events = self.event_logger.get_recent_events(limit=limit * 2)  # Get more for filtering
        except AttributeError:
            return "Event retrieval not supported by current EventLogger."
        
        # Filter events
        filtered = []
        for event in events:
            if len(filtered) >= limit:
                break
            
            # Filter by device name
            if device_name and device_name not in event.get('message', ''):
                continue
            
            # Filter by event type
            if event_types and event.get('type') not in event_types:
                continue
            
            # Filter by timestamp
            event_time = event.get('timestamp')
            if event_time and isinstance(event_time, datetime) and event_time < since:
                continue
            
            filtered.append(event)
        
        if not filtered:
            return "No matching events found."
        
        lines = ["=== EVENT LOGS ==="]
        lines.append(f"Total Events: {len(filtered)}")
        if device_name:
            lines.append(f"Filtered for Device: {device_name}")
        lines.append("")
        
        # Group by event type for better visibility
        errors = [e for e in filtered if e.get('type') == 'ERROR']
        warnings = [e for e in filtered if e.get('type') == 'WARNING']
        transactions = [e for e in filtered if e.get('type') == 'TRANSACTION']
        info = [e for e in filtered if e.get('type') == 'INFO']
        
        if errors:
            lines.append(f"\n🔴 ERRORS ({len(errors)}):")
            for event in errors:
                timestamp = event.get('timestamp', 'N/A')
                message = event.get('message', '')
                source = event.get('source', 'Unknown')
                lines.append(f"  [{timestamp}] [{source}] {message}")
        
        if warnings:
            lines.append(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for event in warnings:
                timestamp = event.get('timestamp', 'N/A')
                message = event.get('message', '')
                source = event.get('source', 'Unknown')
                lines.append(f"  [{timestamp}] [{source}] {message}")
        
        if transactions:
            lines.append(f"\n✅ TRANSACTIONS ({len(transactions)}):")
            for event in transactions:
                timestamp = event.get('timestamp', 'N/A')
                message = event.get('message', '')
                source = event.get('source', 'Unknown')
                lines.append(f"  [{timestamp}] [{source}] {message}")
        
        if info and len(filtered) <= 100:  # Only show INFO if not too many events
            lines.append(f"\nℹ️  INFO ({len(info)}):")
            for event in info[:20]:  # Limit INFO to 20 most recent
                timestamp = event.get('timestamp', 'N/A')
                message = event.get('message', '')
                source = event.get('source', 'Unknown')
                lines.append(f"  [{timestamp}] [{source}] {message}")
            if len(info) > 20:
                lines.append(f"  ... ({len(info) - 20} more INFO events)")
        
        return "\n".join(lines)
    
    def get_watchlist_summary(self) -> str:
        """
        Get watch list configuration and performance metrics.
        
        Returns:
            Formatted watch list summary
        """
        if not self.watch_list_manager:
            return "Watch list not configured."
        
        signals = self.watch_list_manager.get_signals()
        if not signals:
            return "Watch list is empty."
        
        lines = ["=== WATCH LIST CONFIGURATION ===\n"]
        lines.append(f"Total Signals: {len(signals)}")
        lines.append(f"Update Rate: {self.watch_list_manager.update_rate_ms}ms\n")
        
        # Group by device
        by_device: Dict[str, List] = {}
        for signal in signals:
            device_name = signal.split("::")[0] if "::" in signal else "Unknown"
            by_device.setdefault(device_name, []).append(signal)
        
        for device_name, device_signals in by_device.items():
            lines.append(f"\nDevice: {device_name} ({len(device_signals)} signals)")
            
            # Get RTT stats if available
            if hasattr(self.watch_list_manager, 'get_statistics'):
                stats = self.watch_list_manager.get_statistics(device_name)
                if stats:
                    lines.append(f"  Avg RTT: {stats.get('avg_rtt', 'N/A')}ms")
                    lines.append(f"  Success Rate: {stats.get('success_rate', 'N/A')}%")
            
            # List some signals
            for sig in device_signals[:10]:
                lines.append(f"    {sig}")
            
            if len(device_signals) > 10:
                lines.append(f"    ... ({len(device_signals) - 10} more)")
        
        return "\n".join(lines)
    
    def get_gateway_summary(self) -> str:
        """
        Get protocol gateway mapping configuration.
        
        Returns:
            Formatted gateway summary
        """
        if not self.protocol_gateway:
            return "Protocol gateway not configured."
        
        if not hasattr(self.protocol_gateway, 'mappings'):
            return "Gateway mappings not available."
        
        mappings = self.protocol_gateway.mappings
        if not mappings:
            return "No gateway mappings defined."
        
        lines = ["=== PROTOCOL GATEWAY MAPPINGS ===\n"]
        
        for i, mapping in enumerate(mappings, 1):
            lines.append(f"\nMapping {i}:")
            lines.append(f"  Source: {mapping.source_device}::{mapping.source_signal}")
            lines.append(f"  Target: {mapping.target_device}::{mapping.target_address}")
            if hasattr(mapping, 'transform'):
                lines.append(f"  Transform: {mapping.transform}")
        
        return "\n".join(lines)
    
    def get_protocol_details(self, device_name: str) -> Dict:
        """
        Get protocol-specific metadata for a device.
        
        Args:
            device_name: Device name
        
        Returns:
            Dictionary with protocol details
        """
        device = self.device_manager.get_device(device_name)
        if not device:
            return {"error": f"Device '{device_name}' not found"}
        
        details = {
            "device_name": device.config.name,
            "protocol": device.config.device_type.value,
            "ip_address": device.config.ip_address,
            "port": device.config.port,
            "connected": device.connected,
        }
        
        # Protocol-specific fields
        if device.config.device_type == DeviceType.MODBUS_TCP:
            details.update({
                "unit_id": device.config.modbus_unit_id,
                "endianness": getattr(device.config, 'endianness', 'BIG_ENDIAN'),
                "timeout": getattr(device.config, 'modbus_timeout', 5.0),
            })
        
        elif device.config.device_type in (DeviceType.IEC61850_IED, DeviceType.IEC61850_SERVER):
            details.update({
                "ied_name": getattr(device.config, 'ied_name', device.config.name),
                "scd_file": getattr(device.config, 'scd_file_path', None),
                "control_model": getattr(device.config, 'control_model', 'SBO'),
            })
        
        elif device.config.device_type == DeviceType.IEC104_RTU:
            details.update({
                "asdu_address": getattr(device.config, 'asdu_address', 1),
                "cot_size": getattr(device.config, 'cot_size', 2),
                "ioa_size": getattr(device.config, 'ioa_size', 3),
            })
        
        return details
    
    def read_config_file_safe(self, file_path: str) -> str:
        """
        Safely read a configuration file with size limit.
        
        Args:
            file_path: Path to configuration file
        
        Returns:
            File contents (truncated if too large) or error message
        """
        try:
            path = Path(file_path)
            
            # Security check: only allow reading from workspace
            workspace_root = Path(__file__).parent.parent.parent
            if not path.is_relative_to(workspace_root):
                return f"ERROR: File must be within workspace directory"
            
            if not path.exists():
                return f"ERROR: File not found: {file_path}"
            
            if path.stat().st_size > self.MAX_FILE_SIZE:
                return f"ERROR: File too large (>{self.MAX_FILE_SIZE} bytes). Please specify a smaller file or excerpt."
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(self.MAX_FILE_SIZE)
            
            return f"=== {path.name} ===\n{content}"
        
        except Exception as e:
            return f"ERROR reading file: {str(e)}"
    
    def get_diagnostic_context(self, device_name: str = None) -> str:
        """
        Get comprehensive diagnostic context for troubleshooting.
        Combines multiple context sources into one report.
        
        Args:
            device_name: Optional specific device to focus on
        
        Returns:
            Comprehensive diagnostic report
        """
        sections = []
        
        sections.append(self.get_devices_summary([device_name] if device_name else None))
        sections.append("\n" + self.get_signals_summary(device_name, limit=50))
        sections.append("\n" + self.get_event_logs(device_name=device_name, limit=100))
        
        if self.watch_list_manager:
            sections.append("\n" + self.get_watchlist_summary())
        
        if self.protocol_gateway:
            sections.append("\n" + self.get_gateway_summary())
        
        return "\n".join(sections)
    
    @staticmethod
    def _get_signal_age(signal: Signal) -> str:
        """Calculate human-readable age of signal timestamp."""
        if not signal.timestamp:
            return "No timestamp"
        
        try:
            if isinstance(signal.timestamp, str):
                timestamp = datetime.fromisoformat(signal.timestamp.replace('Z', '+00:00'))
            else:
                timestamp = signal.timestamp
            
            age = datetime.now() - timestamp.replace(tzinfo=None)
            
            if age.total_seconds() < 1:
                return "< 1s"
            elif age.total_seconds() < 60:
                return f"{int(age.total_seconds())}s"
            elif age.total_seconds() < 3600:
                return f"{int(age.total_seconds() / 60)}m"
            else:
                return f"{int(age.total_seconds() / 3600)}h"
        except Exception:
            return "Unknown"
