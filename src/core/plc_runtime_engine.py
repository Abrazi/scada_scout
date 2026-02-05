"""
PLC Runtime Engine - Executes PLC programs in continuous cyclic loops.

This module provides a runtime environment for executing PLC programs associated
with IED devices. Each program runs in its own thread with configurable cycle time,
maintains execution state, and provides access to device data through a built-in
function library.
"""

import logging
import threading
import time
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PLCExecutionContext:
    """Execution context for a PLC program instance."""
    program_name: str
    device_name: str
    file_path: str
    cycle_time_ms: int
    enabled: bool
    
    # Runtime state
    running: bool = False
    cycle_count: int = 0
    first_scan: bool = True
    last_scan_time: float = 0.0
    scan_time_ms: float = 0.0
    
    # Variable storage
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # Thread reference
    thread: Optional[threading.Thread] = None
    stop_event: Optional[threading.Event] = None
    
    # Error state
    error: Optional[str] = None
    error_count: int = 0


class PLCRuntimeEngine:
    """
    PLC runtime engine that executes multiple PLC programs concurrently.
    
    Each program runs in a dedicated thread with its own execution context.
    The engine provides built-in functions for IED data access and manages
    the program lifecycle (start, stop, pause, resume).
    
    Architecture:
    - One thread per PLC program
    - Cyclic execution with configurable scan time
    - Sandboxed execution environment
    - Device data access through callback interface
    """
    
    def __init__(self, device_manager=None):
        """
        Initialize PLC runtime engine.
        
        Args:
            device_manager: Reference to DeviceManager for IED data access
        """
        self.device_manager = device_manager
        self.contexts: Dict[str, PLCExecutionContext] = {}
        self._lock = threading.Lock()
        
        # Built-in function handlers
        self._builtin_functions = {
            'READ_IED_DATA': self._read_ied_data,
            'WRITE_IED_DATA': self._write_ied_data,
            'WRITE_IED_CONTROL': self._write_ied_control,
            'SCADA_LOG': self._scada_log,
            'GET_DEVICE_STATUS': self._get_device_status,
        }
        
    def load_program(self, 
                     program_name: str, 
                     device_name: str,
                     file_path: str,
                     cycle_time_ms: int = 100,
                     auto_start: bool = True) -> bool:
        """
        Load a PLC program into the runtime.
        
        Args:
            program_name: Unique program identifier
            device_name: Associated device name
            file_path: Path to .st program file
            cycle_time_ms: Scan cycle time in milliseconds
            auto_start: Start execution immediately
            
        Returns:
            True on success
        """
        try:
            # Check if program file exists
            if not Path(file_path).exists():
                logger.error(f"Program file not found: {file_path}")
                return False
                
            # Create execution context
            context = PLCExecutionContext(
                program_name=program_name,
                device_name=device_name,
                file_path=file_path,
                cycle_time_ms=cycle_time_ms,
                enabled=True
            )
            
            # Initialize variables from program
            self._initialize_context(context)
            
            with self._lock:
                self.contexts[program_name] = context
                
            logger.info(f"Loaded PLC program: {program_name} (device: {device_name})")
            
            if auto_start:
                return self.start_program(program_name)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to load program {program_name}: {e}")
            return False
            
    def start_program(self, program_name: str) -> bool:
        """
        Start execution of a loaded program.
        
        Args:
            program_name: Program to start
            
        Returns:
            True on success
        """
        with self._lock:
            context = self.contexts.get(program_name)
            if not context:
                logger.error(f"Program not found: {program_name}")
                return False
                
            if context.running:
                logger.warning(f"Program already running: {program_name}")
                return True
                
            # Create stop event
            context.stop_event = threading.Event()
            context.running = True
            context.first_scan = True
            context.error = None
            
            # Start execution thread
            context.thread = threading.Thread(
                target=self._execution_loop,
                args=(context,),
                name=f"PLC_{program_name}",
                daemon=True
            )
            context.thread.start()
            
            logger.info(f"Started PLC program: {program_name}")
            return True
            
    def stop_program(self, program_name: str) -> bool:
        """
        Stop execution of a running program.
        
        Args:
            program_name: Program to stop
            
        Returns:
            True on success
        """
        with self._lock:
            context = self.contexts.get(program_name)
            if not context:
                return False
                
            if not context.running:
                return True
                
            # Signal stop
            if context.stop_event:
                context.stop_event.set()
                
            context.running = False
            
        # Wait for thread to finish (outside lock)
        if context.thread and context.thread.is_alive():
            context.thread.join(timeout=2.0)
            
        logger.info(f"Stopped PLC program: {program_name}")
        return True
        
    def unload_program(self, program_name: str) -> bool:
        """
        Stop and unload a program from runtime.
        
        Args:
            program_name: Program to unload
            
        Returns:
            True on success
        """
        self.stop_program(program_name)
        
        with self._lock:
            if program_name in self.contexts:
                del self.contexts[program_name]
                logger.info(f"Unloaded PLC program: {program_name}")
                return True
                
        return False
        
    def stop_all(self):
        """Stop all running programs."""
        with self._lock:
            program_names = list(self.contexts.keys())
            
        for name in program_names:
            self.stop_program(name)
            
    def get_status(self, program_name: str) -> Optional[Dict[str, Any]]:
        """
        Get execution status of a program.
        
        Returns:
            Dictionary with status information or None if not found
        """
        with self._lock:
            context = self.contexts.get(program_name)
            if not context:
                return None
                
            return {
                'program_name': context.program_name,
                'device_name': context.device_name,
                'running': context.running,
                'enabled': context.enabled,
                'cycle_count': context.cycle_count,
                'cycle_time_ms': context.cycle_time_ms,
                'scan_time_ms': context.scan_time_ms,
                'error': context.error,
                'error_count': context.error_count
            }
            
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all programs."""
        statuses = {}
        with self._lock:
            for name in self.contexts.keys():
                status = self.get_status(name)
                if status:
                    statuses[name] = status
        return statuses
        
    def _execution_loop(self, context: PLCExecutionContext):
        """
        Main execution loop for a PLC program.
        Runs cyclically until stopped.
        
        Args:
            context: Execution context
        """
        logger.info(f"PLC execution loop started: {context.program_name}")
        
        cycle_time_sec = context.cycle_time_ms / 1000.0
        
        try:
            while not context.stop_event.is_set():
                cycle_start = time.time()
                
                try:
                    # Execute one scan cycle
                    self._execute_scan(context)
                    
                    # Update timing
                    context.scan_time_ms = (time.time() - cycle_start) * 1000.0
                    context.last_scan_time = time.time()
                    context.cycle_count += 1
                    
                    # Clear first scan flag
                    if context.first_scan:
                        context.first_scan = False
                        
                except Exception as e:
                    context.error = str(e)
                    context.error_count += 1
                    logger.error(f"Error in PLC program {context.program_name}: {e}", exc_info=True)
                    
                    # Stop on repeated errors
                    if context.error_count > 10:
                        logger.error(f"Too many errors, stopping program: {context.program_name}")
                        break
                    
                # Sleep for remainder of cycle time
                elapsed = time.time() - cycle_start
                sleep_time = max(0, cycle_time_sec - elapsed)
                
                if sleep_time > 0:
                    context.stop_event.wait(sleep_time)
                    
        finally:
            context.running = False
            logger.info(f"PLC execution loop stopped: {context.program_name}")
            
    def _execute_scan(self, context: PLCExecutionContext):
        """
        Execute one scan cycle of the PLC program.
        
        This is a simplified interpreter that:
        1. Updates system variables
        2. Simulates program execution (actual ST parsing not implemented)
        3. Processes built-in function calls
        
        Note: Full ST interpreter would require a proper parser and VM.
        For now, this provides the framework and built-in functions.
        
        Args:
            context: Execution context
        """
        # Update system variables
        context.variables['cycle_count'] = context.cycle_count
        context.variables['first_scan'] = context.first_scan
        context.variables['scan_time_ms'] = context.scan_time_ms
        
        # Check IED connection status
        if self.device_manager:
            device = self.device_manager.get_device(context.device_name)
            context.variables['ied_connected'] = device.connected if device else False
        else:
            context.variables['ied_connected'] = False
            
        # TODO: Full ST program interpretation would happen here
        # For now, programs serve as templates/documentation
        # Real execution would require:
        # 1. Parse ST code into AST
        # 2. Interpret/compile to bytecode
        # 3. Execute with variable bindings
        
        # This framework provides the runtime environment and built-in functions
        # that would be called from interpreted code
        
    def _initialize_context(self, context: PLCExecutionContext):
        """
        Initialize execution context from program file.
        
        Args:
            context: Execution context to initialize
        """
        # Initialize system variables
        context.variables = {
            'cycle_count': 0,
            'first_scan': True,
            'scan_time_ms': 0.0,
            'ied_connected': False,
            'ied_name': '',
            'device_name': context.device_name
        }
        
        # TODO: Parse program file to extract variable declarations
        # For now, just initialize with defaults
        
    # ========== Built-in Function Implementations ==========
    
    def _read_ied_data(self, device_name: str, ref: str) -> Any:
        """Read data from IED object reference."""
        if not self.device_manager:
            logger.warning("No device manager available for READ_IED_DATA")
            return None
            
        try:
            # Get device
            device = self.device_manager.get_device(device_name)
            if not device:
                return None
                
            # Read signal
            signal = self.device_manager.get_signal(device_name, ref)
            return signal.value if signal else None
            
        except Exception as e:
            logger.error(f"Failed to read IED data {device_name}::{ref}: {e}")
            return None
            
    def _write_ied_data(self, device_name: str, ref: str, value: Any) -> bool:
        """Write data to IED object reference."""
        if not self.device_manager:
            return False
            
        try:
            # This would call the device manager's write method
            # Implementation depends on device manager API
            logger.info(f"PLC write: {device_name}::{ref} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write IED data: {e}")
            return False
            
    def _write_ied_control(self, device_name: str, ref: str, value: Any) -> bool:
        """Send control command to IED."""
        if not self.device_manager:
            return False
            
        try:
            # This would call control command method
            logger.info(f"PLC control: {device_name}::{ref} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send control: {e}")
            return False
            
    def _scada_log(self, level: str, message: str):
        """Log message to event log."""
        level_map = {
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR
        }
        log_level = level_map.get(level.upper(), logging.INFO)
        logger.log(log_level, f"[PLC] {message}")
        
    def _get_device_status(self, device_name: str) -> bool:
        """Check if device is connected."""
        if not self.device_manager:
            return False
            
        device = self.device_manager.get_device(device_name)
        return device.connected if device else False
